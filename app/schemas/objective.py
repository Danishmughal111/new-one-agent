"""Objective schemas (input vs response)."""

from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.enums import ObjectivePriority, ObjectiveStatus
from app.schemas.common import BaseResponse, ORMModel


class ObjectiveCreate(ORMModel):
    """Request payload for submitting a company objective."""

    title: str = Field(min_length=1, max_length=512)
    description: str | None = None
    priority: ObjectivePriority = ObjectivePriority.MEDIUM
    created_by: str | None = None
    metadata: dict = Field(default_factory=dict)


class ObjectiveUpdate(ORMModel):
    """Request payload for updating an objective (all optional)."""

    title: str | None = Field(default=None, min_length=1, max_length=512)
    description: str | None = None
    priority: ObjectivePriority | None = None
    status: ObjectiveStatus | None = None
    metadata: dict | None = None


class ObjectiveResponse(BaseResponse):
    """Objective response (persisted objective)."""

    title: str
    description: str | None = None
    status: ObjectiveStatus
    priority: ObjectivePriority
    created_by: str | None = None
    result: dict | None = None
    metadata: dict = Field(validation_alias="metadata_")
    completed_at: datetime | None = None


class ObjectiveRunResponse(ORMModel):
    """Result of running a persisted objective through the workflow."""

    objective: ObjectiveResponse
    workflow: dict[str, Any]
