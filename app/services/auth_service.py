from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime
from app.models.user import User
from app.core.security import hash_password, verify_password, create_access_token


def register_user(
    db: Session,
    username: str,
    email: str,
    password: str,
    full_name: str = None,
) -> User:
    """Register a new user"""

    # Check duplicate username
    existing_username = db.query(User).filter(User.username == username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    # Check duplicate email
    existing_email = db.query(User).filter(User.email == email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    new_user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role="student",
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


def authenticate_user(db: Session, username: str, password: str) -> User:
    """Login — verify credentials"""

    user = db.query(User).filter(User.username == username).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Update last_login
    user.last_login = datetime.utcnow()
    db.commit()
    db.refresh(user)

    return user


def create_token_for_user(user: User) -> str:
    """Create JWT token for a user"""
    token_data = {
        "sub": str(user.id),
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
    }
    return create_access_token(token_data)
