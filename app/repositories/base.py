"""Generic async base repository.

Provides common CRUD persistence operations. It remains intentionally thin —
no business rules, permission checks, or orchestration live here.
"""

from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Reusable async repository for a single ORM model."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, entity_id: str) -> ModelT | None:
        """Fetch a single entity by primary key, or None."""
        return await self.session.get(self.model, entity_id)

    async def list(self, offset: int = 0, limit: int = 100) -> list[ModelT]:
        """List entities with simple pagination."""
        stmt = select(self.model).offset(offset).limit(limit)
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def add(self, entity: ModelT) -> ModelT:
        """Persist a new entity (caller must commit)."""
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity: ModelT) -> None:
        """Remove an entity (caller must commit)."""
        await self.session.delete(entity)
        await self.session.flush()