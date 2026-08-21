"""Department business logic."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.department import Department
from app.repositories.department import DepartmentRepository
from app.schemas.department import DepartmentCreate, DepartmentUpdate
from app.services.audit_service import AuditService


class DepartmentService:
    """Business rules for managing departments."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._repo = DepartmentRepository(session)
        self._audit = AuditService(session)

    async def create(self, data: DepartmentCreate) -> Department:
        """Create a department, enforcing a unique name."""
        if await self._repo.get_by_name(data.name):
            raise ValidationError(f"Department with name '{data.name}' already exists")

        department = Department(
            name=data.name,
            description=data.description,
            status=data.status.value,
        )
        department = await self._repo.add(department)
        await self._audit.record(
            action="department.create",
            resource_type="departments",
            resource_id=department.id,
            metadata={"name": department.name},
        )
        await self.session.commit()
        return department

    async def get(self, department_id: str) -> Department:
        """Fetch a department by id, raising if not found."""
        department = await self._repo.get(department_id)
        if department is None:
            raise NotFoundError("Department", department_id)
        return department

    async def list(self, offset: int = 0, limit: int = 100) -> list[Department]:
        """List departments."""
        return await self._repo.list(offset=offset, limit=limit)

    async def update(self, department_id: str, data: DepartmentUpdate) -> Department:
        """Update editable department fields."""
        department = await self.get(department_id)
        updates = data.model_dump(exclude_unset=True)

        if "name" in updates and updates["name"] is not None:
            existing = await self._repo.get_by_name(updates["name"])
            if existing and existing.id != department_id:
                raise ValidationError(
                    f"Department with name '{updates['name']}' already exists"
                )
            department.name = updates["name"]

        if "description" in updates:
            department.description = updates["description"]

        if "status" in updates and updates["status"] is not None:
            department.status = updates["status"].value

        await self.session.commit()
        return department