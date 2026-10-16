from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.curriculum import Subject, Section, Chapter, Topic
from app.schemas.curriculum import (
    SubjectCreate,
    SubjectUpdate,
    SubjectResponse,
    SubjectFull,
    SectionCreate,
    SectionUpdate,
    SectionResponse,
    SectionWithChapters,
    ChapterCreate,
    ChapterUpdate,
    ChapterResponse,
    ChapterWithTopics,
    TopicCreate,
    TopicUpdate,
    TopicResponse,
    MessageResponse,
)
from app.services import curriculum_service as svc


router = APIRouter(
    prefix="/api/admin",
    tags=["Admin — Curriculum"],
    dependencies=[Depends(get_current_admin)],
)


# ============================================================
# LIGHTWEIGHT ENDPOINTS (for admin panel speed)
# ============================================================

@router.get("/curriculum-light")
def get_curriculum_light(db: Session = Depends(get_db)):
    """
    Full curriculum tree in ONE call — subjects + sections + chapters (no topics).
    Much faster than multiple calls.
    """
    subjects = db.query(Subject).filter(
        Subject.is_active == True
    ).order_by(Subject.display_order).all()

    result = []
    for subj in subjects:
        sections = db.query(Section).filter(
            Section.subject_id == subj.id,
            Section.is_active == True,
        ).order_by(Section.display_order).all()

        sections_data = []
        for sec in sections:
            chapters = db.query(Chapter).filter(
                Chapter.section_id == sec.id,
                Chapter.is_active == True,
            ).order_by(Chapter.display_order).all()

            sections_data.append({
                "id": sec.id,
                "name": sec.name,
                "chapters": [
                    {"id": c.id, "name": c.name}
                    for c in chapters
                ],
            })

        result.append({
            "id": subj.id,
            "name": subj.name,
            "code": subj.code,
            "exam_pattern": subj.exam_pattern,
            "sections": sections_data,
        })

    return result


@router.get("/questions-count")
def get_questions_count(db: Session = Depends(get_db)):
    """
    Admin stats — questions count per subject and per chapter.
    """
    from app.models.question import Question
    from sqlalchemy import func

    # Total by subject
    subject_counts = db.query(
        Question.subject_id,
        func.count(Question.id).label("count"),
    ).filter(Question.is_active == True).group_by(Question.subject_id).all()

    # Total by chapter
    chapter_counts = db.query(
        Question.chapter_id,
        func.count(Question.id).label("count"),
    ).filter(Question.is_active == True).group_by(Question.chapter_id).all()

    # Build subject-wise response
    subjects = db.query(Subject).order_by(Subject.display_order).all()

    subject_stats = []
    for subj in subjects:
        # Subject total
        subj_count = next(
            (int(c.count) for c in subject_counts if c.subject_id == subj.id),
            0,
        )

        # Chapter-wise within this subject
        chapters_data = []
        sections = db.query(Section).filter(Section.subject_id == subj.id).all()
        for sec in sections:
            chapters = db.query(Chapter).filter(Chapter.section_id == sec.id).all()
            for ch in chapters:
                ch_count = next(
                    (int(c.count) for c in chapter_counts if c.chapter_id == ch.id),
                    0,
                )
                chapters_data.append({
                    "chapter_id": ch.id,
                    "chapter_name": ch.name,
                    "section_name": sec.name,
                    "count": ch_count,
                })

        subject_stats.append({
            "subject_id": subj.id,
            "subject_name": subj.name,
            "subject_code": subj.code,
            "total_questions": subj_count,
            "chapters": chapters_data,
        })

    return {
        "total_questions": sum(int(c.count) for c in subject_counts),
        "subjects": subject_stats,
    }


# ============================================================
# SUBJECTS
# ============================================================

@router.get("/subjects", response_model=List[SubjectResponse])
def list_subjects(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    return svc.get_all_subjects(db, include_inactive)


@router.post("/subjects", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
def create_subject(data: SubjectCreate, db: Session = Depends(get_db)):
    return svc.create_subject(db, data)


@router.get("/subjects/{subject_id}", response_model=SubjectFull)
def get_subject(subject_id: int, db: Session = Depends(get_db)):
    return svc.get_subject(db, subject_id)


@router.put("/subjects/{subject_id}", response_model=SubjectResponse)
def update_subject(subject_id: int, data: SubjectUpdate, db: Session = Depends(get_db)):
    return svc.update_subject(db, subject_id, data)


@router.delete("/subjects/{subject_id}", response_model=MessageResponse)
def delete_subject(subject_id: int, db: Session = Depends(get_db)):
    svc.delete_subject(db, subject_id)
    return {"message": "Subject deleted successfully"}


# ============================================================
# SECTIONS
# ============================================================

@router.get("/subjects/{subject_id}/sections", response_model=List[SectionResponse])
def list_sections(
    subject_id: int,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    return svc.get_sections_by_subject(db, subject_id, include_inactive)


@router.post("/sections", response_model=SectionResponse, status_code=status.HTTP_201_CREATED)
def create_section(data: SectionCreate, db: Session = Depends(get_db)):
    return svc.create_section(db, data)


@router.put("/sections/{section_id}", response_model=SectionResponse)
def update_section(section_id: int, data: SectionUpdate, db: Session = Depends(get_db)):
    return svc.update_section(db, section_id, data)


@router.delete("/sections/{section_id}", response_model=MessageResponse)
def delete_section(section_id: int, db: Session = Depends(get_db)):
    svc.delete_section(db, section_id)
    return {"message": "Section deleted successfully"}


# ============================================================
# CHAPTERS
# ============================================================

@router.get("/sections/{section_id}/chapters", response_model=List[ChapterResponse])
def list_chapters(
    section_id: int,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    return svc.get_chapters_by_section(db, section_id, include_inactive)


@router.post("/chapters", response_model=ChapterResponse, status_code=status.HTTP_201_CREATED)
def create_chapter(data: ChapterCreate, db: Session = Depends(get_db)):
    return svc.create_chapter(db, data)


@router.get("/chapters/{chapter_id}", response_model=ChapterWithTopics)
def get_chapter(chapter_id: int, db: Session = Depends(get_db)):
    return svc.get_chapter(db, chapter_id)


@router.put("/chapters/{chapter_id}", response_model=ChapterResponse)
def update_chapter(chapter_id: int, data: ChapterUpdate, db: Session = Depends(get_db)):
    return svc.update_chapter(db, chapter_id, data)


@router.delete("/chapters/{chapter_id}", response_model=MessageResponse)
def delete_chapter(chapter_id: int, db: Session = Depends(get_db)):
    svc.delete_chapter(db, chapter_id)
    return {"message": "Chapter deleted successfully"}


# ============================================================
# TOPICS
# ============================================================

@router.get("/chapters/{chapter_id}/topics", response_model=List[TopicResponse])
def list_topics(chapter_id: int, db: Session = Depends(get_db)):
    return svc.get_topics_by_chapter(db, chapter_id)


@router.post("/topics", response_model=TopicResponse, status_code=status.HTTP_201_CREATED)
def create_topic(data: TopicCreate, db: Session = Depends(get_db)):
    return svc.create_topic(db, data)


@router.put("/topics/{topic_id}", response_model=TopicResponse)
def update_topic(topic_id: int, data: TopicUpdate, db: Session = Depends(get_db)):
    return svc.update_topic(db, topic_id, data)


@router.delete("/topics/{topic_id}", response_model=MessageResponse)
def delete_topic(topic_id: int, db: Session = Depends(get_db)):
    svc.delete_topic(db, topic_id)
    return {"message": "Topic deleted successfully"}
