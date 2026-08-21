"""Workflow business logic."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.workflow import Workflow
from app.repositories.workflow import WorkflowRepository
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate
from app.services.audit_service import AuditService


class WorkflowService:
    """Business rules for managing workflow definitions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._repo = WorkflowRepository(session)
        self._audit = AuditService(session)

    async def create(self, data: WorkflowCreate) -> Workflow:
        """Create a workflow definition, enforcing a unique name."""
        if await self._repo.get_by_name(data.name):
            raise ValidationError(f"Workflow with name '{data.name}' already exists")

        workflow = Workflow(
            name=data.name,
            description=data.description,
            status=data.status.value,
            configuration=data.configuration,
        )
        workflow = await self._repo.add(workflow)
        await self._audit.record(
            action="workflow.create",
            resource_type="workflows",
            resource_id=workflow.id,
            metadata={"name": workflow.name},
        )
        await self.session.commit()
        return workflow

    async def get(self, workflow_id: str) -> Workflow:
        """Fetch a workflow by id, raising if not found."""
        workflow = await self._repo.get(workflow_id)
        if workflow is None:
            raise NotFoundError("Workflow", workflow_id)
        return workflow

    async def list(self, offset: int = 0, limit: int = 100) -> list[Workflow]:
        """List workflows."""
        return await self._repo.list(offset=offset, limit=limit)

    async def update(self, workflow_id: str, data: WorkflowUpdate) -> Workflow:
        """Update editable workflow fields."""
        workflow = await self.get(workflow_id)
        updates = data.model_dump(exclude_unset=True)

        if "name" in updates and updates["name"] is not None:
            existing = await self._repo.get_by_name(updates["name"])
            if existing and existing.id != workflow_id:
                raise ValidationError(
                    f"Workflow with name '{updates['name']}' already exists"
                )
            workflow.name = updates["name"]

        if "description" in updates:
            workflow.description = updates["description"]
        if "status" in updates and updates["status"] is not None:
            workflow.status = updates["status"].value
        if "configuration" in updates and updates["configuration"] is not None:
            workflow.configuration = updates["configuration"]

        await self.session.commit()
        return workflow