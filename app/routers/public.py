from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
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


@router.get("/chapters/{chapter_id}", response_model=ChapterWithTopics)
def get_chapter(chapter_id: int, db: Session = Depends(get_db)):
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id, Chapter.is_active == True).first()
    if not chapter:
        raise HTTPException(404, "Chapter not found")
    return chapter
