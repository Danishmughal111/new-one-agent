"""Blogger OAuth connection schemas."""

from datetime import datetime

from app.schemas.common import ORMModel


class BloggerStatusResponse(ORMModel):
    """Connection status (never exposes tokens or secrets)."""

    connected: bool
    blog_id: str | None = None
    blog_name: str | None = None
    email: str | None = None
    connected_at: datetime | None = None
