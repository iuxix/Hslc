from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.analytics import (
    HistoryResponse,
    MistakesResponse,
    WeakAreaResponse,
    ProgressResponse,
    DashboardStats,
    LeaderboardResponse,
)
from app.services import analytics_service as svc

router = APIRouter(
    prefix="/api/student",
    tags=["Student — Analytics"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/dashboard", response_model=DashboardStats)
def dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get dashboard stats"""
    return svc.get_dashboard(db, current_user.id)


@router.get("/history", response_model=HistoryResponse)
def history(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get test history"""
    return svc.get_history(db, current_user.id, limit)


@router.get("/mistakes", response_model=MistakesResponse)
def mistakes(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all wrong answers"""
    return svc.get_mistakes(db, current_user.id, limit)


@router.get("/weak-areas", response_model=WeakAreaResponse)
def weak_areas(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get weakest & strongest chapters"""
    return svc.get_weak_areas(db, current_user.id)


@router.get("/progress", response_model=ProgressResponse)
def progress(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get score progression"""
    return svc.get_progress(db, current_user.id, limit)


@router.get("/leaderboard", response_model=LeaderboardResponse)
def leaderboard(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get top users"""
    return svc.get_leaderboard(db, current_user.id, limit)
