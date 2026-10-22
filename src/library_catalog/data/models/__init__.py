"""ORM-модели. Импорт здесь нужен, чтобы Alembic «видел» все таблицы."""

from .book import Book

__all__ = ["Book"]
