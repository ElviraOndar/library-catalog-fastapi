"""Настройка логирования приложения."""

import logging
import sys

from .config import settings

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def setup_logging() -> None:
    """
    Настроить корневой логгер.

    Уровень берётся из настроек (LOG_LEVEL в .env), вывод — в stdout,
    чтобы логи было видно в консоли uvicorn и в docker logs.
    """
    logging.basicConfig(
        level=settings.log_level,
        format=LOG_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,  # перезаписать настройки, если логгер уже настроен
    )
    # Сделать логи httpx потише: он пишет каждую строку запроса на INFO.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # В режиме DEBUG=true показываем SQL-запросы, которые делает SQLAlchemy.
    sql_level = logging.INFO if settings.debug else logging.WARNING
    logging.getLogger("sqlalchemy.engine").setLevel(sql_level)
