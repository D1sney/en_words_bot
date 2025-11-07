from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from typing import List


def get_main_menu_keyboard(is_active: bool) -> ReplyKeyboardMarkup:
    """
    Главное меню бота

    Args:
        is_active: Активен ли бот (проснулся/спит)
    """
    buttons = []

    if is_active:
        buttons.append([KeyboardButton(text="😴 Лег спать")])
        buttons.append([KeyboardButton(text="⏸ Не беспокоить")])
    else:
        buttons.append([KeyboardButton(text="🌅 Я проснулся")])

    buttons.append([KeyboardButton(text="➕ Добавить слово")])
    buttons.append([KeyboardButton(text="📊 Моя статистика")])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )


def get_multiple_choice_keyboard(options: List[str], task_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура с вариантами ответа для multiple choice

    Args:
        options: Список вариантов ответа
        task_id: ID задания для callback_data
    """
    buttons = []

    for idx, option in enumerate(options):
        buttons.append([
            InlineKeyboardButton(
                text=option,
                callback_data=f"answer_{task_id}_{idx}"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_dnd_duration_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора длительности режима 'Не беспокоить'"""
    buttons = [
        [
            InlineKeyboardButton(text="30 минут", callback_data="dnd_30"),
            InlineKeyboardButton(text="1 час", callback_data="dnd_60"),
        ],
        [
            InlineKeyboardButton(text="2 часа", callback_data="dnd_120"),
            InlineKeyboardButton(text="3 часа", callback_data="dnd_180"),
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="dnd_cancel"),
        ]
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)
