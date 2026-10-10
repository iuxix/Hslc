from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from fastapi import HTTPException
from typing import List, Optional, Dict
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from app.models.test import Test, TestQuestion
from app.models.attempt import Attempt, Answer
from app.models.question import Question
from app.models.curriculum import Chapter, Subject
from app.models.user import User


# ============================================================
# HISTORY
# ============================================================

def get_history(db: Session, user_id: int, limit: int = 50) -> dict:
    """All test attempts by user"""

    attempts = db.query(Attempt).filter(
        Attempt.user_id == user_id
    ).order_by(desc(Attempt.submitted_at)).limit(limit).all()

    if not attempts:
        return {
            "total_tests": 0,
            "average_percentage": 0,
            "best_percentage": 0,
            "average_time_per_question": 0,
            "attempts": [],
        }

    # Stats
    percentages = [float(a.percentage) for a in attempts]
    avg_pct = round(sum(percentages) / len(percentages), 2)
    best_pct = round(max(percentages), 2)
    avg_time = round(
        sum(float(a.avg_time_per_question) for a in attempts) / len(attempts), 2
    )

    attempt_list = []
    for a in attempts:
        test = db.query(Test).filter(Test.id == a.test_id).first()
        config = test.config_json or {} if test else {}

        # Test title
        if test and test.test_type == "chapter":
            ch = db.query(Chapter).filter(Chapter.id == config.get("chapter_ids", [None])[0]).first() if config.get("chapter_ids") else None
            title = f"Chapter: {ch.name}" if ch else "Chapter Test"
        elif test and test.test_type == "full":
            title = "Full MCQ Test"
        elif test and test.test_type == "subject":
            subj = db.query(Subject).filter(Subject.id == test.subject_id).first()
            title = f"Full {subj.name} Test" if subj else "Subject Test"
        else:
            title = "Test"

        attempt_list.append({
            "id": a.id,
            "test_id": a.test_id,
            "test_title": title,
            "exam_type": test.test_type if test else "unknown",
            "subject_id": test.subject_id if test else None,
            "chapter_id": (config.get("chapter_ids") or [None])[0] if config else None,
            "score": a.score,
            "total_marks": a.total_marks,
            "percentage": float(a.percentage),
            "correct_count": a.correct_count,
            "wrong_count": a.wrong_count,
            "unanswered_count": a.unanswered_count,
            "total_time_seconds": a.total_time_seconds,
            "avg_time_per_question": float(a.avg_time_per_question),
            "submitted_at": a.submitted_at,
        })

    return {
        "total_tests": len(attempts),
        "average_percentage": avg_pct,
        "best_percentage": best_pct,
        "average_time_per_question": avg_time,
        "attempts": attempt_list,
    }


# ============================================================
# MISTAKES
# ============================================================

def get_mistakes(db: Session, user_id: int, limit: int = 100) -> dict:
    """Get all wrong answers with details"""

    # Get all wrong answers
    wrong_answers = db.query(Answer).join(Attempt).filter(
        Attempt.user_id == user_id,
        Answer.is_correct == False,
        Answer.selected_option.isnot(None),
    ).order_by(desc(Answer.last_answered_at)).all()

    # Deduplicate by question
    seen = {}
    for ans in wrong_answers:
        tq = db.query(TestQuestion).filter(TestQuestion.id == ans.test_question_id).first()
        if not tq:
            continue
        qid = tq.question_id
        if qid in seen:
            seen[qid]["times_wrong"] += 1
        else:
            question = db.query(Question).filter(Question.id == qid).first()
            if not question:
                continue

            # Original label mapping
            display_labels = ["A", "B", "C", "D"]
            try:
                idx = display_labels.index(ans.selected_option)
                original = tq.option_order[idx]
            except (ValueError, IndexError):
                original = ans.selected_option

            seen[qid] = {
                "question_id": qid,
                "question_text": question.question_text,
                "subject_id": question.subject_id,
                "chapter_id": question.chapter_id,
                "topic_id": question.topic_id,
                "difficulty": question.difficulty,
                "correct_option": question.correct_option,
                "your_last_answer": original,
                "explanation": question.explanation,
                "times_wrong": 1,
                "last_wrong_at": ans.last_answered_at or ans.first_answered_at or datetime.now(timezone.utc),
            }

    mistakes = list(seen.values())[:limit]
    return {"total": len(mistakes), "mistakes": mistakes}


# ============================================================
# WEAK AREAS
# ============================================================

def get_weak_areas(db: Session, user_id: int, min_attempts: int = 1) -> dict:
    """Chapter-wise accuracy → weakest & strongest"""

    # All answers by user
    answers = db.query(Answer).join(Attempt).filter(
        Attempt.user_id == user_id,
    ).all()

    chapter_stats = defaultdict(lambda: {"correct": 0, "total": 0})

    for ans in answers:
        tq = db.query(TestQuestion).filter(TestQuestion.id == ans.test_question_id).first()
        if not tq:
            continue
        question = db.query(Question).filter(Question.id == tq.question_id).first()
        if not question:
            continue

        ch_id = question.chapter_id
        chapter_stats[ch_id]["total"] += 1
        if ans.is_correct:
            chapter_stats[ch_id]["correct"] += 1

    # Build list
    chapters_list = []
    for ch_id, stats in chapter_stats.items():
        if stats["total"] < min_attempts:
            continue
        chapter = db.query(Chapter).filter(Chapter.id == ch_id).first()
        chapters_list.append({
            "chapter_id": ch_id,
            "chapter_name": chapter.name if chapter else f"Chapter {ch_id}",
            "total_attempted": stats["total"],
            "correct": stats["correct"],
            "accuracy": round((stats["correct"] / stats["total"]) * 100, 2),
        })

    # Sort
    chapters_list.sort(key=lambda x: x["accuracy"])
    weakest = chapters_list[:5]
    strongest = list(reversed(chapters_list[-5:]))

    return {
        "weakest_chapters": weakest,
        "strongest_chapters": strongest,
    }


