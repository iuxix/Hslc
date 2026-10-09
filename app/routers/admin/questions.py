from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.schemas.question import (
    QuestionCreate,
    QuestionUpdate,
    QuestionResponse,
    QuestionBulkCreate,
    BulkCreateResponse,
)
from app.services import question_service as svc

router = APIRouter(
    prefix="/api/admin/questions",
    tags=["Admin — Questions"],
    dependencies=[Depends(get_current_admin)],
)


# ============================================================
# CREATE
# ============================================================

@router.post("", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
def create_question(
    data: QuestionCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Create a single question"""
    return svc.create_question(db, data, created_by=current_admin.id)


@router.post("/bulk", response_model=BulkCreateResponse)
def create_bulk(
    data: QuestionBulkCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Bulk create questions (up to 100)"""
    result = svc.create_questions_bulk(db, data.questions, created_by=current_admin.id)
    return result


# ============================================================
# READ
# ============================================================

@router.get("", response_model=List[QuestionResponse])
def list_questions(
    subject_id: Optional[int] = None,
    chapter_id: Optional[int] = None,
    topic_id: Optional[int] = None,
    difficulty: Optional[str] = None,
    source: Optional[str] = None,
    is_active: bool = True,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List questions with filters"""
    return svc.get_questions(
        db,
        subject_id=subject_id,
        chapter_id=chapter_id,
        topic_id=topic_id,
        difficulty=difficulty,
        source=source,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    """Question statistics"""
    return svc.get_stats(db)


@router.get("/{question_id}", response_model=QuestionResponse)
def get_question(question_id: int, db: Session = Depends(get_db)):
    """Get a single question"""
    return svc.get_question(db, question_id)


# ============================================================
# UPDATE / DELETE
# ============================================================

@router.put("/{question_id}", response_model=QuestionResponse)
def update_question(
    question_id: int,
    data: QuestionUpdate,
    db: Session = Depends(get_db),
):
    """Update a question"""
    return svc.update_question(db, question_id, data)


@router.delete("/{question_id}")
def delete_question(question_id: int, db: Session = Depends(get_db)):
    """Delete a question"""
    svc.delete_question(db, question_id)
    return {"message": f"Question {question_id} deleted"}
