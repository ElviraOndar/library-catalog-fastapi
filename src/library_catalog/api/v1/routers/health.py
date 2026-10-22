"""Health check: жив ли сервис и есть ли связь с БД."""

import logging

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from ...dependencies import DbSessionDep
from ..schemas.common import HealthCheckResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "",
    response_model=HealthCheckResponse,
    summary="Health Check",
    responses={503: {"model": HealthCheckResponse, "description": "БД недоступна"}},
)
async def health_check(db: DbSessionDep, response: Response) -> HealthCheckResponse:
    """
    Проверить состояние сервиса.

    Делает `SELECT 1` в БД. Если база недоступна — отвечает 503,
    чтобы балансировщик/оркестратор понял, что сервис нездоров.
    """
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check: database is unavailable")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthCheckResponse(status="unhealthy", database="disconnected")

    return HealthCheckResponse(status="healthy", database="connected")
