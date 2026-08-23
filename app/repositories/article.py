"""TrendEra article persistence."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.repositories.base import BaseRepository


class ArticleRepository(BaseRepository[Article]):
    """Persistence operations for TrendEra articles."""

    model = Article

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_by_product(self, product_id: str) -> list[Article]:
        """List articles generated for a product."""
        stmt = select(Article).where(Article.product_id == product_id)
        result = await self.session.scalars(stmt)
        return list(result.all())