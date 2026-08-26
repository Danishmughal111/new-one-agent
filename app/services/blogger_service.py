"""TrendEra Blogger API v3 publishing (OAuth 2.0)."""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.oauth import build_authorization_url as _build_authorization_url
from app.models.article import Article
from app.models.base import utcnow
from app.repositories.article import ArticleRepository
from app.schemas.article import BloggerDraftPayload
from app.services.blogger_connection_service import BloggerConnectionService
from app.services.html_converter import markdown_to_blogger_html
from app.services.qa_service import validate_article

BLOGGER_API = "https://www.googleapis.com/blogger/v3"


class BloggerService:
    """Publishes QA-passed articles to Blogger (draft or published)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._articles = ArticleRepository(session)
        self._connections = BloggerConnectionService(session)

    # ------------------------------------------------------------------
    # OAuth helpers
    # ------------------------------------------------------------------
    def build_auth_url(self) -> str:
        """Return the Google OAuth consent URL to start authorization."""
        return _build_authorization_url()

    async def handle_callback(self, code: str) -> dict:
        """Exchange an authorization code and persist the connection."""
        return await self._connections.connect(code)

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------
    async def prepare_draft(self, article_id: str) -> BloggerDraftPayload:
        """Return title/content/labels for a Blogger draft."""
        article = await self._get_article(article_id)
        return BloggerDraftPayload(
            title=article.title,
            content=markdown_to_blogger_html(article.content),
            labels=article.labels or [],
        )

    async def publish(
        self,
        article_id: str,
        *,
        publish_now: bool,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> dict:
        """Publish a QA-passed article to Blogger API v3.

        ``publish_now=False`` creates a DRAFT; ``True`` creates a published
        post. Publishing is refused unless the article passes deterministic QA.
        """
        article = await self._get_article(article_id)

        self._ensure_blog_configured()

        # 6. Only publish after deterministic QA passes (no LLM).
        qa = validate_article(
            title=article.title,
            content=article.content,
            product_name=_product_name_for(article),
        )
        if not qa.passed:
            raise ValidationError(
                f"Article failed QA: {', '.join(qa.errors)}"
            )

        access_token = await self._connections.get_access_token(transport=transport)
        body = {
            "kind": "blogger#post",
            "blog": {"id": settings.google_blog_id},
            "title": article.title,
            "content": markdown_to_blogger_html(article.content),
            "labels": article.labels or [],
        }
        # DRAFT is the default; set LIVE only when publish_now is requested.
        # Blogger v3 treats a missing "status" as DRAFT.
        if publish_now:
            body["status"] = "LIVE"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        url = f"{BLOGGER_API}/blogs/{settings.google_blog_id}/posts/"

        async with httpx.AsyncClient(transport=transport, timeout=60) as client:
            response = await client.post(url, json=body, headers=headers)
            response.raise_for_status()
            created = response.json()

        # Persist the Blogger post identity and status on the article.
        article.blogger_post_id = created.get("id")
        article.blogger_url = created.get("url")
        article.status = "PUBLISHED" if publish_now else "DRAFT"
        if publish_now:
            article.published_at = utcnow()
        await self.session.commit()

        return {
            "id": created["id"],
            "url": created.get("url"),
            "status": created.get("status"),
            "published": publish_now,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _get_article(self, article_id: str) -> Article:
        article: Article | None = await self._articles.get(article_id)
        if article is None:
            raise NotFoundError("Article", article_id)
        return article

    @staticmethod
    def _ensure_blog_configured() -> None:
        if not settings.google_blog_id.strip():
            raise ValidationError("Google blog ID is not configured")


def _product_name_for(article: Article) -> str:
    """Derive the product name to check QA against.

    Prefer the explicit ``product_name`` stored in article metadata (set by the
    workflow), then fall back to the legacy ``{product.name} Review`` title
    convention so QA remains deterministic for manually created articles.
    """
    metadata = article.metadata_ or {}
    if metadata.get("product_name"):
        return metadata["product_name"]

    title = article.title or ""
    if title.endswith(" Review"):
        return title[: -len(" Review")].strip()
    return title.removesuffix(" Review").strip()
