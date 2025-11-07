import json
from typing import Dict, Any, Literal
from openai import AsyncOpenAI
from config.settings import settings


# Инициализация клиента OpenRouter через OpenAI SDK
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.openrouter_api_key,
)


class AIService:
    """Сервис для работы с AI через OpenRouter"""

    @staticmethod
    async def generate_task(
        word_en: str,
        word_ru: str,
        task_type: Literal["translation_to_en", "translation_to_ru", "multiple_choice_en_to_ru", "multiple_choice_ru_to_en"]
    ) -> Dict[str, Any]:
        """
        Генерирует задание для изучения слова

        Args:
            word_en: Английское слово
            word_ru: Русский перевод
            task_type: Тип задания

        Returns:
            Dict с данными задания в формате JSON
        """

        # Формируем промпт в зависимости от типа задания
        if task_type == "translation_to_en":
            prompt = f"""Создай задание для изучения английского слова "{word_en}" ({word_ru}).

Составь простое предложение на РУССКОМ языке с использованием слова "{word_ru}".

Верни ответ СТРОГО в формате JSON (без markdown, без ```json):
{{
  "task_type": "translation_to_en",
  "sentence_ru": "предложение на русском",
  "correct_answer_en": "correct translation in English"
}}"""

        elif task_type == "translation_to_ru":
            prompt = f"""Создай задание для изучения английского слова "{word_en}" ({word_ru}).

Составь простое предложение на АНГЛИЙСКОМ языке с использованием слова "{word_en}".

Верни ответ СТРОГО в формате JSON (без markdown, без ```json):
{{
  "task_type": "translation_to_ru",
  "sentence_en": "sentence in English",
  "correct_answer_ru": "правильный перевод на русском"
}}"""

        elif task_type == "multiple_choice_en_to_ru":
            prompt = f"""Создай задание с выбором правильного перевода для английского слова "{word_en}".

Правильный перевод: "{word_ru}".
Придумай 3 неправильных, но похожих варианта перевода на русском.

Верни ответ СТРОГО в формате JSON (без markdown, без ```json):
{{
  "task_type": "multiple_choice_en_to_ru",
  "question": "Как переводится слово '{word_en}'?",
  "options": ["вариант1", "вариант2", "вариант3", "вариант4"],
  "correct_index": 0
}}

ВАЖНО: В массиве options правильный ответ "{word_ru}" должен быть на позиции correct_index."""

        elif task_type == "multiple_choice_ru_to_en":
            prompt = f"""Создай задание с выбором правильного перевода для русского слова "{word_ru}".

Правильный перевод на английском: "{word_en}".
Придумай 3 неправильных, но похожих варианта перевода на английском.

Верни ответ СТРОГО в формате JSON (без markdown, без ```json):
{{
  "task_type": "multiple_choice_ru_to_en",
  "question": "Как переводится слово '{word_ru}' на английский?",
  "options": ["option1", "option2", "option3", "option4"],
  "correct_index": 0
}}

ВАЖНО: В массиве options правильный ответ "{word_en}" должен быть на позиции correct_index."""

        else:
            raise ValueError(f"Unknown task_type: {task_type}")

        # Отправляем запрос к AI
        try:
            response = await client.chat.completions.create(
                model=settings.openrouter_model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты помощник для изучения английского языка. Отвечай строго в формате JSON без дополнительного текста."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                extra_headers={
                    # Optional: помогает избежать бана на бесплатных моделях OpenRouter
                    # и добавляет проект в rankings на openrouter.ai
                    "HTTP-Referer": settings.openrouter_site_url,
                    "X-Title": settings.openrouter_site_name,
                },
            )

            # Парсим ответ
            content = response.choices[0].message.content.strip()

            # Убираем markdown если AI добавил ```json
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()

            task_data = json.loads(content)
            return task_data

        except json.JSONDecodeError as e:
            raise ValueError(f"AI returned invalid JSON: {e}")
        except Exception as e:
            raise RuntimeError(f"Error calling AI API: {e}")

    @staticmethod
    async def check_answer(
        task_content: Dict[str, Any],
        user_answer: str,
        correct_answer: str
    ) -> Dict[str, Any]:
        """
        Проверяет ответ пользователя через AI

        Args:
            task_content: Данные задания
            user_answer: Ответ пользователя
            correct_answer: Правильный ответ

        Returns:
            Dict с результатом проверки: {is_correct: bool, feedback: str}
        """

        task_type = task_content.get("task_type")

        # Формируем промпт для проверки
        if task_type == "translation_to_en":
            original_sentence = task_content.get("sentence_ru")
            prompt = f"""Оцени перевод предложения с русского на английский.

Исходное предложение: "{original_sentence}"
Правильный перевод: "{correct_answer}"
Ответ пользователя: "{user_answer}"

Проверь насколько ответ пользователя близок к правильному. Учитывай синонимы, разный порядок слов, небольшие грамматические отличия.

Верни ответ СТРОГО в формате JSON (без markdown, без ```json):
{{
  "is_correct": true или false,
  "feedback": "краткий комментарий (1-2 предложения)"
}}"""

        elif task_type == "translation_to_ru":
            original_sentence = task_content.get("sentence_en")
            prompt = f"""Оцени перевод предложения с английского на русский.

Исходное предложение: "{original_sentence}"
Правильный перевод: "{correct_answer}"
Ответ пользователя: "{user_answer}"

Проверь насколько ответ пользователя близок к правильному. Учитывай синонимы, разный порядок слов, небольшие грамматические отличия.

Верни ответ СТРОГО в формате JSON (без markdown, без ```json):
{{
  "is_correct": true или false,
  "feedback": "краткий комментарий (1-2 предложения)"
}}"""

        else:
            # Для multiple_choice_* не нужна AI проверка (строгое сравнение)
            is_correct = user_answer.strip().lower() == correct_answer.strip().lower()
            return {
                "is_correct": is_correct,
                "feedback": "Правильно!" if is_correct else f"Правильный ответ: {correct_answer}"
            }

        # Отправляем запрос к AI
        try:
            response = await client.chat.completions.create(
                model=settings.openrouter_model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты помощник для проверки переводов. Будь снисходительным к мелким ошибкам, но строгим к смысловым. Отвечай строго в формате JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                extra_headers={
                    # Optional: помогает избежать бана на бесплатных моделях OpenRouter
                    # и добавляет проект в rankings на openrouter.ai
                    "HTTP-Referer": settings.openrouter_site_url,
                    "X-Title": settings.openrouter_site_name,
                },
            )

            # Парсим ответ
            content = response.choices[0].message.content.strip()

            # Убираем markdown если AI добавил ```json
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()

            result = json.loads(content)
            return result

        except json.JSONDecodeError as e:
            raise ValueError(f"AI returned invalid JSON: {e}")
        except Exception as e:
            raise RuntimeError(f"Error calling AI API: {e}")


# Экспортируем экземпляр сервиса
ai_service = AIService()
