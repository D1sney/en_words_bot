import json
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from database.database import AsyncSessionLocal
from database.models import TaskHistory
from database.crud import (
    get_or_create_user,
    get_last_pending_task,
    update_task_history_answer,
    get_user_word_progress,
    update_word_progress
)
from services.ai_service import ai_service

router = Router()


@router.message(F.text & ~F.text.startswith("/") & ~F.text.in_([
    "🌅 Я проснулся", "😴 Лег спать", "⏸ Не беспокоить",
    "➕ Добавить слово", "📊 Моя статистика"
]))
async def handle_text_answer(message: Message):
    """
    Обработчик текстовых ответов пользователя
    (для заданий translation_to_en и translation_to_ru)
    """
    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, message.from_user.id)

        # Получаем последнее задание без ответа
        task = await get_last_pending_task(session, user.id)

        if not task:
            await message.answer(
                "🤔 Нет активного задания.\n"
                "Дождись следующего задания или нажми '🌅 Я проснулся' если бот неактивен."
            )
            return

        # Парсим данные задания
        task_data = json.loads(task.task_content)
        task_type = task_data.get("task_type")

        # Проверяем что это задание на перевод (не multiple choice)
        if task_type not in ["translation_to_en", "translation_to_ru"]:
            await message.answer(
                "⚠️ Это задание требует выбора варианта, а не текстового ответа."
            )
            return

        # Получаем правильный ответ
        if task_type == "translation_to_en":
            correct_answer = task_data.get("correct_answer_en")
        else:
            correct_answer = task_data.get("correct_answer_ru")

        user_answer = message.text

        try:
            # Проверяем ответ через AI
            check_result = await ai_service.check_answer(
                task_content=task_data,
                user_answer=user_answer,
                correct_answer=correct_answer
            )

            is_correct = check_result.get("is_correct")
            feedback = check_result.get("feedback")

            # Обновляем задание в истории
            await update_task_history_answer(
                session,
                task_id=task.id,
                user_answer=user_answer,
                is_correct=is_correct,
                ai_feedback=feedback
            )

            # Обновляем прогресс по слову
            progress = await get_user_word_progress(session, user.id, task.word_id)
            if progress:
                await update_word_progress(session, progress.id, is_correct)

            # Формируем ответ пользователю
            if is_correct:
                response_text = f"✅ Правильно!\n\n{feedback}"
            else:
                response_text = f"❌ Не совсем.\n\n{feedback}"

            # Показываем обновленный процент знания
            await session.refresh(progress)
            response_text += f"\n\n📊 Уровень знания слова: {progress.knowledge_percent}%"

            await message.answer(response_text)

        except Exception as e:
            print(f"Error checking answer: {e}")
            await message.answer(
                "❌ Произошла ошибка при проверке ответа.\n"
                "Попробуй ответить на следующее задание."
            )


@router.callback_query(F.data.startswith("answer_"))
async def handle_multiple_choice_answer(callback: CallbackQuery):
    """
    Обработчик ответов на multiple choice задания
    callback_data формат: answer_{task_id}_{option_index}
    """
    # Парсим callback_data
    parts = callback.data.split("_")
    task_id = int(parts[1])
    selected_index = int(parts[2])

    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, callback.from_user.id)

        # Получаем задание
        task = await session.get(TaskHistory, task_id)

        if not task:
            await callback.answer("❌ Задание не найдено", show_alert=True)
            return

        # Проверяем что задание еще не отвечено
        if task.is_correct is not None:
            await callback.answer("⚠️ Ты уже ответил на это задание", show_alert=True)
            return

        # Парсим данные задания
        task_data = json.loads(task.task_content)
        options = task_data.get("options", [])
        correct_index = task_data.get("correct_index")

        # Проверяем ответ
        is_correct = (selected_index == correct_index)
        user_answer = options[selected_index]
        correct_answer = options[correct_index]

        # Формируем feedback
        if is_correct:
            feedback = "Правильно! ✅"
        else:
            feedback = f"Неправильно. Правильный ответ: {correct_answer}"

        # Обновляем задание в истории
        await update_task_history_answer(
            session,
            task_id=task.id,
            user_answer=user_answer,
            is_correct=is_correct,
            ai_feedback=feedback
        )

        # Обновляем прогресс по слову
        progress = await get_user_word_progress(session, user.id, task.word_id)
        if progress:
            await update_word_progress(session, progress.id, is_correct)

        # Отправляем ответ
        await session.refresh(progress)
        response_text = (
            f"{feedback}\n\n"
            f"📊 Уровень знания слова: {progress.knowledge_percent}%"
        )

        # Редактируем сообщение (убираем кнопки)
        await callback.message.edit_text(
            callback.message.text + f"\n\n{response_text}",
            reply_markup=None
        )

        await callback.answer()
