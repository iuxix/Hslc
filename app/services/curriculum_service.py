from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List, Optional
from app.models.curriculum import Subject, Section, Chapter, Topic


# ============================================================
# SUBJECT
# ============================================================

def create_subject(db: Session, data) -> Subject:
    # Check duplicate name/code
    if db.query(Subject).filter(Subject.name == data.name).first():
        raise HTTPException(400, f"Subject '{data.name}' already exists")
    if db.query(Subject).filter(Subject.code == data.code).first():
        raise HTTPException(400, f"Subject code '{data.code}' already exists")

    subject = Subject(
        name=data.name,
        code=data.code,
        exam_pattern=data.exam_pattern,
        default_question_count=data.default_question_count,
        default_duration_minutes=data.default_duration_minutes,
        display_order=data.display_order,
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject


def get_all_subjects(db: Session, include_inactive: bool = False) -> List[Subject]:
    query = db.query(Subject)
    if not include_inactive:
        query = query.filter(Subject.is_active == True)
    return query.order_by(Subject.display_order, Subject.name).all()


def get_subject(db: Session, subject_id: int) -> Subject:
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(404, "Subject not found")
    return subject


def update_subject(db: Session, subject_id: int, data) -> Subject:
    subject = get_subject(db, subject_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(subject, key, value)
    db.commit()
    db.refresh(subject)
    return subject


def delete_subject(db: Session, subject_id: int) -> None:
    subject = get_subject(db, subject_id)
    db.delete(subject)
    db.commit()


# ============================================================
# SECTION
# ============================================================

def create_section(db: Session, data) -> Section:
    # Verify subject exists
    get_subject(db, data.subject_id)

    section = Section(
        subject_id=data.subject_id,
        name=data.name,
        display_order=data.display_order,
    )
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


def get_sections_by_subject(db: Session, subject_id: int, include_inactive: bool = False) -> List[Section]:
    query = db.query(Section).filter(Section.subject_id == subject_id)
    if not include_inactive:
        query = query.filter(Section.is_active == True)
    return query.order_by(Section.display_order).all()


def get_section(db: Session, section_id: int) -> Section:
    section = db.query(Section).filter(Section.id == section_id).first()
    if not section:
        raise HTTPException(404, "Section not found")
    return section


def update_section(db: Session, section_id: int, data) -> Section:
    section = get_section(db, section_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(section, key, value)
    db.commit()
    db.refresh(section)
    return section


def delete_section(db: Session, section_id: int) -> None:
    section = get_section(db, section_id)
    db.delete(section)
    db.commit()


# ============================================================
# CHAPTER
# ============================================================

def create_chapter(db: Session, data) -> Chapter:
    # Verify section exists
    get_section(db, data.section_id)

    chapter = Chapter(
        section_id=data.section_id,
        name=data.name,
        display_order=data.display_order,
    )
    db.add(chapter)
    db.commit()
    db.refresh(chapter)
    return chapter


def get_chapters_by_section(db: Session, section_id: int, include_inactive: bool = False) -> List[Chapter]:
    query = db.query(Chapter).filter(Chapter.section_id == section_id)
    if not include_inactive:
        query = query.filter(Chapter.is_active == True)
    return query.order_by(Chapter.display_order).all()


def get_chapter(db: Session, chapter_id: int) -> Chapter:
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(404, "Chapter not found")
    return chapter


def update_chapter(db: Session, chapter_id: int, data) -> Chapter:
    chapter = get_chapter(db, chapter_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(chapter, key, value)
    db.commit()
    db.refresh(chapter)
    return chapter


def delete_chapter(db: Session, chapter_id: int) -> None:
    chapter = get_chapter(db, chapter_id)
    db.delete(chapter)
    db.commit()


# ============================================================
# TOPIC
# ============================================================

def create_topic(db: Session, data) -> Topic:
    get_chapter(db, data.chapter_id)

    topic = Topic(
        chapter_id=data.chapter_id,
        name=data.name,
        display_order=data.display_order,
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return topic


def get_topics_by_chapter(db: Session, chapter_id: int) -> List[Topic]:
    return db.query(Topic).filter(Topic.chapter_id == chapter_id).order_by(Topic.display_order).all()


def get_topic(db: Session, topic_id: int) -> Topic:
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(404, "Topic not found")
    return topic


def update_topic(db: Session, topic_id: int, data) -> Topic:
    topic = get_topic(db, topic_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(topic, key, value)
    db.commit()
    db.refresh(topic)
    return topic


def delete_topic(db: Session, topic_id: int) -> None:
    topic = get_topic(db, topic_id)
    db.delete(topic)
    db.commit()
