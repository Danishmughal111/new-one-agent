"""Core tests: configuration, permissions, and task state machine."""

import pytest

from app.core.config import Settings, get_settings
from app.core.exceptions import InvalidStateTransitionError, PermissionDeniedError
from app.core.permissions import (
    Permission,
    has_permission,
    is_valid_permission,
    require_permission,
)
from app.core.state_machine import TaskStateMachine


def test_settings_are_loaded() -> None:
    settings = get_settings()
    assert settings.app_name
    assert settings.database_url.startswith("sqlite")


def test_settings_from_env() -> None:
    s = Settings(app_name="Test")
    assert s.app_name == "Test"


def test_permission_registry_has_no_secret_or_admin() -> None:
    values = {p.value for p in Permission}
    assert "secret.read" not in values
    assert "system.admin" not in values


def test_is_valid_permission() -> None:
    assert is_valid_permission("task.create") is True
    assert is_valid_permission("secret.read") is False


def test_has_permission_allowed() -> None:
    assert has_permission(["task.create"], "task.create") is True
    assert has_permission(["task.create"], Permission.TASK_CREATE) is True


def test_has_permission_denied_and_empty() -> None:
    assert has_permission(["task.assign"], "task.create") is False
    assert has_permission([], "task.create") is False
    assert has_permission(None, "task.create") is False


def test_require_permission_denied() -> None:
    with pytest.raises(PermissionDeniedError):
        require_permission(["agent.execute"], "task.approve")


@pytest.mark.parametrize(
    "current,target",
    [
        ("PENDING", "QUEUED"),
        ("QUEUED", "IN_PROGRESS"),
        ("IN_PROGRESS", "REVIEW"),
        ("REVIEW", "APPROVED"),
        ("APPROVED", "COMPLETED"),
        ("REVIEW", "REJECTED"),
        ("REJECTED", "REVISION_REQUIRED"),
        ("REVISION_REQUIRED", "IN_PROGRESS"),
        ("IN_PROGRESS", "BLOCKED"),
        ("BLOCKED", "IN_PROGRESS"),
        ("PENDING", "ESCALATED"),
    ],
)
def test_valid_transitions(current: str, target: str) -> None:
    TaskStateMachine.validate(current, target)


@pytest.mark.parametrize(
    "current,target",
    [
        ("COMPLETED", "IN_PROGRESS"),
        ("ESCALATED", "IN_PROGRESS"),
        ("QUEUED", "REVIEW"),
        ("REVIEW", "PENDING"),
        ("REJECTED", "PENDING"),
    ],
)
def test_invalid_transitions(current: str, target: str) -> None:
    with pytest.raises(InvalidStateTransitionError):
        TaskStateMachine.validate(current, target)


def test_new_task_must_start_pending() -> None:
    TaskStateMachine.validate(None, "PENDING")
    with pytest.raises(InvalidStateTransitionError):
        TaskStateMachine.validate(None, "QUEUED")


def test_terminal_statuses() -> None:
    assert TaskStateMachine.is_terminal("COMPLETED")
    assert TaskStateMachine.is_terminal("FAILED")
    assert TaskStateMachine.is_terminal("ESCALATED")
    assert not TaskStateMachine.is_terminal("IN_PROGRESS")