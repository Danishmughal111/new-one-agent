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
from sqlalchemy.pool import NullPool, StaticPool

from app.core.config import normalize_database_url, settings
from app.models.base import Base

_engine_kwargs: dict = {}
if settings.database_url.startswith("sqlite"):
    if ":memory:" in settings.database_url:
        # In-memory SQLite (tests) must reuse a single shared connection so
        # every session sees the same database and no file locking occurs.
        _engine_kwargs["poolclass"] = StaticPool
    else:
        # File-backed SQLite does not need pooling.
        _engine_kwargs["poolclass"] = NullPool

_database_url = normalize_database_url(settings.database_url)
engine = create_async_engine(
    _database_url,
    echo=settings.debug,
    future=True,
    **_engine_kwargs,
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
        if settings.database_url.startswith("sqlite"):
            await conn.run_sync(_ensure_sqlite_columns)


def _ensure_sqlite_columns(sync_conn) -> None:
    """Add columns introduced after the initial schema (SQLite dev only).

    ``Base.metadata.create_all`` never alters existing tables, so this helper
    adds missing nullable columns so an existing ``dev.db`` keeps working after
    model changes without dropping data.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(sync_conn)
    existing = {column["name"] for column in inspector.get_columns("trendera_articles")}
    additions = {
        "blogger_post_id": "VARCHAR(255)",
        "blogger_url": "TEXT",
        "published_at": "DATETIME",
        "metadata": "TEXT",
    }
    for name, typ in additions.items():
        if name not in existing:
            sync_conn.execute(text(f"ALTER TABLE trendera_articles ADD COLUMN {name} {typ}"))

    existing_products = {column["name"] for column in inspector.get_columns("trendera_products")}
    if "affiliate_url" not in existing_products:
        sync_conn.execute(text("ALTER TABLE trendera_products ADD COLUMN affiliate_url TEXT"))


async def drop_all() -> None:
    """Drop all tables (test convenience only)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
