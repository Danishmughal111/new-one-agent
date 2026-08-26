"""Blogger OAuth connection model (persistent refresh token)."""

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, new_uuid


class BloggerConnection(Base, TimestampMixin):
    """Persisted Google OAuth authorization for a single Blogger account.

    A singleton record stores the refresh token so publishing keeps working
    after backend restarts or Uvicorn reloads. The refresh token is a secret
    and is NEVER returned through API responses.
    """

    __tablename__ = "blogger_connection"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    blog_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    blog_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<BloggerConnection id={self.id} blog_id={self.blog_id!r}>"
