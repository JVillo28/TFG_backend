"""
Pydantic schemas para el endpoint de chat.

El chat está dividido por secciones del JSON Schema: cada turno se centra en
una única sección (`current_section`) y el backend calcula la siguiente
sección a rellenar (`next_section`) cuando la actual se completa.
"""

from pydantic import BaseModel


class ChatMessageItem(BaseModel):
    """Un mensaje del historial de chat dentro de la sección activa."""

    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    """
    Request body para POST /api/chat/message.

    current_section indica la clave del JSON Schema cuya configuración se
    está discutiendo. Un `message` vacío se interpreta como turno de
    auto-inicialización: el agente debe abrir la sección con un saludo
    y una primera pregunta.
    """

    research_id: int
    message: str
    form_state: dict
    current_section: str
    history: list[ChatMessageItem] = []


class ChatResponse(BaseModel):
    """
    Response del LLM parseada.

    next_section apunta a la siguiente sección a rellenar cuando el LLM
    devuelve state="ready_to_apply". Vale None si la sección actual es
    la última del schema.
    """

    message: str
    state: str  # "asking" | "ready_to_apply"
    proposed_values: dict | None = None
    next_section: str | None = None
