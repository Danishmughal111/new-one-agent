"""Agent persistence."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.repositories.base import BaseRepository


class AgentRepository(BaseRepository[Agent]):
    """Persistence operations for agents."""

    model = Agent

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_name(self, name: str) -> Agent | None:
        """Fetch an agent by its unique name."""
        stmt = select(Agent).where(Agent.name == name)
        return await self.session.scalar(stmt)

    async def list_by_department(self, department_id: str) -> list[Agent]:
        """List agents belonging to a department."""
        stmt = select(Agent).where(Agent.department_id == department_id)
        result = await self.session.scalars(stmt)
        return list(result.all())