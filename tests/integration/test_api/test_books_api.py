"""
Интеграционные тесты HTTP API.

Проверяем всю цепочку «HTTP → роутер → сервис → ответ»: статус-коды,
формат JSON, валидацию и обработчики исключений. Хранилище — фейковое
(см. фикстуру client в conftest.py), поэтому тесты быстрые.
"""

BOOK = {
    "title": "Clean Code",
    "author": "Robert Martin",
    "year": 2008,
    "genre": "Programming",
    "pages": 464,
    "isbn": "978-0132350884",
}
URL = "/api/v1/books"


def test_create_book_returns_201(client):
    response = client.post(URL, json=BOOK)

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Clean Code"
    assert body["available"] is True
    assert "book_id" in body


def test_duplicate_isbn_returns_409(client):
    client.post(URL, json=BOOK)
    response = client.post(URL, json=BOOK)

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_invalid_body_returns_422(client):
    response = client.post(URL, json={**BOOK, "pages": 0, "isbn": "abc"})

    assert response.status_code == 422


def test_future_year_returns_400(client):
    response = client.post(URL, json={**BOOK, "year": 2099})

    assert response.status_code == 400


def test_get_update_delete_flow(client):
    book_id = client.post(URL, json=BOOK).json()["book_id"]

    assert client.get(f"{URL}/{book_id}").status_code == 200

    patched = client.patch(f"{URL}/{book_id}", json={"available": False})
    assert patched.status_code == 200
    assert patched.json()["available"] is False

    assert client.delete(f"{URL}/{book_id}").status_code == 204
    assert client.get(f"{URL}/{book_id}").status_code == 404


def test_patch_with_null_required_field_returns_422(client):
    book_id = client.post(URL, json=BOOK).json()["book_id"]

    response = client.patch(f"{URL}/{book_id}", json={"title": None})

    assert response.status_code == 422


def test_list_with_filters_and_pagination(client):
    for i in range(3):
        client.post(URL, json={**BOOK, "title": f"Python {i}", "isbn": None})
    client.post(URL, json={**BOOK, "title": "Dune", "author": "Frank Herbert", "isbn": None})

    response = client.get(URL, params={"title": "python", "page": 1, "page_size": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["pages"] == 2
    assert len(body["items"]) == 2


def test_invalid_uuid_returns_422(client):
    assert client.get(f"{URL}/not-a-uuid").status_code == 422
