"""Task persistence."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    """Persistence operations for tasks."""

    model = Task

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_by_assignee(self, agent_id: str) -> list[Task]:
        """List tasks assigned to an agent."""
        stmt = select(Task).where(Task.assigned_agent_id == agent_id)
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def list_by_status(self, status: str) -> list[Task]:
        """List tasks in a given status."""
        stmt = select(Task).where(Task.status == status)
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def list_children(self, parent_task_id: str) -> list[Task]:
        """List subtasks of a parent task."""
        stmt = select(Task).where(Task.parent_task_id == parent_task_id)
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def list_by_objective(self, objective_id: str) -> list[Task]:
        """List tasks generated for a given objective."""
        stmt = select(Task).where(Task.parent_objective_id == objective_id)
        result = await self.session.scalars(stmt)
        return list(result.all())
