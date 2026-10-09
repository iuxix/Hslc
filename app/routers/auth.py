from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    UserResponse,
    TokenResponse,
)
from app.services.auth_service import (
    register_user,
    authenticate_user,
    create_token_for_user,
)
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user"""
    user = register_user(
        db=db,
        username=payload.username,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
    )

    token = create_token_for_user(user)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Login with username and password"""
    user = authenticate_user(db, payload.username, payload.password)
    token = create_token_for_user(user)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Get current logged-in user's info"""
    return UserResponse.model_validate(current_user)
