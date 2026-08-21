"""Audit log schemas (read-only)."""

from datetime import datetime

from pydantic import Field

from app.schemas.common import ORMModel


class AuditLogResponse(ORMModel):
    """Audit log response."""

    id: str
    agent_id: str | None = None
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    metadata: dict = Field(validation_alias="metadata_")
    timestamp: datetime


class TaskStatusHistoryResponse(ORMModel):
    """Task status history response."""

    id: str
    task_id: str
    previous_status: str | None = None
    new_status: str
    changed_by_agent_id: str | None = None
    reason: str | None = None
    timestamp: datetime