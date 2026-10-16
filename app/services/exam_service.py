from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func
from fastapi import HTTPException
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import random
from app.models.test import Test, TestQuestion
from app.models.attempt import Attempt, Answer, QuestionTiming
from app.models.question import Question, QuestionOption
from app.schemas.exam import ExamStartRequest
from app.services.analytics_service import clear_user_cache


def _shuffle(arr: list) -> list:
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
    """
    ✅ OPTIMIZED:
    - selectinload(Question.options)  → N+1 options query fix
    - func.random().limit(count)      → SQL-level random, no full table scan
    """
    query = (
        db.query(Question)
        .options(selectinload(Question.options))   # ✅ eager load options
        .filter(
            Question.subject_id == subject_id,
            Question.is_active == True,
        )
    )

    if exam_type == "ai":
        query = query.filter(Question.source == "ai")

    if exam_type in ("chapter", "multi_chapter") and chapter_ids:
        query = query.filter(Question.chapter_id.in_(chapter_ids))

    if exam_type == "ai" and chapter_ids:
        query = query.filter(Question.chapter_id.in_(chapter_ids))

    if difficulty != "mixed":
        query = query.filter(Question.difficulty == difficulty)

    # ✅ SQL-level random + limit
    questions = query.order_by(func.random()).limit(count).all()

    if not questions:
        raise HTTPException(400, "No questions found for this configuration")

    return questions


def start_exam(db: Session, user_id: int, payload: ExamStartRequest) -> dict:
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
    db.flush()

    shuffled_questions = _shuffle(questions)
    test_questions = []

    for idx, q in enumerate(shuffled_questions):
        # ✅ q.options already loaded via selectinload — no extra query
        options = q.options

        if len(options) != 4:
            db.rollback()
            raise HTTPException(500, f"Question {q.id} has invalid options")

        original_labels = [opt.option_label for opt in options]
        shuffled_labels = _shuffle(original_labels)

        tq = TestQuestion(
            test_id=test.id,
            question_id=q.id,
            display_order=idx + 1,
            option_order=shuffled_labels,
        )
        db.add(tq)
        test_questions.append((tq, q, options))

    db.commit()

    from app.schemas.exam import ExamQuestionView, ExamOptionView

    response_questions = []
    for tq, q, options in test_questions:
        opt_map = {opt.option_label: opt.option_text for opt in options}
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
            topic_id=None,
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
    test = _get_active_test(db, user_id, test_id)

    tq = db.query(TestQuestion).filter(
        TestQuestion.id == test_question_id,
        TestQuestion.test_id == test_id,
    ).first()
    if not tq:
        raise HTTPException(404, "Question not part of this test")

    attempt = db.query(Attempt).filter(Attempt.test_id == test_id).first()

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
    _get_active_test(db, user_id, test_id)

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
        timing = QuestionTiming(
            attempt_id=attempt.id,
            test_question_id=test_question_id,
            opened_at=now,
        )
        db.add(timing)
        db.commit()
        return {"test_question_id": test_question_id, "seconds_spent": 0}

    elif event == "close":
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

        answer = db.query(Answer).filter(
            Answer.test_question_id == test_question_id,
        ).first()
        if answer:
            answer.final_time_spent_seconds = (answer.final_time_spent_seconds or 0) + timing.seconds_spent

        db.commit()
        return {"test_question_id": test_question_id, "seconds_spent": timing.seconds_spent}

    raise HTTPException(400, "Invalid event")


