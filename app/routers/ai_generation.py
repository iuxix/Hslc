from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.schemas.ai import (
    AIGenerateRequest,
    AIGenerateResponse,
    AIModelsResponse,
)
from app.services import ai_service
from app.config import settings

router = APIRouter(
    prefix="/api/admin/ai",
    tags=["Admin — AI Generation"],
    dependencies=[Depends(get_current_admin)],
)


@router.get("/status", response_model=AIModelsResponse)
def ai_status():
    """Check Gemini connection status"""
    return {
        "model": ai_service.MODEL_NAME,
        "status": "ready" if settings.GEMINI_API_KEY else "no_api_key",
    }


@router.post("/generate", response_model=AIGenerateResponse)
def generate(
    payload: AIGenerateRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Generate MCQs via Gemini and save to question bank"""
    result = ai_service.generate_questions(
        db=db,
        chapter_id=payload.chapter_id,
        difficulty=payload.difficulty,
        count=payload.count,
        material=payload.material,
        created_by=current_admin.id,
    )
    return result
