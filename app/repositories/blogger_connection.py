"""Blogger connection persistence (singleton row)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blogger_connection import BloggerConnection
from app.repositories.base import BaseRepository


class BloggerConnectionRepository(BaseRepository[BloggerConnection]):
    """Persistence for the single Blogger OAuth connection record."""

    model = BloggerConnection

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_current(self) -> BloggerConnection | None:
        """Return the most recent connection record, or None."""
        stmt = select(BloggerConnection).order_by(BloggerConnection.created_at.desc()).limit(1)
        result = await self.session.scalars(stmt)
        return result.first()

    async def save(self, connection: BloggerConnection) -> BloggerConnection:
        """Persist ``connection`` as the current (single) record."""
        existing = await self.get_current()
        if existing is not None:
            existing.blog_id = connection.blog_id
            existing.blog_name = connection.blog_name
            existing.email = connection.email
            existing.refresh_token = connection.refresh_token
            existing.connected_at = connection.connected_at
            await self.session.flush()
            return existing
        self.session.add(connection)
        await self.session.flush()
        return connection

    async def clear(self) -> None:
        """Remove the stored connection."""
        existing = await self.get_current()
        if existing is not None:
            await self.session.delete(existing)
            await self.session.flush()
