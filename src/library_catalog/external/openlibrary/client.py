"""Клиент Open Library API (https://openlibrary.org/dev/docs/api/search)."""

from typing import Any

import httpx
from pydantic import ValidationError

from ...domain.exceptions import OpenLibraryException, OpenLibraryTimeoutException
from ..base.base_client import BaseApiClient
from .schemas import OpenLibrarySearchDoc, OpenLibrarySearchResponse

COVER_URL_TEMPLATE = "https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"

# Просим у API только нужные поля — ответ получается в разы меньше.
SEARCH_FIELDS = "title,author_name,cover_i,subject,publisher,language,ratings_average"


class OpenLibraryClient(BaseApiClient):
    """Поиск книг в Open Library и извлечение доп. данных."""

    def __init__(
        self,
        base_url: str = "https://openlibrary.org",
        timeout: float = 10.0,
    ):
        super().__init__(
            base_url,
            timeout=timeout,
            # Open Library просит указывать User-Agent с названием приложения.
            headers={"User-Agent": "LibraryCatalogAPI/1.0 (learning project)"},
        )

    def client_name(self) -> str:
        return "openlibrary"

    async def search_by_isbn(self, isbn: str) -> dict[str, Any]:
        """Найти книгу по ISBN-10/ISBN-13. Пустой dict, если не найдено."""
        return await self._search_first({"isbn": isbn})

    async def search_by_title_author(self, title: str, author: str) -> dict[str, Any]:
        """Найти книгу по названию и автору. Пустой dict, если не найдено."""
        return await self._search_first({"title": title, "author": author})

    async def enrich(
        self,
        title: str,
        author: str,
        isbn: str | None = None,
    ) -> dict[str, Any]:
        """
        Получить доп. данные о книге.

        Сначала ищем по ISBN (самый точный способ), если не нашли —
        по названию и автору.
        """
        if isbn:
            data = await self.search_by_isbn(isbn)
            if data:
                return data
        return await self.search_by_title_author(title, author)

    async def _search_first(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Выполнить /search.json и вернуть данные первого результата.

        Все низкоуровневые ошибки (httpx, кривой JSON) превращаются
        в доменные исключения — сервису не нужно знать про httpx.
        """
        try:
            raw = await self._get(
                "/search.json",
                params={**params, "limit": 1, "fields": SEARCH_FIELDS},
            )
            response = OpenLibrarySearchResponse.model_validate(raw)
        except httpx.TimeoutException as exc:
            raise OpenLibraryTimeoutException(self.timeout) from exc
        except httpx.HTTPError as exc:
            raise OpenLibraryException(str(exc)) from exc
        except (ValueError, ValidationError) as exc:  # невалидный JSON / схема
            raise OpenLibraryException(f"Unexpected response format: {exc}") from exc

        if not response.docs:
            self.logger.info("Nothing found for %s", params)
            return {}
        return self._extract_book_data(response.docs[0])

    def _extract_book_data(self, doc: OpenLibrarySearchDoc) -> dict[str, Any]:
        """Оставить из документа только то, что сохраним в Book.extra."""
        result: dict[str, Any] = {}

        if cover_url := self._get_cover_url(doc.cover_i):
            result["cover_url"] = cover_url
        if doc.subject:
            result["subjects"] = doc.subject[:10]
        if doc.publisher:
            result["publisher"] = doc.publisher[0]
        if doc.language:
            result["language"] = doc.language[0]
        if doc.ratings_average is not None:
            result["rating"] = round(doc.ratings_average, 2)

        return result

    @staticmethod
    def _get_cover_url(cover_id: int | None) -> str | None:
        """URL обложки по её id."""
        if not cover_id:
            return None
        return COVER_URL_TEMPLATE.format(cover_id=cover_id)
