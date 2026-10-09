from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime
from app.models.user import User
from app.core.security import hash_password, verify_password, create_access_token


def register_user_admin(
    db: Session,
    username: str,
    email: str,
    password: str,
    full_name: str = None,
    role: str = "student",
) -> User:
    """Admin-only: register a new user"""

    if db.query(User).filter(User.username == username).first():
        raise HTTPException(400, "Username already taken")

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "Email already registered")

    if role not in ["student", "admin"]:
        raise HTTPException(400, "Role must be 'student' or 'admin'")

    new_user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
        is_active=True,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def authenticate_user(db: Session, username: str, password: str) -> User:
    user = db.query(User).filter(User.username == username).first()

    if not user:
        raise HTTPException(401, "Invalid username or password")

    if not verify_password(password, user.password_hash):
        raise HTTPException(401, "Invalid username or password")

    if not user.is_active:
        raise HTTPException(403, "Account is disabled. Contact admin.")

    user.last_login = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user


def create_token_for_user(user: User) -> str:
    return create_access_token({
        "sub": str(user.id),
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
    })
