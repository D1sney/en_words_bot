from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict


class Settings(BaseSettings):
    """Основные настройки приложения"""

    # Telegram
    telegram_bot_token: str

    # OpenRouter AI
    openrouter_api_key: str
    openrouter_model: str = "nvidia/nemotron-nano-12b-v2-vl:free"
    openrouter_site_url: str = "https://github.com/user/en_words_bot"
    openrouter_site_name: str = "EnglishWordsBot"

    # Database
    database_url: str = "sqlite+aiosqlite:///./bot.db"

    # Bot behavior
    default_interval_minutes: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


class LearningConfig:
    """Константы для алгоритма обучения"""

    # Приоритеты при подборе слов (чем выше - тем важнее)
    NEW_WORD_PRIORITY = 3  # Совсем новые слова (ни разу не показывали)
    STRUGGLING_WORD_PRIORITY = 2  # Слова с knowledge < 50%
    REVIEW_WORD_PRIORITY = 1  # Обычное повторение

    # Интервалы повторений в зависимости от процента знания (в часах)
    # Основано на принципах spaced repetition (метод Лейтнера)
    REVIEW_INTERVALS: Dict[tuple, float] = {
        (0, 20): 0.5,      # Очень плохо знаем - каждые 30 минут
        (21, 50): 4,       # Средне - раз в 4 часа
        (51, 70): 24,      # Хорошо - раз в день
        (71, 89): 72,      # Отлично - раз в 3 дня
        (90, 100): 168,    # Выучено - раз в неделю
    }

    # Влияние правильного/неправильного ответа на процент знания
    CORRECT_ANSWER_BOOST = 15  # +15% за правильный ответ
    INCORRECT_ANSWER_PENALTY = 10  # -10% за неправильный ответ

    # Минимальное и максимальное значение knowledge_percent
    MIN_KNOWLEDGE = 0
    MAX_KNOWLEDGE = 100

    @classmethod
    def get_review_interval(cls, knowledge_percent: int) -> float:
        """Возвращает интервал повторения в часах для данного процента знания"""
        for (min_k, max_k), hours in cls.REVIEW_INTERVALS.items():
            if min_k <= knowledge_percent <= max_k:
                return hours
        return 168  # По умолчанию раз в неделю


# Глобальный экземпляр настроек
settings = Settings()
learning_config = LearningConfig()
