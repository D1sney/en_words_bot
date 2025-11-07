from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, Word, UserWordProgress, TaskHistory
from config.settings import learning_config


# ==================== USER CRUD ====================

async def create_user(session: AsyncSession, telegram_id: int) -> User:
    """Создает нового пользователя"""
    user = User(telegram_id=telegram_id, is_active=False)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
    """Получает пользователя по telegram_id"""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def get_or_create_user(session: AsyncSession, telegram_id: int) -> User:
    """Получает существующего пользователя или создает нового"""
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        user = await create_user(session, telegram_id)
    return user


async def update_user_active_status(session: AsyncSession, user_id: int, is_active: bool) -> None:
    """Обновляет статус активности пользователя"""
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(is_active=is_active, updated_at=datetime.utcnow())
    )
    await session.commit()


async def set_do_not_disturb(session: AsyncSession, user_id: int, minutes: int) -> None:
    """Устанавливает режим 'Не беспокоить' на N минут"""
    until = datetime.utcnow() + timedelta(minutes=minutes)
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(do_not_disturb_until=until, updated_at=datetime.utcnow())
    )
    await session.commit()


async def clear_do_not_disturb(session: AsyncSession, user_id: int) -> None:
    """Отключает режим 'Не беспокоить'"""
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(do_not_disturb_until=None, updated_at=datetime.utcnow())
    )
    await session.commit()


# ==================== WORD CRUD ====================

async def create_word(session: AsyncSession, word_en: str, word_ru: str) -> Word:
    """Создает новое слово"""
    word = Word(word_en=word_en.lower().strip(), word_ru=word_ru.strip())
    session.add(word)
    await session.commit()
    await session.refresh(word)
    return word


async def get_word_by_en(session: AsyncSession, word_en: str) -> Optional[Word]:
    """Получает слово по английскому варианту"""
    result = await session.execute(
        select(Word).where(Word.word_en == word_en.lower().strip())
    )
    return result.scalar_one_or_none()


async def get_all_words(session: AsyncSession) -> List[Word]:
    """Получает все слова"""
    result = await session.execute(select(Word))
    return list(result.scalars().all())


async def get_or_create_word(session: AsyncSession, word_en: str, word_ru: str) -> Word:
    """Получает существующее слово или создает новое"""
    word = await get_word_by_en(session, word_en)
    if not word:
        word = await create_word(session, word_en, word_ru)
    return word


# ==================== USER WORD PROGRESS CRUD ====================

async def create_user_word_progress(session: AsyncSession, user_id: int, word_id: int) -> UserWordProgress:
    """Создает запись прогресса для пользователя по слову"""
    progress = UserWordProgress(
        user_id=user_id,
        word_id=word_id,
        knowledge_percent=0,
        next_review_at=datetime.utcnow()  # Доступно для изучения сразу
    )
    session.add(progress)
    await session.commit()
    await session.refresh(progress)
    return progress


async def get_user_word_progress(session: AsyncSession, user_id: int, word_id: int) -> Optional[UserWordProgress]:
    """Получает прогресс пользователя по конкретному слову"""
    result = await session.execute(
        select(UserWordProgress)
        .where(UserWordProgress.user_id == user_id, UserWordProgress.word_id == word_id)
    )
    return result.scalar_one_or_none()


