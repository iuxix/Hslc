from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Literal


# ============================================================
# START EXAM
# ============================================================

class ExamStartRequest(BaseModel):
    exam_type: Literal["full", "chapter", "multi_chapter", "subject", "practice", "mistake"]
    subject_id: int
    chapter_ids: Optional[List[int]] = None  # for chapter/multi_chapter
    difficulty: Literal["mixed", "easy", "hard"] = "mixed"
    count: int = Field(45, ge=1, le=100)
    duration_minutes: int = Field(60, ge=1, le=180)


class ExamStartResponse(BaseModel):
    test_id: int
    exam_type: str
    total_questions: int
    duration_minutes: int
    started_at: datetime
    expires_at: datetime
    questions: List["ExamQuestionView"]


class ExamQuestionView(BaseModel):
    """Question as seen during exam — no correct answer revealed"""
    test_question_id: int
    question_id: int
    display_order: int
    question_text: str
    difficulty: str
    chapter_id: int
    topic_id: Optional[int] = None
    options: List["ExamOptionView"]


class ExamOptionView(BaseModel):
    option_label: str  # shuffled label (A/B/C/D as displayed)
    option_text: str
    original_label: str  # original label for internal tracking


# ============================================================
# ANSWER SAVE
# ============================================================

class AnswerSaveRequest(BaseModel):
    test_question_id: int
    selected_option: Optional[str] = None  # A/B/C/D or None to clear


class AnswerSaveResponse(BaseModel):
    test_question_id: int
    selected_option: Optional[str] = None
    status: str  # answered / unanswered / skipped
    answer_change_count: int


# ============================================================
# TIMING EVENT
# ============================================================

class TimingEventRequest(BaseModel):
    test_question_id: int
    event: Literal["open", "close"]
    selected_during_visit: Optional[str] = None


class TimingEventResponse(BaseModel):
    test_question_id: int
    seconds_spent: int


# ============================================================
# SUBMIT
# ============================================================

class ExamSubmitResponse(BaseModel):
    attempt_id: int
    test_id: int
    score: int
    total_marks: int
    correct_count: int
    wrong_count: int
    unanswered_count: int
    percentage: float
    total_time_seconds: int
    avg_time_per_question: float


# ============================================================
# RESULT
# ============================================================

class QuestionResult(BaseModel):
    test_question_id: int
    question_id: int
    question_text: str
    difficulty: str
    chapter_id: int
    topic_id: Optional[int] = None
    selected_option: Optional[str] = None
    correct_option: str
    is_correct: bool
    time_spent_seconds: int
    explanation: Optional[str] = None
    options: List[dict] = []


class ExamResultResponse(BaseModel):
    attempt_id: int
    test_id: int
    user_id: int
    score: int
    total_marks: int
    correct_count: int
    wrong_count: int
    unanswered_count: int
    percentage: float
    total_time_seconds: int
    avg_time_per_question: float
    submitted_at: datetime
    questions: List[QuestionResult]


# ============================================================
# CURRENT STATE (for resume)
# ============================================================

class ExamStateResponse(BaseModel):
    test_id: int
    status: str
    remaining_seconds: int
    current_question_index: int
    answers: dict  # {test_question_id: selected_option}
    marked: List[int]  # test_question_ids marked


ExamStartResponse.model_rebuild()
ExamQuestionView.model_rebuild()
