import json
import random
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from aiogram import Bot
from database.database import AsyncSessionLocal
from database.crud import (
    get_user_by_telegram_id,
    get_words_for_review,
    create_task_history,
)
from database.models import UserWordProgress
from services.ai_service import ai_service
from bot.keyboards import get_multiple_choice_keyboard
from config.settings import settings

# Глобальный scheduler
scheduler = AsyncIOScheduler()

# Храним экземпляр бота (будет установлен из main.py)
bot_instance: Bot = None


def set_bot_instance(bot: Bot):
    """Устанавливает экземпляр бота для использования в scheduler"""
    global bot_instance
    bot_instance = bot


async def send_task_to_user(user_id: int, telegram_id: int):
    """
    Отправляет задание пользователю

    Args:
        user_id: ID пользователя в БД
        telegram_id: Telegram ID пользователя
    """
    async with AsyncSessionLocal() as session:
        # Получаем пользователя
        user = await get_user_by_telegram_id(session, telegram_id)

        # Проверка: бот активен?
        if not user or not user.is_active:
            return

        # Проверка: режим "Не беспокоить"?
        if user.do_not_disturb_until:
            if datetime.utcnow() < user.do_not_disturb_until:
                return  # Еще не время

        # Получаем слова готовые для повторения
        words_progress = await get_words_for_review(session, user_id, limit=1)

        if not words_progress:
            # Нет слов для повторения
            await bot_instance.send_message(
                telegram_id,
                "🎉 Отлично! Все слова повторены.\n"
                "Следующее задание придет позже согласно расписанию повторений."
            )
            return

        # Берем первое слово
        progress: UserWordProgress = words_progress[0]
        await session.refresh(progress, ["word"])  # Загружаем связанное слово
        word = progress.word

        # Выбираем случайный тип задания
        task_types = [
            "translation_to_en",
            "translation_to_ru",
            "multiple_choice_en_to_ru",
            "multiple_choice_ru_to_en"
        ]
        task_type = random.choice(task_types)

        try:
            # Генерируем задание через AI
            task_data = await ai_service.generate_task(
                word_en=word.word_en,
                word_ru=word.word_ru,
                task_type=task_type
            )

            # Сохраняем задание в историю
            task_history = await create_task_history(
                session,
                user_id=user_id,
                word_id=word.id,
                task_type=task_type,
                task_content=json.dumps(task_data, ensure_ascii=False)
            )

            # Формируем сообщение и отправляем
            await _send_task_message(telegram_id, task_data, task_history.id)

        except Exception as e:
            # Логируем ошибку и отправляем fallback сообщение
            print(f"Error generating task for user {telegram_id}: {e}")
            await bot_instance.send_message(
                telegram_id,
                "❌ Произошла ошибка при генерации задания.\n"
                "Попробую снова через некоторое время."
            )


async def _send_task_message(telegram_id: int, task_data: dict, task_id: int):
    """
    Отправляет сообщение с заданием пользователю

    Args:
        telegram_id: Telegram ID пользователя
        task_data: Данные задания от AI
        task_id: ID задания в TaskHistory
    """
    task_type = task_data.get("task_type")

    if task_type == "translation_to_en":
        # Перевод предложения на английский
        sentence_ru = task_data.get("sentence_ru")
        message_text = (
            "📝 Переведи предложение на английский:\n\n"
            f"<b>{sentence_ru}</b>\n\n"
            "Напиши свой вариант перевода:"
        )
        await bot_instance.send_message(telegram_id, message_text, parse_mode="HTML")

    elif task_type == "translation_to_ru":
        # Перевод предложения на русский
        sentence_en = task_data.get("sentence_en")
        message_text = (
            "📝 Переведи предложение на русский:\n\n"
            f"<b>{sentence_en}</b>\n\n"
            "Напиши свой вариант перевода:"
        )
        await bot_instance.send_message(telegram_id, message_text, parse_mode="HTML")

    elif task_type in ["multiple_choice_en_to_ru", "multiple_choice_ru_to_en"]:
        # Multiple choice задание
        question = task_data.get("question")
        options = task_data.get("options", [])

        message_text = f"🔤 {question}\n\nВыбери правильный вариант:"

        keyboard = get_multiple_choice_keyboard(options, task_id)
        await bot_instance.send_message(
            telegram_id,
            message_text,
            reply_markup=keyboard
        )


async def start_user_scheduler(user_id: int, telegram_id: int, interval_minutes: int):
    """
    Запускает периодическую отправку заданий для пользователя

    Args:
        user_id: ID пользователя в БД
        telegram_id: Telegram ID пользователя
        interval_minutes: Интервал в минутах
    """
    job_id = f"user_{user_id}"

    # Удаляем существующий job если есть
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    # Добавляем новый job
    scheduler.add_job(
        send_task_to_user,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id=job_id,
        args=[user_id, telegram_id],
        replace_existing=True
    )

    # Отправляем первое задание сразу
    await send_task_to_user(user_id, telegram_id)


async def stop_user_scheduler(user_id: int):
    """
    Останавливает периодическую отправку заданий для пользователя

    Args:
        user_id: ID пользователя в БД
    """
    job_id = f"user_{user_id}"

    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


def start_scheduler():
    """Запускает scheduler"""
    if not scheduler.running:
        scheduler.start()


def shutdown_scheduler():
    """Останавливает scheduler"""
    if scheduler.running:
        scheduler.shutdown()
