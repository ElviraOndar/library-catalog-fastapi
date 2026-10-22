"""
Базовые исключения приложения и их обработчики.

Идея: сервисы ничего не знают про HTTP и бросают свои исключения
(AppException и наследники). А здесь, в одном месте, мы говорим FastAPI,
как превращать такие исключения в HTTP-ответы с нужным статус-кодом.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppException(Exception):
    """Базовое исключение приложения: сообщение + HTTP статус-код."""

    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundException(AppException):
    """Запрошенный ресурс не найден (404)."""

    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} with id '{identifier}' not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Зарегистрировать обработчики исключений в приложении."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        """Наши ожидаемые ошибки → JSON с их статус-кодом."""
        logger.info(
            "%s %s -> %s: %s",
            request.method,
            request.url.path,
            exc.status_code,
            exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Неожиданные ошибки → 500 без деталей наружу, но с логом."""
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
