from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from config.settings import settings
from database.models import Base


# Создаем асинхронный движок БД
engine = create_async_engine(
    settings.database_url,
    echo=False,  # Если True - будет логировать все SQL запросы (полезно для отладки)
    poolclass=NullPool,  # Для SQLite рекомендуется NullPool
)

# Фабрика для создания сессий
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Объекты остаются доступны после commit
)


async def init_db():
    """Инициализация базы данных - создание всех таблиц"""
    async with engine.begin() as conn:
        # Создаем все таблицы из Base.metadata
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """
    Генератор для получения сессии БД
    Используется как dependency в aiogram или FastAPI
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def close_db():
    """Закрытие соединений с БД при завершении приложения"""
    await engine.dispose()
