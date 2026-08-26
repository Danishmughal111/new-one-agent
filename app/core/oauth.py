"""Google OAuth 2.0 helpers for Blogger API v3.

Implements the minimum server-side flow for a single owner account:
- build an authorization URL (offline access so a refresh token is issued)
- exchange the authorization code for tokens
- reuse the refresh token to obtain a fresh access token

Secrets (client secret, refresh/access tokens) are never logged.
"""

from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.core.exceptions import ValidationError

TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
SCOPE = "https://www.googleapis.com/auth/blogger"
USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
BLOGGER_API = "https://www.googleapis.com/blogger/v3"


def build_authorization_url(state: str = "trendera") -> str:
    """Build the Google OAuth consent URL for the Blogger scope."""
    if not settings.google_oauth_client_id.strip():
        raise ValidationError("Google OAuth client ID is not configured")

    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_token(code: str, transport: httpx.AsyncBaseTransport | None = None) -> dict:
    """Exchange an authorization code for access + refresh tokens."""
    payload = {
        "code": code,
        "client_id": settings.google_oauth_client_id,
        "client_secret": settings.google_oauth_client_secret,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "grant_type": "authorization_code",
    }
    return await _post_form(TOKEN_URL, payload, transport=transport)


async def fetch_access_token(
    refresh_token: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    """Return a fresh access token using the provided refresh token."""
    payload = {
        "client_id": settings.google_oauth_client_id,
        "client_secret": settings.google_oauth_client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    data = await _post_form(TOKEN_URL, payload, transport=transport)
    return data["access_token"]


async def fetch_user_email(
    access_token: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str | None:
    """Best-effort fetch of the authorized account's email address."""
    try:
        async with httpx.AsyncClient(transport=transport, timeout=30) as client:
            response = await client.get(
                USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            return response.json().get("email")
    except Exception:  # noqa: BLE001 - optional enrichment, never fatal
        return None


async def fetch_blog_name(
    access_token: str,
    blog_id: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str | None:
    """Best-effort fetch of the Blogger blog name."""
    if not blog_id:
        return None
    try:
        async with httpx.AsyncClient(transport=transport, timeout=30) as client:
            response = await client.get(
                f"{BLOGGER_API}/blogs/{blog_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return response.json().get("name")
    except Exception:  # noqa: BLE001 - optional enrichment, never fatal
        return None


async def _post_form(
    url: str,
    payload: dict,
    transport: httpx.AsyncBaseTransport | None,
) -> dict:
    async with httpx.AsyncClient(transport=transport, timeout=60) as client:
        response = await client.post(url, data=payload)
        response.raise_for_status()
        return response.json()