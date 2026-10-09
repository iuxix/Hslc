from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.schemas.user import (
    UserAdminView,
    UserRoleUpdate,
    UserCreateAdmin,
    MessageResponse,
)
from app.services import user_service as svc
from app.services.auth_service import register_user_admin

router = APIRouter(
    prefix="/api/admin/users",
    tags=["Admin — Users"],
    dependencies=[Depends(get_current_admin)],
)


@router.post("", response_model=UserAdminView, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreateAdmin, db: Session = Depends(get_db)):
    """Admin creates a new user"""
    return register_user_admin(
        db=db,
        username=data.username,
        email=data.email,
        password=data.password,
        full_name=data.full_name,
        role=data.role,
    )


@router.get("", response_model=List[UserAdminView])
def list_users(include_inactive: bool = False, db: Session = Depends(get_db)):
    return svc.get_all_users(db, include_inactive)


@router.get("/{user_id}", response_model=UserAdminView)
def get_user(user_id: int, db: Session = Depends(get_db)):
    return svc.get_user_by_id(db, user_id)


@router.patch("/{user_id}/role", response_model=UserAdminView)
def change_role(
    user_id: int,
    data: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    if data.role not in ["student", "admin"]:
        raise HTTPException(400, "Role must be 'student' or 'admin'")

    if user_id == current_admin.id:
        raise HTTPException(400, "Cannot change your own role")

    user = svc.get_user_by_id(db, user_id)
    user.role = data.role
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/deactivate", response_model=UserAdminView)
def deactivate(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    return svc.deactivate_user(db, user_id, current_admin)


@router.patch("/{user_id}/activate", response_model=UserAdminView)
def activate(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    return svc.activate_user(db, user_id)


@router.delete("/{user_id}", response_model=MessageResponse)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    svc.delete_user(db, user_id, current_admin)
    return {"message": f"User {user_id} deleted permanently"}