async def get_words_for_review(session: AsyncSession, user_id: int, limit: int = 10) -> List[UserWordProgress]:
    """
    Получает слова готовые для повторения, отсортированные по приоритету

    Приоритеты:
    1. Новые слова (never reviewed) - приоритет 3
    2. Плохо выученные (knowledge < 50%) - приоритет 2
    3. Обычное повторение (next_review_at <= now) - приоритет 1
    """
    now = datetime.utcnow()

    result = await session.execute(
        select(UserWordProgress)
        .where(
            UserWordProgress.user_id == user_id,
            UserWordProgress.next_review_at <= now
        )
        .order_by(
            # Сортируем по приоритету (новые → плохо выученные → обычные)
            # Новые слова: last_reviewed_at IS NULL
            UserWordProgress.last_reviewed_at.is_(None).desc(),
            # Плохо выученные: knowledge_percent ASC (от меньшего к большему)
            UserWordProgress.knowledge_percent.asc(),
            # Старые повторения раньше
            UserWordProgress.next_review_at.asc()
        )
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_word_progress(
    session: AsyncSession,
    progress_id: int,
    is_correct: bool
) -> None:
    """
    Обновляет прогресс изучения слова после ответа

    Args:
        progress_id: ID записи прогресса
        is_correct: Правильно ли ответил пользователь
    """
    # Получаем текущий прогресс
    progress = await session.get(UserWordProgress, progress_id)
    if not progress:
        return

    # Обновляем счетчики
    progress.total_answers_count += 1
    if is_correct:
        progress.correct_answers_count += 1
        # Увеличиваем процент знания
        progress.knowledge_percent = min(
            learning_config.MAX_KNOWLEDGE,
            progress.knowledge_percent + learning_config.CORRECT_ANSWER_BOOST
        )
    else:
        # Уменьшаем процент знания
        progress.knowledge_percent = max(
            learning_config.MIN_KNOWLEDGE,
            progress.knowledge_percent - learning_config.INCORRECT_ANSWER_PENALTY
        )

    # Обновляем время последнего повторения
    progress.last_reviewed_at = datetime.utcnow()

    # Рассчитываем следующее время повторения
    interval_hours = learning_config.get_review_interval(progress.knowledge_percent)
    progress.next_review_at = datetime.utcnow() + timedelta(hours=interval_hours)

    progress.updated_at = datetime.utcnow()

    await session.commit()


# ==================== TASK HISTORY CRUD ====================

async def create_task_history(
    session: AsyncSession,
    user_id: int,
    word_id: int,
    task_type: str,
    task_content: str  # JSON string
) -> TaskHistory:
    """Создает запись задания в истории"""
    task = TaskHistory(
        user_id=user_id,
        word_id=word_id,
        task_type=task_type,
        task_content=task_content
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def update_task_history_answer(
    session: AsyncSession,
    task_id: int,
    user_answer: str,
    is_correct: bool,
    ai_feedback: str
) -> None:
    """Обновляет запись задания после ответа пользователя"""
    await session.execute(
        update(TaskHistory)
        .where(TaskHistory.id == task_id)
        .values(
            user_answer=user_answer,
            is_correct=is_correct,
            ai_feedback=ai_feedback
        )
    )
    await session.commit()


async def get_last_pending_task(session: AsyncSession, user_id: int) -> Optional[TaskHistory]:
    """Получает последнее задание пользователя без ответа"""
    result = await session.execute(
        select(TaskHistory)
        .where(
            TaskHistory.user_id == user_id,
            TaskHistory.is_correct.is_(None)  # Еще не отвечено
        )
        .order_by(TaskHistory.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_user_statistics(session: AsyncSession, user_id: int) -> dict:
    """Получает статистику пользователя"""
    # Получаем все прогрессы пользователя
    result = await session.execute(
        select(UserWordProgress).where(UserWordProgress.user_id == user_id)
    )
    progresses = list(result.scalars().all())

    total_words = len(progresses)
    learned_words = len([p for p in progresses if p.knowledge_percent >= 90])
    in_progress_words = len([p for p in progresses if 0 < p.knowledge_percent < 90])
    new_words = len([p for p in progresses if p.knowledge_percent == 0])

    avg_knowledge = sum(p.knowledge_percent for p in progresses) / total_words if total_words > 0 else 0

    return {
        "total_words": total_words,
        "learned_words": learned_words,
        "in_progress_words": in_progress_words,
        "new_words": new_words,
        "average_knowledge": round(avg_knowledge, 2)
    }
