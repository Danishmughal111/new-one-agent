"""Health endpoint."""

from fastapi import APIRouter

from app import __version__
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Return service health without exposing secrets/internal config."""
    return {
        "status": "ok",
        "version": __version__,
        "environment": settings.app_env,
    }