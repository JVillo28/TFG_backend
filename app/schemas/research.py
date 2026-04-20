from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ResearchCreate(BaseModel):
    """Request body para POST /api/research"""

    user_id: int
    name: str = "NEW RESEARCH"
    research_json: dict = {}


class ResearchUpdate(BaseModel):
    """Request body para PUT /api/research/<id>"""

    name: str | None = None
    research_json: dict | None = None
    status: Literal["draft", "running", "finished"] | None = None


class ResearchResponse(BaseModel):
    """Response para endpoints de research"""

    id: int
    name: str
    research_json: dict
    user_id: int
    status: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
