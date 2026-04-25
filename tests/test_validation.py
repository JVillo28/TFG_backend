"""
Tests para la validación de JSON Schema (AdminService y ResearchService)
y los endpoints de la API.

Ejecutar con:  pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import create_app
from app.database import Base, get_db
from app.models import Admin, Users
from app.services.admin_service import AdminService
from app.services.research_service import ResearchService
from config import TestingSettings

# ── Fixtures ────────────────────────────────────────────────────

VALID_SCHEMA = {
    "title": "Simulation Configuration",
    "description": "Configuration schema for simulation parameters",
    "type": "object",
    "properties": {
        "generalConfiguration": {
            "title": "General Configuration",
            "type": "object",
            "properties": {
                "totalTries": {"type": "integer", "minimum": 1},
                "dirOutput": {"type": "string"},
                "fileOutput": {"type": "string"},
                "simulationName": {"type": "string"},
                "simulationType": {"type": "string", "enum": ["basic"]},
                "activateGUI": {"type": "boolean", "default": False},
            },
            "required": [
                "totalTries",
                "dirOutput",
                "fileOutput",
                "simulationName",
                "simulationType",
            ],
        }
    },
    "required": ["generalConfiguration"],
}


VALID_RESEARCH_DATA = {
    "generalConfiguration": {
        "totalTries": 100,
        "dirOutput": "/output",
        "fileOutput": "result.csv",
        "simulationName": "sim1",
        "simulationType": "basic",
    }
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
    """Crea la app FastAPI con configuración de testing."""
    settings = TestingSettings()
    application = create_app(settings=settings)
    application.dependency_overrides[get_db] = override_get_db
    yield application


@pytest.fixture(scope="function")
def db():
    """Crea las tablas antes de cada test y las elimina después."""
    Base.metadata.create_all(bind=TEST_ENGINE)
    session = TestSession()
    yield session
    session.rollback()
    session.close()
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture
def client(app, db):
    """Cliente HTTP de FastAPI para tests de endpoints."""
    return TestClient(app)


@pytest.fixture
def seed_data(db):
    """Inserta el schema de admin y un usuario."""
    admin = Admin(id=1, json_schema=VALID_SCHEMA)
    user = Users(name="Jaime", email="jaime@test.com")
    db.add_all([admin, user])
    db.commit()
    return {"admin": admin, "user": user}


# ═══════════════════════════════════════════════════════════════
# UNIT: AdminService.validate_json_schema
# ═══════════════════════════════════════════════════════════════


class TestAdminServiceValidation:
    """Tests unitarios de la meta-validación de JSON Schema."""

    # ── Schemas válidos ────────────────────────────────────────

    def test_valid_minimal_schema(self):
        """El schema mínimo {'type': 'object'} es válido."""
        valid, err = AdminService.validate_json_schema({"type": "object"})
        assert valid is True
        assert err is None

    def test_valid_full_schema(self):
        """El schema completo de simulación es válido."""
        valid, err = AdminService.validate_json_schema(VALID_SCHEMA)
        assert valid is True
        assert err is None

    def test_valid_schema_with_string_type(self):
        valid, _ = AdminService.validate_json_schema({"type": "string", "minLength": 1})
        assert valid is True

    def test_valid_schema_with_array(self):
        schema = {
            "type": "array",
            "items": {"type": "integer"},
        }
        valid, _ = AdminService.validate_json_schema(schema)
        assert valid is True

    def test_valid_schema_with_nested_objects(self):
        schema = {
            "type": "object",
            "properties": {
                "level1": {
                    "type": "object",
                    "properties": {"level2": {"type": "string"}},
                }
            },
        }
        valid, _ = AdminService.validate_json_schema(schema)
        assert valid is True

    def test_valid_empty_object_schema(self):
        """Schema vacío {} es válido (acepta cualquier cosa)."""
        valid, _ = AdminService.validate_json_schema({})
        assert valid is True

    def test_valid_schema_with_enum(self):
        schema = {"type": "string", "enum": ["a", "b", "c"]}
        valid, _ = AdminService.validate_json_schema(schema)
        assert valid is True

    def test_valid_schema_boolean_default(self):
        schema = {"type": "boolean", "default": False}
        valid, _ = AdminService.validate_json_schema(schema)
        assert valid is True

    def test_valid_schema_with_required(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        valid, _ = AdminService.validate_json_schema(schema)
        assert valid is True

    # ── Schemas inválidos ─────────────────────────────────────

    def test_invalid_not_a_dict(self):
        """Un string no es un JSON Schema."""
        valid, err = AdminService.validate_json_schema("not a schema")
        assert valid is False
        assert err is not None

    def test_invalid_list(self):
        """Una lista no es un JSON Schema."""
        valid, _ = AdminService.validate_json_schema([1, 2, 3])
        assert valid is False

    def test_invalid_none(self):
        valid, _ = AdminService.validate_json_schema(None)
        assert valid is False

    def test_invalid_type_value(self):
        """type debe ser uno de los tipos válidos de JSON Schema."""
        valid, err = AdminService.validate_json_schema({"type": "invalido"})
        assert valid is False
        assert err is not None

    def test_invalid_type_is_number_instead_of_string(self):
        """type no puede ser un número."""
        valid, _ = AdminService.validate_json_schema({"type": 123})
        assert valid is False

    def test_invalid_properties_not_object(self):
        """properties debe ser un objeto, no una lista."""
        valid, _ = AdminService.validate_json_schema(
            {
                "type": "object",
                "properties": ["name", "age"],
            }
        )
        assert valid is False

    def test_invalid_required_not_array(self):
        """required debe ser un array."""
        valid, _ = AdminService.validate_json_schema(
            {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": "name",
            }
        )
        assert valid is False

    def test_invalid_minimum_on_string(self):
        """type con valor incorrecto es inválido."""
        valid, _ = AdminService.validate_json_schema({"type": "foobar"})
        assert valid is False

    def test_invalid_enum_not_array(self):
        """enum debe ser un array."""
        valid, _ = AdminService.validate_json_schema(
            {
                "type": "string",
                "enum": "not_an_array",
            }
        )
        assert valid is False

    def test_invalid_items_not_schema(self):
        """items debe ser un schema válido, no un string."""
        valid, _ = AdminService.validate_json_schema(
            {
                "type": "array",
                "items": "not_a_schema",
            }
        )
        assert valid is False

    def test_invalid_additional_properties_bad_type(self):
        """additionalProperties debe ser boolean o un schema."""
        valid, _ = AdminService.validate_json_schema(
            {
                "type": "object",
                "additionalProperties": "yes",
            }
        )
        assert valid is False

    def test_invalid_minimum_not_number(self):
        """minimum debe ser un número."""
        valid, _ = AdminService.validate_json_schema(
            {
                "type": "integer",
                "minimum": "ten",
            }
        )
        assert valid is False


# ═══════════════════════════════════════════════════════════════
# UNIT: ResearchService.validate_research
# ═══════════════════════════════════════════════════════════════


class TestResearchServiceValidation:
    """Tests unitarios de validación de research contra el schema de admin."""

    # ── Datos válidos ─────────────────────────────────────────

    def test_valid_research_data(self):
        valid, err = ResearchService.validate_research(VALID_RESEARCH_DATA, VALID_SCHEMA)
        assert valid is True
        assert err is None

    def test_valid_research_with_optional_fields(self):
        data = {
            "generalConfiguration": {
                "totalTries": 50,
                "dirOutput": "/tmp",
                "fileOutput": "out.csv",
                "simulationName": "test",
                "simulationType": "basic",
                "activateGUI": True,
            }
        }
        valid, _ = ResearchService.validate_research(data, VALID_SCHEMA)
        assert valid is True

    # ── Datos inválidos ───────────────────────────────────────

    def test_invalid_not_dict(self):
        valid, _ = ResearchService.validate_research("string", VALID_SCHEMA)
        assert valid is False

    def test_invalid_missing_required_top_level(self):
        """Falta generalConfiguration (required)."""
        valid, err = ResearchService.validate_research({}, VALID_SCHEMA)
        assert valid is False
        assert "generalConfiguration" in err

    def test_invalid_missing_required_nested(self):
        """Falta totalTries (required) dentro de generalConfiguration."""
        data = {
            "generalConfiguration": {
                "dirOutput": "/output",
                "fileOutput": "result.csv",
                "simulationName": "sim1",
                "simulationType": "basic",
            }
        }
        valid, err = ResearchService.validate_research(data, VALID_SCHEMA)
        assert valid is False
        assert "totalTries" in err

    def test_invalid_wrong_type_integer(self):
        """totalTries debe ser integer, no string."""
        data = {
            "generalConfiguration": {
                "totalTries": "not_a_number",
                "dirOutput": "/output",
                "fileOutput": "result.csv",
                "simulationName": "sim1",
                "simulationType": "basic",
            }
        }
        valid, _ = ResearchService.validate_research(data, VALID_SCHEMA)
        assert valid is False

    def test_invalid_wrong_type_boolean(self):
        """activateGUI debe ser boolean, no string."""
        data = {
            "generalConfiguration": {
                "totalTries": 10,
                "dirOutput": "/output",
                "fileOutput": "result.csv",
                "simulationName": "sim1",
                "simulationType": "basic",
                "activateGUI": "yes",
            }
        }
        valid, _ = ResearchService.validate_research(data, VALID_SCHEMA)
        assert valid is False

    def test_invalid_enum_value(self):
        """simulationType solo acepta 'basic'."""
        data = {
            "generalConfiguration": {
                "totalTries": 10,
                "dirOutput": "/output",
                "fileOutput": "result.csv",
                "simulationName": "sim1",
                "simulationType": "advanced",
            }
        }
        valid, _ = ResearchService.validate_research(data, VALID_SCHEMA)
        assert valid is False

    def test_invalid_minimum_constraint(self):
        """totalTries tiene minimum=1, 0 no debe pasar."""
        data = {
            "generalConfiguration": {
                "totalTries": 0,
                "dirOutput": "/output",
                "fileOutput": "result.csv",
                "simulationName": "sim1",
                "simulationType": "basic",
            }
        }
        valid, _ = ResearchService.validate_research(data, VALID_SCHEMA)
        assert valid is False

    def test_invalid_negative_tries(self):
        """totalTries negativo no debe pasar (minimum=1)."""
        data = {
            "generalConfiguration": {
                "totalTries": -5,
                "dirOutput": "/output",
                "fileOutput": "result.csv",
                "simulationName": "sim1",
                "simulationType": "basic",
            }
        }
        valid, _ = ResearchService.validate_research(data, VALID_SCHEMA)
        assert valid is False


# ═══════════════════════════════════════════════════════════════
# INTEGRATION: Endpoints de la API
# ═══════════════════════════════════════════════════════════════


class TestAdminSchemaEndpoints:
    """Tests de integración para GET/PUT /api/admin/schema."""

    def test_get_schema(self, client, seed_data):
        resp = client.get("/api/admin/schema")
        assert resp.status_code == 200
        data = resp.json()
        assert "schema" in data
        assert data["schema"]["type"] == "object"

    def test_get_schema_not_found(self, client, db):
        """Sin datos en admin, devuelve 404."""
        resp = client.get("/api/admin/schema")
        assert resp.status_code == 404

    def test_put_schema_valid(self, client, seed_data):
        new_schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        resp = client.put(
            "/api/admin/schema",
            json={"json_schema": new_schema},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["schema"]["properties"]["name"]["type"] == "string"

    def test_put_schema_invalid(self, client, seed_data):
        resp = client.put(
            "/api/admin/schema",
            json={"json_schema": {"type": "invalido"}},
        )
        assert resp.status_code == 400

    def test_put_schema_no_body(self, client, seed_data):
        resp = client.put(
            "/api/admin/schema",
            content=b"",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 422

    def test_put_schema_missing_key(self, client, seed_data):
        resp = client.put(
            "/api/admin/schema",
            json={"wrong_key": {}},
        )
        assert resp.status_code == 422

    def test_put_schema_persists(self, client, seed_data):
        """Verifica que el schema se persiste correctamente tras PUT."""
        new_schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
        client.put("/api/admin/schema", json={"json_schema": new_schema})

        resp = client.get("/api/admin/schema")
        data = resp.json()
        assert "x" in data["schema"]["properties"]


class TestResearchEndpoints:
    """Tests de integración para endpoints de research."""

    def test_create_research_valid(self, client, seed_data):
        resp = client.post(
            "/api/research",
            json={
                "user_id": seed_data["user"].id,
                "name": "Test Research",
                "research_json": VALID_RESEARCH_DATA,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Research"
        assert data["status"] == "draft"

    def test_create_research_invalid_data_creates_draft(self, client, seed_data):
        """research_json inválido → se crea como draft (sin validación)."""
        resp = client.post(
            "/api/research",
            json={
                "user_id": seed_data["user"].id,
                "research_json": {"wrong": "data"},
            },
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "draft"

    def test_create_research_missing_fields(self, client, seed_data):
        resp = client.post("/api/research", json={"name": "test"})
        assert resp.status_code == 422

    def test_create_research_user_not_found(self, client, seed_data):
        resp = client.post(
            "/api/research",
            json={
                "user_id": 999,
                "research_json": VALID_RESEARCH_DATA,
            },
        )
        assert resp.status_code == 404

    def test_get_research(self, client, seed_data):
        # Crear primero
        post_resp = client.post(
            "/api/research",
            json={
                "user_id": seed_data["user"].id,
                "research_json": VALID_RESEARCH_DATA,
            },
        )
        rid = post_resp.json()["id"]

        resp = client.get(f"/api/research/{rid}")
        assert resp.status_code == 200
        assert resp.json()["id"] == rid

    def test_get_research_not_found(self, client, seed_data):
        resp = client.get("/api/research/999")
        assert resp.status_code == 404

    def test_get_researches_by_user(self, client, seed_data):
        uid = seed_data["user"].id
        client.post(
            "/api/research",
            json={
                "user_id": uid,
                "research_json": VALID_RESEARCH_DATA,
            },
        )
        resp = client.get(f"/api/research/user/{uid}")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_researches_by_user_not_found(self, client, seed_data):
        resp = client.get("/api/research/user/999")
        assert resp.status_code == 404

    def test_update_research(self, client, seed_data):
        post_resp = client.post(
            "/api/research",
            json={
                "user_id": seed_data["user"].id,
                "research_json": VALID_RESEARCH_DATA,
            },
        )
        rid = post_resp.json()["id"]

        resp = client.put(
            f"/api/research/{rid}",
            json={
                "name": "Updated Name",
                "status": "running",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"
        assert resp.json()["status"] == "running"

    def test_update_research_invalid_status(self, client, seed_data):
        post_resp = client.post(
            "/api/research",
            json={
                "user_id": seed_data["user"].id,
                "research_json": VALID_RESEARCH_DATA,
            },
        )
        rid = post_resp.json()["id"]

        resp = client.put(f"/api/research/{rid}", json={"status": "deleted"})
        assert resp.status_code == 422


class TestDraftValidation:
    """Tests de validación condicional para drafts."""

    def test_create_research_without_research_json(self, client, seed_data):
        """Crear research sin research_json → se crea con {}."""
        resp = client.post(
            "/api/research",
            json={"user_id": seed_data["user"].id},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["research_json"] == {}
        assert data["status"] == "draft"

    def test_create_research_with_partial_data(self, client, seed_data):
        """Crear research con datos parciales → draft sin error."""
        resp = client.post(
            "/api/research",
            json={
                "user_id": seed_data["user"].id,
                "research_json": {"generalConfiguration": {"totalTries": 10}},
            },
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "draft"

    def test_update_draft_with_partial_data(self, client, seed_data):
        """Actualizar draft con datos parciales → OK."""
        post_resp = client.post(
            "/api/research",
            json={"user_id": seed_data["user"].id},
        )
        rid = post_resp.json()["id"]

        resp = client.put(
            f"/api/research/{rid}",
            json={"research_json": {"incomplete": True}},
        )
        assert resp.status_code == 200
        assert resp.json()["research_json"] == {"incomplete": True}

    def test_draft_to_running_with_valid_data(self, client, seed_data):
        """Cambiar draft→running con datos válidos → OK."""
        post_resp = client.post(
            "/api/research",
            json={
                "user_id": seed_data["user"].id,
                "research_json": VALID_RESEARCH_DATA,
            },
        )
        rid = post_resp.json()["id"]

        resp = client.put(
            f"/api/research/{rid}",
            json={"status": "running"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_draft_to_running_with_invalid_data(self, client, seed_data):
        """Cambiar draft→running con datos inválidos → 400."""
        post_resp = client.post(
            "/api/research",
            json={
                "user_id": seed_data["user"].id,
                "research_json": {"bad": "data"},
            },
        )
        rid = post_resp.json()["id"]

        resp = client.put(
            f"/api/research/{rid}",
            json={"status": "running"},
        )
        assert resp.status_code == 400

    def test_update_running_with_invalid_data(self, client, seed_data):
        """Actualizar research running con datos inválidos → 400."""
        post_resp = client.post(
            "/api/research",
            json={
                "user_id": seed_data["user"].id,
                "research_json": VALID_RESEARCH_DATA,
            },
        )
        rid = post_resp.json()["id"]
        client.put(f"/api/research/{rid}", json={"status": "running"})

        resp = client.put(
            f"/api/research/{rid}",
            json={"research_json": {"bad": "data"}},
        )
        assert resp.status_code == 400

    def test_update_running_with_valid_data(self, client, seed_data):
        """Actualizar research running con datos válidos → OK."""
        post_resp = client.post(
            "/api/research",
            json={
                "user_id": seed_data["user"].id,
                "research_json": VALID_RESEARCH_DATA,
            },
        )
        rid = post_resp.json()["id"]
        client.put(f"/api/research/{rid}", json={"status": "running"})

        new_data = {
            "generalConfiguration": {
                "totalTries": 200,
                "dirOutput": "/new_output",
                "fileOutput": "new_result.csv",
                "simulationName": "sim2",
                "simulationType": "basic",
            }
        }
        resp = client.put(
            f"/api/research/{rid}",
            json={"research_json": new_data},
        )
        assert resp.status_code == 200
        assert resp.json()["research_json"] == new_data


class TestUserEndpoints:
    """Tests de integración para endpoints de usuario."""

    def test_get_user(self, client, seed_data):
        uid = seed_data["user"].id
        resp = client.get(f"/api/users/{uid}")
        assert resp.status_code == 200
        assert resp.json()["email"] == "jaime@test.com"

    def test_get_user_not_found(self, client, seed_data):
        resp = client.get("/api/users/999")
        assert resp.status_code == 404
