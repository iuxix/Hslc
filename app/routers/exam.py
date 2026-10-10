from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.exam import (
    ExamStartRequest,
    ExamStartResponse,
    ExamStateResponse,
    AnswerSaveRequest,
    AnswerSaveResponse,
    TimingEventRequest,
    TimingEventResponse,
    ExamSubmitResponse,
    ExamResultResponse,
)
from app.services import exam_service as svc

router = APIRouter(
    prefix="/api/exam",
    tags=["Exam"],
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# START EXAM
# ============================================================

@router.post("/start", response_model=ExamStartResponse, status_code=status.HTTP_201_CREATED)
def start_exam(
    payload: ExamStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a new exam"""
    return svc.start_exam(db, current_user.id, payload)


# ============================================================
# CURRENT STATE (RESUME)
# ============================================================

@router.get("/{test_id}/state", response_model=ExamStateResponse)
def get_state(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current state of an in-progress test"""
    return svc.get_exam_state(db, current_user.id, test_id)


# ============================================================
# SAVE ANSWER
# ============================================================

@router.post("/{test_id}/answer", response_model=AnswerSaveResponse)
def save_answer(
    test_id: int,
    payload: AnswerSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save or update an answer"""
    return svc.save_answer(
        db=db,
        user_id=current_user.id,
        test_id=test_id,
        test_question_id=payload.test_question_id,
        selected_option=payload.selected_option,
    )


# ============================================================
# TIMING EVENT
# ============================================================

@router.post("/{test_id}/timing", response_model=TimingEventResponse)
def record_timing(
    test_id: int,
    payload: TimingEventRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record question open/close for timing"""
    return svc.record_timing(
        db=db,
        user_id=current_user.id,
        test_id=test_id,
        test_question_id=payload.test_question_id,
        event=payload.event,
        selected_during_visit=payload.selected_during_visit,
    )


# ============================================================
# SUBMIT
# ============================================================

@router.post("/{test_id}/submit", response_model=ExamSubmitResponse)
def submit_exam(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit test and calculate score"""
    return svc.submit_exam(db, current_user.id, test_id, auto=False)


# ============================================================
# RESULT
# ============================================================

@router.get("/{test_id}/result", response_model=ExamResultResponse)
def get_result(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get full result with question-wise breakdown"""
    return svc.get_result(db, current_user.id, test_id)
