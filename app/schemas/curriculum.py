from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


# ============================================================
# TOPIC
# ============================================================

class TopicCreate(BaseModel):
    chapter_id: int
    name: str = Field(..., min_length=1, max_length=200)
    display_order: int = 0


class TopicUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    display_order: Optional[int] = None


class TopicResponse(BaseModel):
    id: int
    chapter_id: int
    name: str
    display_order: int
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# CHAPTER
# ============================================================

class ChapterCreate(BaseModel):
    section_id: int
    name: str = Field(..., min_length=1, max_length=200)
    display_order: int = 0


class ChapterUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class ChapterResponse(BaseModel):
    id: int
    section_id: int
    name: str
    display_order: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ChapterWithTopics(ChapterResponse):
    topics: List[TopicResponse] = []


# ============================================================
# SECTION
# ============================================================

class SectionCreate(BaseModel):
    subject_id: int
    name: str = Field(..., min_length=1, max_length=100)
    display_order: int = 0


class SectionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class SectionResponse(BaseModel):
    id: int
    subject_id: int
    name: str
    display_order: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SectionWithChapters(SectionResponse):
    chapters: List[ChapterResponse] = []


# ============================================================
# SUBJECT
# ============================================================

class SubjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)
    exam_pattern: str = "standard_45"
    default_question_count: int = 45
    default_duration_minutes: int = 60
    display_order: int = 0


class SubjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    exam_pattern: Optional[str] = None
    default_question_count: Optional[int] = None
    default_duration_minutes: Optional[int] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


class SubjectResponse(BaseModel):
    id: int
    name: str
    code: str
    exam_pattern: str
    default_question_count: int
    default_duration_minutes: int
    is_active: bool
    display_order: int
    created_at: datetime

    class Config:
        from_attributes = True


class SubjectFull(SubjectResponse):
    sections: List[SectionWithChapters] = []


# ============================================================
# MESSAGE
# ============================================================

class MessageResponse(BaseModel):
    message: str
