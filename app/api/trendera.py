"""TrendEra MVP endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.schemas.article import ArticleResponse, BloggerDraftPayload
from app.schemas.product import ProductCreate, ProductResponse
from app.services.blogger_service import BloggerService
from app.services.content_service import ContentService
from app.services.product_service import ProductService

router = APIRouter(prefix="/trendera", tags=["trendera"])


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