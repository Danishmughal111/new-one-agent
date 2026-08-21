"""Declarative base and shared mixins for all ORM models."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Return the current UTC timestamp (timezone-aware)."""
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    """Generate a new UUID as a 32-character hex string.

    Using a string (rather than a DB-native UUID type) keeps models portable
    across PostgreSQL and SQLite without requiring extra type handling.
    """
    return uuid4().hex


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` columns.

    Uses a naive UTC timestamp for maximum portability between
    PostgreSQL (timestamptz) and SQLite (no tz support).
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )