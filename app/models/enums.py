"""Enumerations shared across models, schemas, and services.

Status/priority values are plain string constants (rather than SQLAlchemy
``Enum``) to stay portable across PostgreSQL and SQLite and to avoid
migration friction when adding new values.
"""

from enum import Enum


class DepartmentStatus(str, Enum):
    """Lifecycle status of a department."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"


class AgentStatus(str, Enum):
    """Lifecycle status of an agent."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    OFFLINE = "OFFLINE"
    ERROR = "ERROR"


class TaskPriority(str, Enum):
    """Priority levels for tasks."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TaskStatus(str, Enum):
    """Full task lifecycle.

    Primary path: PENDING -> QUEUED -> IN_PROGRESS -> REVIEW -> APPROVED -> COMPLETED
    Revision path: REJECTED -> REVISION_REQUIRED -> IN_PROGRESS
    """

    PENDING = "PENDING"
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    BLOCKED = "BLOCKED"
    ESCALATED = "ESCALATED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class WorkflowStatus(str, Enum):
    """Lifecycle status of a workflow definition."""

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"


class WorkflowRunStatus(str, Enum):
    """Execution status of a workflow run (future orchestration)."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ObjectiveStatus(str, Enum):
    """Lifecycle status of a company objective."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ObjectivePriority(str, Enum):
    """Priority levels for company objectives."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
