from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Literal


# ============================================================
# OPTIONS
# ============================================================

class OptionCreate(BaseModel):
    option_label: Literal["A", "B", "C", "D"]
    option_text: str = Field(..., min_length=1)


class OptionResponse(BaseModel):
    id: int
    option_label: str
    option_text: str

    class Config:
        from_attributes = True


# ============================================================
# QUESTION — CREATE
# ============================================================

class QuestionCreate(BaseModel):
    subject_id: int
    section_id: Optional[int] = None
    chapter_id: int
    topic_id: Optional[int] = None
    question_text: str = Field(..., min_length=5)
    correct_option: Literal["A", "B", "C", "D"]
    explanation: Optional[str] = None
    difficulty: Literal["easy", "hard"] = "easy"
    question_type: Literal["mcq", "hots_mcq", "theory"] = "mcq"
    options: List[OptionCreate] = Field(..., min_length=4, max_length=4)


# ============================================================
# QUESTION — UPDATE
# ============================================================

class QuestionUpdate(BaseModel):
    question_text: Optional[str] = Field(None, min_length=5)
    correct_option: Optional[Literal["A", "B", "C", "D"]] = None
    explanation: Optional[str] = None
    difficulty: Optional[Literal["easy", "hard"]] = None
    topic_id: Optional[int] = None
    is_active: Optional[bool] = None


# ============================================================
# QUESTION — RESPONSE
# ============================================================

class QuestionResponse(BaseModel):
    id: int
    subject_id: int
    section_id: Optional[int] = None
    chapter_id: int
    topic_id: Optional[int] = None
    question_text: str
    correct_option: str
    explanation: Optional[str] = None
    difficulty: str
    question_type: str
    source: str
    is_active: bool
    created_at: datetime
    options: List[OptionResponse] = []

    class Config:
        from_attributes = True


# ============================================================
# QUESTION — FOR EXAM (without correct answer)
# ============================================================

class QuestionExamView(BaseModel):
    """Question view for students during exam — no correct answer"""
    id: int
    question_text: str
    difficulty: str
    chapter_id: int
    topic_id: Optional[int] = None
    options: List[OptionResponse] = []

    class Config:
        from_attributes = True


# ============================================================
# BULK CREATE
# ============================================================

class QuestionBulkCreate(BaseModel):
    questions: List[QuestionCreate] = Field(..., min_length=1, max_length=100)


class BulkCreateResponse(BaseModel):
    created: int
    failed: int
    errors: List[str] = []
