"""Blogger OAuth connection routes (start / callback / status / disconnect)."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.core.config import settings
from app.core.oauth import build_authorization_url
from app.schemas.blogger import BloggerStatusResponse
from app.services.blogger_connection_service import BloggerConnectionService

router = APIRouter(prefix="/auth/blogger", tags=["blogger-auth"])


@router.get("")
async def start_authorization():
    """Redirect the browser to Google's OAuth consent screen."""
    return RedirectResponse(url=build_authorization_url(), status_code=302)


@router.get("/callback")
async def authorization_callback(
    code: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Exchange the authorization code, persist it, and return to the frontend."""
    await BloggerConnectionService(session).connect(code)
    return RedirectResponse(url=settings.frontend_url, status_code=302)


@router.get("/status", response_model=BloggerStatusResponse)
async def connection_status(session: AsyncSession = Depends(get_session)):
    """Return the current Blogger connection status (no secrets)."""
    return await BloggerConnectionService(session).status()


@router.post("/disconnect")
async def disconnect(session: AsyncSession = Depends(get_session)):
    """Remove the stored Blogger authorization."""
    await BloggerConnectionService(session).disconnect()
    return {"connected": False}
