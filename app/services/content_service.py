"""TrendEra content generation service (one LLM call per article)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.llm import generate_article_text
from app.models.article import Article
from app.models.product import Product
from app.repositories.article import ArticleRepository
from app.repositories.product import ProductRepository
from app.services.qa_service import validate_article


class ContentService:
    """Generates and persists articles using exactly one LLM request."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._articles = ArticleRepository(session)
        self._products = ProductRepository(session)

    async def get_article(self, article_id: str) -> Article:
        """Fetch an article by id."""
        article = await self._articles.get(article_id)
        if article is None:
            raise NotFoundError("Article", article_id)
        return article

    async def generate(self, product_id: str) -> Article:
        """Generate one article for a product and persist it."""
        product: Product | None = await self._products.get(product_id)
        if product is None:
            raise NotFoundError("Product", product_id)

        # Build a structured prompt from stored product data.
        extra = [f"Category: {product.category}"] if product.category else None

        # ONE LLM request (or deterministic mock fallback).
        content = await generate_article_text(product.name, extra)

        title = f"{product.name} Review"

        # Deterministic QA (no LLM).
        qa = validate_article(
            title=title,
            content=content,
            product_name=product.name,
        )
        if not qa.passed:
            raise ValidationError(f"Generated article failed QA: {', '.join(qa.errors)}")

        article = Article(
            product_id=product.id,
            title=title,
            content=content,
            status="DRAFT",
            labels=[product.category] if product.category else None,
        )
        article = await self._articles.add(article)
        await self.session.commit()
        return article