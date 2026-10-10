from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import random
import hashlib
from app.models.test import Test, TestQuestion
from app.models.attempt import Attempt, Answer, QuestionTiming
from app.models.question import Question, QuestionOption
from app.models.curriculum import Chapter
from app.schemas.exam import ExamStartRequest


def _shuffle(arr: list) -> list:
    """Fisher-Yates shuffle"""
    a = arr[:]
    for i in range(len(a) - 1, 0, -1):
        j = random.randint(0, i)
        a[i], a[j] = a[j], a[i]
    return a


def _select_questions(
    db: Session,
    exam_type: str,
    subject_id: int,
    chapter_ids: Optional[List[int]],
    difficulty: str,
    count: int,
) -> List[Question]:
    """Select questions based on config"""

    query = db.query(Question).filter(
        Question.subject_id == subject_id,
        Question.is_active == True,
    )

    # Chapter filter
    if exam_type in ("chapter", "multi_chapter") and chapter_ids:
        query = query.filter(Question.chapter_id.in_(chapter_ids))

    # Difficulty filter
    if difficulty != "mixed":
        query = query.filter(Question.difficulty == difficulty)

    all_matching = query.all()

    if not all_matching:
        raise HTTPException(400, "No questions found for this configuration")

    # If we have more questions than needed → random sample
    if len(all_matching) >= count:
        return random.sample(all_matching, count)

    # If fewer → return all (with warning to user)
    return all_matching


def start_exam(db: Session, user_id: int, payload: ExamStartRequest) -> dict:
    """Create a new test, pick questions, randomize order"""

    questions = _select_questions(
        db=db,
        exam_type=payload.exam_type,
        subject_id=payload.subject_id,
        chapter_ids=payload.chapter_ids,
        difficulty=payload.difficulty,
        count=payload.count,
    )

    if not questions:
        raise HTTPException(400, "No questions available")

    total_q = len(questions)

    # Create test
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=payload.duration_minutes)

    test = Test(
        user_id=user_id,
        subject_id=payload.subject_id,
        test_type=payload.exam_type,
        config_json={
            "subject_id": payload.subject_id,
            "chapter_ids": payload.chapter_ids,
            "difficulty": payload.difficulty,
            "count": total_q,
        },
        total_questions=total_q,
        duration_minutes=payload.duration_minutes,
        status="in_progress",
        started_at=now,
        expires_at=expires,
    )
    db.add(test)
    db.flush()  # get test.id

    # Shuffle questions
    shuffled_questions = _shuffle(questions)

    # Create TestQuestion entries
    test_questions = []
    for idx, q in enumerate(shuffled_questions):
        # Get options and shuffle their order
        options = db.query(QuestionOption).filter(
            QuestionOption.question_id == q.id
        ).all()

        if len(options) != 4:
            db.rollback()
            raise HTTPException(500, f"Question {q.id} has invalid options")

        # Original labels: A, B, C, D
        original_labels = [opt.option_label for opt in options]
        # Shuffle and re-map to A, B, C, D display
        shuffled_labels = _shuffle(original_labels)

        tq = TestQuestion(
            test_id=test.id,
            question_id=q.id,
            display_order=idx + 1,
            option_order=shuffled_labels,  # ["C", "A", "D", "B"]
        )
        db.add(tq)
        test_questions.append((tq, q, options))

    db.commit()

    # Build response with shuffled options
    from app.schemas.exam import ExamQuestionView, ExamOptionView

    response_questions = []
    for tq, q, options in test_questions:
        # Map original label → text
        opt_map = {opt.option_label: opt.option_text for opt in options}

        # Shuffled display: A, B, C, D → original labels
        display_labels = ["A", "B", "C", "D"]
        shuffled_options = []
        for display_label, original_label in zip(display_labels, tq.option_order):
            shuffled_options.append(ExamOptionView(
                option_label=display_label,
                option_text=opt_map[original_label],
                original_label=original_label,
            ))

        response_questions.append(ExamQuestionView(
            test_question_id=tq.id,
            question_id=q.id,
            display_order=tq.display_order,
            question_text=q.question_text,
            difficulty=q.difficulty,
            chapter_id=q.chapter_id,
            topic_id=q.topic_id,
            options=shuffled_options,
        ))

    return {
        "test_id": test.id,
        "exam_type": test.test_type,
        "total_questions": test.total_questions,
        "duration_minutes": test.duration_minutes,
        "started_at": test.started_at,
        "expires_at": test.expires_at,
        "questions": response_questions,
    }


