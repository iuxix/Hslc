from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional
import hashlib
import re
from app.models.question import Question, QuestionOption
from app.models.curriculum import Chapter, Subject, Section, Topic
from app.schemas.question import QuestionCreate, QuestionUpdate


def _normalize_text(text: str) -> str:
    """Lowercase + remove extra spaces + remove punctuation for hashing"""
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)
    return text


def _generate_content_hash(question_text: str) -> str:
    """SHA-256 hash of normalized question text"""
    return hashlib.sha256(_normalize_text(question_text).encode()).hexdigest()


def _verify_foreign_keys(db: Session, data: QuestionCreate):
    """Verify all foreign keys exist"""
    subject = db.query(Subject).filter(Subject.id == data.subject_id).first()
    if not subject:
        raise HTTPException(400, f"Subject {data.subject_id} not found")

    chapter = db.query(Chapter).filter(Chapter.id == data.chapter_id).first()
    if not chapter:
        raise HTTPException(400, f"Chapter {data.chapter_id} not found")

    if data.section_id:
        section = db.query(Section).filter(Section.id == data.section_id).first()
        if not section:
            raise HTTPException(400, f"Section {data.section_id} not found")

    if data.topic_id:
        topic = db.query(Topic).filter(Topic.id == data.topic_id).first()
        if not topic:
            raise HTTPException(400, f"Topic {data.topic_id} not found")


def _verify_options(data: QuestionCreate):
    """Verify exactly 4 options with labels A, B, C, D"""
    if len(data.options) != 4:
        raise HTTPException(400, "Exactly 4 options required")

    labels = [opt.option_label for opt in data.options]
    if set(labels) != {"A", "B", "C", "D"}:
        raise HTTPException(400, "Options must have labels A, B, C, D")

    if data.correct_option not in labels:
        raise HTTPException(400, "Correct option must match one of the option labels")


def create_question(db: Session, data: QuestionCreate, created_by: Optional[int] = None) -> Question:
    """Create a single question"""

    # Verify FKs
    _verify_foreign_keys(db, data)

    # Verify options
    _verify_options(data)

    # Duplicate check via hash
    content_hash = _generate_content_hash(data.question_text)
    existing = db.query(Question).filter(Question.content_hash == content_hash).first()
    if existing:
        raise HTTPException(400, f"Duplicate question detected (id: {existing.id})")

    # Create question
    question = Question(
        subject_id=data.subject_id,
        section_id=data.section_id,
        chapter_id=data.chapter_id,
        topic_id=data.topic_id,
        question_text=data.question_text,
        correct_option=data.correct_option,
        explanation=data.explanation,
        difficulty=data.difficulty,
        question_type=data.question_type,
        source="manual",
        content_hash=content_hash,
        created_by=created_by,
    )
    db.add(question)
    db.flush()  # get question.id

    # Create options
    for opt in data.options:
        option = QuestionOption(
            question_id=question.id,
            option_label=opt.option_label,
            option_text=opt.option_text,
        )
        db.add(option)

    db.commit()
    db.refresh(question)
    return question


def create_questions_bulk(
    db: Session,
    questions_data: List[QuestionCreate],
    created_by: Optional[int] = None,
) -> dict:
    """Bulk create — skips duplicates, returns stats"""

    created = 0
    failed = 0
    errors = []

    for idx, data in enumerate(questions_data, start=1):
        try:
            _verify_foreign_keys(db, data)
            _verify_options(data)

            content_hash = _generate_content_hash(data.question_text)
            existing = db.query(Question).filter(Question.content_hash == content_hash).first()
            if existing:
                failed += 1
                errors.append(f"Q{idx}: Duplicate")
                continue

            question = Question(
                subject_id=data.subject_id,
                section_id=data.section_id,
                chapter_id=data.chapter_id,
                topic_id=data.topic_id,
                question_text=data.question_text,
                correct_option=data.correct_option,
                explanation=data.explanation,
                difficulty=data.difficulty,
                question_type=data.question_type,
                source="manual",
                content_hash=content_hash,
                created_by=created_by,
            )
            db.add(question)
            db.flush()

            for opt in data.options:
                db.add(QuestionOption(
                    question_id=question.id,
                    option_label=opt.option_label,
                    option_text=opt.option_text,
                ))

            db.commit()
            created += 1

        except HTTPException as e:
            db.rollback()
            failed += 1
            errors.append(f"Q{idx}: {e.detail}")
        except Exception as e:
            db.rollback()
            failed += 1
            errors.append(f"Q{idx}: {str(e)}")

    return {"created": created, "failed": failed, "errors": errors[:20]}


