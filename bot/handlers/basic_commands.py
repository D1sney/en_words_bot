from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from database.database import AsyncSessionLocal
from database.crud import get_or_create_user, update_user_active_status, get_all_words, create_user_word_progress, get_user_word_progress, get_user_statistics
from bot.keyboards import get_main_menu_keyboard
from scheduler.tasks import start_user_scheduler, stop_user_scheduler

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    async with AsyncSessionLocal() as session:
        # Получаем или создаем пользователя
        user = await get_or_create_user(session, message.from_user.id)

        # Если новый пользователь - инициализируем базовые слова
        words = await get_all_words(session)

        # Если слов еще нет в базе - создаем базовые
        if len(words) == 0:
            from database.crud import create_word
            # Добавляем 3 базовых слова для MVP
            base_words = [
                ("apple", "яблоко"),
                ("book", "книга"),
                ("cat", "кот"),
            ]
            for word_en, word_ru in base_words:
                word = await create_word(session, word_en, word_ru)
                words.append(word)

        # Создаем прогресс для всех слов если еще нет
        for word in words:
            progress = await get_user_word_progress(session, user.id, word.id)
            if not progress:
                await create_user_word_progress(session, user.id, word.id)

    welcome_text = (
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Я помогу тебе учить английские слова.\n\n"
        "📚 Как это работает:\n"
        "1. Нажми '🌅 Я проснулся' когда готов учиться\n"
        "2. Я буду присылать тебе задания каждые 30 минут\n"
        "3. Отвечай на задания и повышай уровень знания слов\n"
        "4. Когда хочешь отдохнуть - нажми '😴 Лег спать'\n\n"
        "Дополнительно:\n"
        "• ➕ Добавить слово - добавь новое слово для изучения\n"
        "• ⏸ Не беспокоить - приостанови задания на время\n"
        "• 📊 Моя статистика - посмотри свой прогресс\n\n"
        "Начнем? 🚀"
    )

    await message.answer(
        welcome_text,
        reply_markup=get_main_menu_keyboard(is_active=False)
    )


@router.message(F.text == "🌅 Я проснулся")
async def cmd_wake_up(message: Message):
    """Активация бота - начало отправки заданий"""
    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, message.from_user.id)

        # Обновляем статус
        await update_user_active_status(session, user.id, is_active=True)

        # Запускаем scheduler для этого пользователя
        await start_user_scheduler(user.id, message.from_user.id, user.interval_minutes)

    await message.answer(
        "✅ Бот активирован!\n\n"
        f"Буду отправлять задания каждые {user.interval_minutes} минут.\n"
        "Первое задание придет через несколько секунд! 📝",
        reply_markup=get_main_menu_keyboard(is_active=True)
    )


@router.message(F.text == "😴 Лег спать")
async def cmd_sleep(message: Message):
    """Деактивация бота - остановка заданий"""
    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, message.from_user.id)

        # Обновляем статус
        await update_user_active_status(session, user.id, is_active=False)

        # Останавливаем scheduler
        await stop_user_scheduler(user.id)

    await message.answer(
        "😴 Спокойной ночи!\n\n"
        "Задания остановлены.\n"
        "Когда будешь готов продолжить - нажми '🌅 Я проснулся'",
        reply_markup=get_main_menu_keyboard(is_active=False)
    )


@router.message(F.text == "📊 Моя статистика")
async def cmd_statistics(message: Message):
    """Показывает статистику пользователя"""
    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, message.from_user.id)
        stats = await get_user_statistics(session, user.id)

    stats_text = (
        "📊 Твоя статистика:\n\n"
        f"📚 Всего слов: {stats['total_words']}\n"
        f"✅ Выучено (≥90%): {stats['learned_words']}\n"
        f"📖 В процессе: {stats['in_progress_words']}\n"
        f"🆕 Новых: {stats['new_words']}\n\n"
        f"📈 Средний уровень знания: {stats['average_knowledge']}%\n\n"
        "Продолжай в том же духе! 💪"
    )

    await message.answer(stats_text)
