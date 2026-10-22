"""
Dependency Injection: «фабрики», из которых FastAPI собирает объекты.

Цепочка для одного запроса:
    get_db() → AsyncSession
        └→ get_book_repository(session) → BookRepository
               └→ get_book_service(repo, client) → BookService
    get_openlibrary_client() → один OpenLibraryClient на всё приложение
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.database import get_db
from ..data.repositories.book_repository import BookRepository
from ..domain.services.book_service import BookService
from ..external.openlibrary.client import OpenLibraryClient

# ========== EXTERNAL CLIENTS (Singletons) ==========


@lru_cache
def get_openlibrary_client() -> OpenLibraryClient:
    """
    Singleton OpenLibraryClient.

    lru_cache у функции без аргументов = «создать один раз и запомнить».
    Так все запросы используют общий пул HTTP-соединений.
    Закрывается клиент в lifespan (main.py) при остановке приложения.
    """
    return OpenLibraryClient(
        base_url=settings.openlibrary_base_url,
        timeout=settings.openlibrary_timeout,
    )


# ========== REPOSITORIES ==========


async def get_book_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BookRepository:
    """Новый репозиторий на каждый запрос (у каждого запроса своя сессия)."""
    return BookRepository(db)


# ========== SERVICES ==========


async def get_book_service(
    book_repo: Annotated[BookRepository, Depends(get_book_repository)],
    ol_client: Annotated[OpenLibraryClient, Depends(get_openlibrary_client)],
) -> BookService:
    """Собрать BookService из готовых зависимостей."""
    return BookService(
        book_repository=book_repo,
        openlibrary_client=ol_client,
    )


# ========== TYPE ALIASES ==========
# В роутере достаточно написать `service: BookServiceDep`.

BookServiceDep = Annotated[BookService, Depends(get_book_service)]
BookRepoDep = Annotated[BookRepository, Depends(get_book_repository)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db)]