def save_answer(
    db: Session,
    user_id: int,
    test_id: int,
    test_question_id: int,
    selected_option: Optional[str],
) -> dict:
    """Save or update an answer"""

    test = _get_active_test(db, user_id, test_id)

    # Get test question
    tq = db.query(TestQuestion).filter(
        TestQuestion.id == test_question_id,
        TestQuestion.test_id == test_id,
    ).first()
    if not tq:
        raise HTTPException(404, "Question not part of this test")

    # Find or create Answer row
    attempt = db.query(Attempt).filter(Attempt.test_id == test_id).first()

    # Attempt not created yet — create it on first answer
    if not attempt:
        attempt = Attempt(
            test_id=test_id,
            user_id=user_id,
            total_marks=test.total_questions,
        )
        db.add(attempt)
        db.flush()

    answer = db.query(Answer).filter(
        Answer.test_question_id == test_question_id,
    ).first()

    now = datetime.now(timezone.utc)

    if not answer:
        answer = Answer(
            attempt_id=attempt.id,
            test_question_id=test_question_id,
            selected_option=selected_option,
            status="answered" if selected_option else "unanswered",
            first_answered_at=now if selected_option else None,
            last_answered_at=now if selected_option else None,
            answer_change_count=0,
        )
        db.add(answer)
    else:
        # Answer changed
        if answer.selected_option != selected_option:
            answer.answer_change_count += 1
            answer.selected_option = selected_option
            answer.last_answered_at = now
            answer.status = "answered" if selected_option else "unanswered"

    db.commit()
    db.refresh(answer)

    return {
        "test_question_id": test_question_id,
        "selected_option": answer.selected_option,
        "status": answer.status,
        "answer_change_count": answer.answer_change_count,
    }


def record_timing(
    db: Session,
    user_id: int,
    test_id: int,
    test_question_id: int,
    event: str,
    selected_during_visit: Optional[str] = None,
) -> dict:
    """Record question open/close event"""

    _get_active_test(db, user_id, test_id)

    # Ensure attempt exists
    attempt = db.query(Attempt).filter(Attempt.test_id == test_id).first()
    if not attempt:
        attempt = Attempt(
            test_id=test_id,
            user_id=user_id,
            total_marks=0,
        )
        db.add(attempt)
        db.flush()

    now = datetime.now(timezone.utc)

    if event == "open":
        # Create new timing entry
        timing = QuestionTiming(
            attempt_id=attempt.id,
            test_question_id=test_question_id,
            opened_at=now,
        )
        db.add(timing)
        db.commit()
        return {"test_question_id": test_question_id, "seconds_spent": 0}

    elif event == "close":
        # Find latest open entry
        timing = db.query(QuestionTiming).filter(
            QuestionTiming.attempt_id == attempt.id,
            QuestionTiming.test_question_id == test_question_id,
            QuestionTiming.closed_at.is_(None),
        ).order_by(QuestionTiming.opened_at.desc()).first()

        if not timing:
            return {"test_question_id": test_question_id, "seconds_spent": 0}

        timing.closed_at = now
        delta = (now - timing.opened_at).total_seconds()
        timing.seconds_spent = int(delta)
        timing.selected_during_visit = selected_during_visit

        # Update answer's final_time_spent
        answer = db.query(Answer).filter(
            Answer.test_question_id == test_question_id,
        ).first()
        if answer:
            answer.final_time_spent_seconds = (answer.final_time_spent_seconds or 0) + timing.seconds_spent

        db.commit()
        return {"test_question_id": test_question_id, "seconds_spent": timing.seconds_spent}

    raise HTTPException(400, "Invalid event")


def submit_exam(db: Session, user_id: int, test_id: int, auto: bool = False) -> dict:
    """Submit test — calculate score"""

    test = db.query(Test).filter(
        Test.id == test_id,
        Test.user_id == user_id,
    ).first()
    if not test:
        raise HTTPException(404, "Test not found")

    if test.status == "submitted":
        raise HTTPException(400, "Test already submitted")

    attempt = db.query(Attempt).filter(Attempt.test_id == test_id).first()

    # If no attempt yet (student never answered anything)
    if not attempt:
        attempt = Attempt(
            test_id=test_id,
            user_id=user_id,
            total_marks=test.total_questions,
        )
        db.add(attempt)
        db.flush()

    # Score calculation
    test_questions = db.query(TestQuestion).filter(
        TestQuestion.test_id == test_id
    ).all()

    correct = 0
    wrong = 0
    unanswered = 0

    for tq in test_questions:
        # Get question and its correct option
        question = db.query(Question).filter(Question.id == tq.question_id).first()

        # Find answer
        answer = db.query(Answer).filter(Answer.test_question_id == tq.id).first()

        if not answer or not answer.selected_option:
            unanswered += 1
            if answer:
                answer.is_correct = False
                answer.status = "unanswered"
            continue

        # Display label → original label mapping
        display_labels = ["A", "B", "C", "D"]
        try:
            display_index = display_labels.index(answer.selected_option)
            original_label = tq.option_order[display_index]
        except (ValueError, IndexError):
            original_label = answer.selected_option

        # Compare with correct_option (original)
        if original_label == question.correct_option:
            answer.is_correct = True
            answer.status = "answered"
            correct += 1
        else:
            answer.is_correct = False
            answer.status = "answered"
            wrong += 1

    # Update attempt
    attempt.correct_count = correct
    attempt.wrong_count = wrong
    attempt.unanswered_count = unanswered
    attempt.score = correct
    attempt.total_marks = test.total_questions
    attempt.percentage = round((correct / test.total_questions) * 100, 2) if test.total_questions else 0

    # Time
    now = datetime.now(timezone.utc)
    total_seconds = int((now - test.started_at).total_seconds())
    attempt.total_time_seconds = total_seconds
    attempt.avg_time_per_question = round(total_seconds / test.total_questions, 2) if test.total_questions else 0
    attempt.submitted_at = now

    test.status = "submitted" if not auto else "expired"
    test.submitted_at = now

    db.commit()
    db.refresh(attempt)

    return {
        "attempt_id": attempt.id,
        "test_id": test_id,
        "score": attempt.score,
        "total_marks": attempt.total_marks,
        "correct_count": attempt.correct_count,
        "wrong_count": attempt.wrong_count,
        "unanswered_count": attempt.unanswered_count,
        "percentage": float(attempt.percentage),
        "total_time_seconds": attempt.total_time_seconds,
        "avg_time_per_question": float(attempt.avg_time_per_question),
    }


