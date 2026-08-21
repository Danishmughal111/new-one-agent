"""Deterministic company workflow.

Implements the Phase 1 pipeline end-to-end without LLMs, external APIs, or a
background queue:

    Human Objective -> CEO -> Strategic Objective -> COO -> Tasks
        -> Worker Execution -> REVIEW -> QA (APPROVED/REJECTED)

The workflow operates ONLY through services and agents — it never touches
task database models or writes queries directly.
"""

from typing import Any

from app.agents.base import AgentContext, BaseAgent
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.orchestration.base import WorkflowResult
from app.schemas.task import TaskStatusTransition
from app.services.task_service import TaskService

logger = get_logger("orchestration.company_workflow")


class CompanyWorkflow:
    """Runs a human objective through the CEO -> COO -> Worker -> QA pipeline."""

    def __init__(
        self,
        ceo: BaseAgent,
        coo: BaseAgent,
        worker: BaseAgent,
        qa: BaseAgent,
        task_service: TaskService,
    ) -> None:
        self._ceo = ceo
        self._coo = coo
        self._worker = worker
        self._qa = qa
        self._tasks = task_service

    async def run(self, objective: str, objective_id: str | None = None) -> WorkflowResult:
        """Execute the company workflow for a single objective.

        ``objective_id``, when provided, is propagated so generated tasks are
        linked back to the persisted objective.
        """
        try:
            # 1. CEO strategic decomposition.
            ceo_result = await self._ceo.execute(
                AgentContext(payload={"objective": objective})
            )
            if not ceo_result.ok:
                return WorkflowResult(
                    ok=False,
                    objective=objective,
                    final_status="FAILED",
                    error=ceo_result.error or "CEO failed to decompose objective",
                )
            strategy = ceo_result.data

            # 2. COO creates + assigns actionable tasks.
            coo_result = await self._coo.execute(
                AgentContext(
                    payload={
                        "objective": objective,
                        "objective_id": objective_id,
                        "actions": strategy.get("actions", []),
                        "priority": strategy.get("priority", "medium"),
                        "worker_agent_id": self._worker.agent_id,
                    }
                )
            )
            if not coo_result.ok:
                return WorkflowResult(
                    ok=False,
                    objective=objective,
                    final_status="FAILED",
                    ceo_output=strategy,
                    error=coo_result.error or "COO failed to plan tasks",
                )

            created_tasks = coo_result.data.get("created_tasks", [])
            task_records: list[dict[str, Any]] = []
            qa_decisions: list[dict[str, Any]] = []

            # 3. Execute each task, then QA-review it.
            for created in created_tasks:
                task_id = created["task_id"]
                worker_result = await self._worker.execute(
                    AgentContext(task_id=task_id)
                )
                if not worker_result.ok:
                    await self._fail_task(task_id, worker_result.error or "worker failed")
                    task_records.append(
                        {"task_id": task_id, "status": "FAILED", "error": worker_result.error}
                    )
                    continue

                qa_result = await self._qa.execute(AgentContext(task_id=task_id))
                qa_decision = qa_result.data if qa_result.data else {}
                qa_decision.setdefault("task_id", task_id)
                qa_decisions.append(qa_decision)

                task = await self._tasks.get(task_id)
                task_records.append({"task_id": task_id, "status": task.status})

            # 4. Determine overall workflow status.
            if any(t["status"] == "FAILED" for t in task_records):
                final_status = "FAILED"
            elif task_records and all(t["status"] == "COMPLETED" for t in task_records):
                final_status = "COMPLETED"
            elif task_records and all(
                t["status"] in ("APPROVED", "COMPLETED") for t in task_records
            ):
                final_status = "APPROVED"
            elif any(t["status"] == "REJECTED" for t in task_records):
                final_status = "REJECTED"
            else:
                final_status = "PARTIAL"

            return WorkflowResult(
                ok=final_status in ("COMPLETED", "APPROVED"),
                objective=objective,
                final_status=final_status,
                ceo_output=strategy,
                tasks=task_records,
                qa_decisions=qa_decisions,
            )

        except AppError as exc:
            logger.error("CompanyWorkflow failed for objective '%s': %s", objective, exc)
            return WorkflowResult(
                ok=False,
                objective=objective,
                final_status="FAILED",
                error=str(exc),
            )

    async def _fail_task(self, task_id: str, reason: str) -> None:
        """Move a task to FAILED if the transition is legal."""
        try:
            await self._tasks.transition(
                task_id,
                TaskStatusTransition(
                    target_status="FAILED",
                    changed_by_agent_id=self._worker.agent_id,
                    reason=reason,
                ),
            )
        except AppError as exc:
            # Unable to mark FAILED (e.g., already terminal); log but don't
            # crash the whole workflow.
            logger.warning("Could not mark task %s FAILED: %s", task_id, exc)