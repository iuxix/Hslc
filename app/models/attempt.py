from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Boolean,
    Numeric,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Attempt(Base):
    """Aggregate result of a test attempt"""

    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(
        Integer,
        ForeignKey("tests.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    score = Column(Integer, default=0)
    total_marks = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    wrong_count = Column(Integer, default=0)
    unanswered_count = Column(Integer, default=0)

    total_time_seconds = Column(Integer, default=0)
    avg_time_per_question = Column(Numeric(6, 2), default=0)
    percentage = Column(Numeric(5, 2), default=0)

    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    test = relationship("Test", back_populates="attempt")
    answers = relationship(
        "Answer",
        back_populates="attempt",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Attempt test={self.test_id} score={self.score}/{self.total_marks}>"


class Answer(Base):
    """Answer to a single question in a test"""

    __tablename__ = "answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(
        Integer,
        ForeignKey("attempts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    test_question_id = Column(
        Integer,
        ForeignKey("test_questions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    selected_option = Column(String(1), nullable=True)  # A/B/C/D or NULL
    is_correct = Column(Boolean, default=False)
    status = Column(String(15), default="unanswered")  # answered, unanswered, skipped

    first_answered_at = Column(DateTime(timezone=True), nullable=True)
    last_answered_at = Column(DateTime(timezone=True), nullable=True)
    answer_change_count = Column(Integer, default=0)
    final_time_spent_seconds = Column(Integer, default=0)

    # Relationships
    attempt = relationship("Attempt", back_populates="answers")
    test_question = relationship("TestQuestion", back_populates="answer")

    def __repr__(self):
        return f"<Answer q={self.test_question_id} sel={self.selected_option}>"


class QuestionTiming(Base):
    """Event log — every open/close of a question"""

    __tablename__ = "question_timing"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(
        Integer,
        ForeignKey("attempts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    test_question_id = Column(
        Integer,
        ForeignKey("test_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    opened_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    seconds_spent = Column(Integer, nullable=True)
    selected_during_visit = Column(String(1), nullable=True)

    def __repr__(self):
        return f"<Timing q={self.test_question_id} {self.seconds_spent}s>"
