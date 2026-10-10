from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    JSON,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Test(Base):
    """A test instance created for a student"""

    __tablename__ = "tests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id = Column(
        Integer,
        ForeignKey("subjects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Config
    test_type = Column(String(30), nullable=False)  # full_mcq, chapter, multi_chapter, etc.
    config_json = Column(JSON, nullable=True)  # {chapter_ids: [1,2], difficulty: "mixed"}

    total_questions = Column(Integer, nullable=False)
    duration_minutes = Column(Integer, nullable=False)

    # Status
    status = Column(String(15), nullable=False, default="in_progress")
    # in_progress, submitted, expired, abandoned

    # Timing
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User")
    questions = relationship(
        "TestQuestion",
        back_populates="test",
        cascade="all, delete-orphan",
        order_by="TestQuestion.display_order",
    )
    attempt = relationship(
        "Attempt",
        back_populates="test",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Test #{self.id} user={self.user_id} {self.test_type}>"


class TestQuestion(Base):
    """Questions belonging to a test (with randomized order)"""

    __tablename__ = "test_questions"

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(
        Integer,
        ForeignKey("tests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id = Column(
        Integer,
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    display_order = Column(Integer, nullable=False)
    option_order = Column(JSON, nullable=False)  # e.g. ["C", "A", "D", "B"]

    __table_args__ = (
        UniqueConstraint("test_id", "display_order", name="uq_test_display_order"),
    )

    # Relationships
    test = relationship("Test", back_populates="questions")
    question = relationship("Question")
    answer = relationship(
        "Answer",
        back_populates="test_question",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<TestQuestion test={self.test_id} Q={self.question_id}>"
