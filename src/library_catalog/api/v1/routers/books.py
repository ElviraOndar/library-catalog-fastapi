"""
CRUD-эндпоинты для книг.

Роутеры «тонкие»: принять запрос → вызвать сервис → вернуть ответ.
Ошибки (404, 409, 400) бросает сервис, а в HTTP их превращают
обработчики из core/exceptions.py.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from ...dependencies import BookServiceDep
from ..schemas.book import BookCreate, BookUpdate, ShowBook
from ..schemas.common import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/books", tags=["Books"])

# Описание возможных ошибок — попадёт в Swagger.
NOT_FOUND: dict[int | str, dict[str, Any]] = {404: {"description": "Книга не найдена"}}


@router.post(
    "",
    response_model=ShowBook,
    status_code=status.HTTP_201_CREATED,
    summary="Создать книгу",
    responses={409: {"description": "Книга с таким ISBN уже есть"}},
)
async def create_book(book_data: BookCreate, service: BookServiceDep) -> ShowBook:
    """
    Создать новую книгу.

    Данные автоматически обогащаются из Open Library (обложка, темы,
    издатель, язык, рейтинг) и сохраняются в поле `extra`.
    Если Open Library недоступен, книга всё равно будет создана.
    """
    return await service.create_book(book_data)


@router.get(
    "",
    response_model=PaginatedResponse[ShowBook],
    summary="Получить список книг",
)
async def get_books(
    service: BookServiceDep,
    pagination: Annotated[PaginationParams, Depends()],
    title: Annotated[
        str | None, Query(description="Поиск по названию (частичное совпадение)")
    ] = None,
    author: Annotated[
        str | None, Query(description="Поиск по автору (частичное совпадение)")
    ] = None,
    genre: Annotated[str | None, Query(description="Фильтр по жанру (точное совпадение)")] = None,
    year: Annotated[int | None, Query(description="Фильтр по году")] = None,
    available: Annotated[bool | None, Query(description="Фильтр по доступности")] = None,
) -> PaginatedResponse[ShowBook]:
    """
    Список книг с фильтрами и пагинацией.

    - `title`, `author` — подстрока, без учёта регистра;
    - `genre`, `year`, `available` — точное совпадение;
    - `page` (с 1) и `page_size` (1–100, по умолчанию 20).
    """
    books, total = await service.search_books(
        title=title,
        author=author,
        genre=genre,
        year=year,
        available=available,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return PaginatedResponse[ShowBook].create(books, total, pagination)


@router.get(
    "/{book_id}",
    response_model=ShowBook,
    summary="Получить книгу",
    responses=NOT_FOUND,
)
async def get_book(book_id: UUID, service: BookServiceDep) -> ShowBook:
    """Получить книгу по ID."""
    return await service.get_book(book_id)


@router.patch(
    "/{book_id}",
    response_model=ShowBook,
    summary="Обновить книгу",
    responses={**NOT_FOUND, 409: {"description": "ISBN занят другой книгой"}},
)
async def update_book(
    book_id: UUID,
    book_data: BookUpdate,
    service: BookServiceDep,
) -> ShowBook:
    """Частичное обновление: передавайте только поля, которые меняются."""
    return await service.update_book(book_id, book_data)


@router.delete(
    "/{book_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить книгу",
    responses=NOT_FOUND,
)
async def delete_book(book_id: UUID, service: BookServiceDep) -> None:
    """Удалить книгу из каталога. При успехе — пустой ответ 204."""
    await service.delete_book(book_id)
