"""Async database engine, session factory, and declarative base.

Uses SQLAlchemy 2.0 async APIs. PostgreSQL (via asyncpg) is the production
database; SQLite (via aiosqlite) is used only for the automated test suite.

We intentionally keep this layer free of PostgreSQL-specific SQL for the
models themselves so the SQLite test suite remains portable.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.models.base import Base

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session per request."""
    async with async_session_factory() as session:
        yield session


async def create_all() -> None:
    """Create all tables (development/test convenience only).

    Production should use Alembic migrations instead.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all() -> None:
    """Drop all tables (test convenience only)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)