"""TrendEra Blogger draft preparation (no OAuth/publishing)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.article import Article
from app.repositories.article import ArticleRepository
from app.schemas.article import BloggerDraftPayload


class BloggerService:
    """Transforms a validated article into a Blogger draft payload."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._articles = ArticleRepository(session)

    async def prepare_draft(self, article_id: str) -> BloggerDraftPayload:
        """Return title/content/labels for a Blogger draft."""
        article: Article | None = await self._articles.get(article_id)
        if article is None:
            raise NotFoundError("Article", article_id)

        return BloggerDraftPayload(
            title=article.title,
            content=article.content,
            labels=article.labels or [],
        )