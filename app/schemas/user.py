from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, Literal


class UserCreateAdmin(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)
    full_name: Optional[str] = Field(None, max_length=100)
    role: Literal["student", "admin"] = "student"


class UserAdminView(BaseModel):
    id: int
    username: str
    email: str
    role: str
    full_name: Optional[str] = None
    class_level: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserRoleUpdate(BaseModel):
    role: Literal["student", "admin"]


class MessageResponse(BaseModel):
    message: str
