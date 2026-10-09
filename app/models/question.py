from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Text,
    ForeignKey,
    DateTime,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)

    # Foreign keys
    subject_id = Column(
        Integer,
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_id = Column(
        Integer,
        ForeignKey("sections.id", ondelete="SET NULL"),
        nullable=True,
    )
    chapter_id = Column(
        Integer,
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_id = Column(
        Integer,
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Content
    question_text = Column(Text, nullable=False)
    correct_option = Column(String(1), nullable=False)  # A, B, C, D
    explanation = Column(Text, nullable=True)

    # Metadata
    difficulty = Column(String(10), nullable=False, default="easy")  # easy / hard
    question_type = Column(String(20), default="mcq")  # mcq, hots_mcq, theory
    source = Column(String(20), default="manual")  # manual / ai
    ai_model = Column(String(50), nullable=True)

    # Deduplication
    content_hash = Column(String(64), nullable=True, index=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    options = relationship(
        "QuestionOption",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="QuestionOption.option_label",
    )

    def __repr__(self):
        return f"<Question #{self.id} ({self.difficulty})>"


class QuestionOption(Base):
    __tablename__ = "question_options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(
        Integer,
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    option_label = Column(String(1), nullable=False)  # A, B, C, D
    option_text = Column(Text, nullable=False)

    # Unique: one question can't have two A's
    __table_args__ = (
        UniqueConstraint("question_id", "option_label", name="uq_question_option"),
    )

    question = relationship("Question", back_populates="options")

    def __repr__(self):
        return f"<Option {self.option_label}>"
