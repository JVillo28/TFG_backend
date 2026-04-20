"""
Servicio de Admin — validación de JSON Schema
"""

from jsonschema import Draft202012Validator


class AdminService:
    """Lógica de negocio para la gestión del schema de admin"""

    @staticmethod
    def validate_json_schema(schema: dict) -> tuple[bool, str | None]:
        """
        Meta-valida que el objeto recibido sea un JSON Schema válido
        según la especificación Draft 2020-12.

        Returns:
            (True, None)  si es válido
            (False, msg)  si no es válido
        """
        if not isinstance(schema, dict):
            return False, "Schema must be a JSON object"

        meta_schema = Draft202012Validator.META_SCHEMA
        meta_validator = Draft202012Validator(meta_schema)

        errors = list(meta_validator.iter_errors(schema))
        if errors:
            messages = [e.message for e in errors]
            return False, "; ".join(messages)

        return True, None
