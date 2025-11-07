from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовый класс для всех моделей"""
    pass


class User(Base):
    """Пользователь бота"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(default=False, nullable=False)
    interval_minutes: Mapped[int] = mapped_column(default=30, nullable=False)
    do_not_disturb_until: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    word_progress: Mapped[list["UserWordProgress"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    task_history: Mapped[list["TaskHistory"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, is_active={self.is_active})>"


class Word(Base):
    """Английское слово для изучения"""
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    word_en: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    word_ru: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)

    # Relationships
    user_progress: Mapped[list["UserWordProgress"]] = relationship(back_populates="word", cascade="all, delete-orphan")
    task_history: Mapped[list["TaskHistory"]] = relationship(back_populates="word")

    def __repr__(self) -> str:
        return f"<Word(id={self.id}, word_en='{self.word_en}', word_ru='{self.word_ru}')>"


class UserWordProgress(Base):
    """Прогресс пользователя по конкретному слову"""
    __tablename__ = "user_word_progress"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_percent: Mapped[int] = mapped_column(default=0, nullable=False)
    last_reviewed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    next_review_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False, index=True)
    correct_answers_count: Mapped[int] = mapped_column(default=0, nullable=False)
    total_answers_count: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="word_progress")
    word: Mapped["Word"] = relationship(back_populates="user_progress")

    def __repr__(self) -> str:
        return f"<UserWordProgress(user_id={self.user_id}, word_id={self.word_id}, knowledge={self.knowledge_percent}%)>"


class TaskHistory(Base):
    """История заданий и ответов пользователя"""
    __tablename__ = "task_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)  # translation_to_en, translation_to_ru, multiple_choice
    task_content: Mapped[str] = mapped_column(Text, nullable=False)  # JSON с данными задания
    user_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_correct: Mapped[Optional[bool]] = mapped_column(nullable=True)
    ai_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="task_history")
    word: Mapped["Word"] = relationship(back_populates="task_history")

    def __repr__(self) -> str:
        return f"<TaskHistory(id={self.id}, user_id={self.user_id}, task_type='{self.task_type}', is_correct={self.is_correct})>"
