"""
Окружение Alembic, настроенное для асинхронного SQLAlchemy.

Отличия от стандартного шаблона:
- URL базы берётся из настроек приложения (.env), а не из alembic.ini;
- миграции выполняются через async engine (драйвер asyncpg);
- target_metadata = Base.metadata — по ней работает --autogenerate.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from src.library_catalog.core.config import settings
from src.library_catalog.core.database import Base

# Импорт моделей ОБЯЗАТЕЛЕН: без него Base.metadata пустая,
# и autogenerate решит, что таблиц нет вообще.
from src.library_catalog.data import models  # noqa: F401

config = context.config

# ⚠️ В ТЗ здесь убирают "+asyncpg". Но ниже используется
# async_engine_from_config, которому нужен именно асинхронный драйвер.
# Без "+asyncpg" SQLAlchemy возьмёт синхронный psycopg2, и миграции упадут.
# Поэтому оставляем URL как есть: postgresql+asyncpg://...
config.set_main_option("sqlalchemy.url", settings.database_url_str)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Режим offline: сгенерировать SQL-скрипт без подключения к БД."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Синхронная часть: Alembic сам по себе синхронный."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Создать async engine и выполнить миграции через run_sync."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Режим online: подключиться к БД и применить миграции."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
