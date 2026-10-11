import json
import re
import hashlib
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException
from google import genai

from app.config import settings
from app.models.curriculum import Chapter, Section, Subject, Topic
from app.models.question import Question, QuestionOption


# ============================================================
# GEMINI CLIENT
# ============================================================

def _get_client():
    return genai.Client(api_key=settings.GEMINI_API_KEY)


MODEL_NAME = "gemini-3.5-flash-lite"


# ============================================================
# HASH FOR DEDUP
# ============================================================

def _normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text


def _content_hash(question_text: str) -> str:
    return hashlib.sha256(_normalize_text(question_text).encode()).hexdigest()


# ============================================================
# PROMPT BUILDER
# ============================================================

def _build_prompt(
    subject_name: str,
    section_name: Optional[str],
    chapter_name: str,
    difficulty: str,
    count: int,
    material: Optional[str],
) -> str:
    context_parts = [
        f"Subject: {subject_name}",
    ]
    if section_name:
        context_parts.append(f"Section: {section_name}")
    context_parts.append(f"Chapter: {chapter_name}")
    context_parts.append(f"Difficulty: {difficulty}")
    context_parts.append(f"Generate exactly {count} MCQ questions.")

    context = "\n".join(context_parts)

    material_block = ""
    if material:
        material_block = f"\n\nStudy Material (primary source):\n{material}"

    prompt = f"""You are an expert question generator for SEBA HSLC Class 10 exam training.

{context}{material_block}

RULES:
- Each question must have EXACTLY 4 options labeled A, B, C, D.
- Exactly one option is correct.
- Include a short explanation for each answer.
- Difficulty must be "{difficulty}".
- Generate UNIQUE questions (no duplicates).
- If study material is provided, base questions STRICTLY on it.
- If no material, use standard SEBA HSLC Class 10 syllabus knowledge.

Return ONLY a valid JSON array. No markdown, no extra text.

Format:
[
  {{
    "question": "What is the SI unit of resistance?",
    "options": {{"A": "Volt", "B": "Ampere", "C": "Ohm", "D": "Watt"}},
    "correct": "C",
    "explanation": "Resistance is measured in Ohm (Ω).",
    "difficulty": "{difficulty}"
  }}
]
"""
    return prompt


# ============================================================
# GEMINI CALL
# ============================================================

def _call_gemini(prompt: str) -> str:
    try:
        client = _get_client()
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )
        return response.text or ""
    except Exception as e:
        raise HTTPException(500, f"Gemini call failed: {str(e)}")


def _parse_json_response(text: str) -> List[dict]:
    """Strip markdown, parse JSON"""
    text = text.strip()

    # Remove markdown code blocks
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    # Find first [ and last ]
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("No JSON array found")

    json_str = text[start : end + 1]
    return json.loads(json_str)


# ============================================================
# VALIDATION
# ============================================================

def _validate_question(q: dict) -> Optional[dict]:
    """Return cleaned question dict or None if invalid"""

    if not isinstance(q, dict):
        return None

    question_text = (q.get("question") or "").strip()
    if len(question_text) < 5:
        return None

    options = q.get("options") or {}
    if not isinstance(options, dict):
        return None

    # Must have exactly A, B, C, D
    labels = set(options.keys())
    if labels != {"A", "B", "C", "D"}:
        return None

    for label in ["A", "B", "C", "D"]:
        if not isinstance(options[label], str) or not options[label].strip():
            return None

    correct = (q.get("correct") or "").strip().upper()
    if correct not in ["A", "B", "C", "D"]:
        return None

    difficulty = (q.get("difficulty") or "easy").strip().lower()
    if difficulty not in ["easy", "hard"]:
        difficulty = "easy"

    explanation = (q.get("explanation") or "").strip() or None

    return {
        "question_text": question_text,
        "options": {k: options[k].strip() for k in ["A", "B", "C", "D"]},
        "correct_option": correct,
        "difficulty": difficulty,
        "explanation": explanation,
    }


def _is_duplicate(db: Session, content_hash: str) -> bool:
    return db.query(Question).filter(Question.content_hash == content_hash).first() is not None


# ============================================================
# MAIN GENERATION
# ============================================================

def generate_questions(
    db: Session,
    chapter_id: int,
    difficulty: str,
    count: int,
    material: Optional[str],
    created_by: int,
    max_retries: int = 2,
) -> dict:
    """Generate questions via Gemini and save to database"""

    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(404, "Chapter not found")

    section = db.query(Section).filter(Section.id == chapter.section_id).first()
    if not section:
        raise HTTPException(404, "Section not found")

    subject = db.query(Subject).filter(Subject.id == section.subject_id).first()
    if not subject:
        raise HTTPException(404, "Subject not found")

    # If no material passed, use existing study material (future)
    # For now, generate without material

    total_created = 0
    total_skipped = 0
    generated_questions = []
    errors = []

    remaining = count
    attempt = 0

    while remaining > 0 and attempt <= max_retries:
        attempt += 1

        # Slightly over-request to compensate for duplicates/invalid
        request_count = min(remaining + 3, 20)

        prompt = _build_prompt(
            subject_name=subject.name,
            section_name=section.name,
            chapter_name=chapter.name,
            difficulty=difficulty,
            count=request_count,
            material=material,
        )

        try:
            raw = _call_gemini(prompt)
            parsed = _parse_json_response(raw)
        except Exception as e:
            errors.append(f"Attempt {attempt}: {str(e)}")
            continue

        for item in parsed:
            if remaining <= 0:
                break

            cleaned = _validate_question(item)
            if not cleaned:
                total_skipped += 1
                continue

            content_hash = _content_hash(cleaned["question_text"])
            if _is_duplicate(db, content_hash):
                total_skipped += 1
                continue

            # Also check current batch
            already = False
            for gq in generated_questions:
                if gq["content_hash"] == content_hash:
                    already = True
                    break
            if already:
                total_skipped += 1
                continue

            # Create
            question = Question(
                subject_id=subject.id,
                section_id=section.id,
                chapter_id=chapter.id,
                topic_id=None,
                question_text=cleaned["question_text"],
                correct_option=cleaned["correct_option"],
                explanation=cleaned["explanation"],
                difficulty=cleaned["difficulty"],
                question_type="mcq",
                source="ai",
                ai_model=MODEL_NAME,
                content_hash=content_hash,
                created_by=created_by,
            )
            db.add(question)
            db.flush()

            for label in ["A", "B", "C", "D"]:
                db.add(QuestionOption(
                    question_id=question.id,
                    option_label=label,
                    option_text=cleaned["options"][label],
                ))

            db.commit()
            db.refresh(question)

            generated_questions.append({
                "id": question.id,
                "content_hash": content_hash,
                "question": question.question_text,
            })
            total_created += 1
            remaining -= 1

    return {
        "status": "success" if total_created > 0 else "failed",
        "created": total_created,
        "skipped": total_skipped,
        "errors": errors,
        "questions": generated_questions,
    }
