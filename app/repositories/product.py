"""TrendEra product persistence."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    """Persistence operations for TrendEra products."""

    model = Product

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)