import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config.settings import settings
from database.database import init_db, close_db
from bot.handlers import basic_commands, answers, word_management
from scheduler.tasks import start_scheduler, shutdown_scheduler, set_bot_instance

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Основная функция запуска бота"""
    logger.info("Starting bot...")

    # Инициализация бота и диспетчера
    bot = Bot(token=settings.telegram_bot_token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Регистрация роутеров (порядок важен!)
    dp.include_router(basic_commands.router)
    dp.include_router(word_management.router)
    dp.include_router(answers.router)

    # Инициализация базы данных
    logger.info("Initializing database...")
    await init_db()

    # Устанавливаем экземпляр бота для scheduler
    set_bot_instance(bot)

    # Запускаем scheduler
    logger.info("Starting scheduler...")
    start_scheduler()

    try:
        logger.info("Bot started successfully! Press Ctrl+C to stop.")
        # Запуск polling
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        # Graceful shutdown
        logger.info("Shutting down...")
        shutdown_scheduler()
        await close_db()
        await bot.session.close()
        logger.info("Bot stopped successfully")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application interrupted")
