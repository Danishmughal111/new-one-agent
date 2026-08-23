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

# In-memory token store. The refresh token may also be bootstrapped from
# ``GOOGLE_REFRESH_TOKEN`` so a single owner can reuse credentials without
# re-running the OAuth consent flow after the first time.
_refresh_token: str | None = None


def _get_refresh_token() -> str:
    token = _refresh_token or settings.google_refresh_token.strip() or None
    if not token:
        raise ValidationError(
            "No Google refresh token available; run blogger authorization first"
        )
    return token


def store_refresh_token(token: str) -> None:
    """Persist a refresh token in memory for reuse during this process."""
    global _refresh_token
    _refresh_token = token


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
    data = await _post_form(TOKEN_URL, payload, transport=transport)

    refresh = data.get("refresh_token")
    if refresh:
        store_refresh_token(refresh)

    return data


async def fetch_access_token(transport: httpx.AsyncBaseTransport | None = None) -> str:
    """Return a fresh access token using the stored refresh token."""
    payload = {
        "client_id": settings.google_oauth_client_id,
        "client_secret": settings.google_oauth_client_secret,
        "refresh_token": _get_refresh_token(),
        "grant_type": "refresh_token",
    }
    data = await _post_form(TOKEN_URL, payload, transport=transport)
    return data["access_token"]


async def _post_form(
    url: str,
    payload: dict,
    transport: httpx.AsyncBaseTransport | None,
) -> dict:
    async with httpx.AsyncClient(transport=transport, timeout=60) as client:
        response = await client.post(url, data=payload)
        response.raise_for_status()
        return response.json()