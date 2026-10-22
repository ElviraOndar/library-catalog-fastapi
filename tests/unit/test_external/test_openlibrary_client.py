"""
Тесты OpenLibraryClient без интернета.

httpx.MockTransport позволяет подставить свою функцию вместо сети:
она получает запрос и возвращает заготовленный ответ.
"""

import httpx
import pytest

from src.library_catalog.domain.exceptions import (
    OpenLibraryException,
    OpenLibraryTimeoutException,
)
from src.library_catalog.external.openlibrary.client import OpenLibraryClient

SAMPLE_RESPONSE = {
    "numFound": 1,
    "docs": [
        {
            "title": "Clean Code",
            "author_name": ["Robert C. Martin"],
            "cover_i": 8065615,
            "subject": [f"Subject {i}" for i in range(15)],
            "publisher": ["Prentice Hall"],
            "language": ["eng"],
            "ratings_average": 4.3333,
        }
    ],
}


def make_client(handler) -> OpenLibraryClient:
    client = OpenLibraryClient(timeout=1.0)
    client.backoff = 0  # не ждать между повторами в тестах
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client


async def test_search_by_isbn_extracts_fields():
    seen_params = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(request.url.params)
        return httpx.Response(200, json=SAMPLE_RESPONSE)

    client = make_client(handler)
    data = await client.search_by_isbn("9780132350884")
    await client.close()

    assert seen_params["isbn"] == "9780132350884"
    assert data["cover_url"] == "https://covers.openlibrary.org/b/id/8065615-L.jpg"
    assert len(data["subjects"]) == 10
    assert data["publisher"] == "Prentice Hall"
    assert data["language"] == "eng"
    assert data["rating"] == 4.33


async def test_enrich_falls_back_to_title_author():
    def handler(request: httpx.Request) -> httpx.Response:
        if "isbn" in request.url.params:
            return httpx.Response(200, json={"numFound": 0, "docs": []})
        return httpx.Response(200, json=SAMPLE_RESPONSE)

    client = make_client(handler)
    data = await client.enrich("Clean Code", "Robert Martin", isbn="0000000000")
    await client.close()

    assert data["publisher"] == "Prentice Hall"


async def test_retries_on_5xx_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json=SAMPLE_RESPONSE)

    client = make_client(handler)
    data = await client.search_by_title_author("Clean Code", "Robert Martin")
    await client.close()

    assert calls["n"] == 3
    assert data


async def test_4xx_is_not_retried():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400)

    client = make_client(handler)
    with pytest.raises(OpenLibraryException):
        await client.search_by_isbn("9780132350884")
    await client.close()

    assert calls["n"] == 1


async def test_timeout_becomes_domain_exception():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    client = make_client(handler)
    with pytest.raises(OpenLibraryTimeoutException):
        await client.search_by_isbn("9780132350884")
    await client.close()
