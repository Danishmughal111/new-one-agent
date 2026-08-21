"""Department persistence."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department import Department
from app.repositories.base import BaseRepository


class DepartmentRepository(BaseRepository[Department]):
    """Persistence operations for departments."""

    model = Department

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_name(self, name: str) -> Department | None:
        """Fetch a department by its unique name."""
        stmt = select(Department).where(Department.name == name)
        return await self.session.scalar(stmt)