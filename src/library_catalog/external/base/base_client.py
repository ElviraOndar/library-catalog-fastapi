"""Базовый асинхронный HTTP-клиент для внешних API."""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx


class BaseApiClient(ABC):
    """
    Общая логика для всех клиентов внешних API.

    - один httpx.AsyncClient на всё время жизни (переиспользует соединения);
    - таймаут на каждый запрос;
    - повторные попытки (retry) с экспоненциальной задержкой
      для временных ошибок: таймаут, обрыв сети, ответы 5xx;
    - логирование.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        retries: int = 3,
        backoff: float = 0.5,
        headers: dict[str, str] | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self._client = httpx.AsyncClient(timeout=timeout, headers=headers)
        self.logger = logging.getLogger(self.client_name())

    @abstractmethod
    def client_name(self) -> str:
        """Имя клиента (используется как имя логгера)."""

    def _build_url(self, path: str) -> str:
        """Склеить base_url и путь."""
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def _wait_time(self, attempt: int) -> float:
        """Экспоненциальная задержка: 0.5с, 1с, 2с, ..."""
        return self.backoff * (2**attempt)

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """
        Выполнить HTTP-запрос с повторами и вернуть распарсенный JSON.

        Raises:
            httpx.TimeoutException: таймаут на последней попытке
            httpx.HTTPError: прочие сетевые/HTTP ошибки
        """
        url = self._build_url(path)

        for attempt in range(self.retries):
            is_last_attempt = attempt == self.retries - 1
            try:
                self.logger.debug("%s %s params=%s (attempt %d)", method, url, params, attempt + 1)
                response = await self._client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                    headers=headers,
                )
                response.raise_for_status()
                return response.json()

            except httpx.TransportError as exc:
                # Таймауты и сетевые сбои — временные, есть смысл повторить.
                if is_last_attempt:
                    self.logger.error(
                        "%s %s failed after %d attempts: %r", method, url, self.retries, exc
                    )
                    raise
                wait = self._wait_time(attempt)
                self.logger.warning("%r, retrying in %.1fs...", exc, wait)
                # ⚠️ В ТЗ здесь time.sleep(). В async-коде это блокирует
                # весь event loop — сервер перестаёт отвечать ВСЕМ клиентам.
                # Правильно — await asyncio.sleep().
                await asyncio.sleep(wait)

            except httpx.HTTPStatusError as exc:
                # 5xx — проблема на стороне сервера, можно повторить.
                # 4xx — ошибка в нашем запросе, повтор не поможет.
                if exc.response.status_code >= 500 and not is_last_attempt:
                    wait = self._wait_time(attempt)
                    self.logger.warning(
                        "Server error %d, retrying in %.1fs...", exc.response.status_code, wait
                    )
                    await asyncio.sleep(wait)
                else:
                    self.logger.error("HTTP error: %s", exc)
                    raise

        # Сюда не дойдём (на последней попытке всегда return или raise),
        # но mypy этого не знает.
        raise RuntimeError("Unreachable")

    async def _get(self, path: str, **kwargs: Any) -> Any:
        """GET-запрос."""
        return await self._request("GET", path, **kwargs)

    async def close(self) -> None:
        """Закрыть соединения HTTP-клиента."""
        await self._client.aclose()
