from datetime import datetime

from pydantic import BaseModel


class AdminSchemaUpdate(BaseModel):
    """Request body para PUT /api/admin/schema"""

    json_schema: dict


class AdminSchemaResponse(BaseModel):
    """Response para endpoints de admin schema"""

    id: int
    schema_: dict
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
