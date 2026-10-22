"""
Настройки приложения.

Все параметры читаются из переменных окружения и файла .env
с помощью pydantic-settings. Pydantic сам приводит строки из .env
к нужным типам (bool, int, list) и падает с понятной ошибкой,
если значение некорректно.
"""

from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Типизированная конфигурация приложения."""

    # --- Общие ---
    app_name: str = "Library Catalog API"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # --- База данных ---
    database_url: PostgresDsn
    database_pool_size: int = 20

    # --- API ---
    api_v1_prefix: str = "/api/v1"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    cors_origins: list[str] = ["*"]

    # --- Логирование ---
    log_level: str = "INFO"

    # --- Open Library ---
    openlibrary_base_url: str = "https://openlibrary.org"
    openlibrary_timeout: float = 10.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("database_url")
    @classmethod
    def validate_async_driver(cls, value: PostgresDsn) -> PostgresDsn:
        """
        Проверить, что используется асинхронный драйвер asyncpg.

        PostgresDsn уже гарантирует, что это PostgreSQL-URL.
        Дополнительно требуем схему postgresql+asyncpg, потому что
        всё приложение работает через async SQLAlchemy.
        """
        if value.scheme != "postgresql+asyncpg":
            raise ValueError("DATABASE_URL должен начинаться с 'postgresql+asyncpg://'")
        return value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Разрешить только стандартные уровни логирования."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = value.upper()
        if upper not in allowed:
            raise ValueError(f"LOG_LEVEL должен быть одним из {sorted(allowed)}")
        return upper

    @property
    def database_url_str(self) -> str:
        """URL базы данных в виде строки (create_async_engine ждёт str)."""
        return str(self.database_url)

    @property
    def is_production(self) -> bool:
        """Запущено ли приложение в production."""
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """
    Вернуть объект настроек.

    lru_cache гарантирует, что .env прочитается один раз,
    а все последующие вызовы получат тот же объект.
    """
    return Settings()


settings = get_settings()
