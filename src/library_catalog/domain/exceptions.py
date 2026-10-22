"""Доменные исключения: ошибки бизнес-правил и внешних сервисов."""

from datetime import datetime
from uuid import UUID

from ..core.exceptions import AppException, NotFoundException


class BookNotFoundException(NotFoundException):
    """Книга не найдена (404)."""

    def __init__(self, book_id: UUID):
        super().__init__(resource="Book", identifier=book_id)


class BookAlreadyExistsException(AppException):
    """Книга с таким ISBN уже существует (409 Conflict)."""

    def __init__(self, isbn: str):
        super().__init__(
            message=f"Book with ISBN '{isbn}' already exists",
            status_code=409,
        )


class InvalidYearException(AppException):
    """Невалидный год издания (400)."""

    def __init__(self, year: int):
        current_year = datetime.now().year
        super().__init__(
            message=f"Year {year} is invalid (must be 1000-{current_year})",
            status_code=400,
        )


class InvalidPagesException(AppException):
    """Невалидное количество страниц (400)."""

    def __init__(self, pages: int):
        super().__init__(
            message=f"Pages count must be positive, got {pages}",
            status_code=400,
        )


class OpenLibraryException(AppException):
    """Ошибка Open Library API (503)."""

    def __init__(self, message: str, status_code: int = 503):
        super().__init__(
            message=f"Open Library API error: {message}",
            status_code=status_code,
        )


class OpenLibraryTimeoutException(OpenLibraryException):
    """
    Таймаут Open Library API (504).

    ⚠️ В ТЗ этот класс наследуется от AppException, и тогда
    `except OpenLibraryException` в сервисе НЕ ловит таймаут —
    создание книги падало бы с 504. Наследуем от OpenLibraryException,
    чтобы «любая проблема с Open Library» ловилась одним except.
    """

    def __init__(self, timeout: float):
        AppException.__init__(
            self,
            message=f"Open Library API timeout after {timeout}s",
            status_code=504,
        )
