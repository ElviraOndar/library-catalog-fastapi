"""
Pydantic-схемы книги (DTO — объекты передачи данных между API и клиентом).

Отдельные схемы для разных операций:
- BookCreate — что клиент присылает при создании;
- BookUpdate — что можно частично обновить (все поля опциональны);
- ShowBook  — что API отдаёт наружу.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def normalize_isbn(value: str | None) -> str | None:
    """
    Проверить ISBN и привести к единому виду (только цифры и X).

    "978-0-13-235088-4" и "9780132350884" — это один и тот же ISBN.
    Если хранить их по-разному, проверка уникальности не сработает,
    поэтому сохраняем «чистую» форму.
    """
    if value is None:
        return None

    clean = value.replace("-", "").replace(" ", "").upper()

    if len(clean) not in (10, 13):
        raise ValueError("ISBN must be 10 or 13 digits")

    # X допускается только последним символом ISBN-10 (контрольная цифра = 10).
    body, last = clean[:-1], clean[-1]
    if not body.isdigit() or not (last.isdigit() or (last == "X" and len(clean) == 10)):
        raise ValueError("ISBN must contain only digits (and X at the end of ISBN-10)")

    return clean


# Эти колонки в БД NOT NULL — в PATCH явный null для них недопустим.
NOT_NULLABLE_FIELDS = ("title", "author", "year", "genre", "pages", "available")


class BookBase(BaseModel):
    """Общие поля книги."""

    title: str = Field(..., min_length=1, max_length=500)
    author: str = Field(..., min_length=1, max_length=300)
    year: int = Field(..., ge=1000, le=2100)
    genre: str = Field(..., min_length=1, max_length=100)
    pages: int = Field(..., gt=0)


class BookCreate(BookBase):
    """Тело запроса на создание книги."""

    isbn: str | None = Field(None, min_length=10, max_length=20)
    description: str | None = Field(None, max_length=5000)

    @field_validator("isbn")
    @classmethod
    def validate_isbn(cls, value: str | None) -> str | None:
        """Валидация и нормализация ISBN."""
        return normalize_isbn(value)

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "Clean Code",
                    "author": "Robert Martin",
                    "year": 2008,
                    "genre": "Programming",
                    "pages": 464,
                    "isbn": "978-0132350884",
                    "description": "A Handbook of Agile Software Craftsmanship",
                }
            ]
        }
    )


class BookUpdate(BaseModel):
    """Тело запроса на частичное обновление (PATCH): все поля опциональны."""

    title: str | None = Field(None, min_length=1, max_length=500)
    author: str | None = Field(None, min_length=1, max_length=300)
    year: int | None = Field(None, ge=1000, le=2100)
    genre: str | None = Field(None, min_length=1, max_length=100)
    pages: int | None = Field(None, gt=0)
    available: bool | None = None
    isbn: str | None = Field(None, min_length=10, max_length=20)
    description: str | None = Field(None, max_length=5000)

    @field_validator("isbn")
    @classmethod
    def validate_isbn(cls, value: str | None) -> str | None:
        """Та же проверка ISBN, что и при создании."""
        return normalize_isbn(value)

    @model_validator(mode="after")
    def forbid_null_for_required(self) -> "BookUpdate":
        """
        Запретить {"title": null}.

        Не передать поле — значит «не менять». А передать null для
        обязательного поля — значит сломать запись (в БД NOT NULL).
        isbn и description обнулять можно.
        """
        for field in NOT_NULLABLE_FIELDS:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"Field '{field}' cannot be null")
        return self

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"available": False}, {"pages": 480}]}
    )


class ShowBook(BookBase):
    """Книга в ответе API."""

    book_id: UUID
    available: bool
    isbn: str | None
    description: str | None
    extra: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,  # позволяет ShowBook.model_validate(orm_объект)
        json_schema_extra={
            "examples": [
                {
                    "book_id": "123e4567-e89b-12d3-a456-426614174000",
                    "title": "Clean Code",
                    "author": "Robert Martin",
                    "year": 2008,
                    "genre": "Programming",
                    "pages": 464,
                    "available": True,
                    "isbn": "9780132350884",
                    "description": "A Handbook of Agile Software Craftsmanship",
                    "extra": {
                        "cover_url": "https://covers.openlibrary.org/b/id/123-L.jpg",
                        "subjects": ["Computer Science", "Software Engineering"],
                    },
                    "created_at": "2024-01-01T12:00:00Z",
                    "updated_at": "2024-01-01T12:00:00Z",
                }
            ]
        },
    )


class BookFilters(BaseModel):
    """Фильтры поиска книг (используются как query-параметры GET /books)."""

    title: str | None = Field(None, description="Поиск по названию (частичное совпадение)")
    author: str | None = Field(None, description="Поиск по автору (частичное совпадение)")
    genre: str | None = Field(None, description="Точное совпадение жанра")
    year: int | None = Field(None, description="Точное совпадение года")
    available: bool | None = Field(None, description="Фильтр по доступности")
