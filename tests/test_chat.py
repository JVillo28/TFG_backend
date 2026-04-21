"""
Tests del endpoint de chat por sección (/api/chat/message) y de las
utilidades de recorrido de secciones del JSON Schema.

Ejecutar con:  pytest tests/test_chat.py -v
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import create_app
from app.database import Base, get_db
from app.models import Admin, Users
from app.services.llm import (
    build_system_prompt,
    get_next_section,
    get_section_order,
    get_section_type,
)
from config import TestingSettings

# ── Fixtures ────────────────────────────────────────────────────

MULTI_SECTION_SCHEMA = {
    "title": "Simulation Configuration",
    "type": "object",
    "properties": {
        "cells": {
            "title": "Cells",
            "type": "object",
            "properties": {
                "count": {"type": "integer", "minimum": 1},
                "type": {"type": "string"},
            },
            "required": ["count"],
        },
        "events": {
            "title": "Events",
            "type": "object",
            "properties": {
                "kind": {"type": "string"},
            },
        },
        "empty_section": {
            "title": "Empty",
            "type": "object",
            "properties": {},
        },
        "transporters": {
            "title": "Transporters",
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
        },
    },
}


TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=TEST_ENGINE, autocommit=False, autoflush=False)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def app():
    settings = TestingSettings()
    application = create_app(settings=settings)
    application.dependency_overrides[get_db] = override_get_db
    yield application


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=TEST_ENGINE)
    session = TestSession()
    yield session
    session.rollback()
    session.close()
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture
def client(app, db):
    return TestClient(app)


@pytest.fixture
def seed(db):
    admin = Admin(id=1, json_schema=MULTI_SECTION_SCHEMA)
    user = Users(name="Jaime", email="jaime@test.com", password_hash="pwd")
    db.add_all([admin, user])
    db.commit()
    return {"admin": admin, "user": user}


# ═══════════════════════════════════════════════════════════════
# UNIT: utilidades de sección
# ═══════════════════════════════════════════════════════════════


class TestSectionUtils:
    def test_order_preserves_declaration(self):
        order = get_section_order(MULTI_SECTION_SCHEMA)
        assert order == ["cells", "events", "empty_section", "transporters"]

    def test_next_section_normal_case(self):
        assert get_next_section(MULTI_SECTION_SCHEMA, "cells") == "events"

    def test_next_section_skips_empty(self):
        # después de "events" viene "empty_section" (sin properties) → debe saltarla
        assert get_next_section(MULTI_SECTION_SCHEMA, "events") == "transporters"

    def test_next_section_returns_none_on_last(self):
        assert get_next_section(MULTI_SECTION_SCHEMA, "transporters") is None

    def test_next_section_returns_none_on_unknown(self):
        assert get_next_section(MULTI_SECTION_SCHEMA, "inexistent") is None


# ═══════════════════════════════════════════════════════════════
# INTEGRATION: POST /api/chat/message
# ═══════════════════════════════════════════════════════════════


def _mock_llm_response(content: str):
    """Construye un MagicMock que imita la respuesta del SDK OpenAI."""
    from unittest.mock import MagicMock

    choice = MagicMock()
    choice.message.content = content
    completion = MagicMock()
    completion.choices = [choice]
    return completion


class TestChatEndpoint:
    def test_request_without_current_section_returns_422(self, client, seed):
        resp = client.post(
            "/api/chat/message",
            json={
                "research_id": 1,
                "message": "hola",
                "form_state": {},
            },
        )
        assert resp.status_code == 422

    def test_unknown_section_returns_400(self, client, seed):
        resp = client.post(
            "/api/chat/message",
            json={
                "research_id": 1,
                "message": "hola",
                "form_state": {},
                "current_section": "nope",
            },
        )
        assert resp.status_code == 400
        assert "Invalid section" in resp.json()["detail"]["error"]

    @patch("app.api.chat.get_llm_client")
    def test_valid_turn_returns_response_with_next_section(self, mock_client, client, seed):
        # El LLM responde ready_to_apply para la sección "cells"
        mock_client.return_value.chat.completions.create.return_value = _mock_llm_response(
            '{"message":"todo listo","state":"ready_to_apply","proposed_values":{"cells":{"count":100,"type":"tumor"}}}'
        )

        resp = client.post(
            "/api/chat/message",
            json={
                "research_id": 1,
                "message": "quiero 100 células tumorales",
                "form_state": {},
                "current_section": "cells",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["state"] == "ready_to_apply"
        assert body["next_section"] == "events"

    @patch("app.api.chat.get_llm_client")
    def test_last_section_has_null_next_section(self, mock_client, client, seed):
        mock_client.return_value.chat.completions.create.return_value = _mock_llm_response(
            '{"message":"fin","state":"ready_to_apply","proposed_values":{"transporters":{"name":"t1"}}}'
        )

        resp = client.post(
            "/api/chat/message",
            json={
                "research_id": 1,
                "message": "t1",
                "form_state": {},
                "current_section": "transporters",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["next_section"] is None

    @patch("app.api.chat.get_llm_client")
    def test_asking_state_does_not_include_next_section(self, mock_client, client, seed):
        mock_client.return_value.chat.completions.create.return_value = _mock_llm_response(
            '{"message":"¿cuántas?","state":"asking"}'
        )

        resp = client.post(
            "/api/chat/message",
            json={
                "research_id": 1,
                "message": "células tumorales",
                "form_state": {},
                "current_section": "cells",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["state"] == "asking"
        assert resp.json()["next_section"] is None

    @patch("app.api.chat.get_llm_client")
    def test_empty_message_is_init_turn(self, mock_client, client, seed):
        """Un mensaje vacío debe provocar que el prompt incluya la instrucción de apertura."""
        create_mock = mock_client.return_value.chat.completions.create
        create_mock.return_value = _mock_llm_response('{"message":"¡Hola! Vamos con Cells...","state":"asking"}')

        resp = client.post(
            "/api/chat/message",
            json={
                "research_id": 1,
                "message": "",
                "form_state": {},
                "current_section": "cells",
            },
        )
        assert resp.status_code == 200

        # Verificar que el último mensaje enviado al LLM contiene la instrucción de apertura
        call_kwargs = create_mock.call_args.kwargs
        last_msg = call_kwargs["messages"][-1]
        assert last_msg["role"] == "user"
        assert "[Inicio de sección]" in last_msg["content"]
        assert "cells" in last_msg["content"]


# ═══════════════════════════════════════════════════════════════
# UNIT + INTEGRATION: secciones de tipo array
# ═══════════════════════════════════════════════════════════════


MIXED_SCHEMA = {
    "title": "Mixed Schema",
    "type": "object",
    "properties": {
        "environment": {
            "title": "Environment",
            "type": "object",
            "properties": {
                "width": {"type": "integer", "minimum": 1},
            },
        },
        "cells": {
            "title": "Cells",
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "count": {"type": "integer", "minimum": 1},
                },
            },
        },
        "transporters": {
            "title": "Transporters",
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "empty_array": {
            "title": "Empty Array",
            "type": "array",
            "items": {},
        },
        "agents": {
            "title": "Agents",
            "type": "object",
            "properties": {
                "kind": {"type": "string"},
            },
        },
    },
}


class TestArraySections:
    def test_get_section_order_includes_arrays(self):
        order = get_section_order(MIXED_SCHEMA)
        # empty_array tiene items = {} → sigue apareciendo en el orden pero
        # get_next_section la salta cuando es candidata
        assert order == [
            "environment",
            "cells",
            "transporters",
            "empty_array",
            "agents",
        ]

    def test_get_section_type_returns_correct_type(self):
        assert get_section_type(MIXED_SCHEMA, "environment") == "object"
        assert get_section_type(MIXED_SCHEMA, "cells") == "array"
        assert get_section_type(MIXED_SCHEMA, "transporters") == "array"
        assert get_section_type(MIXED_SCHEMA, "nonexistent") is None

    def test_get_next_section_skips_empty_array(self):
        # tras transporters debería saltarse empty_array (items == {}) y
        # devolver directamente agents
        assert get_next_section(MIXED_SCHEMA, "transporters") == "agents"

    def test_get_next_section_last_array_returns_none(self):
        # agents es la última, no hay next
        assert get_next_section(MIXED_SCHEMA, "agents") is None

    def test_prompt_for_object_section_mentions_object_format(self):
        prompt = build_system_prompt(
            schema=MIXED_SCHEMA,
            current_section="environment",
            next_section="cells",
            section_type="object",
        )
        assert "environment" in prompt
        assert "object" in prompt
        # No debe filtrarse el ejemplo de array
        assert "campo1" in prompt or "campos" in prompt

    def test_prompt_for_array_of_objects_mentions_list_format(self):
        prompt = build_system_prompt(
            schema=MIXED_SCHEMA,
            current_section="cells",
            next_section="transporters",
            section_type="array",
        )
        assert "cells" in prompt
        assert "array" in prompt
        assert "colección" in prompt.lower() or "cuántos elementos" in prompt
        # El ejemplo debe contener formato de lista con objetos
        assert "[" in prompt
        assert "items" in prompt.lower()

    def test_prompt_for_array_of_primitives_uses_primitive_example(self):
        prompt = build_system_prompt(
            schema=MIXED_SCHEMA,
            current_section="transporters",
            next_section="agents",
            section_type="array",
        )
        assert "transporters" in prompt
        # El ejemplo debe ser una lista de strings, sin objetos anidados
        assert '"valor1"' in prompt or '"val1"' in prompt

    @patch("app.api.chat.get_llm_client")
    def test_endpoint_accepts_array_section(self, mock_client, client, db):
        # Seed con schema mixto
        admin = Admin(id=1, json_schema=MIXED_SCHEMA)
        user = Users(name="Jaime", email="j@test.com", password_hash="pwd")
        db.add_all([admin, user])
        db.commit()

        mock_client.return_value.chat.completions.create.return_value = _mock_llm_response(
            '{"message":"ok","state":"ready_to_apply",'
            '"proposed_values":{"cells":['
            '{"name":"tumor","count":100},'
            '{"name":"healthy","count":50}]}}'
        )

        resp = client.post(
            "/api/chat/message",
            json={
                "research_id": 1,
                "message": "100 tumorales y 50 sanas",
                "form_state": {},
                "current_section": "cells",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["state"] == "ready_to_apply"
        assert isinstance(body["proposed_values"]["cells"], list)
        assert len(body["proposed_values"]["cells"]) == 2

    @patch("app.api.chat.get_llm_client")
    def test_endpoint_normalizes_non_list_for_array_section(self, mock_client, client, db):
        """Cuando el LLM devuelve un objeto donde esperábamos una lista
        (escenario típico de skip mal formado), el backend normaliza a []
        en lugar de rechazar con 500."""
        admin = Admin(id=1, json_schema=MIXED_SCHEMA)
        user = Users(name="Jaime", email="j@test.com", password_hash="pwd")
        db.add_all([admin, user])
        db.commit()

        mock_client.return_value.chat.completions.create.return_value = _mock_llm_response(
            '{"message":"ok","state":"ready_to_apply","proposed_values":{"cells":{"name":"tumor","count":100}}}'
        )

        resp = client.post(
            "/api/chat/message",
            json={
                "research_id": 1,
                "message": "una tumoral",
                "form_state": {},
                "current_section": "cells",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["proposed_values"]["cells"] == []

    @patch("app.api.chat.get_llm_client")
    def test_endpoint_normalizes_missing_section_key_for_skip(self, mock_client, client, db):
        """Escenario típico de skip: LLM devuelve ready_to_apply con
        proposed_values = null o sin la clave. El backend normaliza a []
        para que el flujo de aplicación continúe."""
        admin = Admin(id=1, json_schema=MIXED_SCHEMA)
        user = Users(name="Jaime", email="j@test.com", password_hash="pwd")
        db.add_all([admin, user])
        db.commit()

        mock_client.return_value.chat.completions.create.return_value = _mock_llm_response(
            '{"message":"Ok, saltando","state":"ready_to_apply","proposed_values":null}'
        )

        resp = client.post(
            "/api/chat/message",
            json={
                "research_id": 1,
                "message": "saltemos esto",
                "form_state": {},
                "current_section": "cells",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["state"] == "ready_to_apply"
        assert body["proposed_values"]["cells"] == []

    @patch("app.api.chat.get_llm_client")
    def test_endpoint_uses_empty_list_for_array_form_state(self, mock_client, client, db):
        """El prompt debe recibir [] como estado actual de un array vacío."""
        admin = Admin(id=1, json_schema=MIXED_SCHEMA)
        user = Users(name="Jaime", email="j@test.com", password_hash="pwd")
        db.add_all([admin, user])
        db.commit()

        create_mock = mock_client.return_value.chat.completions.create
        create_mock.return_value = _mock_llm_response('{"message":"¿cuántas?","state":"asking"}')

        client.post(
            "/api/chat/message",
            json={
                "research_id": 1,
                "message": "hola",
                "form_state": {},
                "current_section": "cells",
            },
        )

        # Verificar que el mensaje del user del prompt menciona "[]"
        messages = create_mock.call_args.kwargs["messages"]
        form_state_msg = messages[1]["content"]
        assert "[]" in form_state_msg
