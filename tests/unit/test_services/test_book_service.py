"""Unit-тесты BookService: проверяем бизнес-правила без БД и сети."""

import uuid
from datetime import datetime

import pytest

from src.library_catalog.api.v1.schemas.book import BookCreate, BookUpdate
from src.library_catalog.domain.exceptions import (
    BookAlreadyExistsException,
    BookNotFoundException,
    InvalidYearException,
    OpenLibraryTimeoutException,
)
from src.library_catalog.domain.services.book_service import BookService
from tests.conftest import FakeOpenLibraryClient


def make_book(**overrides) -> BookCreate:
    data = {
        "title": "Clean Code",
        "author": "Robert Martin",
        "year": 2008,
        "genre": "Programming",
        "pages": 464,
        "isbn": "978-0132350884",
    }
    data.update(overrides)
    return BookCreate(**data)


async def test_create_book_saves_and_enriches(service, fake_ol_client):
    book = await service.create_book(make_book())

    assert book.title == "Clean Code"
    assert book.isbn == "9780132350884"  # ISBN нормализован
    assert book.extra == {"cover_url": "https://example.com/c.jpg"}
    assert fake_ol_client.calls[0]["isbn"] == "9780132350884"


async def test_create_book_with_future_year_fails(service):
    next_year = datetime.now().year + 1
    with pytest.raises(InvalidYearException):
        await service.create_book(make_book(year=next_year))


async def test_create_book_with_duplicate_isbn_fails(service):
    await service.create_book(make_book())
    # Тот же ISBN, но записанный по-другому — всё равно дубликат.
    with pytest.raises(BookAlreadyExistsException):
        await service.create_book(make_book(title="Other", isbn="9780132350884"))


async def test_create_book_when_open_library_is_down(fake_repo, failing_ol_client):
    service = BookService(fake_repo, failing_ol_client)

    book = await service.create_book(make_book())

    assert book.extra is None  # книга создана, просто без обогащения


async def test_create_book_when_open_library_times_out(fake_repo):
    client = FakeOpenLibraryClient(error=OpenLibraryTimeoutException(10.0))
    service = BookService(fake_repo, client)

    book = await service.create_book(make_book())

    assert book.extra is None


async def test_get_missing_book_raises_not_found(service):
    with pytest.raises(BookNotFoundException):
        await service.get_book(uuid.uuid4())


async def test_update_changes_only_passed_fields(service):
    created = await service.create_book(make_book())

    updated = await service.update_book(created.book_id, BookUpdate(available=False))

    assert updated.available is False
    assert updated.title == "Clean Code"


async def test_update_to_taken_isbn_fails(service):
    await service.create_book(make_book(isbn="0306406152"))
    other = await service.create_book(make_book(title="Other", isbn=None))

    with pytest.raises(BookAlreadyExistsException):
        await service.update_book(other.book_id, BookUpdate(isbn="0-306-40615-2"))


async def test_delete_missing_book_raises_not_found(service):
    with pytest.raises(BookNotFoundException):
        await service.delete_book(uuid.uuid4())


async def test_search_returns_page_and_total(service):
    for i in range(5):
        await service.create_book(make_book(title=f"Book {i}", isbn=None))

    books, total = await service.search_books(title="book", limit=2, offset=0)

    assert total == 5
    assert len(books) == 2
