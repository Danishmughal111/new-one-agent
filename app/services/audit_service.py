"""Audit service — records operational events for accountability.

Only *significant* write/decision events are audited (task creation,
assignment, approval, rejection, agent execution, permission denial, etc.).
Trivial reads are intentionally NOT audited.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.repositories.audit_log import AuditLogRepository


class AuditService:
    """Writes append-only audit events via the audit repository."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._repo = AuditLogRepository(session)

    async def record(
        self,
        action: str,
        agent_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Persist a single audit event (caller must commit)."""
        return await self._repo.add(
            AuditLog(
                agent_id=agent_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                metadata_=metadata or {},
            )
        )

    async def list(self, offset: int = 0, limit: int = 100) -> list[AuditLog]:
        """List recent audit events."""
        return await self._repo.list(offset=offset, limit=limit)

    async def list_filtered(
        self,
        agent_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        """List audit events with optional filters (most recent first)."""
        return await self._repo.list_filtered(
            agent_id=agent_id,
            action=action,
            resource_type=resource_type,
            limit=limit,
        )
