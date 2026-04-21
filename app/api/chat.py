"""
Chat endpoint — POST /api/chat/message

Asistente LLM stateless que guía al investigador sección por sección del
JSON Schema. Cada turno está acotado a `current_section` y, al cerrar la
sección, el backend calcula `next_section` para que el frontend avance.
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from openai import APIConnectionError, APITimeoutError, BadRequestError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Admin
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm import (
    build_system_prompt,
    get_llm_client,
    get_llm_model,
    get_next_section,
    get_section_order,
    get_section_type,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat/message", response_model=ChatResponse)
def chat_message(body: ChatRequest, db: Session = Depends(get_db)):
    """POST /api/chat/message — un turno del chat, acotado a una sección."""

    # 1. Cargar schema desde BD
    admin = db.get(Admin, 1)
    if not admin:
        raise HTTPException(status_code=500, detail="Admin schema not configured")

    schema = admin.json_schema

    # 2. Validar que current_section existe en el schema
    section_order = get_section_order(schema)
    if body.current_section not in section_order:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid section",
                "details": (
                    f"The section '{body.current_section}' does not exist in "
                    f"the current schema. Valid sections: {section_order}."
                ),
            },
        )

    # 3. Calcular la siguiente sección y el tipo de la actual
    next_section_value = get_next_section(schema, body.current_section)
    section_type = get_section_type(schema, body.current_section) or "object"

    # 4. Construir mensajes para el LLM
    system_prompt = build_system_prompt(
        schema=schema,
        current_section=body.current_section,
        next_section=next_section_value,
        section_type=section_type,
    )

    # form_state se restringe a la sección activa y al tipo esperado
    default_form_state = [] if section_type == "array" else {}
    section_form_state = (
        body.form_state.get(body.current_section, default_form_state)
        if isinstance(body.form_state, dict)
        else default_form_state
    )
    form_state_text = (
        f"Estado actual de los campos de la sección:\n{json.dumps(section_form_state, indent=2, ensure_ascii=False)}"
    )

    # Turno de auto-inicialización: message == "" → instrucción explícita
    if body.message == "":
        user_message = (
            f"[Inicio de sección] Abre la sección «{body.current_section}» con "
            "un saludo breve y una primera pregunta sobre sus campos."
        )
    else:
        user_message = body.message

    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": form_state_text},
    ]
    for msg in body.history[-20:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})

    # 5. Llamar al LLM
    try:
        client = get_llm_client()
        completion = client.chat.completions.create(
            model=get_llm_model(),
            messages=messages,
            response_format={"type": "json_object"},
        )
    except (APIConnectionError, APITimeoutError):
        raise HTTPException(
            status_code=503,
            detail={
                "error": "LLM service unavailable",
                "details": "Cannot connect to the LLM provider. Check your LLM_BASE_URL configuration.",
            },
        ) from None
    except BadRequestError as exc:
        # El proveedor rechaza la petición; habitualmente porque el modelo
        # generó un JSON malformado (json_validate_failed en Groq) o porque
        # el prompt supera el límite de tokens del modelo.
        logger.error("LLM provider rejected the request: %s", exc)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "LLM returned invalid response",
                "details": ("El modelo generó una respuesta malformada. Vuelve a enviar tu mensaje."),
            },
        ) from exc

    # 6. Parsear respuesta
    raw = completion.choices[0].message.content
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.error("LLM returned unparseable response: %s", raw)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "LLM returned invalid response",
                "details": "The model response could not be parsed. Try again.",
            },
        ) from exc

    state = parsed.get("state", "asking")
    response_next_section = next_section_value if state == "ready_to_apply" else None
    proposed_values = parsed.get("proposed_values")

    # Normalización defensiva: si el LLM dice ready_to_apply pero no coloca la
    # sección o su tipo no coincide (p. ej. durante un skip), normalizamos al
    # contenedor vacío apropiado. Solo rechazamos si el payload tiene un tipo
    # groseramente incompatible (p. ej. string donde se esperaba lista).
    if state == "ready_to_apply":
        if not isinstance(proposed_values, dict):
            proposed_values = {}

        section_payload = proposed_values.get(body.current_section)
        empty_container: list | dict = [] if section_type == "array" else {}

        if section_payload is None:
            # El LLM no puso la clave (típico en skips sin valores deducidos)
            proposed_values[body.current_section] = empty_container
            logger.info(
                "Normalized missing proposed_values[%s] to empty %s",
                body.current_section,
                section_type,
            )
        elif section_type == "array" and not isinstance(section_payload, list):
            # Tipo groseramente incorrecto: preferimos normalizar a [] a rechazar
            # para que el skip funcione aunque el LLM mande objeto.
            proposed_values[body.current_section] = empty_container
            logger.warning(
                "LLM returned non-list for array section '%s' (%r); normalized to []",
                body.current_section,
                section_payload,
            )
        elif section_type == "object" and not isinstance(section_payload, dict):
            proposed_values[body.current_section] = empty_container
            logger.warning(
                "LLM returned non-object for object section '%s' (%r); normalized to {}",
                body.current_section,
                section_payload,
            )

    return ChatResponse(
        message=parsed.get("message", ""),
        state=state,
        proposed_values=proposed_values,
        next_section=response_next_section,
    )
