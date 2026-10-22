"""Репозиторий книг: CRUD из базового класса + поиск и подсчёт."""

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.book import Book
from .base_repository import BaseRepository


class BookRepository(BaseRepository[Book]):
    """Доступ к таблице books."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Book)

    async def find_by_filters(
        self,
        title: str | None = None,
        author: str | None = None,
        genre: str | None = None,
        year: int | None = None,
        available: bool | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Book]:
        """
        Найти книги по фильтрам (None = фильтр не применяется).

        Сортируем по дате создания (новые сверху) и по id — стабильный порядок
        нужен, чтобы пагинация не «прыгала» между страницами.
        """
        stmt = self._apply_filters(
            select(Book),
            title=title,
            author=author,
            genre=genre,
            year=year,
            available=available,
        )
        stmt = stmt.order_by(Book.created_at.desc(), Book.book_id).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_filters(
        self,
        title: str | None = None,
        author: str | None = None,
        genre: str | None = None,
        year: int | None = None,
        available: bool | None = None,
    ) -> int:
        """Посчитать, сколько книг подходит под фильтры (для пагинации)."""
        stmt = self._apply_filters(
            select(func.count()).select_from(Book),
            title=title,
            author=author,
            genre=genre,
            year=year,
            available=available,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def find_by_isbn(self, isbn: str) -> Book | None:
        """Найти книгу по ISBN."""
        stmt = select(Book).where(Book.isbn == isbn)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _apply_filters(
        stmt: Select,
        title: str | None,
        author: str | None,
        genre: str | None,
        year: int | None,
        available: bool | None,
    ) -> Select:
        """
        Добавить WHERE-условия к запросу.

        Вынесено в отдельный метод, чтобы find_by_filters и count_by_filters
        гарантированно фильтровали одинаково (и не дублировать код).
        """
        if title:
            stmt = stmt.where(Book.title.ilike(f"%{title}%"))
        if author:
            stmt = stmt.where(Book.author.ilike(f"%{author}%"))
        if genre:
            stmt = stmt.where(Book.genre == genre)
        if year is not None:
            stmt = stmt.where(Book.year == year)
        if available is not None:
            stmt = stmt.where(Book.available == available)
        return stmt
