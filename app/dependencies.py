from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from cachetools import TTLCache
from app.database import get_db
from app.models.user import User
from app.core.security import decode_access_token

security = HTTPBearer()

# ✅ Sirf primitives store karo, ORM object nahi
user_cache = TTLCache(maxsize=1000, ttl=60)


def _serialize_user(user: User) -> dict:
    """User ko dict mein convert — detached-safe"""
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "is_active": user.is_active,
    }


class CachedUser:
    """User jaisa object, but detached-safe"""
    def __init__(self, data: dict):
        self.id = data["id"]
        self.username = data["username"]
        self.role = data["role"]
        self.is_active = data["is_active"]


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """Get current user from JWT token (cached safely)"""

    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    cached = user_cache.get(user_id)
    if cached is not None:
        return CachedUser(cached)

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    user_cache[user_id] = _serialize_user(user)
    return CachedUser(user_cache[user_id])


def get_current_admin(current_user=Depends(get_current_user)):
    """Require admin role"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