def get_questions(
    db: Session,
    subject_id: Optional[int] = None,
    chapter_id: Optional[int] = None,
    topic_id: Optional[int] = None,
    difficulty: Optional[str] = None,
    source: Optional[str] = None,
    is_active: bool = True,
    skip: int = 0,
    limit: int = 50,
) -> List[Question]:
    """List questions with filters"""
    query = db.query(Question)

    if is_active is not None:
        query = query.filter(Question.is_active == is_active)

    if subject_id:
        query = query.filter(Question.subject_id == subject_id)
    if chapter_id:
        query = query.filter(Question.chapter_id == chapter_id)
    if topic_id:
        query = query.filter(Question.topic_id == topic_id)
    if difficulty:
        query = query.filter(Question.difficulty == difficulty)
    if source:
        query = query.filter(Question.source == source)

    return query.order_by(Question.id.desc()).offset(skip).limit(limit).all()


def get_question(db: Session, question_id: int) -> Question:
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(404, "Question not found")
    return question


def update_question(db: Session, question_id: int, data: QuestionUpdate) -> Question:
    question = get_question(db, question_id)

    update_data = data.model_dump(exclude_unset=True)

    # If question_text is updated, regenerate hash
    if "question_text" in update_data:
        new_hash = _generate_content_hash(update_data["question_text"])
        existing = db.query(Question).filter(
            Question.content_hash == new_hash,
            Question.id != question_id,
        ).first()
        if existing:
            raise HTTPException(400, f"Duplicate question detected (id: {existing.id})")
        update_data["content_hash"] = new_hash

    for key, value in update_data.items():
        setattr(question, key, value)

    db.commit()
    db.refresh(question)
    return question


def delete_question(db: Session, question_id: int) -> None:
    """Hard delete"""
    question = get_question(db, question_id)
    db.delete(question)
    db.commit()


def get_stats(db: Session) -> dict:
    """Question statistics"""
    from sqlalchemy import func

    total = db.query(Question).filter(Question.is_active == True).count()

    # By difficulty
    easy = db.query(Question).filter(
        Question.is_active == True,
        Question.difficulty == "easy",
    ).count()
    hard = db.query(Question).filter(
        Question.is_active == True,
        Question.difficulty == "hard",
    ).count()

    # By source
    manual = db.query(Question).filter(
        Question.is_active == True,
        Question.source == "manual",
    ).count()
    ai = db.query(Question).filter(
        Question.is_active == True,
        Question.source == "ai",
    ).count()

    # By chapter
    chapter_counts = db.query(
        Question.chapter_id,
        func.count(Question.id).label("count"),
    ).filter(Question.is_active == True).group_by(Question.chapter_id).all()

    # Get chapter names
    chapter_stats = []
    for ch_id, count in chapter_counts:
        chapter = db.query(Chapter).filter(Chapter.id == ch_id).first()
        chapter_stats.append({
            "chapter_id": ch_id,
            "chapter_name": chapter.name if chapter else f"Unknown ({ch_id})",
            "count": count,
        })

    return {
        "total": total,
        "easy": easy,
        "hard": hard,
        "manual": manual,
        "ai": ai,
        "by_chapter": chapter_stats,
    }
