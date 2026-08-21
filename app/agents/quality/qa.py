"""QA agent — deterministic quality review.

Reviews task results and approves or rejects them via ``TaskService``.
QA does NOT auto-approve: a task with no result or an invalid result
structure is rejected and moved to REVISION_REQUIRED.
"""

from app.agents.base import AgentContext, AgentExecutionResult, BaseAgent
from app.core.exceptions import AppError
from app.schemas.task import TaskStatusTransition
from app.services.task_service import TaskService

_VALID_KEYS = {"output"}


class QAAgent(BaseAgent):
    """Reviews completed work and issues approval/rejection decisions."""

    role = "qa"

    def __init__(
        self,
        agent_id: str,
        task_service: TaskService,
        name: str = "QA Agent",
        capabilities: list[str] | None = None,
        permissions: list[str] | None = None,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            name=name,
            capabilities=capabilities or ["quality_review"],
            permissions=permissions or ["task.review", "task.approve", "task.reject"],
        )
        self._tasks = task_service

    async def execute(self, context: AgentContext) -> AgentExecutionResult:
        """Validate the task result in ``context`` and decide approve/reject."""
        task_id = context.task_id
        if not task_id:
            return self.create_result(ok=False, error="No task_id provided to QA")

        task = await self._tasks.get(task_id)
        result = getattr(task, "result", None)
        valid = self._validate_result(result)

        try:
            if valid:
                await self._tasks.transition(
                    task_id,
                    TaskStatusTransition(
                        target_status="APPROVED",
                        changed_by_agent_id=self.agent_id,
                        reason="QA validation passed",
                    ),
                )
                await self._tasks.transition(
                    task_id,
                    TaskStatusTransition(
                        target_status="COMPLETED",
                        changed_by_agent_id=self.agent_id,
                        reason="QA approval finalized",
                    ),
                )
                return self.create_result(
                    ok=True, data={"decision": "APPROVED", "task_id": task_id}
                )
            await self._tasks.transition(
                task_id,
                TaskStatusTransition(
                    target_status="REJECTED",
                    changed_by_agent_id=self.agent_id,
                    reason="QA validation failed: missing or invalid result",
                ),
            )
            await self._tasks.transition(
                task_id,
                TaskStatusTransition(
                    target_status="REVISION_REQUIRED",
                    changed_by_agent_id=self.agent_id,
                    reason="QA sent task back for revision",
                ),
            )
            return self.create_result(
                ok=False,
                data={"decision": "REJECTED", "task_id": task_id},
                error="Missing or invalid result structure",
            )
        except AppError as exc:
            self.logger.warning("QA transition failed for task %s: %s", task_id, exc)
            return self.create_result(ok=False, data={"task_id": task_id}, error=str(exc))

    def _validate_result(self, result: object | None) -> bool:
        """Deterministically validate a task result structure.

        A task result is valid when it is a non-empty dict containing an
        ``output`` key with a non-empty value (plus optional ``simulated``).
        """
        if not isinstance(result, dict):
            return False
        output = result.get("output")
        if not output:
            return False
        if not isinstance(output, (str, dict, list)):
            return False
        if isinstance(output, (str, list)) and len(output) == 0:
            return False
        return True

    def validate_task(self, payload: dict) -> bool:
        """A QA-reviewable payload must have a non-empty result structure."""
        return self._validate_result(payload.get("result"))