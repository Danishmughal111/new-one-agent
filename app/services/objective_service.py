"""Objective business logic — persistence and settlement-of-objectives.

The ``run`` method orchestrates the deterministic ``CompanyWorkflow`` and
persists its outcome back onto the objective. The workflow is passed in
(dependency injection) so this service stays free of agent/orchestration
import cycles and remains testable with any engine.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.enums import ObjectiveStatus
from app.models.objective import Objective
from app.repositories.objective import ObjectiveRepository
from app.repositories.task import TaskRepository
from app.schemas.objective import ObjectiveCreate, ObjectiveUpdate
from app.services.audit_service import AuditService

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.orchestration.company_workflow import CompanyWorkflow


class ObjectiveService:
    """Business rules for company objectives."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._repo = ObjectiveRepository(session)
        self._tasks = TaskRepository(session)
        self._audit = AuditService(session)

    async def create(self, data: ObjectiveCreate) -> Objective:
        """Persist a new objective."""
        objective = Objective(
            title=data.title,
            description=data.description,
            priority=data.priority.value,
            created_by=data.created_by,
            metadata_=data.metadata,
            status=ObjectiveStatus.PENDING.value,
        )
        objective = await self._repo.add(objective)
        await self._audit.record(
            action="objective.create",
            resource_type="objectives",
            resource_id=objective.id,
            metadata={"title": objective.title},
        )
        await self.session.commit()
        return objective

    async def get(self, objective_id: str) -> Objective:
        """Fetch an objective by id."""
        objective = await self._repo.get(objective_id)
        if objective is None:
            raise NotFoundError("Objective", objective_id)
        return objective

    async def list(self, offset: int = 0, limit: int = 100) -> list[Objective]:
        """List objectives."""
        return await self._repo.list(offset=offset, limit=limit)

    async def update(self, objective_id: str, data: ObjectiveUpdate) -> Objective:
        """Update editable objective fields."""
        objective = await self.get(objective_id)
        updates = data.model_dump(exclude_unset=True)

        if "title" in updates and updates["title"] is not None:
            objective.title = updates["title"]
        if "description" in updates:
            objective.description = updates["description"]
        if "priority" in updates and updates["priority"] is not None:
            objective.priority = updates["priority"].value
        if "status" in updates and updates["status"] is not None:
            objective.status = updates["status"].value
        if "metadata" in updates and updates["metadata"] is not None:
            objective.metadata_ = updates["metadata"]

        await self.session.commit()
        return objective

    async def mark_running(self, objective_id: str) -> Objective:
        """Move an objective to IN_PROGRESS before workflow execution."""
        objective = await self.get(objective_id)
        if objective.status in (ObjectiveStatus.COMPLETED.value,):
            raise ValidationError("Objective is already completed")
        objective.status = ObjectiveStatus.IN_PROGRESS.value
        await self.session.commit()
        return objective

    async def settle(
        self,
        objective_id: str,
        result: dict[str, Any],
    ) -> Objective:
        """Persist a workflow result onto the objective (COMPLETED/FAILED)."""
        objective = await self.get(objective_id)
        objective.result = result

        if result.get("ok") is True:
            objective.status = ObjectiveStatus.COMPLETED.value
            objective.completed_at = datetime.now(timezone.utc)
        else:
            objective.status = ObjectiveStatus.FAILED.value

        await self.session.commit()
        return objective

    async def list_tasks(self, objective_id: str) -> list[Any]:
        """List tasks generated for an objective."""
        await self.get(objective_id)
        return await self._tasks.list_by_objective(objective_id)

    async def run(
        self,
        objective_id: str,
        workflow: "CompanyWorkflow",
    ) -> tuple[Objective, Any]:
        """Run the deterministic workflow for a persisted objective.

        Returns ``(objective, workflow_result)``. The route layer passes in a
        fully-built ``CompanyWorkflow``.
        """
        objective = await self.mark_running(objective_id)

        try:
            result = await workflow.run(objective.title, objective_id=objective.id)
        except Exception as exc:  # noqa: BLE001 - surface as failed result
            await self.settle(
                objective_id,
                {"ok": False, "final_status": "FAILED", "error": str(exc)},
            )
            raise

        objective = await self.settle(objective_id, result.to_dict())
        return objective, result