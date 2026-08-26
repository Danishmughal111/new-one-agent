"""Targeted tests for Blogger API v3 publishing (OAuth + mock HTTP)."""

import json

import httpx
import pytest

from app.core.config import settings
from app.models.blogger_connection import BloggerConnection
from app.schemas.product import ProductCreate
from app.services.blogger_service import BloggerService
from app.services.content_service import ContentService
from app.services.product_service import ProductService


@pytest.fixture(autouse=True)
async def _seed_connection(session):
    """Seed a persisted Blogger connection so publishing tests have a token."""
    session.add(BloggerConnection(refresh_token="test-refresh-token", blog_id="blog-1"))
    await session.commit()
    yield


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


async def test_prepare_draft_contains_html(session) -> None:
    product = await ProductService(session).create(
        ProductCreate(name="Draft Gadget", category="Electronics")
    )
    article = await ContentService(session).generate(product.id)

    draft = await BloggerService(session).prepare_draft(article.id)

    assert draft.content.startswith("<h2>Draft Gadget Review</h2>")
    assert "<p>" in draft.content
    assert "Draft Gadget" in draft.content


async def test_publish_sends_html_content(session) -> None:
    settings.google_blog_id = "blog-1"
    settings.google_refresh_token = "refresh-1"

    product = await ProductService(session).create(
        ProductCreate(name="HTML Gadget", category="Electronics")
    )
    article = await ContentService(session).generate(product.id)

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "test-token"})
        if request.url.host == "www.googleapis.com":
            captured["content"] = json.loads(request.read())["content"]
            return httpx.Response(
                200, json={"id": "post-html", "url": "u", "status": "DRAFT"}
            )
        return httpx.Response(404, json={"error": "unexpected"})

    result = await BloggerService(session).publish(
        article.id,
        publish_now=False,
        transport=httpx.MockTransport(handler),
    )

    assert result["id"] == "post-html"
    assert captured["content"].startswith("<h2>HTML Gadget Review</h2>")
    assert "<p>" in captured["content"]
    assert "HTML Gadget" in captured["content"]


async def test_no_deepseek_request(session, monkeypatch) -> None:
    async def fail(*args, **kwargs):
        raise AssertionError("DeepSeek must not be called")

    monkeypatch.setattr("app.core.llm._deepseek_completion", fail)

    product = await ProductService(session).create(
        ProductCreate(name="Mock Only Gadget", category="Electronics")
    )
    article = await ContentService(session).generate(product.id)

    assert article.content.startswith("# Mock Only Gadget Review")
    assert "Mock Only Gadget" in article.content