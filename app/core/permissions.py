"""Centralized permission registry and validation helpers.

Implements least-privilege by default. An agent's permissions are a plain
set of permission keys (see ``Permission``). Helper functions answer the
single question: "does this agent hold the required permission?".

Deliberately NOT defined here: ``secret.read`` and ``system.admin``. No agent
may retrieve or expose application secrets; the Security Agent validates
*sensitive operations* but never receives secret values.
"""

from enum import Enum


class Permission(str, Enum):
    """The complete set of permissions recognized by the system.

    Adding a new permission here makes it available to the validation helper
    without touching any agent implementation or service logic.
    """

    # Task operations
    TASK_CREATE = "task.create"
    TASK_ASSIGN = "task.assign"
    TASK_REVIEW = "task.review"
    TASK_APPROVE = "task.approve"
    TASK_REJECT = "task.reject"

    # Agent execution
    AGENT_EXECUTE = "agent.execute"

    # Workflow operations
    WORKFLOW_CREATE = "workflow.create"
    WORKFLOW_EXECUTE = "workflow.execute"

    # System / operational
    SYSTEM_READ = "system.read"

    # Security-agent-only permissions (never expose secrets)
    PERMISSION_VALIDATE = "permission.validate"
    AUDIT_READ = "audit.read"
    SECURITY_VALIDATE = "security.validate"


# Distinct lookup set for fast membership checks.
ALL_PERMISSIONS = frozenset(p.value for p in Permission)


def is_valid_permission(permission: str) -> bool:
    """Return True if ``permission`` is a known permission key."""
    return permission in ALL_PERMISSIONS


def has_permission(
    agent_permissions: list[str] | set[str] | tuple[str, ...] | None,
    required: str | Permission,
) -> bool:
    """Return True if the agent holds ``required``.

    An empty/missing permission set grants nothing — least privilege by
    default. Unknown permission keys are treated as not held.
    """
    required_value = required.value if isinstance(required, Permission) else required
    return required_value in set(agent_permissions or ())


def require_permission(
    agent_permissions: list[str] | set[str] | tuple[str, ...] | None,
    required: str | Permission,
) -> None:
    """Raise ``PermissionDeniedError`` if the agent lacks ``required``.

    The caller (service layer) is responsible for turning this into an audit
    event and, later, an HTTP 403 response.
    """
    if not has_permission(agent_permissions, required):
        from app.core.exceptions import PermissionDeniedError

        required_value = required.value if isinstance(required, Permission) else required
        raise PermissionDeniedError(required_value)