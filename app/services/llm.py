"""
Servicio LLM — cliente OpenAI apuntando a Groq (default) u Ollama local.

Este módulo concentra:
- La construcción del cliente OpenAI-compatible.
- Las utilidades para recorrer las secciones del JSON Schema en orden
  (get_section_order, get_next_section).
- La construcción del system prompt acotado a una única sección activa.
"""

import json

from openai import OpenAI

from config import get_settings


def get_llm_client() -> OpenAI:
    """Devuelve un cliente OpenAI configurado según las settings."""
    settings = get_settings()
    return OpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
    )


def get_llm_model() -> str:
    """Devuelve el nombre del modelo LLM configurado."""
    return get_settings().llm_model


# JSON Schema de referencia de la respuesta del LLM (para proveedores que
# soporten grammar-constrained generation, p. ej. Ollama)
LLM_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "message": {
            "type": "string",
            "description": "Mensaje conversacional para el usuario (en español)",
        },
        "state": {
            "type": "string",
            "enum": ["asking", "ready_to_apply"],
            "description": "asking = sigue preguntando, ready_to_apply = tiene toda la info",
        },
        "proposed_values": {
            "type": "object",
            "description": "Valores propuestos para rellenar el formulario. Solo cuando state=ready_to_apply.",
        },
    },
    "required": ["message", "state"],
}


# ──────────────────────────────────────────────────────────────────────────
# Utilidades de secciones del JSON Schema
# ──────────────────────────────────────────────────────────────────────────

_VALID_SECTION_TYPES = ("object", "array")


def get_section_type(schema: dict, section: str) -> str | None:
    """Devuelve "object", "array" o None según el tipo de la sección."""
    if not isinstance(schema, dict):
        return None
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return None
    section_schema = properties.get(section)
    if not isinstance(section_schema, dict):
        return None
    section_type = section_schema.get("type")
    if section_type in _VALID_SECTION_TYPES:
        return section_type
    return None


def get_section_order(schema: dict) -> list[str]:
    """
    Devuelve la lista ordenada de claves de las secciones del schema.

    Se consideran secciones las entradas de `schema["properties"]` cuyo tipo
    es "object" o "array". El orden es el declarado por el administrador al
    construir el schema (preservado por `dict` en Python 3.7+).
    """
    if not isinstance(schema, dict):
        return []
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return []
    return [
        key
        for key, value in properties.items()
        if isinstance(value, dict) and value.get("type") in _VALID_SECTION_TYPES
    ]


def _is_section_non_empty(section_schema: dict) -> bool:
    """True si la sección aporta estructura: propiedades para objetos, o
    un esquema de items para arrays."""
    if not isinstance(section_schema, dict):
        return False
    section_type = section_schema.get("type")
    if section_type == "object":
        props = section_schema.get("properties", {})
        return isinstance(props, dict) and len(props) > 0
    if section_type == "array":
        items = section_schema.get("items")
        return isinstance(items, dict) and bool(items)
    return False


def get_next_section(schema: dict, current: str) -> str | None:
    """
    Devuelve la siguiente sección no vacía declarada tras `current`.

    - Salta secciones sin estructura (objetos sin propiedades, arrays sin items).
    - Devuelve None si `current` es la última sección o no existe en el schema.
    """
    order = get_section_order(schema)
    if current not in order:
        return None
    idx = order.index(current)
    properties = schema.get("properties", {})
    for candidate in order[idx + 1:]:
        candidate_schema = properties.get(candidate, {})
        if _is_section_non_empty(candidate_schema):
            return candidate
    return None


# ──────────────────────────────────────────────────────────────────────────
# System prompt por sección
# ──────────────────────────────────────────────────────────────────────────

