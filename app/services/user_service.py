from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List
from app.models.user import User


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
