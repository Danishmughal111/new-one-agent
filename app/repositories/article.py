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

    async def list_with_product(self, limit: int = 100) -> list[tuple[Article, str | None]]:
        """List recent articles together with their product name (newest first)."""
        from app.models.product import Product

        stmt = (
            select(Article, Product.name)
            .join(Product, Article.product_id == Product.id)
            .order_by(Article.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [(article, product_name) for article, product_name in result.all()]