def submit_exam(db: Session, user_id: int, test_id: int, auto: bool = False) -> dict:
    test = db.query(Test).filter(
        Test.id == test_id,
        Test.user_id == user_id,
    ).first()
    if not test:
        raise HTTPException(404, "Test not found")

    if test.status == "submitted":
        raise HTTPException(400, "Test already submitted")

    attempt = db.query(Attempt).filter(Attempt.test_id == test_id).first()

    if not attempt:
        attempt = Attempt(
            test_id=test_id,
            user_id=user_id,
            total_marks=test.total_questions,
        )
        db.add(attempt)
        db.flush()

    test_questions = db.query(TestQuestion).filter(
        TestQuestion.test_id == test_id
    ).all()

    correct = 0
    wrong = 0
    unanswered = 0

    for tq in test_questions:
        question = db.query(Question).filter(Question.id == tq.question_id).first()
        answer = db.query(Answer).filter(Answer.test_question_id == tq.id).first()

        if not answer or not answer.selected_option:
            unanswered += 1
            if answer:
                answer.is_correct = False
                answer.status = "unanswered"
            continue

        display_labels = ["A", "B", "C", "D"]
        try:
            display_index = display_labels.index(answer.selected_option)
            original_label = tq.option_order[display_index]
        except (ValueError, IndexError):
            original_label = answer.selected_option

        if original_label == question.correct_option:
            answer.is_correct = True
            answer.status = "answered"
            correct += 1
        else:
            answer.is_correct = False
            answer.status = "answered"
            wrong += 1

    attempt.correct_count = correct
    attempt.wrong_count = wrong
    attempt.unanswered_count = unanswered
    attempt.score = correct
    attempt.total_marks = test.total_questions
    attempt.percentage = round((correct / test.total_questions) * 100, 2) if test.total_questions else 0

    now = datetime.now(timezone.utc)
    total_seconds = int((now - test.started_at).total_seconds())
    attempt.total_time_seconds = total_seconds
    attempt.avg_time_per_question = round(total_seconds / test.total_questions, 2) if test.total_questions else 0
    attempt.submitted_at = now

    test.status = "submitted" if not auto else "expired"
    test.submitted_at = now

    db.commit()
    db.refresh(attempt)

    clear_user_cache(user_id)

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
    test = db.query(Test).filter(
        Test.id == test_id,
        Test.user_id == user_id,
    ).first()
    if not test:
        raise HTTPException(404, "Test not found")

    attempt = db.query(Attempt).filter(Attempt.test_id == test_id).first()
    if not attempt:
        raise HTTPException(404, "No attempt found")

    from sqlalchemy.orm import joinedload
    test_questions = (
        db.query(TestQuestion)
        .options(joinedload(TestQuestion.question))
        .filter(TestQuestion.test_id == test_id)
        .order_by(TestQuestion.display_order)
        .all()
    )

    answers_map = {}
    for ans in db.query(Answer).filter(Answer.attempt_id == attempt.id).all():
        answers_map[ans.test_question_id] = ans

    question_ids = [tq.question_id for tq in test_questions]
    all_options = db.query(QuestionOption).filter(
        QuestionOption.question_id.in_(question_ids)
    ).all()
    options_map = {}
    for opt in all_options:
        options_map.setdefault(opt.question_id, []).append(opt)

    question_results = []

    for tq in test_questions:
        question = tq.question
        answer = answers_map.get(tq.id)
        options_db = options_map.get(question.id, [])

        opt_map = {opt.option_label: opt.option_text for opt in options_db}
        display_labels = ["A", "B", "C", "D"]

        display_options = []
        for display_label, original_label in zip(display_labels, tq.option_order):
            display_options.append({
                "display_label": display_label,
                "original_label": original_label,
                "text": opt_map.get(original_label, ""),
            })

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
            "topic_id": None,
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
    test = db.query(Test).filter(
        Test.id == test_id,
        Test.user_id == user_id,
    ).first()
    if not test:
        raise HTTPException(404, "Test not found")

    if test.status != "in_progress":
        raise HTTPException(400, f"Test is {test.status}, cannot resume")

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
    test = db.query(Test).filter(
        Test.id == test_id,
        Test.user_id == user_id,
    ).first()
    if not test:
        raise HTTPException(404, "Test not found")

    if test.status != "in_progress":
        raise HTTPException(400, f"Test is {test.status}")

    now = datetime.now(timezone.utc)
    if test.expires_at < now:
        test.status = "expired"
        db.commit()
        raise HTTPException(400, "Test has expired")

    return test
