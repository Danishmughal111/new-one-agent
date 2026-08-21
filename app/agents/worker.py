"""Placeholder worker agent — deterministic task execution.

Phase 1 has no TrendEra/Automation specialist agents yet. This minimal
worker produces clearly-marked simulated results so the full workflow can
run end-to-end without LLM/API keys.

Execution contract (via TaskService only):
    QUEUED -> IN_PROGRESS -> (write result) -> REVIEW
"""

from app.agents.base import AgentContext, AgentExecutionResult, BaseAgent
from app.core.exceptions import AppError
from app.schemas.task import TaskStatusTransition, TaskUpdate
from app.services.task_service import TaskService


class WorkerAgent(BaseAgent):
    """Deterministic placeholder executor."""

    role = "worker"

    def __init__(
        self,
        agent_id: str,
        task_service: TaskService,
        name: str = "Worker Agent",
        capabilities: list[str] | None = None,
        permissions: list[str] | None = None,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            name=name,
            capabilities=capabilities or ["deterministic_execution"],
            permissions=permissions or ["agent.execute"],
        )
        self._tasks = task_service

    async def execute(self, context: AgentContext) -> AgentExecutionResult:
        """Execute a task deterministically and move it to REVIEW."""
        task_id = context.task_id
        if not task_id:
            return self.create_result(ok=False, error="No task_id provided to worker")

        try:
            task = await self._tasks.get(task_id)

            # Advance into IN_PROGRESS if not already there.
            if task.status == "QUEUED":
                await self._tasks.transition(
                    task_id,
                    TaskStatusTransition(
                        target_status="IN_PROGRESS",
                        changed_by_agent_id=self.agent_id,
                        reason="Worker started execution",
                    ),
                )
            elif task.status != "IN_PROGRESS":
                return self.create_result(
                    ok=False,
                    error=f"Worker cannot execute task in status {task.status}",
                    data={"task_id": task_id},
                )

            # Deterministic, clearly-marked simulated output.
            output = (
                f"Simulated deterministic execution completed for: {task.title}"
            )
            await self._tasks.update(
                task_id,
                TaskUpdate(
                    result={"output": output, "simulated": True},
                ),
            )

            await self._tasks.transition(
                task_id,
                TaskStatusTransition(
                    target_status="REVIEW",
                    changed_by_agent_id=self.agent_id,
                    reason="Worker finished; ready for QA review",
                ),
            )

            return self.create_result(
                ok=True,
                data={
                    "task_id": task_id,
                    "output": output,
                    "simulated": True,
                    "generated_by": "deterministic_placeholder",
                },
            )
        except AppError as exc:
            self.logger.warning("Worker execution failed for task %s: %s", task_id, exc)
            return self.create_result(ok=False, data={"task_id": task_id}, error=str(exc))