"""Blogger OAuth connection service (persistent refresh token)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.core.oauth import (
    exchange_code_for_token,
    fetch_access_token,
    fetch_blog_name,
    fetch_user_email,
)
from app.models.base import utcnow
from app.models.blogger_connection import BloggerConnection
from app.repositories.blogger_connection import BloggerConnectionRepository


class BloggerConnectionService:
    """Manages the persisted Blogger OAuth connection."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._repo = BloggerConnectionRepository(session)

    async def get_current(self) -> BloggerConnection | None:
        return await self._repo.get_current()

    async def is_connected(self) -> bool:
        connection = await self.get_current()
        return bool(connection and (connection.refresh_token or "").strip())

    async def get_refresh_token(self) -> str:
        """Return the stored refresh token or raise a clear validation error."""
        connection = await self.get_current()
        token = connection.refresh_token if connection else None
        if not (token or "").strip():
            raise ValidationError(
                "Blogger is not connected. Connect Blogger before publishing live."
            )
        return token

    async def connect(self, code: str, transport=None) -> dict:
        """Exchange an authorization code and persist the connection."""
        data = await exchange_code_for_token(code, transport=transport)
        refresh_token = data.get("refresh_token")

        # Google only returns a refresh token on first consent. If it is absent,
        # keep any previously stored token so a re-auth does not disconnect us.
        if not refresh_token:
            existing = await self.get_current()
            refresh_token = existing.refresh_token if existing else None
        if not (refresh_token or "").strip():
            raise ValidationError(
                "Google did not return a refresh token. Re-authorize with "
                "prompt=consent to obtain one."
            )

        access_token = data.get("access_token")
        email = await fetch_user_email(access_token, transport=transport) if access_token else None
        blog_name = (
            await fetch_blog_name(access_token, settings.google_blog_id, transport=transport)
            if access_token and settings.google_blog_id.strip()
            else None
        )

        connection = await self.get_current() or BloggerConnection()
        connection.refresh_token = refresh_token
        connection.blog_id = settings.google_blog_id.strip() or None
        connection.blog_name = blog_name
        connection.email = email
        connection.connected_at = utcnow()
        await self._repo.save(connection)
        await self.session.commit()

        return {
            "connected": True,
            "blog_id": connection.blog_id,
            "blog_name": connection.blog_name,
            "email": connection.email,
        }

    async def disconnect(self) -> None:
        await self._repo.clear()
        await self.session.commit()

    async def status(self) -> dict:
        connection = await self.get_current()
        if not connection or not (connection.refresh_token or "").strip():
            return {
                "connected": False,
                "blog_id": settings.google_blog_id.strip() or None,
                "blog_name": None,
                "email": None,
                "connected_at": None,
            }
        return {
            "connected": True,
            "blog_id": connection.blog_id,
            "blog_name": connection.blog_name,
            "email": connection.email,
            "connected_at": connection.connected_at,
        }

    async def get_access_token(self, transport=None) -> str:
        """Return a fresh access token using the stored refresh token."""
        refresh_token = await self.get_refresh_token()
        return await fetch_access_token(refresh_token, transport=transport)
