"""
Общие фикстуры pytest.

- FakeBookRepository / FakeOpenLibraryClient — «ненастоящие» зависимости
  для unit-тестов сервиса: работают в памяти, БД и интернет не нужны.
- client — HTTP-клиент для интеграционных тестов API, в котором
  BookService собран из фейков через dependency_overrides.
- db_session — сессия к настоящей тестовой БД (для тестов репозитория).
"""

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.library_catalog.api.dependencies import get_book_service
from src.library_catalog.core.database import Base
from src.library_catalog.data.models.book import Book
from src.library_catalog.domain.exceptions import OpenLibraryException
from src.library_catalog.domain.services.book_service import BookService
from src.library_catalog.main import app

# ==================== ФЕЙКИ ====================


class FakeBookRepository:
    """Репозиторий в памяти с тем же интерфейсом, что и BookRepository."""

    def __init__(self) -> None:
        self.books: dict[uuid.UUID, Book] = {}

    async def create(self, **kwargs: Any) -> Book:
        now = datetime.now(UTC)
        book = Book(
            book_id=uuid.uuid4(),
            available=True,
            created_at=now,
            updated_at=now,
            **kwargs,
        )
        self.books[book.book_id] = book
        return book

    async def get_by_id(self, id: uuid.UUID) -> Book | None:
        return self.books.get(id)

    async def update(self, id: uuid.UUID, **kwargs: Any) -> Book | None:
        book = self.books.get(id)
        if book is None:
            return None
        for key, value in kwargs.items():
            setattr(book, key, value)
        book.updated_at = datetime.now(UTC)
        return book

    async def delete(self, id: uuid.UUID) -> bool:
        return self.books.pop(id, None) is not None

    async def find_by_isbn(self, isbn: str) -> Book | None:
        return next((b for b in self.books.values() if b.isbn == isbn), None)

    def _filter(self, title=None, author=None, genre=None, year=None, available=None):
        result = list(self.books.values())
        if title:
            result = [b for b in result if title.lower() in b.title.lower()]
        if author:
            result = [b for b in result if author.lower() in b.author.lower()]
        if genre:
            result = [b for b in result if b.genre == genre]
        if year is not None:
            result = [b for b in result if b.year == year]
        if available is not None:
            result = [b for b in result if b.available == available]
        return result

    async def find_by_filters(self, limit: int = 20, offset: int = 0, **filters: Any) -> list[Book]:
        return self._filter(**filters)[offset : offset + limit]

    async def count_by_filters(self, **filters: Any) -> int:
        return len(self._filter(**filters))


class FakeOpenLibraryClient:
    """Клиент Open Library, который ничего не скачивает."""

    def __init__(self, data: dict | None = None, error: Exception | None = None):
        self.data = data if data is not None else {"cover_url": "https://example.com/c.jpg"}
        self.error = error
        self.calls: list[dict] = []

    async def enrich(self, title: str, author: str, isbn: str | None = None) -> dict:
        self.calls.append({"title": title, "author": author, "isbn": isbn})
        if self.error:
            raise self.error
        return self.data


# ==================== ФИКСТУРЫ: СЕРВИС ====================


@pytest.fixture
def fake_repo() -> FakeBookRepository:
    return FakeBookRepository()


@pytest.fixture
def fake_ol_client() -> FakeOpenLibraryClient:
    return FakeOpenLibraryClient()


@pytest.fixture
def service(fake_repo, fake_ol_client) -> BookService:
    return BookService(book_repository=fake_repo, openlibrary_client=fake_ol_client)


@pytest.fixture
def failing_ol_client() -> FakeOpenLibraryClient:
    return FakeOpenLibraryClient(error=OpenLibraryException("service down"))


# ==================== ФИКСТУРЫ: API ====================


@pytest.fixture
def client(service: BookService) -> Iterator[TestClient]:
    """
    TestClient, в котором BookService подменён на сервис с фейками.

    dependency_overrides — штатный механизм FastAPI для тестов:
    «вместо get_book_service используй вот эту функцию».
    """
    app.dependency_overrides[get_book_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ==================== ФИКСТУРЫ: НАСТОЯЩАЯ БД ====================

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5433/library_catalog_test",
)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """
    Сессия к отдельной тестовой БД (library_catalog_test).

    Таблицы создаются перед тестом и удаляются после, поэтому тесты
    не мешают друг другу и не трогают рабочую БД. Если PostgreSQL
    недоступен — тест пропускается (skip), а не падает.
    """
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:  # БД не запущена или нет базы
        await engine.dispose()
        pytest.skip(f"Test database is not available: {exc}")

    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
