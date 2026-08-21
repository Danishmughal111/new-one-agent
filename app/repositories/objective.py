"""Objective persistence."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.objective import Objective
from app.repositories.base import BaseRepository


class ObjectiveRepository(BaseRepository[Objective]):
    """Persistence operations for company objectives."""

    model = Objective

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)