def get_result(db: Session, user_id: int, test_id: int) -> dict:
    """Full result with question-wise breakdown"""

    test = db.query(Test).filter(
        Test.id == test_id,
        Test.user_id == user_id,
    ).first()
    if not test:
        raise HTTPException(404, "Test not found")

    attempt = db.query(Attempt).filter(Attempt.test_id == test_id).first()
    if not attempt:
        raise HTTPException(404, "No attempt found")

    test_questions = db.query(TestQuestion).filter(
        TestQuestion.test_id == test_id
    ).order_by(TestQuestion.display_order).all()

    question_results = []

    for tq in test_questions:
        question = db.query(Question).filter(Question.id == tq.question_id).first()
        answer = db.query(Answer).filter(Answer.test_question_id == tq.id).first()

        # Options (with display order)
        options_db = db.query(QuestionOption).filter(
            QuestionOption.question_id == question.id
        ).all()
        opt_map = {opt.option_label: opt.option_text for opt in options_db}
        display_labels = ["A", "B", "C", "D"]

        display_options = []
        for display_label, original_label in zip(display_labels, tq.option_order):
            display_options.append({
                "display_label": display_label,
                "original_label": original_label,
                "text": opt_map.get(original_label, ""),
            })

        # Correct display label
        correct_display = None
        for i, orig in enumerate(tq.option_order):
            if orig == question.correct_option:
                correct_display = display_labels[i]
                break

        question_results.append({
            "test_question_id": tq.id,
            "question_id": question.id,
            "question_text": question.question_text,
            "difficulty": question.difficulty,
            "chapter_id": question.chapter_id,
            "topic_id": question.topic_id,
            "selected_option": answer.selected_option if answer else None,
            "correct_option": correct_display or question.correct_option,
            "is_correct": answer.is_correct if answer else False,
            "time_spent_seconds": answer.final_time_spent_seconds if answer else 0,
            "explanation": question.explanation,
            "options": display_options,
        })

    return {
        "attempt_id": attempt.id,
        "test_id": test_id,
        "user_id": user_id,
        "score": attempt.score,
        "total_marks": attempt.total_marks,
        "correct_count": attempt.correct_count,
        "wrong_count": attempt.wrong_count,
        "unanswered_count": attempt.unanswered_count,
        "percentage": float(attempt.percentage),
        "total_time_seconds": attempt.total_time_seconds,
        "avg_time_per_question": float(attempt.avg_time_per_question),
        "submitted_at": attempt.submitted_at,
        "questions": question_results,
    }


def get_exam_state(db: Session, user_id: int, test_id: int) -> dict:
    """Get current state — for resume"""

    test = db.query(Test).filter(
        Test.id == test_id,
        Test.user_id == user_id,
    ).first()
    if not test:
        raise HTTPException(404, "Test not found")

    if test.status != "in_progress":
        raise HTTPException(400, f"Test is {test.status}, cannot resume")

    # Remaining time
    now = datetime.now(timezone.utc)
    remaining = int((test.expires_at - now).total_seconds())
    if remaining < 0:
        remaining = 0

    attempt = db.query(Attempt).filter(Attempt.test_id == test_id).first()

    answers = {}
    if attempt:
        answer_rows = db.query(Answer).filter(Answer.attempt_id == attempt.id).all()
        for a in answer_rows:
            answers[a.test_question_id] = a.selected_option

    return {
        "test_id": test_id,
        "status": test.status,
        "remaining_seconds": remaining,
        "current_question_index": 0,
        "answers": answers,
        "marked": [],
    }


def _get_active_test(db: Session, user_id: int, test_id: int) -> Test:
    """Get test and verify it's active and not expired"""
    test = db.query(Test).filter(
        Test.id == test_id,
        Test.user_id == user_id,
    ).first()
    if not test:
        raise HTTPException(404, "Test not found")

    if test.status != "in_progress":
        raise HTTPException(400, f"Test is {test.status}")

    # Check expiry
    now = datetime.now(timezone.utc)
    if test.expires_at < now:
        # Auto-expire
        test.status = "expired"
        db.commit()
        raise HTTPException(400, "Test has expired")

    return test
