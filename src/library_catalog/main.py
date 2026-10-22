"""
Library Catalog API — точка входа приложения.

Запуск из корня проекта:
    poetry run uvicorn src.library_catalog.main:app --reload
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.dependencies import get_openlibrary_client
from .api.v1.routers import books, health
from .core.config import settings
from .core.database import dispose_engine, init_db
from .core.exceptions import register_exception_handlers
from .core.logging_config import setup_logging

logger = logging.getLogger(__name__)


# ========== LIFECYCLE ==========


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Код до yield — при старте приложения, после yield — при остановке.

    startup: логирование, проверка БД;
    shutdown: закрыть HTTP-клиент Open Library и пул соединений с БД.
    """
    setup_logging()
    await init_db()
    logger.info("🚀 %s started (%s)", settings.app_name, settings.environment)

    yield

    if get_openlibrary_client.cache_info().currsize:
        await get_openlibrary_client().close()
        get_openlibrary_client.cache_clear()
    await dispose_engine()
    logger.info("👋 Application stopped")


# ========== APP ==========

app = FastAPI(
    title=settings.app_name,
    description="REST API для управления библиотечным каталогом",
    version="1.0.0",
    docs_url=settings.docs_url,
    redoc_url=settings.redoc_url,
    lifespan=lifespan,
)

# CORS — разрешаем браузерным фронтендам с других доменов обращаться к API.
# Браузеры запрещают allow_credentials вместе с "*", поэтому включаем
# credentials только для явно перечисленных доменов.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials="*" not in settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(books.router, prefix=settings.api_v1_prefix)
app.include_router(health.router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """Корневой эндпоинт: приветствие и ссылка на документацию."""
    return {
        "message": "Welcome to Library Catalog API",
        "docs": settings.docs_url or "",
        "version": "1.0.0",
    }


if __name__ == "__main__":
    import uvicorn

    # В ТЗ здесь "main:app" — такой путь не найдётся при запуске из корня.
    uvicorn.run(
        "src.library_catalog.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
