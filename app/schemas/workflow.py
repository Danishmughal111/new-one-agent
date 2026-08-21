"""Workflow schemas (input vs response)."""

from pydantic import Field

from app.models.enums import WorkflowStatus
from app.schemas.common import BaseResponse, ORMModel


class WorkflowCreate(ORMModel):
    """Request payload for creating a workflow definition."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: WorkflowStatus = WorkflowStatus.DRAFT
    configuration: dict = Field(default_factory=dict)


class WorkflowUpdate(ORMModel):
    """Request payload for updating a workflow definition."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: WorkflowStatus | None = None
    configuration: dict | None = None


class WorkflowResponse(BaseResponse):
    """Workflow response."""

    name: str
    description: str | None = None
    status: WorkflowStatus
    configuration: dict