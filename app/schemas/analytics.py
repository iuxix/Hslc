from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict


# ============================================================
# HISTORY
# ============================================================

class AttemptSummary(BaseModel):
    id: int
    test_id: int
    test_title: str
    exam_type: str
    subject_id: Optional[int] = None
    chapter_id: Optional[int] = None
    score: int
    total_marks: int
    percentage: float
    correct_count: int
    wrong_count: int
    unanswered_count: int
    total_time_seconds: int
    avg_time_per_question: float
    submitted_at: datetime


class HistoryResponse(BaseModel):
    total_tests: int
    average_percentage: float
    best_percentage: float
    average_time_per_question: float
    attempts: List[AttemptSummary]


# ============================================================
# MISTAKES
# ============================================================

class MistakeItem(BaseModel):
    question_id: int
    question_text: str
    subject_id: int
    chapter_id: int
    topic_id: Optional[int] = None
    difficulty: str
    correct_option: str
    your_last_answer: Optional[str] = None
    explanation: Optional[str] = None
    times_wrong: int
    last_wrong_at: datetime


class MistakesResponse(BaseModel):
    total: int
    mistakes: List[MistakeItem]


# ============================================================
# WEAK AREAS
# ============================================================

class WeakChapter(BaseModel):
    chapter_id: int
    chapter_name: str
    total_attempted: int
    correct: int
    accuracy: float


class WeakAreaResponse(BaseModel):
    weakest_chapters: List[WeakChapter]
    strongest_chapters: List[WeakChapter]


# ============================================================
# PROGRESS
# ============================================================

class ProgressPoint(BaseModel):
    attempt_id: int
    percentage: float
    submitted_at: datetime


class ProgressResponse(BaseModel):
    points: List[ProgressPoint]
    trend: str  # improving / declining / stable


# ============================================================
# DASHBOARD STATS
# ============================================================

class DashboardStats(BaseModel):
    total_tests: int
    average_accuracy: float
    best_score: float
    avg_time_per_question: float
    total_time_spent_minutes: int
    total_questions_attempted: int
    total_correct: int
    total_wrong: int
    total_unanswered: int
    streak_days: int
    weak_chapters: List[WeakChapter]


# ============================================================
# LEADERBOARD
# ============================================================

class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    username: str
    full_name: Optional[str] = None
    total_tests: int
    average_percentage: float
    best_percentage: float


class LeaderboardResponse(BaseModel):
    entries: List[LeaderboardEntry]
    user_rank: Optional[int] = None


# ============================================================
# FULL RESULT (already in exam, but here for reference)
# ============================================================

class SubjectBreakdown(BaseModel):
    subject_id: int
    subject_name: str
    total_attempted: int
    correct: int
    accuracy: float
