from pydantic import BaseModel, Field
from typing import Optional, List


class AIGenerateRequest(BaseModel):
    chapter_id: int
    difficulty: str = Field("easy", pattern="^(easy|hard)$")
    count: int = Field(10, ge=1, le=20)
    material: Optional[str] = None


class AIGeneratedQuestion(BaseModel):
    id: int
    question: str


class AIGenerateResponse(BaseModel):
    status: str
    created: int
    skipped: int
    errors: List[str] = []
    questions: List[AIGeneratedQuestion] = []


class AIModelsResponse(BaseModel):
    model: str
    status: str
