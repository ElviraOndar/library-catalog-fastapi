"""Pydantic-схемы ответа Open Library /search.json."""

from pydantic import BaseModel, ConfigDict


class OpenLibrarySearchDoc(BaseModel):
    """Один документ (книга) из результатов поиска."""

    # Open Library присылает десятки полей; лишние просто игнорируем.
    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    author_name: list[str] | None = None
    cover_i: int | None = None
    subject: list[str] | None = None
    publisher: list[str] | None = None
    language: list[str] | None = None
    ratings_average: float | None = None


class OpenLibrarySearchResponse(BaseModel):
    """Ответ /search.json целиком."""

    model_config = ConfigDict(extra="ignore")

    numFound: int = 0
    docs: list[OpenLibrarySearchDoc] = []
