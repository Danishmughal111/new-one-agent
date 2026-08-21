"""Audit log routes with optional filtering."""

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_audit_service
from app.schemas.audit import AuditLogResponse
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("", response_model=list[AuditLogResponse])
async def list_audit_logs(
    agent_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    service: AuditService = Depends(get_audit_service),
) -> list:
    return await service.list_filtered(
        agent_id=agent_id,
        action=action,
        resource_type=resource_type,
        limit=limit,
    )