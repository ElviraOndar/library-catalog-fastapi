"""Сервис книг — вся бизнес-логика приложения."""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from ...api.v1.schemas.book import BookCreate, BookUpdate, ShowBook
from ...data.repositories.book_repository import BookRepository
from ...external.openlibrary.client import OpenLibraryClient
from ..exceptions import (
    BookAlreadyExistsException,
    BookNotFoundException,
    InvalidPagesException,
    InvalidYearException,
    OpenLibraryException,
)
from ..mappers.book_mapper import BookMapper

logger = logging.getLogger(__name__)


class BookService:
    """
    Операции над книгами.

    Сервис не знает ни про HTTP, ни про SQL: с БД он работает через
    репозиторий, с внешним миром — через клиент. Оба передаются
    в конструктор (Dependency Injection), поэтому в тестах их легко
    подменить фейками.
    """

    def __init__(
        self,
        book_repository: BookRepository,
        openlibrary_client: OpenLibraryClient,
    ):
        self.book_repo = book_repository
        self.ol_client = openlibrary_client

    async def create_book(self, book_data: BookCreate) -> ShowBook:
        """
        Создать книгу с обогащением из Open Library.

        Бизнес-правила: год от 1000 до текущего, страниц > 0, ISBN уникален.

        Raises:
            InvalidYearException, InvalidPagesException, BookAlreadyExistsException
        """
        self._validate_year(book_data.year)
        self._validate_pages(book_data.pages)

        if book_data.isbn:
            await self._ensure_isbn_is_free(book_data.isbn)

        extra = await self._enrich_book_data(book_data)

        book = await self.book_repo.create(
            **book_data.model_dump(),
            extra=extra,
        )
        logger.info("Book created: %s", book.book_id)
        return BookMapper.to_show_book(book)

    async def get_book(self, book_id: UUID) -> ShowBook:
        """Получить книгу по ID. Raises: BookNotFoundException."""
        book = await self.book_repo.get_by_id(book_id)
        if book is None:
            raise BookNotFoundException(book_id)
        return BookMapper.to_show_book(book)

    async def update_book(self, book_id: UUID, book_data: BookUpdate) -> ShowBook:
        """
        Частично обновить книгу: меняются только переданные поля.

        Raises:
            BookNotFoundException, InvalidYearException,
            InvalidPagesException, BookAlreadyExistsException
        """
        existing = await self.book_repo.get_by_id(book_id)
        if existing is None:
            raise BookNotFoundException(book_id)

        # exclude_unset=True: берём только поля, которые клиент реально прислал.
        changes = book_data.model_dump(exclude_unset=True)

        if changes.get("year") is not None:
            self._validate_year(changes["year"])
        if changes.get("pages") is not None:
            self._validate_pages(changes["pages"])
        new_isbn = changes.get("isbn")
        if new_isbn and new_isbn != existing.isbn:
            await self._ensure_isbn_is_free(new_isbn)

        if not changes:
            return BookMapper.to_show_book(existing)

        updated = await self.book_repo.update(book_id, **changes)
        if updated is None:  # книгу успели удалить между запросами
            raise BookNotFoundException(book_id)

        logger.info("Book updated: %s (%s)", book_id, ", ".join(changes))
        return BookMapper.to_show_book(updated)

    async def delete_book(self, book_id: UUID) -> None:
        """Удалить книгу. Raises: BookNotFoundException."""
        deleted = await self.book_repo.delete(book_id)
        if not deleted:
            raise BookNotFoundException(book_id)
        logger.info("Book deleted: %s", book_id)

    async def search_books(
        self,
        title: str | None = None,
        author: str | None = None,
        genre: str | None = None,
        year: int | None = None,
        available: bool | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ShowBook], int]:
        """Найти книги. Возвращает (книги текущей страницы, всего найдено)."""
        filters: dict[str, Any] = {
            "title": title,
            "author": author,
            "genre": genre,
            "year": year,
            "available": available,
        }
        books = await self.book_repo.find_by_filters(**filters, limit=limit, offset=offset)
        total = await self.book_repo.count_by_filters(**filters)
        return BookMapper.to_show_books(books), total

    # ========== ПРИВАТНЫЕ МЕТОДЫ ==========

    @staticmethod
    def _validate_year(year: int) -> None:
        """Год должен быть от 1000 до текущего (книги из будущего не бывает)."""
        if year < 1000 or year > datetime.now().year:
            raise InvalidYearException(year)

    @staticmethod
    def _validate_pages(pages: int) -> None:
        """Количество страниц должно быть положительным."""
        if pages <= 0:
            raise InvalidPagesException(pages)

    async def _ensure_isbn_is_free(self, isbn: str) -> None:
        """Бросить BookAlreadyExistsException, если ISBN уже занят."""
        if await self.book_repo.find_by_isbn(isbn) is not None:
            raise BookAlreadyExistsException(isbn)

    async def _enrich_book_data(self, book_data: BookCreate) -> dict[str, Any] | None:
        """
        Получить доп. данные из Open Library.

        Важно: если Open Library недоступен, книга всё равно создаётся —
        ошибка логируется, а extra остаётся пустым.
        """
        try:
            extra = await self.ol_client.enrich(
                title=book_data.title,
                author=book_data.author,
                isbn=book_data.isbn,
            )
        except OpenLibraryException as exc:
            logger.warning(
                "Failed to enrich book '%s' from Open Library: %s",
                book_data.title,
                exc.message,
            )
            return None
        return extra or None
