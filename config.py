"""
Configuración de la aplicación
"""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuración base"""

    database_url: str = "sqlite:///app.db"
    secret_key: str = "fallback-dev-key"
    allowed_origins: str = "*"
    debug: bool = False
    testing: bool = False
    sqlalchemy_echo: bool = False

    # LLM
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_api_key: str = "ollama"

    model_config = {"env_file": ".env", "extra": "ignore"}


class DevelopmentSettings(Settings):
    """Configuración para desarrollo"""

    debug: bool = True
    sqlalchemy_echo: bool = True


class ProductionSettings(Settings):
    """Configuración para producción"""

    debug: bool = False
    testing: bool = False


class TestingSettings(Settings):
    """Configuración para tests"""

    testing: bool = True
    database_url: str = "sqlite://"


@lru_cache
def get_settings() -> Settings:
    env = os.environ.get("APP_ENV", "development")
    if env == "testing":
        return TestingSettings()
    elif env == "production":
        return ProductionSettings()
    return DevelopmentSettings()
