"""Chief of Staff agent — deterministic operational monitoring.

Summarizes task counts by status, detects blocked/escalated tasks, and
produces a lightweight operational report. No analytics infrastructure; no
direct DB access — all reads flow through ``TaskService``.
"""

from typing import Any

from app.agents.base import AgentContext, AgentExecutionResult, BaseAgent
from app.services.task_service import TaskService


class ChiefOfStaffAgent(BaseAgent):
    """Monitors company-wide activity and generates operational reports."""

    role = "chief_of_staff"

    def __init__(
        self,
        agent_id: str,
        task_service: TaskService,
        name: str = "Chief of Staff Agent",
        capabilities: list[str] | None = None,
        permissions: list[str] | None = None,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            name=name,
            capabilities=capabilities or ["monitoring", "operational_reporting"],
            permissions=permissions or ["system.read"],
        )
        self._tasks = task_service

    async def execute(self, context: AgentContext) -> AgentExecutionResult:
        """Generate a deterministic operational report snapshot."""
        counts = await self._tasks.get_status_counts()
        blocked = await self._tasks.list_blocked()
        escalated = await self._tasks.list_escalated()

        report: dict[str, Any] = {
            "simulated": True,
            "generated_by": "deterministic_placeholder",
            "task_counts_by_status": counts,
            "blocked_task_count": len(blocked),
            "blocked_tasks": [t.id for t in blocked],
            "escalated_task_count": len(escalated),
            "escalated_tasks": [t.id for t in escalated],
            "bottleneck_detected": len(blocked) > 0 or len(escalated) > 0,
        }

        self.logger.info(
            "Chief of Staff report: %d blocked, %d escalated",
            len(blocked),
            len(escalated),
        )
        return self.create_result(ok=True, data=report)