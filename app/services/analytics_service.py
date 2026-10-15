from sqlalchemy.orm import Session, joinedload
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
# SIMPLE IN-MEMORY CACHE
# ============================================================

_cache = {}
CACHE_TTL = 300  # 5 minutes


def _get_cached(key: str):
    if key in _cache:
        data, expiry = _cache[key]
        if datetime.now(timezone.utc) < expiry:
            return data
        del _cache[key]
    return None


def _set_cached(key: str, data):
    _cache[key] = (data, datetime.now(timezone.utc) + timedelta(seconds=CACHE_TTL))


def clear_user_cache(user_id: int):
    """Call this after submit/reset to invalidate cache"""
    keys_to_remove = [k for k in _cache.keys() if str(user_id) in k]
    for k in keys_to_remove:
        del _cache[k]


# ============================================================
# HISTORY — with pagination
# ============================================================

def get_history(db: Session, user_id: int, limit: int = 20, skip: int = 0) -> dict:
    """Get user's test history with pagination"""

    # Count total
    total_count = db.query(func.count(Attempt.id)).filter(
        Attempt.user_id == user_id
    ).scalar()

    # Get paginated attempts with joined test (single query — no N+1)
    attempts = (
        db.query(Attempt)
        .options(joinedload(Attempt.test))
        .filter(Attempt.user_id == user_id)
        .order_by(desc(Attempt.submitted_at))
        .offset(skip)
        .limit(limit)
        .all()
    )

    if not attempts:
        return {
            "total_tests": total_count,
            "average_percentage": 0,
            "best_percentage": 0,
            "average_time_per_question": 0,
            "attempts": [],
            "has_more": False,
        }

    # Stats from ALL attempts (not just paginated) — separate query
    all_stats = db.query(
        func.avg(Attempt.percentage).label("avg_pct"),
        func.max(Attempt.percentage).label("best_pct"),
        func.avg(Attempt.avg_time_per_question).label("avg_time"),
    ).filter(Attempt.user_id == user_id).first()

    avg_pct = round(float(all_stats.avg_pct or 0), 2)
    best_pct = round(float(all_stats.best_pct or 0), 2)
    avg_time = round(float(all_stats.avg_time or 0), 2)

    # Build attempt list — use joined test
    attempt_list = []
    for a in attempts:
        test = a.test  # ← Already loaded via joinedload — no query!
        config = test.config_json or {} if test else {}

        # Determine title
        if test and test.test_type == "chapter":
            ch_id = (config.get("chapter_ids") or [None])[0]
            ch = db.query(Chapter).filter(Chapter.id == ch_id).first() if ch_id else None
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
        "total_tests": total_count,
        "average_percentage": avg_pct,
        "best_percentage": best_pct,
        "average_time_per_question": avg_time,
        "attempts": attempt_list,
        "has_more": skip + limit < total_count,
    }


# ============================================================
# MISTAKES
# ============================================================

def get_mistakes(db: Session, user_id: int, limit: int = 100) -> dict:
    """Get all wrong answers — optimized with single query"""

    wrong_answers = (
        db.query(Answer)
        .join(Attempt, Answer.attempt_id == Attempt.id)
        .options(joinedload(Answer.test_question).joinedload(TestQuestion.question))
        .filter(
            Attempt.user_id == user_id,
            Answer.is_correct == False,
            Answer.selected_option.isnot(None),
        )
        .order_by(desc(Answer.last_answered_at))
        .all()
    )

    seen = {}
    for ans in wrong_answers:
        tq = ans.test_question  # Already loaded
        if not tq:
            continue

        question = tq.question  # Already loaded
        if not question:
            continue

        qid = question.id
        if qid in seen:
            seen[qid]["times_wrong"] += 1
        else:
            # Map display → original label
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
# WEAK AREAS — optimized
# ============================================================

