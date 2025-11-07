from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.database import AsyncSessionLocal
from database.crud import (
    get_or_create_user,
    get_or_create_word,
    create_user_word_progress,
    get_user_word_progress,
    set_do_not_disturb,
    clear_do_not_disturb
)
from bot.keyboards import get_dnd_duration_keyboard, get_main_menu_keyboard

router = Router()


# FSM для добавления слова
class AddWordStates(StatesGroup):
    waiting_for_word_en = State()
    waiting_for_word_ru = State()


@router.message(F.text == "➕ Добавить слово")
async def cmd_add_word_start(message: Message, state: FSMContext):
    """Начало процесса добавления слова"""
    await state.set_state(AddWordStates.waiting_for_word_en)
    await message.answer(
        "📝 Добавление нового слова\n\n"
        "Введи английское слово:"
    )


@router.message(AddWordStates.waiting_for_word_en)
async def process_word_en(message: Message, state: FSMContext):
    """Получение английского слова"""
    word_en = message.text.strip().lower()

    # Простая валидация
    if not word_en.replace(" ", "").isalpha():
        await message.answer(
            "⚠️ Слово должно содержать только буквы.\n"
            "Попробуй еще раз:"
        )
        return

    # Сохраняем в FSM
    await state.update_data(word_en=word_en)
    await state.set_state(AddWordStates.waiting_for_word_ru)

    await message.answer(
        f"Английское слово: <b>{word_en}</b>\n\n"
        "Теперь введи перевод на русский:",
        parse_mode="HTML"
    )


@router.message(AddWordStates.waiting_for_word_ru)
async def process_word_ru(message: Message, state: FSMContext):
    """Получение русского перевода и сохранение слова"""
    word_ru = message.text.strip()

    # Простая валидация
    if not word_ru.replace(" ", "").replace("-", "").isalpha():
        await message.answer(
            "⚠️ Перевод должен содержать только буквы.\n"
            "Попробуй еще раз:"
        )
        return

    # Получаем английское слово из FSM
    data = await state.get_data()
    word_en = data.get("word_en")

    # Сохраняем в БД
    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, message.from_user.id)

        # Создаем или получаем слово
        word = await get_or_create_word(session, word_en, word_ru)

        # FIXME: Если слово уже существует с другим переводом, word_ru игнорируется
        # В будущем: добавить поддержку множественных переводов или предупреждение

        # Проверяем есть ли уже прогресс у пользователя
        progress = await get_user_word_progress(session, user.id, word.id)
        if progress:
            await message.answer(
                f"ℹ️ Слово <b>{word_en}</b> ({word.word_ru}) уже в твоем списке!\n"
                f"Текущий уровень знания: {progress.knowledge_percent}%",
                parse_mode="HTML"
            )
        else:
            # Создаем прогресс для пользователя
            await create_user_word_progress(session, user.id, word.id)
            await message.answer(
                f"✅ Слово добавлено!\n\n"
                f"<b>{word_en}</b> — {word_ru}\n\n"
                "Оно появится в следующих заданиях.",
                parse_mode="HTML"
            )

    # Очищаем FSM
    await state.clear()


@router.message(F.text == "⏸ Не беспокоить")
async def cmd_dnd_start(message: Message):
    """Запуск режима 'Не беспокоить'"""
    await message.answer(
        "⏸ Режим 'Не беспокоить'\n\n"
        "На сколько времени приостановить задания?",
        reply_markup=get_dnd_duration_keyboard()
    )


@router.callback_query(F.data.startswith("dnd_"))
async def process_dnd_duration(callback: CallbackQuery):
    """Обработка выбора длительности режима 'Не беспокоить'"""
    action = callback.data.split("_")[1]

    if action == "cancel":
        await callback.message.edit_text("❌ Отменено")
        await callback.answer()
        return

    # Получаем количество минут
    minutes = int(action)

    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, callback.from_user.id)

        # Устанавливаем режим DND
        await set_do_not_disturb(session, user.id, minutes)

    hours = minutes / 60
    if hours >= 1:
        duration_text = f"{int(hours)} час" if hours == 1 else f"{hours} часа" if hours < 5 else f"{int(hours)} часов"
    else:
        duration_text = f"{minutes} минут"

    await callback.message.edit_text(
        f"✅ Режим 'Не беспокоить' включен на {duration_text}\n\n"
        "Задания не будут приходить до истечения времени."
    )

    await callback.answer()
