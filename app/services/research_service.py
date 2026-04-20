"""
Servicio de Research — validación de datos contra el schema de admin
"""

import jsonschema


class ResearchService:
    """Lógica de negocio para la gestión de researches"""

    @staticmethod
    def validate_research(research_json: dict, schema: dict) -> tuple[bool, str | None]:
        """
        Valida que research_json cumpla con el JSON Schema guardado en admin.

        Returns:
            (True, None)  si es válido
            (False, msg)  si no es válido
        """
        if not isinstance(research_json, dict):
            return False, "research_json must be a JSON object"

        try:
            jsonschema.validate(instance=research_json, schema=schema)
        except jsonschema.ValidationError as e:
            return False, e.message
        except jsonschema.SchemaError as e:
            return False, f"Admin schema is invalid: {e.message}"

        return True, None

    @staticmethod
    def validate_research_for_status(
        research_json: dict,
        schema: dict,
        current_status: str | None,
        target_status: str | None,
    ) -> tuple[bool, str | None]:
        """
        Valida research_json solo si es necesario según el status.

        No valida si:
        - El status destino es 'draft' o no se cambia de status
          y el status actual es 'draft'

        Valida si:
        - Se transiciona fuera de 'draft' (draft → running/finished)
        - Se actualiza research_json en un research no-draft
        """
        effective_status = target_status or current_status
        if effective_status == "draft":
            return True, None
        return ResearchService.validate_research(research_json, schema)
