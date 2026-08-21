"""Task status history persistence."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task_status_history import TaskStatusHistory
from app.repositories.base import BaseRepository


class TaskStatusHistoryRepository(BaseRepository[TaskStatusHistory]):
    """Persistence operations for task status history records.

    History records are append-only.
    """

    model = TaskStatusHistory

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_by_task(self, task_id: str) -> list[TaskStatusHistory]:
        """List status history for a task (oldest first)."""
        stmt = (
            select(TaskStatusHistory)
            .where(TaskStatusHistory.task_id == task_id)
            .order_by(TaskStatusHistory.timestamp.asc())
        )
        result = await self.session.scalars(stmt)
        return list(result.all())