"""Audit log persistence."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    """Persistence operations for audit logs.

    Audit records are append-only: no update/delete business is exposed here
    beyond the shared ``add``/``list`` helpers.
    """

    model = AuditLog

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_by_agent(self, agent_id: str, limit: int = 100) -> list[AuditLog]:
        """List audit events for a given agent (most recent first)."""
        stmt = (
            select(AuditLog)
            .where(AuditLog.agent_id == agent_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
        )
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def list_filtered(
        self,
        agent_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        """List audit events with optional filters (most recent first)."""
        stmt = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
        if agent_id is not None:
            stmt = stmt.where(AuditLog.agent_id == agent_id)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        if resource_type is not None:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        result = await self.session.scalars(stmt)
        return list(result.all())
