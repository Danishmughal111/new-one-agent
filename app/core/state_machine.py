"""Centralized task status state machine.

Validates status transitions only. It performs NO database access — the
``TaskService`` is responsible for persisting the new status and recording
history once a transition is validated.

All task status changes MUST pass through ``TaskStateMachine.validate``.
"""

from app.models.enums import TaskStatus

# Mapping of current status -> allowed next statuses.
# Every value is frozen to signal these transition tables are immutable.
TRANSITIONS: dict[str, frozenset[str]] = {
    # Primary path
    TaskStatus.PENDING.value: frozenset(
        {
            TaskStatus.QUEUED.value,
            TaskStatus.BLOCKED.value,
            TaskStatus.ESCALATED.value,
            TaskStatus.FAILED.value,
        }
    ),
    TaskStatus.QUEUED.value: frozenset(
        {
            TaskStatus.IN_PROGRESS.value,
            TaskStatus.ESCALATED.value,
            TaskStatus.FAILED.value,
        }
    ),
    TaskStatus.IN_PROGRESS.value: frozenset(
        {
            TaskStatus.REVIEW.value,
            TaskStatus.BLOCKED.value,
            TaskStatus.ESCALATED.value,
            TaskStatus.FAILED.value,
        }
    ),
    TaskStatus.REVIEW.value: frozenset(
        {
            TaskStatus.APPROVED.value,
            TaskStatus.REJECTED.value,
            TaskStatus.ESCALATED.value,
        }
    ),
    TaskStatus.APPROVED.value: frozenset(
        {
            TaskStatus.COMPLETED.value,
        }
    ),
    TaskStatus.REJECTED.value: frozenset(
        {
            TaskStatus.REVISION_REQUIRED.value,
        }
    ),
    TaskStatus.REVISION_REQUIRED.value: frozenset(
        {
            TaskStatus.IN_PROGRESS.value,
            TaskStatus.FAILED.value,
        }
    ),
    # Blocked tasks can resume, be escalated for human action, or be abandoned.
    TaskStatus.BLOCKED.value: frozenset(
        {
            TaskStatus.IN_PROGRESS.value,
            TaskStatus.ESCALATED.value,
            TaskStatus.FAILED.value,
        }
    ),
    # ESCALATED is intentionally terminal in Phase 1: it must remain pending
    # until a future human-approval action is implemented. No automatic
    # outgoing transition is defined yet.
    TaskStatus.ESCALATED.value: frozenset(),
    # Terminal states.
    TaskStatus.COMPLETED.value: frozenset(),
    TaskStatus.FAILED.value: frozenset(),
}

# Statuses from which no further transition is possible in Phase 1.
TERMINAL_STATUSES = frozenset(
    {TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.ESCALATED.value}
)

# A brand-new task may only begin in PENDING.
INITIAL_STATUS = TaskStatus.PENDING.value


class TaskStateMachine:
    """Validates task status transitions against the central transition table."""

    @staticmethod
    def can_transition(current_status: str | None, target_status: str) -> bool:
        """Return True if ``current_status -> target_status`` is allowed."""
        # A task with no current status is being created; only PENDING is valid.
        if current_status is None:
            return target_status == INITIAL_STATUS
        return target_status in TRANSITIONS.get(current_status, frozenset())

    @staticmethod
    def allowed_transitions(current_status: str | None) -> list[str]:
        """Return the sorted list of allowed next statuses for ``current_status``."""
        if current_status is None:
            return [INITIAL_STATUS]
        return sorted(TRANSITIONS.get(current_status, frozenset()))

    @staticmethod
    def validate(current_status: str | None, target_status: str) -> None:
        """Raise ``InvalidStateTransitionError`` if the transition is not allowed.

        This is the single validation entry point every status change must call.
        """
        from app.core.exceptions import InvalidStateTransitionError

        if not TaskStateMachine.can_transition(current_status, target_status):
            raise InvalidStateTransitionError(
                current=current_status,
                target=target_status,
                allowed=TaskStateMachine.allowed_transitions(current_status),
            )

    @staticmethod
    def is_terminal(status: str) -> bool:
        """Return True if ``status`` is terminal (no further transitions)."""
        return status in TERMINAL_STATUSES