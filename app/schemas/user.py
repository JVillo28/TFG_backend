from datetime import datetime

from pydantic import BaseModel


class UserResponse(BaseModel):
    """Response para endpoints de usuario"""

    id: int
    name: str
    email: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
