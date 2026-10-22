"""Маппер: ORM-модель Book → DTO ShowBook."""

from ...api.v1.schemas.book import ShowBook
from ...data.models.book import Book


class BookMapper:
    """
    Преобразование сущности БД в схему ответа API.

    Зачем отдельный класс: правило «как книга выглядит снаружи» описано
    в одном месте. Если завтра поле переименуют — правим только здесь.
    """

    @staticmethod
    def to_show_book(book: Book) -> ShowBook:
        """Преобразовать одну книгу."""
        return ShowBook(
            book_id=book.book_id,
            title=book.title,
            author=book.author,
            year=book.year,
            genre=book.genre,
            pages=book.pages,
            available=book.available,
            isbn=book.isbn,
            description=book.description,
            extra=book.extra,
            created_at=book.created_at,
            updated_at=book.updated_at,
        )

    @staticmethod
    def to_show_books(books: list[Book]) -> list[ShowBook]:
        """Преобразовать список книг."""
        return [BookMapper.to_show_book(book) for book in books]
