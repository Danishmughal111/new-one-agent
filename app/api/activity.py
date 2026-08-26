"""TrendEra activity feed route."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.schemas.activity import ActivityResponse
from app.services.audit_service import AuditService

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("", response_model=list[ActivityResponse])
async def list_activity(
    limit: int = Query(default=50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list:
    """Return recent TrendEra workflow events (most recent first)."""
    logs = await AuditService(session).list_filtered(resource_type="trendera", limit=limit)
    return [
        {
            "id": log.id,
            "message": (log.metadata_ or {}).get("message") or log.action,
            "type": log.action,
            "created_at": log.timestamp,
            "resource_id": log.resource_id,
        }
        for log in logs
    ]
