from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List

from app.database import get_db
from app.models.curriculum import Subject, Section, Chapter
from app.schemas.curriculum import (
    SubjectResponse,
    SubjectFull,
    SectionWithChapters,
    ChapterWithTopics,
)

router = APIRouter(prefix="/api/public", tags=["Public Curriculum"])


# ============================================================
# ✅ WARMUP — UptimeRobot ke liye (Neon ko warm rakhta hai)
# ============================================================

@router.api_route("/warmup", methods=["GET", "HEAD"], tags=["Health"])
def warmup(db: Session = Depends(get_db)):
    """
    Warm-up endpoint for UptimeRobot.
    Touches DB so Neon doesn't auto-suspend (5 min idle).
    Supports GET and HEAD (UptimeRobot uses HEAD).
    """
    count = db.execute(text("SELECT COUNT(*) FROM questions")).scalar()
    return {
        "warm": True,
        "question_count": count,
        "status": "ok",
    }


# ============================================================
# SUBJECTS
# ============================================================

@router.get("/subjects", response_model=List[SubjectResponse])
def list_subjects(db: Session = Depends(get_db)):
    return db.query(Subject).filter(Subject.is_active == True).order_by(Subject.display_order).all()


@router.get("/subjects/{subject_id}", response_model=SubjectFull)
def get_subject(subject_id: int, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id, Subject.is_active == True).first()
    if not subject:
        raise HTTPException(404, "Subject not found")
    return subject


@router.get("/subjects/{subject_id}/sections", response_model=List[SectionWithChapters])
def list_sections(subject_id: int, db: Session = Depends(get_db)):
    return db.query(Section).filter(Section.subject_id == subject_id, Section.is_active == True).order_by(Section.display_order).all()


# ✅ Lightweight — only sections + chapters (no topics)
@router.get("/subjects/{subject_id}/chapters-only")
def get_subject_chapters_only(subject_id: int, db: Session = Depends(get_db)):
    """Fast version — sections + chapters only, NO topics"""
    sections = db.query(Section).filter(
        Section.subject_id == subject_id,
        Section.is_active == True,
    ).order_by(Section.display_order).all()

    result = []
    for sec in sections:
        chapters = db.query(Chapter).filter(
            Chapter.section_id == sec.id,
            Chapter.is_active == True,
        ).order_by(Chapter.display_order).all()
        result.append({
            "id": sec.id,
            "name": sec.name,
            "chapters": [{"id": c.id, "name": c.name} for c in chapters],
        })
    return result


@router.get("/chapters/{chapter_id}")
def get_chapter_light(chapter_id: int, db: Session = Depends(get_db)):
    """Lightweight — chapter name only"""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(404, "Chapter not found")
    return {"id": chapter.id, "name": chapter.name}
