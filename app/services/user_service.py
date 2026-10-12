from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List
from app.models.user import User
from app.models.test import Test
from app.models.attempt import Attempt, Answer, QuestionTiming


def get_all_users(db: Session, include_inactive: bool = False) -> List[User]:
    query = db.query(User)
    if not include_inactive:
        query = query.filter(User.is_active == True)
    return query.order_by(User.created_at.desc()).all()


def get_user_by_id(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    return user


def delete_user(db: Session, user_id: int, current_admin: User) -> None:
    if user_id == current_admin.id:
        raise HTTPException(400, "Cannot delete your own account")

    user = get_user_by_id(db, user_id)

    if user.role == "admin":
        raise HTTPException(400, "Cannot delete another admin")

    db.delete(user)
    db.commit()


def deactivate_user(db: Session, user_id: int, current_admin: User) -> User:
    if user_id == current_admin.id:
        raise HTTPException(400, "Cannot deactivate your own account")

    user = get_user_by_id(db, user_id)
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user


def activate_user(db: Session, user_id: int) -> User:
    user = get_user_by_id(db, user_id)
    user.is_active = True
    db.commit()
    db.refresh(user)
    return user


# ============================================================
# RESET USER DATA
# ============================================================

def reset_user_data(db: Session, user_id: int, current_admin: User) -> dict:
    """
    Delete all test attempts, answers, and timing records for a user.
    User account stays — only progress resets.
    """
    user = get_user_by_id(db, user_id)

    # Safety: don't reset yourself
    if user.id == current_admin.id:
        raise HTTPException(400, "Cannot reset your own data")

    # Get all attempts for the user
    attempts = db.query(Attempt).filter(Attempt.user_id == user_id).all()
    attempt_ids = [a.id for a in attempts]

    # Count before delete
    total_attempts = len(attempt_ids)
    total_answers = 0
    total_timings = 0

    if attempt_ids:
        total_answers = db.query(Answer).filter(Answer.attempt_id.in_(attempt_ids)).count()
        total_timings = db.query(QuestionTiming).filter(QuestionTiming.attempt_id.in_(attempt_ids)).count()

    # Delete attempts (cascade should delete answers + timings)
    if attempt_ids:
        # Explicit delete for safety
        db.query(QuestionTiming).filter(QuestionTiming.attempt_id.in_(attempt_ids)).delete(synchronize_session=False)
        db.query(Answer).filter(Answer.attempt_id.in_(attempt_ids)).delete(synchronize_session=False)
        db.query(Attempt).filter(Attempt.id.in_(attempt_ids)).delete(synchronize_session=False)

    # Get all tests for the user (in_progress, submitted, expired)
    tests = db.query(Test).filter(Test.user_id == user_id).all()
    total_tests = len(tests)

    if tests:
        # Delete test_questions first (cascade)
        from app.models.test import TestQuestion
        test_ids = [t.id for t in tests]
        db.query(TestQuestion).filter(TestQuestion.test_id.in_(test_ids)).delete(synchronize_session=False)
        db.query(Test).filter(Test.id.in_(test_ids)).delete(synchronize_session=False)

    db.commit()

    return {
        "message": f"Reset complete for user {user.username}",
        "user_id": user_id,
        "username": user.username,
        "deleted": {
            "tests": total_tests,
            "attempts": total_attempts,
            "answers": total_answers,
            "timings": total_timings,
        },
    }