def build_system_prompt(
    schema: dict,
    current_section: str,
    next_section: str | None,
    section_type: str = "object",
) -> str:
    """
    Construye el system prompt en español, acotado a la sección activa.

    Parámetros
    ----------
    schema
        JSON Schema completo, tal como lo guarda el administrador.
    current_section
        Clave de la sección que el agente está discutiendo en este turno.
    next_section
        Clave de la siguiente sección (o None si es la última). Se entrega
        al LLM para que pueda anunciar textualmente la transición al cerrar.
    section_type
        "object" (valor por defecto) o "array". Determina el formato
        esperado de `proposed_values` y las instrucciones al LLM.
    """
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    section_schema = properties.get(current_section, {}) if isinstance(properties, dict) else {}
    section_title = (
        section_schema.get("title", current_section)
        if isinstance(section_schema, dict)
        else current_section
    )
    section_json = json.dumps(section_schema, indent=2, ensure_ascii=False)

    next_section_clause = (
        f"La siguiente sección tras esta será «{next_section}»; al cerrar la actual,"
        " anuncia textualmente al usuario que pasaréis a esa sección."
        if next_section
        else "Esta es la última sección del schema; al cerrarla, indica al usuario"
        " que la configuración está completa y que debe pulsar Save."
    )

    # Formato vacío de proposed_values según tipo (para los ejemplos de skip)
    empty_payload_example = (
        f'{{"{current_section}": []}}'
        if section_type == "array"
        else f'{{"{current_section}": {{}}}}'
    )

    # Bloque común a ambas ramas: saltar la sección si el usuario lo pide.
    skip_clause = f"""## Saltar la sección

Si el usuario expresa explícitamente la intención de saltar la sección actual (frases como "saltar", "saltemos", "no quiero rellenar esto", "pasa a la siguiente", "siguiente sección", "omitir esta sección", "skip"), responde OBLIGATORIAMENTE así:

- state="ready_to_apply"  (NO "asking"; esto es CLAVE para que el botón Aplicar aparezca en la UI)
- proposed_values con los valores que hayas podido deducir hasta ahora; si no hay ninguno, envía el contenedor vacío apropiado: `{empty_payload_example}`.
- message: informa brevemente de que vas a saltar la sección mencionando que los valores quedarán vacíos. NO pidas confirmación verbal en el message (la interfaz ya muestra un botón "Aplicar" para eso).

Ejemplo de respuesta ante intent de skip sin valores deducidos:
{{"message": "Entendido, saltamos esta sección. Los valores quedarán vacíos.", "state": "ready_to_apply", "proposed_values": {empty_payload_example}}}

IMPORTANTE: solo interpreta como skip aquellas frases que claramente se refieren a saltar la **sección completa**, no a avanzar al siguiente campo dentro de la sección. Si tienes dudas sobre la intención, pregunta en lugar de asumir."""

    if section_type == "array":
        items = section_schema.get("items", {}) if isinstance(section_schema, dict) else {}
        items_type = items.get("type") if isinstance(items, dict) else None
        if items_type == "object":
            example = (
                f'{{"{current_section}": [\n'
                f'    {{"campo1": "valor", "campo2": 123}},\n'
                f'    {{"campo1": "otro", "campo2": 456}}\n'
                f"  ]}}"
            )
            items_clause = (
                "Cada elemento del array es un objeto con los campos declarados en "
                "`items.properties`. Al aplicar, proporciona un objeto por cada elemento."
            )
        else:
            example = f'{{"{current_section}": ["valor1", "valor2", "valor3"]}}'
            items_clause = (
                f"Cada elemento del array es un valor primitivo de tipo "
                f"`{items_type or 'string'}`."
            )

        type_specific = f"""## Instrucciones específicas para esta sección (tipo array)

Esta sección es una **colección** (array). {items_clause}

1. Si el mensaje del usuario es la cadena vacía, saluda brevemente, menciona el nombre de la sección y PREGUNTA primero al usuario cuántos elementos desea configurar (salvo que la cifra aparezca de forma inequívoca en un mensaje posterior).
2. Una vez conozcas el número de elementos, recorre los campos de `items` para cada uno de ellos, preguntando de forma conversacional.
3. NO inventes valores; pregunta cuando la intención sea ambigua.
4. NO menciones campos que no estén en `items` de la sección.
5. Respeta las restricciones (tipos, enums, mínimos, máximos, longitudes, patrones) de `items`.
6. Cuando tengas la información de TODOS los elementos, responde con state="ready_to_apply" y coloca la lista completa en `proposed_values`. El formato debe ser:

```
{example}
```

7. Al cerrar la sección, anuncia textualmente la transición a la siguiente (o el cierre final si no hay siguiente).
8. Siempre responde en español, independientemente del idioma de los nombres de campos."""
        response_format_line = (
            f"proposed_values: (solo cuando state=\"ready_to_apply\") objeto con la "
            f"forma `{{\"{current_section}\": [ ...items... ]}}`"
        )
    else:  # object (default)
        type_specific = f"""## Instrucciones específicas para esta sección (tipo object)

1. Si el mensaje del usuario es la cadena vacía, interpreta que es un turno de apertura: saluda brevemente, menciona el nombre de la sección activa y formula una primera pregunta orientada a sus campos.
2. Analiza el estado actual del formulario (lo recibirás en el mensaje del usuario) restringido a esta sección, e identifica qué campos faltan por rellenar.
3. Pregunta al usuario de forma conversacional en español hasta obtener la información necesaria para los campos de esta sección.
4. NO inventes valores cuando la intención del usuario sea ambigua — pregunta en su lugar.
5. NO menciones campos que no estén en el sub-schema de esta sección.
6. Respeta las restricciones (tipos, enums, mínimos, máximos, longitudes, patrones).
7. Cuando tengas suficiente información, responde con state="ready_to_apply" y coloca los valores en `proposed_values`. El objeto `proposed_values` debe tener como única clave de primer nivel el nombre de la sección activa (`{current_section}`) y, dentro, los campos rellenados. Formato:

```
{{"{current_section}": {{"campo1": "valor", "campo2": 123}}}}
```

8. Al cerrar la sección, anuncia textualmente al usuario la transición a la siguiente (o el cierre final si no hay siguiente).
9. Siempre responde en español, independientemente del idioma de los nombres de campos."""
        response_format_line = (
            f"proposed_values: (solo cuando state=\"ready_to_apply\") objeto con la "
            f"forma `{{\"{current_section}\": {{...campos...}}}}`"
        )

    return f"""Eres un asistente de configuración para simulaciones biológicas que guía al investigador sección por sección.

## Sección activa

Estás ayudando a rellenar la sección «{section_title}» (clave interna: `{current_section}`, tipo `{section_type}`). Trabaja exclusivamente dentro de esta sección.

Sub-schema de la sección (estructura, tipos y restricciones):

{section_json}

## Transición

{next_section_clause}

{type_specific}

{skip_clause}

## Formato de respuesta

Responde SIEMPRE con un JSON válido con estos campos:
- message: tu mensaje conversacional al usuario (en español)
- state: "asking" si aún necesitas información de esta sección, "ready_to_apply" si ya tienes todo
- {response_format_line}"""
