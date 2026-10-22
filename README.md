# Library Catalog API

REST API для управления библиотечным каталогом: CRUD книг, поиск с фильтрами,
пагинация, автоматическое обогащение данных из [Open Library](https://openlibrary.org).

**Стек:** FastAPI · SQLAlchemy 2 (async) · PostgreSQL 16 · Alembic · Pydantic 2 · httpx · Poetry

## Архитектура

```
api/        HTTP: роутеры, Pydantic-схемы, Dependency Injection   (тонкий слой)
domain/     бизнес-логика: BookService, исключения, маппер         (вся логика)
data/       БД: ORM-модель Book, репозитории                       (только SQL)
external/   внешние API: клиент Open Library с retry               (только HTTP наружу)
core/       настройки, подключение к БД, логирование, обработчики ошибок
```

Запрос идёт сверху вниз: `роутер → BookService → BookRepository / OpenLibraryClient`.

## Быстрый старт

Нужны: Python 3.11+, Poetry, Docker.

```bash
poetry install                      # зависимости + виртуальное окружение
cp .env.example .env                # локальные настройки
docker compose up -d postgres       # PostgreSQL в контейнере
poetry run alembic upgrade head     # создать таблицы
poetry run uvicorn src.library_catalog.main:app --reload
```

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Health check: http://127.0.0.1:8000/api/v1/health

## Эндпоинты

| Метод  | Путь                    | Описание                                  | Коды             |
|--------|-------------------------|-------------------------------------------|------------------|
| POST   | `/api/v1/books`         | Создать книгу (+ обогащение Open Library) | 201, 400, 409, 422 |
| GET    | `/api/v1/books`         | Список: `title`, `author`, `genre`, `year`, `available`, `page`, `page_size` | 200, 422 |
| GET    | `/api/v1/books/{id}`    | Книга по ID                               | 200, 404         |
| PATCH  | `/api/v1/books/{id}`    | Частичное обновление                      | 200, 400, 404, 409, 422 |
| DELETE | `/api/v1/books/{id}`    | Удалить                                   | 204, 404         |
| GET    | `/api/v1/health`        | Состояние сервиса и БД                    | 200, 503         |

## Тесты и качество кода

```bash
# Тестам репозитория нужна отдельная БД (один раз):
docker compose exec postgres createdb -U postgres library_catalog_test

poetry run pytest            # 29 тестов: сервис, репозиторий, клиент Open Library, API
poetry run ruff check .      # линтер
poetry run black .           # форматирование
poetry run mypy src          # проверка типов
```

Если тестовая БД недоступна, тесты репозитория пропускаются (skip), остальные работают без БД и интернета.

## Миграции

```bash
poetry run alembic revision --autogenerate -m "описание изменений"
poetry run alembic upgrade head      # применить
poetry run alembic downgrade -1      # откатить последнюю
poetry run alembic current           # текущая версия
```
