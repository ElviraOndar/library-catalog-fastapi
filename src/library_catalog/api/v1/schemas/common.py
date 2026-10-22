"""Общие схемы: пагинация и health check."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Параметры пагинации из query-строки: ?page=2&page_size=20."""

    page: int = Field(1, ge=1, description="Номер страницы (с 1)")
    page_size: int = Field(20, ge=1, le=100, description="Размер страницы")

    @property
    def offset(self) -> int:
        """Сколько записей пропустить (OFFSET в SQL)."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Сколько записей взять (LIMIT в SQL)."""
        return self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Универсальный ответ со списком и метаданными пагинации.

    Generic[T] позволяет написать PaginatedResponse[ShowBook] —
    и Swagger покажет, что items — это список книг.
    """

    items: list[T]
    total: int = Field(..., description="Всего элементов")
    page: int = Field(..., description="Текущая страница")
    page_size: int = Field(..., description="Размер страницы")
    pages: int = Field(..., description="Всего страниц")

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        pagination: PaginationParams,
    ) -> "PaginatedResponse[T]":
        """Собрать ответ, посчитав количество страниц (округление вверх)."""
        pages = (total + pagination.page_size - 1) // pagination.page_size
        return cls(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            pages=pages,
        )


class HealthCheckResponse(BaseModel):
    """Ответ health check."""

    status: str = "healthy"
    database: str = "connected"
