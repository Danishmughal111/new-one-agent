"""TrendEra endpoints (products, article generation, Blogger publishing)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.schemas.article import (
    ArticleResponse,
    BloggerAuthUrlResponse,
    BloggerDraftPayload,
    BloggerPublishRequest,
    BloggerPublishResponse,
)
from app.schemas.product import ProductCreate, ProductResponse
from app.services.blogger_service import BloggerService
from app.services.content_service import ContentService
from app.services.product_service import ProductService

router = APIRouter(prefix="/trendera", tags=["trendera"])


def _get_blogger_transport(request: Request):
    """Optional test transport set on app.state; defaults to None (real HTTP)."""
    return getattr(request.app.state, "blogger_transport", None)


@router.post("/products", response_model=ProductResponse, status_code=201)
async def create_product(
    payload: ProductCreate,
    session: AsyncSession = Depends(get_session),
):
    return await ProductService(session).create(payload)


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
    """Exchange an authorization code for Blogger credentials."""
    await BloggerService(session).handle_callback(code)
    return {"status": "ok"}


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