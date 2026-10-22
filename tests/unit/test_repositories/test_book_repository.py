"""Тесты BookRepository на настоящей PostgreSQL (тестовая БД)."""

import uuid

from src.library_catalog.data.repositories.book_repository import BookRepository


def book_kwargs(**overrides) -> dict:
    data = {
        "title": "Clean Code",
        "author": "Robert Martin",
        "year": 2008,
        "genre": "Programming",
        "pages": 464,
    }
    data.update(overrides)
    return data


async def test_create_and_get_by_id(db_session):
    repo = BookRepository(db_session)

    created = await repo.create(**book_kwargs(isbn="9780132350884"))
    found = await repo.get_by_id(created.book_id)

    assert found is not None
    assert found.title == "Clean Code"
    assert found.available is True  # значение по умолчанию
    assert found.created_at is not None  # заполнила сама БД


async def test_update_changes_fields_and_updated_at(db_session):
    repo = BookRepository(db_session)
    book = await repo.create(**book_kwargs())
    old_updated_at = book.updated_at

    updated = await repo.update(book.book_id, pages=500)

    assert updated is not None
    assert updated.pages == 500
    assert updated.updated_at >= old_updated_at


async def test_update_and_delete_missing_return_none_false(db_session):
    repo = BookRepository(db_session)
    missing = uuid.uuid4()

    assert await repo.update(missing, pages=1) is None
    assert await repo.delete(missing) is False


async def test_delete(db_session):
    repo = BookRepository(db_session)
    book = await repo.create(**book_kwargs())

    assert await repo.delete(book.book_id) is True
    assert await repo.get_by_id(book.book_id) is None


async def test_find_by_isbn(db_session):
    repo = BookRepository(db_session)
    await repo.create(**book_kwargs(isbn="9780132350884"))

    assert await repo.find_by_isbn("9780132350884") is not None
    assert await repo.find_by_isbn("0000000000") is None


async def test_filters_and_count(db_session):
    repo = BookRepository(db_session)
    await repo.create(**book_kwargs(title="Clean Code"))
    await repo.create(**book_kwargs(title="Clean Architecture", year=2017))
    await repo.create(**book_kwargs(title="Dune", author="Frank Herbert", genre="Sci-Fi"))
    await repo.create(**book_kwargs(title="Refactoring", author="Martin Fowler", available=False))

    # ilike: подстрока без учёта регистра
    assert await repo.count_by_filters(title="clean") == 2
    assert await repo.count_by_filters(author="MARTIN") == 3
    assert await repo.count_by_filters(genre="Sci-Fi") == 1
    assert await repo.count_by_filters(year=2017) == 1
    assert await repo.count_by_filters(available=False) == 1
    assert await repo.count_by_filters(title="clean", year=2008) == 1

    page = await repo.find_by_filters(author="martin", limit=2, offset=0)
    rest = await repo.find_by_filters(author="martin", limit=2, offset=2)
    assert len(page) == 2
    assert len(rest) == 1
    assert {b.book_id for b in page}.isdisjoint({b.book_id for b in rest})
