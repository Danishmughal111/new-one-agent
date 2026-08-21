"""Base agent abstraction.

Agents are pure business actors. They receive services/state through their
constructor (dependency injection) and must NOT touch SQLAlchemy models,
write queries, or communicate with other agents directly. Any database or
task mutation happens through the service layer.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger


@dataclass
class AgentContext:
    """Input passed to an agent's ``execute`` method.

    Carries either a human objective (for the CEO) or a task payload (for
    task-executing agents), plus optional structured instructions.
    """

    objective_id: str | None = None
    task_id: str | None = None
    task_status: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    instructions: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentExecutionResult:
    """Structured, deterministic output produced by an agent."""

    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    # Always True in Phase 1 — clearly marks output as deterministic placeholder
    # logic rather than real LLM/agent intelligence.
    simulated: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "data": self.data,
            "error": self.error,
            "simulated": self.simulated,
        }


class BaseAgent(ABC):
    """Abstract base class for every company agent.

    Subclasses implement ``execute`` and may override ``validate_task``.
    """

    #: Canonical role key used for discovery in the registry.
    role: str = "base"

    def __init__(
        self,
        agent_id: str,
        name: str,
        capabilities: list[str] | None = None,
        permissions: list[str] | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.name = name
        self.capabilities = capabilities or []
        self.permissions = permissions or []
        self.logger = get_logger(f"agent.{self.role}")

    # ------------------------------------------------------------------
    # Core contract
    # ------------------------------------------------------------------
    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentExecutionResult:
        """Execute the agent's responsibility against ``context``."""

    def validate_task(self, payload: dict[str, Any]) -> bool:
        """Validate that a task payload is actionable for this agent.

        Default implementation accepts anything; agents may override to
        enforce required fields.
        """
        return True

    def create_result(
        self,
        ok: bool,
        data: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> AgentExecutionResult:
        """Construct a structured agent execution result."""
        return AgentExecutionResult(ok=ok, data=data or {}, error=error)

    def report_status(self) -> dict[str, Any]:
        """Produce a lightweight status snapshot of this agent."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "capabilities": self.capabilities,
            "permissions": self.permissions,
        }

    def has_permission(self, permission: str) -> bool:
        """Convenience permission check (delegates to core permissions)."""
        from app.core.permissions import has_permission

        return has_permission(self.permissions, permission)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{type(self).__name__} id={self.agent_id} role={self.role}>"