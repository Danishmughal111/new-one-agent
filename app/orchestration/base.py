"""Engine-agnostic orchestration abstraction.

Defines the workflow result shape and the ``Orchestrator`` protocol. The
concrete ``CompanyWorkflow`` implements this synchronously/deterministically.
A future LangGraph implementation can satisfy the same interface without
touching core layers.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class WorkflowResult:
    """Structured outcome of running a company workflow."""

    ok: bool
    objective: str
    final_status: str
    ceo_output: dict[str, Any] = field(default_factory=dict)
    tasks: list[dict[str, Any]] = field(default_factory=dict)
    qa_decisions: list[dict[str, Any]] = field(default_factory=dict)
    error: str | None = None
    simulated: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "objective": self.objective,
            "final_status": self.final_status,
            "ceo_output": self.ceo_output,
            "tasks": self.tasks,
            "qa_decisions": self.qa_decisions,
            "error": self.error,
            "simulated": self.simulated,
        }


class Orchestrator(Protocol):
    """Protocol every orchestration engine must satisfy."""

    async def run(self, objective: str) -> WorkflowResult:
        """Execute the company workflow for a single human objective."""
        ...