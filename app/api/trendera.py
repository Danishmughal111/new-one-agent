"""TrendEra endpoints (products, article generation, Blogger publishing)."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.core.config import settings
from app.repositories.article import ArticleRepository
from app.repositories.product import ProductRepository
from app.schemas.article import (
    ArticleListResponse,
    ArticleResponse,
    BloggerAuthUrlResponse,
    BloggerDraftPayload,
    BloggerPublishRequest,
    BloggerPublishResponse,
)
from app.schemas.product import ProductCreate, ProductResponse
from app.schemas.trendera_workflow import TrenderaRunRequest, TrenderaRunResponse
from app.services.blogger_service import BloggerService
from app.services.content_service import ContentService
from app.services.product_service import ProductService
from app.services.trendera_workflow import TrenderaWorkflow

router = APIRouter(prefix="/trendera", tags=["trendera"])


def _get_blogger_transport(request: Request):
    """Optional test transport set on app.state; defaults to None (real HTTP)."""
    return getattr(request.app.state, "blogger_transport", None)


def _get_image_transport(request: Request):
    """Optional Pollinations test transport; defaults to None (real HTTP)."""
    return getattr(request.app.state, "pollinations_transport", None)


@router.post("/products", response_model=ProductResponse, status_code=201)
async def create_product(
    payload: ProductCreate,
    session: AsyncSession = Depends(get_session),
):
    return await ProductService(session).create(payload)


@router.get("/products", response_model=list[ProductResponse])
async def list_products(
    session: AsyncSession = Depends(get_session),
):
    """List products created by the TrendEra workflow."""
    return await ProductRepository(session).list(limit=100)


@router.post("/products/{product_id}/generate", response_model=ArticleResponse)
async def generate_article(
    product_id: str,
    session: AsyncSession = Depends(get_session),
):
    return await ContentService(session).generate(product_id)


@router.get("/articles/{article_id}", response_model=ArticleResponse)
async def get_article(
    article_id: str,
    session: AsyncSession = Depends(get_session),
):
    return await ContentService(session).get_article(article_id)


@router.get("/articles", response_model=list[ArticleListResponse])
async def list_articles(
    session: AsyncSession = Depends(get_session),
):
    """List generated articles (newest first) with their product name."""
    rows = await ArticleRepository(session).list_with_product(limit=100)
    return [
        {
            "id": article.id,
            "product_id": article.product_id,
            "product_name": product_name,
            "title": article.title,
            "status": article.status,
            "labels": article.labels,
            "blogger_post_id": article.blogger_post_id,
            "blogger_url": article.blogger_url,
            "published_at": article.published_at,
            "created_at": article.created_at,
            "updated_at": article.updated_at,
        }
        for article, product_name in rows
    ]


@router.post("/articles/{article_id}/prepare-blogger", response_model=BloggerDraftPayload)
async def prepare_blogger(
    article_id: str,
    session: AsyncSession = Depends(get_session),
):
    return await BloggerService(session).prepare_draft(article_id)


# ---------------------------------------------------------------------------
# Blogger OAuth 2.0 + publishing
# ---------------------------------------------------------------------------
@router.get("/blogger/oauth/start", response_model=BloggerAuthUrlResponse)
async def blogger_oauth_start(session: AsyncSession = Depends(get_session)):
    """Return the Google OAuth consent URL to begin authorization."""
    url = BloggerService(session).build_auth_url()
    return {"authorization_url": url}


@router.get("/blogger/oauth/callback")
async def blogger_oauth_callback(
    code: str,
    session: AsyncSession = Depends(get_session),
):
    """Exchange an authorization code and persist Blogger credentials."""
    await BloggerService(session).handle_callback(code)
    return RedirectResponse(url=settings.frontend_url, status_code=302)


@router.post("/articles/{article_id}/publish", response_model=BloggerPublishResponse)
async def publish_article(
    article_id: str,
    payload: BloggerPublishRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Publish a QA-passed article as a Blogger draft or live post."""
    transport = _get_blogger_transport(request)
    result = await BloggerService(session).publish(
        article_id,
        publish_now=payload.publish_now,
        transport=transport,
    )
    return result


@router.post("/run", response_model=TrenderaRunResponse)
async def run_autonomous_workflow(
    payload: TrenderaRunRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Trigger one autonomous discovery -> article -> publish run."""
    return await TrenderaWorkflow(session).run(
        publish_now=payload.publish_now,
        image_transport=_get_image_transport(request),
        blogger_transport=_get_blogger_transport(request),
    )