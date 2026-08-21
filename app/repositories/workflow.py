"""Workflow persistence."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import Workflow
from app.repositories.base import BaseRepository


class WorkflowRepository(BaseRepository[Workflow]):
    """Persistence operations for workflow definitions."""

    model = Workflow

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_name(self, name: str) -> Workflow | None:
        """Fetch a workflow by its unique name."""
        stmt = select(Workflow).where(Workflow.name == name)
        return await self.session.scalar(stmt)