"""
Application Factory para FastAPI
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from config import get_settings


def create_app(settings=None) -> FastAPI:
    """
    Factory que crea y configura la aplicación FastAPI

    Args:
        settings: Instancia de Settings (si None, usa get_settings())

    Returns:
        app: Instancia de FastAPI configurada
    """
    if settings is None:
        settings = get_settings()

    app = FastAPI(title="TFG Backend", debug=settings.debug)

    # Inicializar base de datos
    init_db(settings.database_url, echo=settings.sqlalchemy_echo)

    # CORS
    origins = [o.strip() for o in settings.allowed_origins.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Registrar router
    from app.api import router

    app.include_router(router)

    return app
