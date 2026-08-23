"""Targeted tests for Blogger API v3 publishing (OAuth + mock HTTP)."""

import httpx

from app.core.config import settings
from app.schemas.product import ProductCreate
from app.services.blogger_service import BloggerService
from app.services.content_service import ContentService
from app.services.product_service import ProductService


def _mock_transport(publish_now: bool) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "test-token"})
        if request.url.host == "www.googleapis.com":
            sent = request.read()
            import json

            body = json.loads(sent) if sent else {}
            assert body["title"]
            assert body["content"]
            status = body.get("status", "DRAFT")
            return httpx.Response(
                200,
                json={
                    "id": "post-123",
                    "url": "http://blog.example/post-123",
                    "status": status,
                },
            )
        return httpx.Response(404, json={"error": "unexpected"})

    return httpx.MockTransport(handler)


async def test_publish_draft(session) -> None:
    settings.google_blog_id = "blog-1"
    settings.google_refresh_token = "refresh-1"

    product = await ProductService(session).create(
        ProductCreate(name="Test Gadget", category="Electronics")
    )
    article = await ContentService(session).generate(product.id)

    result = await BloggerService(session).publish(
        article.id,
        publish_now=False,
        transport=_mock_transport(publish_now=False),
    )
    assert result["published"] is False
    assert result["id"] == "post-123"


async def test_publish_live(session) -> None:
    settings.google_blog_id = "blog-1"
    settings.google_refresh_token = "refresh-1"

    product = await ProductService(session).create(
        ProductCreate(name="Test Gadget", category="Electronics")
    )
    article = await ContentService(session).generate(product.id)

    result = await BloggerService(session).publish(
        article.id,
        publish_now=True,
        transport=_mock_transport(publish_now=True),
    )
    assert result["published"] is True
    assert result["status"] == "LIVE"


async def test_publish_blocked_by_qa(session) -> None:
    settings.google_blog_id = "blog-1"
    settings.google_refresh_token = "refresh-1"

    from app.core.exceptions import ValidationError
    from app.models.article import Article

    # Insert an article that fails QA (missing product name, short content).
    article = Article(
        product_id="missing",
        title="Bad",
        content="too short",
        status="DRAFT",
    )
    session.add(article)
    await session.commit()

    service = BloggerService(session)
    try:
        await service.publish(article.id, publish_now=False, transport=_mock_transport(False))
        raise AssertionError("publish should have been blocked by QA")
    except ValidationError:
        pass