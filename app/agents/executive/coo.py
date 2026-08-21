"""COO agent — deterministic task planning and delegation.

Converts structured strategic objectives into actionable tasks using the
``TaskService`` and assigns them to a placeholder/simulated worker. The COO
never writes DB queries directly — all persistence flows through services.
"""

from typing import Any

from app.agents.base import AgentContext, AgentExecutionResult, BaseAgent
from app.core.exceptions import AppError
from app.schemas.task import TaskCreate, TaskStatusTransition
from app.services.agent_service import AgentService
from app.services.task_service import TaskService


class COOAgent(BaseAgent):
    """Turns strategic actions into assigned tasks."""

    role = "coo"

    def __init__(
        self,
        agent_id: str,
        task_service: TaskService,
        agent_service: AgentService,
        name: str = "COO Agent",
        capabilities: list[str] | None = None,
        permissions: list[str] | None = None,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            name=name,
            capabilities=capabilities or ["task_planning", "task_delegation"],
            permissions=permissions or ["task.create", "task.assign"],
        )
        self._tasks = task_service
        self._agents = agent_service

    async def execute(self, context: AgentContext) -> AgentExecutionResult:
        """Create and assign one task per strategic action."""
        actions: list[str] = context.payload.get("actions", [])
        objective: str = context.payload.get("objective", "Company objective")
        objective_id: str | None = context.payload.get("objective_id")
        priority: str = context.payload.get("priority", "medium")

        if not actions:
            return self.create_result(ok=False, error="No actions provided to COO")

        worker_id = context.payload.get("worker_agent_id")
        if not worker_id:
            worker = await self._find_worker()
            if worker is None:
                return self.create_result(ok=False, error="No worker agent available")
            worker_id = worker.id

        created_tasks: list[dict[str, Any]] = []
        try:
            for action in actions:
                task = await self._tasks.create(
                    TaskCreate(
                        title=action,
                        description=f"Objective: {objective}",
                        priority=priority.upper(),
                        created_by_agent_id=self.agent_id,
                        parent_objective_id=objective_id,
                        metadata={"objective": objective, "simulated": True},
                    )
                )
                await self._tasks.assign(
                    task.id,
                    assignee_agent_id=worker_id,
                    changed_by_agent_id=self.agent_id,
                )
                # Move PENDING -> QUEUED so the worker can pick it up.
                await self._tasks.transition(
                    task.id,
                    TaskStatusTransition(
                        target_status="QUEUED",
                        changed_by_agent_id=self.agent_id,
                        reason="COO queued task for execution",
                    ),
                )
                created_tasks.append(
                    {"task_id": task.id, "title": task.title, "assignee": worker_id}
                )

        except AppError as exc:
            self.logger.warning("COO task planning failed: %s", exc)
            return self.create_result(ok=False, error=str(exc), data={"created_tasks": created_tasks})

        self.logger.info("COO created %d tasks", len(created_tasks))
        return self.create_result(
            ok=True,
            data={
                "simulated": True,
                "generated_by": "deterministic_placeholder",
                "created_tasks": created_tasks,
            },
        )

    async def _find_worker(self) -> Any | None:
        """Locate a placeholder worker agent via AgentService (no direct DB)."""
        agents = await self._agents.list(limit=500)
        for agent in agents:
            if getattr(agent, "role", None) == "worker":
                return agent
        return None