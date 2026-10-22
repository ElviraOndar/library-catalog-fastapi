"""
Подключение к PostgreSQL через асинхронный SQLAlchemy.

Здесь создаются:
- engine — пул соединений с БД (один на всё приложение);
- async_session_maker — фабрика сессий (одна сессия на один HTTP-запрос);
- Base — базовый класс для всех ORM-моделей;
- get_db — зависимость FastAPI, которая выдаёт сессию и закрывает её.
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Базовый класс для всех ORM-моделей. Хранит общую metadata."""


engine = create_async_engine(
    settings.database_url_str,
    pool_size=settings.database_pool_size,
    pool_pre_ping=True,  # проверять соединение перед использованием
    # echo=True добавляет SQLAlchemy собственный обработчик логов, и каждая
    # SQL-строка печаталась бы дважды. Поэтому вывод SQL включаем через
    # уровень логгера в logging_config.py.
    echo=False,
)

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    # После commit объекты не "протухают": можно читать их поля
    # без нового запроса к БД (в async это важно — ленивых загрузок нет).
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Зависимость FastAPI: выдать сессию БД на время запроса.

    Код до yield выполняется перед обработкой запроса,
    код после — когда ответ уже сформирован.
    """
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        # Закрывать вручную не нужно: это делает `async with`.


async def check_db_connection() -> bool:
    """Проверить, что БД доступна (выполнить SELECT 1)."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Database is not available")
        return False


async def init_db() -> None:
    """Проверить подключение к БД при старте приложения."""
    if await check_db_connection():
        logger.info("Database connection established")
    else:
        logger.warning("Database is not reachable at startup")


async def dispose_engine() -> None:
    """Закрыть все соединения пула при остановке приложения."""
    await engine.dispose()
    logger.info("Database engine disposed")