# ============================================================
# PROGRESS
# ============================================================

def get_progress(db: Session, user_id: int, limit: int = 20) -> dict:
    """Score progression over time"""

    attempts = db.query(Attempt).filter(
        Attempt.user_id == user_id
    ).order_by(Attempt.submitted_at).limit(limit).all()

    points = [
        {
            "attempt_id": a.id,
            "percentage": float(a.percentage),
            "submitted_at": a.submitted_at,
        }
        for a in attempts
    ]

    # Trend
    trend = "stable"
    if len(points) >= 4:
        first_half = sum(p["percentage"] for p in points[:len(points)//2]) / (len(points)//2)
        second_half = sum(p["percentage"] for p in points[len(points)//2:]) / (len(points) - len(points)//2)
        diff = second_half - first_half
        if diff > 5:
            trend = "improving"
        elif diff < -5:
            trend = "declining"

    return {"points": points, "trend": trend}


# ============================================================
# DASHBOARD
# ============================================================

def get_dashboard(db: Session, user_id: int) -> dict:
    """Aggregate stats for dashboard"""

    attempts = db.query(Attempt).filter(Attempt.user_id == user_id).all()

    if not attempts:
        return {
            "total_tests": 0,
            "average_accuracy": 0,
            "best_score": 0,
            "avg_time_per_question": 0,
            "total_time_spent_minutes": 0,
            "total_questions_attempted": 0,
            "total_correct": 0,
            "total_wrong": 0,
            "total_unanswered": 0,
            "streak_days": 0,
            "weak_chapters": [],
        }

    total_tests = len(attempts)
    avg_acc = round(sum(float(a.percentage) for a in attempts) / total_tests, 2)
    best = round(max(float(a.percentage) for a in attempts), 2)
    avg_time = round(sum(float(a.avg_time_per_question) for a in attempts) / total_tests, 2)
    total_time_min = round(sum(a.total_time_seconds for a in attempts) / 60, 1)

    total_correct = sum(a.correct_count for a in attempts)
    total_wrong = sum(a.wrong_count for a in attempts)
    total_unanswered = sum(a.unanswered_count for a in attempts)
    total_q = total_correct + total_wrong + total_unanswered

    # Streak — consecutive days
    streak = _calculate_streak(attempts)

    # Weak chapters
    weak_data = get_weak_areas(db, user_id)
    weak_chapters = weak_data["weakest_chapters"][:3]

    return {
        "total_tests": total_tests,
        "average_accuracy": avg_acc,
        "best_score": best,
        "avg_time_per_question": avg_time,
        "total_time_spent_minutes": int(total_time_min),
        "total_questions_attempted": total_q,
        "total_correct": total_correct,
        "total_wrong": total_wrong,
        "total_unanswered": total_unanswered,
        "streak_days": streak,
        "weak_chapters": weak_chapters,
    }


def _calculate_streak(attempts) -> int:
    """Consecutive days with at least one test (ending today)"""
    if not attempts:
        return 0

    dates = sorted({a.submitted_at.date() for a in attempts if a.submitted_at}, reverse=True)
    if not dates:
        return 0

    today = datetime.now(timezone.utc).date()
    streak = 0

    # Latest date must be today or yesterday
    if dates[0] not in [today, today - timedelta(days=1)]:
        return 0

    expected = dates[0]
    for d in dates:
        if d == expected:
            streak += 1
            expected = d - timedelta(days=1)
        else:
            break

    return streak


# ============================================================
# LEADERBOARD
# ============================================================

def get_leaderboard(db: Session, user_id: int, limit: int = 20) -> dict:
    """Top users by average percentage"""

    # Aggregate per user
    user_stats = db.query(
        Attempt.user_id,
        func.count(Attempt.id).label("tests"),
        func.avg(Attempt.percentage).label("avg_pct"),
        func.max(Attempt.percentage).label("best_pct"),
    ).group_by(Attempt.user_id).all()

    if not user_stats:
        return {"entries": [], "user_rank": None}

    # Sort by avg_pct descending
    sorted_stats = sorted(user_stats, key=lambda x: float(x.avg_pct or 0), reverse=True)

    entries = []
    user_rank = None

    for idx, stat in enumerate(sorted_stats[:limit], start=1):
        user = db.query(User).filter(User.id == stat.user_id).first()
        entries.append({
            "rank": idx,
            "user_id": stat.user_id,
            "username": user.username if user else "unknown",
            "full_name": user.full_name if user else None,
            "total_tests": stat.tests,
            "average_percentage": round(float(stat.avg_pct or 0), 2),
            "best_percentage": round(float(stat.best_pct or 0), 2),
        })
        if stat.user_id == user_id:
            user_rank = idx

    # If user not in top, find their rank
    if user_rank is None:
        for idx, stat in enumerate(sorted_stats, start=1):
            if stat.user_id == user_id:
                user_rank = idx
                break

    return {"entries": entries, "user_rank": user_rank}
