"""
Rutas de la API
"""

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import router
from app.database import get_db
from app.models import Admin, Research, Users
from app.schemas.admin import AdminSchemaUpdate
from app.schemas.research import ResearchCreate, ResearchResponse, ResearchUpdate
from app.schemas.user import UserResponse
from app.services.admin_service import AdminService
from app.services.research_service import ResearchService


@router.get("/health")
def health_check():
    return {"status": "healthy", "database": "connected"}


# ── Admin Schema ────────────────────────────────────────────


@router.get("/admin/schema")
def get_schema(db: Session = Depends(get_db)):
    """GET /api/admin/schema — devuelve el JSON Schema actual (id=1)"""
    admin = db.get(Admin, 1)
    if not admin:
        raise HTTPException(status_code=404, detail="Schema not found")
    return {
        "id": admin.id,
        "schema": admin.json_schema,
        "created_at": admin.created_at,
        "updated_at": admin.updated_at,
    }


@router.put("/admin/schema")
def update_schema(body: AdminSchemaUpdate, db: Session = Depends(get_db)):
    """PUT /api/admin/schema — actualiza el JSON Schema."""
    valid, error_msg = AdminService.validate_json_schema(body.json_schema)
    if not valid:
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid JSON Schema", "details": error_msg},
        )

    admin = db.get(Admin, 1)
    if not admin:
        raise HTTPException(status_code=404, detail="Schema not found")

    admin.json_schema = body.json_schema
    db.commit()
    return {
        "id": admin.id,
        "schema": admin.json_schema,
        "created_at": admin.created_at,
        "updated_at": admin.updated_at,
    }


# ── Research ────────────────────────────────────────────────


@router.post("/research", status_code=201)
def create_research(body: ResearchCreate, db: Session = Depends(get_db)):
    """POST /api/research — crea una research como draft (sin validación)"""
    user = db.get(Users, body.user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {body.user_id} not found")

    research = Research(
        name=body.name,
        research_json=body.research_json,
        user_id=body.user_id,
    )
    db.add(research)
    db.commit()
    db.refresh(research)
    return ResearchResponse.model_validate(research)


@router.get("/research/{research_id}")
def get_research(research_id: int, db: Session = Depends(get_db)):
    """GET /api/research/<id>"""
    research = db.get(Research, research_id)
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")
    return ResearchResponse.model_validate(research)


@router.get("/research/user/{user_id}")
def get_researches_by_user(user_id: int, db: Session = Depends(get_db)):
    """GET /api/research/user/<user_id>"""
    user = db.get(Users, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    stmt = select(Research).where(Research.user_id == user_id)
    researches = db.execute(stmt).scalars().all()
    return [ResearchResponse.model_validate(r) for r in researches]


@router.put("/research/{research_id}")
def update_research(
    research_id: int, body: ResearchUpdate, db: Session = Depends(get_db)
):
    """PUT /api/research/<id> — actualiza una research existente"""
    research = db.get(Research, research_id)
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    # Determinar si hay que validar research_json
    needs_validation = body.research_json is not None or body.status is not None
    if needs_validation:
        research_data = body.research_json or research.research_json
        target_status = body.status or research.status

        admin = db.get(Admin, 1)
        if not admin:
            raise HTTPException(status_code=500, detail="Admin schema not configured")
        valid, error_msg = ResearchService.validate_research_for_status(
            research_data, admin.json_schema, research.status, target_status
        )
        if not valid:
            raise HTTPException(
                status_code=400,
                detail={"error": "Validation error", "details": error_msg},
            )

    if body.research_json is not None:
        research.research_json = body.research_json
    if body.name is not None:
        research.name = body.name
    if body.status is not None:
        research.status = body.status

    db.commit()
    db.refresh(research)
    return ResearchResponse.model_validate(research)


# ── Users ───────────────────────────────────────────────────


@router.get("/users/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    """GET /api/users/<id>"""
    user = db.get(Users, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return UserResponse.model_validate(user)
