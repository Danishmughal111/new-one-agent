"""Agent business logic (registration and lifecycle)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.permissions import is_valid_permission
from app.models.agent import Agent
from app.repositories.agent import AgentRepository
from app.repositories.department import DepartmentRepository
from app.schemas.agent import AgentCreate, AgentUpdate
from app.services.audit_service import AuditService


class AgentService:
    """Business rules for registering and managing agents."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._repo = AgentRepository(session)
        self._departments = DepartmentRepository(session)
        self._audit = AuditService(session)

    async def create(self, data: AgentCreate) -> Agent:
        """Register a new agent.

        Validates:
        - unique agent name
        - department exists (when provided)
        - all permissions are known permission keys
        """
        if await self._repo.get_by_name(data.name):
            raise ValidationError(f"Agent with name '{data.name}' already exists")

        if data.department_id is not None:
            department = await self._departments.get(data.department_id)
            if department is None:
                raise NotFoundError("Department", data.department_id)

        unknown_permissions = [
            p for p in data.permissions if not is_valid_permission(p)
        ]
        if unknown_permissions:
            raise ValidationError(
                f"Unknown permission(s): {', '.join(sorted(unknown_permissions))}"
            )

        agent = Agent(
            name=data.name,
            role=data.role,
            department_id=data.department_id,
            status=data.status.value,
            capabilities=data.capabilities,
            permissions=data.permissions,
            configuration=data.configuration,
        )
        agent = await self._repo.add(agent)
        await self._audit.record(
            action="agent.create",
            agent_id=agent.id,
            resource_type="agents",
            resource_id=agent.id,
            metadata={"role": agent.role, "permissions": agent.permissions},
        )
        await self.session.commit()
        return agent

    async def get(self, agent_id: str) -> Agent:
        """Fetch an agent by id, raising if not found."""
        agent = await self._repo.get(agent_id)
        if agent is None:
            raise NotFoundError("Agent", agent_id)
        return agent

    async def list(self, offset: int = 0, limit: int = 100) -> list[Agent]:
        """List agents."""
        return await self._repo.list(offset=offset, limit=limit)

    async def update(self, agent_id: str, data: AgentUpdate) -> Agent:
        """Update editable agent fields."""
        agent = await self.get(agent_id)
        updates = data.model_dump(exclude_unset=True)

        if "name" in updates and updates["name"] is not None:
            existing = await self._repo.get_by_name(updates["name"])
            if existing and existing.id != agent_id:
                raise ValidationError(f"Agent with name '{updates['name']}' already exists")
            agent.name = updates["name"]

        if "role" in updates and updates["role"] is not None:
            agent.role = updates["role"]

        if "department_id" in updates:
            if updates["department_id"] is not None:
                department = await self._departments.get(updates["department_id"])
                if department is None:
                    raise NotFoundError("Department", updates["department_id"])
            agent.department_id = updates["department_id"]

        if "status" in updates and updates["status"] is not None:
            agent.status = updates["status"].value

        if "capabilities" in updates and updates["capabilities"] is not None:
            agent.capabilities = updates["capabilities"]

        if "permissions" in updates and updates["permissions"] is not None:
            unknown_permissions = [
                p for p in updates["permissions"] if not is_valid_permission(p)
            ]
            if unknown_permissions:
                raise ValidationError(
                    f"Unknown permission(s): {', '.join(sorted(unknown_permissions))}"
                )
            agent.permissions = updates["permissions"]

        if "configuration" in updates and updates["configuration"] is not None:
            agent.configuration = updates["configuration"]

        await self.session.commit()
        return agent