def get_weak_areas(db: Session, user_id: int, min_attempts: int = 1) -> dict:
    """Chapter-wise accuracy — single query with joins"""

    # Get all answers with chapter_id in one query
    rows = (
        db.query(
            Question.chapter_id,
            Answer.is_correct,
        )
        .join(TestQuestion, Answer.test_question_id == TestQuestion.id)
        .join(Question, TestQuestion.question_id == Question.id)
        .join(Attempt, Answer.attempt_id == Attempt.id)
        .filter(Attempt.user_id == user_id)
        .all()
    )

    chapter_stats = defaultdict(lambda: {"correct": 0, "total": 0})
    for ch_id, is_correct in rows:
        chapter_stats[ch_id]["total"] += 1
        if is_correct:
            chapter_stats[ch_id]["correct"] += 1

    # Get all chapter names in one query
    chapter_ids = list(chapter_stats.keys())
    chapters = db.query(Chapter).filter(Chapter.id.in_(chapter_ids)).all() if chapter_ids else []
    chapter_names = {c.id: c.name for c in chapters}

    chapters_list = []
    for ch_id, stats in chapter_stats.items():
        if stats["total"] < min_attempts:
            continue
        chapters_list.append({
            "chapter_id": ch_id,
            "chapter_name": chapter_names.get(ch_id, f"Chapter {ch_id}"),
            "total_attempted": stats["total"],
            "correct": stats["correct"],
            "accuracy": round((stats["correct"] / stats["total"]) * 100, 2),
        })

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
    attempts = (
        db.query(Attempt)
        .filter(Attempt.user_id == user_id)
        .order_by(Attempt.submitted_at)
        .limit(limit)
        .all()
    )

    points = [
        {
            "attempt_id": a.id,
            "percentage": float(a.percentage),
            "submitted_at": a.submitted_at,
        }
        for a in attempts
    ]

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
# DASHBOARD — with cache
# ============================================================

def get_dashboard(db: Session, user_id: int) -> dict:
    # Cache check
    cache_key = f"dashboard_{user_id}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    attempts_count = db.query(func.count(Attempt.id)).filter(
        Attempt.user_id == user_id
    ).scalar()

    if attempts_count == 0:
        result = {
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
        _set_cached(cache_key, result)
        return result

    # Aggregate stats — single query
    agg = db.query(
        func.avg(Attempt.percentage).label("avg_acc"),
        func.max(Attempt.percentage).label("best"),
        func.avg(Attempt.avg_time_per_question).label("avg_time"),
        func.sum(Attempt.total_time_seconds).label("total_time"),
        func.sum(Attempt.correct_count).label("correct"),
        func.sum(Attempt.wrong_count).label("wrong"),
        func.sum(Attempt.unanswered_count).label("unanswered"),
    ).filter(Attempt.user_id == user_id).first()

    total_correct = int(agg.correct or 0)
    total_wrong = int(agg.wrong or 0)
    total_unanswered = int(agg.unanswered or 0)

    # Streak — one query
    streak = _get_streak(db, user_id)

    # Weak chapters
    weak_data = get_weak_areas(db, user_id)
    weak_chapters = weak_data["weakest_chapters"][:3]

    result = {
        "total_tests": attempts_count,
        "average_accuracy": round(float(agg.avg_acc or 0), 2),
        "best_score": round(float(agg.best or 0), 2),
        "avg_time_per_question": round(float(agg.avg_time or 0), 2),
        "total_time_spent_minutes": int((agg.total_time or 0) / 60),
        "total_questions_attempted": total_correct + total_wrong + total_unanswered,
        "total_correct": total_correct,
        "total_wrong": total_wrong,
        "total_unanswered": total_unanswered,
        "streak_days": streak,
        "weak_chapters": weak_chapters,
    }

    _set_cached(cache_key, result)
    return result


def _get_streak(db: Session, user_id: int) -> int:
    # Get distinct dates
    dates = db.query(func.date(Attempt.submitted_at)).filter(
        Attempt.user_id == user_id
    ).distinct().all()

    if not dates:
        return 0

    date_list = sorted({d[0] for d in dates if d[0]}, reverse=True)
    if not date_list:
        return 0

    today = datetime.now(timezone.utc).date()
    if date_list[0] not in [today, today - timedelta(days=1)]:
        return 0

    streak = 0
    expected = date_list[0]
    for d in date_list:
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
    # Single query for user stats
    user_stats = db.query(
        Attempt.user_id,
        func.count(Attempt.id).label("tests"),
        func.avg(Attempt.percentage).label("avg_pct"),
        func.max(Attempt.percentage).label("best_pct"),
    ).group_by(Attempt.user_id).all()

    if not user_stats:
        return {"entries": [], "user_rank": None}

    sorted_stats = sorted(user_stats, key=lambda x: float(x.avg_pct or 0), reverse=True)

    # Get user names in one query
    user_ids = [s.user_id for s in sorted_stats[:limit]]
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    users_map = {u.id: u for u in users}

    entries = []
    user_rank = None

    for idx, stat in enumerate(sorted_stats[:limit], start=1):
        user = users_map.get(stat.user_id)
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

    if user_rank is None:
        for idx, stat in enumerate(sorted_stats, start=1):
            if stat.user_id == user_id:
                user_rank = idx
                break

    return {"entries": entries, "user_rank": user_rank}
