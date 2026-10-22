"""Базовый generic-репозиторий с CRUD-операциями."""

from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import Base

# T — «любая ORM-модель». bound=Base не даст подставить сюда посторонний класс.
T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """
    Общие операции с БД для любой модели.

    Наследник указывает конкретную модель: BaseRepository[Book],
    и все методы автоматически становятся типизированными под Book.
    """

    def __init__(self, session: AsyncSession, model: type[T]):
        self.session = session
        self.model = model

    async def create(self, **kwargs: Any) -> T:
        """Создать запись и вернуть её со значениями, сгенерированными БД."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.commit()
        # refresh подтягивает поля, которые заполнила сама БД (created_at и т.п.)
        await self.session.refresh(instance)
        return instance

    async def get_by_id(self, id: UUID) -> T | None:
        """
        Получить запись по первичному ключу.

        session.get() сам знает, какое поле является primary key модели
        (id, book_id, user_id...), поэтому метод подходит для любой модели.
        """
        return await self.session.get(self.model, id)

    async def update(self, id: UUID, **kwargs: Any) -> T | None:
        """Обновить переданные поля записи. Вернуть None, если записи нет."""
        instance = await self.get_by_id(id)
        if instance is None:
            return None

        for field, value in kwargs.items():
            setattr(instance, field, value)

        await self.session.commit()
        # updated_at обновляет сама БД (onupdate) — перечитываем запись.
        await self.session.refresh(instance)
        return instance

    async def delete(self, id: UUID) -> bool:
        """Удалить запись. Вернуть True, если она была удалена."""
        instance = await self.get_by_id(id)
        if instance is None:
            return False

        await self.session.delete(instance)
        await self.session.commit()
        return True

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[T]:
        """Получить записи с пагинацией."""
        stmt = select(self.model).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
