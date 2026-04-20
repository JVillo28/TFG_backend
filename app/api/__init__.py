"""
Router para la API REST
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api")

from app.api import routes  # noqa: E402, F401
from app.api.chat import router as chat_router  # noqa: E402

router.include_router(chat_router)
