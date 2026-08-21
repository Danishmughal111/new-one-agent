"""Task schemas (input vs response)."""

from datetime import datetime

from pydantic import Field

from app.models.enums import TaskPriority, TaskStatus
from app.schemas.common import BaseResponse, ORMModel


class TaskCreate(ORMModel):
    """Request payload for creating a task.

    ``status`` is intentionally NOT accepted here — new tasks always start
    in PENDING and must transition through the state machine.
    """

    title: str = Field(min_length=1, max_length=512)
    description: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    assigned_agent_id: str | None = None
    created_by_agent_id: str | None = None
    parent_task_id: str | None = None
    parent_objective_id: str | None = None
    metadata: dict = Field(default_factory=dict)


class TaskUpdate(ORMModel):
    """Request payload for updating task fields (all optional).

    Does NOT allow changing ``status`` directly — use ``TaskStatusTransition``.
    """

    title: str | None = Field(default=None, min_length=1, max_length=512)
    description: str | None = None
    priority: TaskPriority | None = None
    assigned_agent_id: str | None = None
    result: dict | None = None
    metadata: dict | None = None


class TaskStatusTransition(ORMModel):
    """Request payload for a validated status transition."""

    target_status: TaskStatus
    changed_by_agent_id: str | None = None
    reason: str | None = None


class TaskAssign(ORMModel):
    """Request payload for assigning a task to an agent."""

    assignee_agent_id: str
    changed_by_agent_id: str | None = None


class TaskResponse(BaseResponse):
    """Task response."""

    title: str
    description: str | None = None
    priority: TaskPriority
    status: TaskStatus
    assigned_agent_id: str | None = None
    created_by_agent_id: str | None = None
    parent_task_id: str | None = None
    parent_objective_id: str | None = None
    result: dict | None = None
    metadata: dict = Field(validation_alias="metadata_")
    completed_at: datetime | None = None
