"""Task business logic — creation, assignment, and validated transitions.

This service:
- uses ``TaskStateMachine`` for transition validation (no DB logic there)
- persists task changes AND records ``TaskStatusHistory`` + audit events
- enforces permissions via the acting agent's permission set
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.permissions import require_permission
from app.core.state_machine import TaskStateMachine
from app.models.agent import Agent
from app.models.task import Task
from app.models.task_status_history import TaskStatusHistory
from app.repositories.agent import AgentRepository
from app.repositories.task import TaskRepository
from app.repositories.task_status_history import TaskStatusHistoryRepository
from app.schemas.task import TaskCreate, TaskStatusTransition, TaskUpdate
from app.services.audit_service import AuditService

# Required permission for each (previous_status, target_status) transition.
# ``None`` means system-initiated (no agent permission check).
_PERMISSION_BY_TRANSITION: dict[tuple[str, str], str | None] = {
    ("PENDING", "QUEUED"): "task.create",
    ("PENDING", "BLOCKED"): "task.assign",
    ("PENDING", "ESCALATED"): "task.assign",
    ("PENDING", "FAILED"): "task.assign",
    ("QUEUED", "IN_PROGRESS"): "agent.execute",
    ("QUEUED", "ESCALATED"): "task.assign",
    ("QUEUED", "FAILED"): "task.assign",
    ("IN_PROGRESS", "REVIEW"): "agent.execute",
    ("IN_PROGRESS", "BLOCKED"): "agent.execute",
    ("IN_PROGRESS", "ESCALATED"): "agent.execute",
    ("IN_PROGRESS", "FAILED"): "agent.execute",
    ("REVIEW", "APPROVED"): "task.approve",
    ("REVIEW", "REJECTED"): "task.reject",
    ("REVIEW", "ESCALATED"): "task.review",
    ("APPROVED", "COMPLETED"): "task.approve",
    ("REJECTED", "REVISION_REQUIRED"): "task.reject",
    ("REVISION_REQUIRED", "IN_PROGRESS"): "agent.execute",
    ("REVISION_REQUIRED", "FAILED"): "agent.execute",
    ("BLOCKED", "IN_PROGRESS"): "agent.execute",
    ("BLOCKED", "ESCALATED"): "task.assign",
    ("BLOCKED", "FAILED"): "task.assign",
}


class TaskService:
    """Business rules for the centralized task workflow."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._tasks = TaskRepository(session)
        self._agents = AgentRepository(session)
        self._history = TaskStatusHistoryRepository(session)
        self._audit = AuditService(session)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _get_task(self, task_id: str) -> Task:
        task = await self._tasks.get(task_id)
        if task is None:
            raise NotFoundError("Task", task_id)
        return task

    async def _get_agent_permissions(self, agent_id: str | None) -> list[str] | None:
        """Return an agent's permissions, or None when no agent is specified."""
        if agent_id is None:
            return None
        agent: Agent | None = await self._agents.get(agent_id)
        if agent is None:
            raise NotFoundError("Agent", agent_id)
        return agent.permissions

    async def _record_history(
        self,
        task: Task,
        previous_status: str,
        new_status: str,
        changed_by_agent_id: str | None,
        reason: str | None,
    ) -> TaskStatusHistory:
        record = TaskStatusHistory(
            task_id=task.id,
            previous_status=previous_status,
            new_status=new_status,
            changed_by_agent_id=changed_by_agent_id,
            reason=reason,
        )
        return await self._history.add(record)

    # ------------------------------------------------------------------
    # Creation / query
    # ------------------------------------------------------------------
    async def create(self, data: TaskCreate) -> Task:
        """Create a task in the initial PENDING state."""
        creator = data.created_by_agent_id
        creator_permissions = await self._get_agent_permissions(creator)
        if creator_permissions is not None:
            try:
                require_permission(creator_permissions, "task.create")
            except PermissionDeniedError:
                await self._audit.record(
                    action="permission.denied",
                    agent_id=creator,
                    resource_type="tasks",
                    metadata={"permission": "task.create"},
                )
                raise

        task = Task(
            title=data.title,
            description=data.description,
            priority=data.priority.value,
            status="PENDING",
            assigned_agent_id=data.assigned_agent_id,
            created_by_agent_id=creator,
            parent_task_id=data.parent_task_id,
            parent_objective_id=data.parent_objective_id,
            metadata_=data.metadata,
        )
        task = await self._tasks.add(task)
        await self._record_history(
            task, previous_status=None, new_status="PENDING",
            changed_by_agent_id=creator, reason="created",
        )
        await self._audit.record(
            action="task.create",
            agent_id=creator,
            resource_type="tasks",
            resource_id=task.id,
            metadata={"priority": task.priority},
        )
        await self.session.commit()
        return task

    async def get(self, task_id: str) -> Task:
        """Fetch a task by id."""
        return await self._get_task(task_id)

    async def list(self, offset: int = 0, limit: int = 100) -> list[Task]:
        """List tasks."""
        return await self._tasks.list(offset=offset, limit=limit)

    async def list_by_status(self, status: str) -> list[Task]:
        """List tasks in a given status."""
        return await self._tasks.list_by_status(status)

    async def list_by_assignee(self, agent_id: str) -> list[Task]:
        """List tasks assigned to an agent."""
        return await self._tasks.list_by_assignee(agent_id)

    async def list_by_objective(self, objective_id: str) -> list[Task]:
        """List tasks generated for an objective."""
        return await self._tasks.list_by_objective(objective_id)

    async def get_status_counts(self) -> dict[str, int]:
        """Return a summary of task counts keyed by status."""
        counts: dict[str, int] = {}
        tasks = await self._tasks.list(offset=0, limit=10000)
        for task in tasks:
            counts[task.status] = counts.get(task.status, 0) + 1
        return counts

    async def list_blocked(self) -> list[Task]:
        """Return all currently blocked tasks."""
        return await self._tasks.list_by_status("BLOCKED")

    async def list_escalated(self) -> list[Task]:
        """Return all currently escalated tasks."""
        return await self._tasks.list_by_status("ESCALATED")

    async def update(self, task_id: str, data: TaskUpdate) -> Task:
        """Update editable task fields (status NOT changeable here)."""
        task = await self._get_task(task_id)
        updates = data.model_dump(exclude_unset=True)

        if "title" in updates and updates["title"] is not None:
            task.title = updates["title"]
        if "description" in updates:
            task.description = updates["description"]
        if "priority" in updates and updates["priority"] is not None:
            task.priority = updates["priority"].value
        if "assigned_agent_id" in updates:
            task.assigned_agent_id = updates["assigned_agent_id"]
        if "result" in updates:
            task.result = updates["result"]
        if "metadata" in updates and updates["metadata"] is not None:
            task.metadata_ = updates["metadata"]

        await self.session.commit()
        return task

    # ------------------------------------------------------------------
    # Assignment
    # ------------------------------------------------------------------
    async def assign(
        self,
        task_id: str,
        assignee_agent_id: str,
        changed_by_agent_id: str | None,
    ) -> Task:
        """Assign a task to an agent, enforcing ``task.assign``."""
        task = await self._get_task(task_id)
        assignee = await self._agents.get(assignee_agent_id)
        if assignee is None:
            raise NotFoundError("Agent", assignee_agent_id)

        actor_permissions = await self._get_agent_permissions(changed_by_agent_id)
        if actor_permissions is not None:
            try:
                require_permission(actor_permissions, "task.assign")
            except PermissionDeniedError:
                await self._audit.record(
                    action="permission.denied",
                    agent_id=changed_by_agent_id,
                    resource_type="tasks",
                    resource_id=task_id,
                    metadata={"permission": "task.assign"},
                )
                raise

        task.assigned_agent_id = assignee_agent_id
        await self._audit.record(
            action="task.assign",
            agent_id=changed_by_agent_id,
            resource_type="tasks",
            resource_id=task_id,
            metadata={"assignee": assignee_agent_id},
        )
        await self.session.commit()
        return task

    # ------------------------------------------------------------------
    # Status transitions
    # ------------------------------------------------------------------
    async def transition(self, task_id: str, data: TaskStatusTransition) -> Task:
        """Validate, persist, and record a task status transition."""
        task = await self._get_task(task_id)
        previous_status = task.status
        target = data.target_status.value
        actor = data.changed_by_agent_id

        # 1. Validate the transition centrally.
        TaskStateMachine.validate(previous_status, target)

        # 2. Enforce the transition's required permission.
        required = _PERMISSION_BY_TRANSITION.get((previous_status, target))
        actor_permissions = await self._get_agent_permissions(actor)
        if required is not None and actor_permissions is not None:
            try:
                require_permission(actor_permissions, required)
            except PermissionDeniedError:
                await self._audit.record(
                    action="permission.denied",
                    agent_id=actor,
                    resource_type="tasks",
                    resource_id=task_id,
                    metadata={"permission": required, "transition": f"{previous_status}->{target}"},
                )
                raise

        # 3. Persist the change.
        task.status = target
        if target == "COMPLETED":
            task.completed_at = datetime.now(timezone.utc)

        await self._record_history(
            task, previous_status=previous_status, new_status=target,
            changed_by_agent_id=actor, reason=data.reason,
        )
        await self._audit.record(
            action="task.status_changed",
            agent_id=actor,
            resource_type="tasks",
            resource_id=task_id,
            metadata={"from": previous_status, "to": target, "reason": data.reason},
        )
        await self.session.commit()
        return task

    async def get_history(self, task_id: str) -> list[TaskStatusHistory]:
        """List a task's status history (oldest first)."""
        await self._get_task(task_id)
        return await self._history.list_by_task(task_id)