"""Targeted tests for the autonomous TrendEra workflow (mocked external I/O)."""

import json

import httpx
import pytest

from app.core.config import settings
from app.models.blogger_connection import BloggerConnection
from app.schemas.product import ProductCreate
from app.services.html_converter import insert_image_after_intro, markdown_to_blogger_html
from app.services.product_discovery import CATALOG, ProductDiscoveryService
from app.services.product_service import ProductService
from app.services.trendera_workflow import (
    TrenderaWorkflow,
    is_public_url,
    validate_publication_html,
)


@pytest.fixture(autouse=True)
def _stub_research(monkeypatch):
    """Avoid real network research in workflow tests (catalog fallback)."""

    async def fake_research(self, candidate, transport=None):
        return {
            "status": "partial",
            "sources_attempted": 1,
            "sources_succeeded": 1,
            "sources": [],
            "missing_information": [],
            "data": {
                "name": candidate.get("name"),
                "brand": candidate.get("brand"),
                "category": candidate.get("category"),
                "description": candidate.get("description"),
                "features": candidate.get("features") or [],
                "specs": candidate.get("specs") or {},
                "limitations": candidate.get("limitations") or [],
                "advantages": candidate.get("features") or [],
                "disadvantages": candidate.get("limitations") or [],
                "target_audience": ["People shopping for this"],
                "pricing": None,
                "alternatives": [],
                "faqs": ["Is it worth buying?"],
                "live_summary": None,
            },
        }

    monkeypatch.setattr("app.services.research_service.ResearchService.research", fake_research)


def _configure_blog():
    settings.google_blog_id = "blog-1"
    settings.google_refresh_token = "refresh-1"


async def _seed_connection(session):
    session.add(BloggerConnection(refresh_token="test-refresh-token", blog_id="blog-1"))
    await session.commit()


def _image_transport():
    calls = {"count": 0}

    def handler(request):
        calls["count"] += 1
        if request.url.host == "image.pollinations.ai":
            return httpx.Response(200, content=b"img-bytes", headers={"content-type": "image/jpeg"})
        return httpx.Response(404, json={"error": "unexpected"})

    return httpx.MockTransport(handler), calls


def _blogger_transport():
    captured = {}

    def handler(request):
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "test-token"})
        if request.url.host == "www.googleapis.com":
            captured["body"] = json.loads(request.read())
            status = captured["body"].get("status", "DRAFT")
            return httpx.Response(200, json={"id": "post-1", "url": "http://blog/x", "status": status})
        return httpx.Response(404, json={"error": "unexpected"})

    return httpx.MockTransport(handler), captured


async def test_workflow_completes_draft(session):
    _configure_blog()
    img_t, img_calls = _image_transport()
    blog_t, _ = _blogger_transport()
    result = await TrenderaWorkflow(session).run(publish_now=False, image_transport=img_t, blogger_transport=blog_t)
    assert result["status"] == "success"
    assert result["published"] is False
    assert result["publish_status"] == "draft"
    assert result["selected_product"]
    assert result["product_id"]
    assert result["article_id"]
    assert result["image_url"].startswith("https://image.pollinations.ai/")
    assert img_calls["count"] == 1


async def test_workflow_completes_live(session):
    _configure_blog()
    await _seed_connection(session)
    img_t, _ = _image_transport()
    blog_t, captured = _blogger_transport()
    result = await TrenderaWorkflow(session).run(publish_now=True, image_transport=img_t, blogger_transport=blog_t)
    assert result["status"] == "success"
    assert result["published"] is True
    assert result["publish_status"] == "live"
    assert captured["body"]["status"] == "LIVE"


async def test_image_inserted_and_alt_present(session):
    _configure_blog()
    await _seed_connection(session)
    img_t, _ = _image_transport()
    blog_t, captured = _blogger_transport()
    result = await TrenderaWorkflow(session).run(publish_now=True, image_transport=img_t, blogger_transport=blog_t)
    html = captured["body"]["content"]
    assert "<img" in html
    assert 'alt="' in html
    assert "image.pollinations.ai" in html
    assert html.index("<img") > html.index("<p")
    assert result["selected_product"] in html


async def test_live_without_connection_partial_success(session):
    _configure_blog()
    img_t, _ = _image_transport()
    blog_t, captured = _blogger_transport()
    result = await TrenderaWorkflow(session).run(publish_now=True, image_transport=img_t, blogger_transport=blog_t)
    assert result["status"] == "partial_success"
    assert result["published"] is False
    assert result["article_id"]  # article is preserved
    assert "not connected" in result["error"].lower()
    assert captured == {}  # Blogger never called


async def test_duplicate_products_skipped(session):
    _configure_blog()
    await ProductService(session).create(ProductCreate(name=CATALOG[0]["name"], category=CATALOG[0]["category"]))
    img_t, _ = _image_transport()
    blog_t, _ = _blogger_transport()
    result = await TrenderaWorkflow(session).run(publish_now=False, image_transport=img_t, blogger_transport=blog_t)
    assert result["status"] == "success"
    assert result["selected_product"].lower() != CATALOG[0]["name"].lower()


async def test_no_product_stops_without_deepseek(session, monkeypatch):
    async def none(self, limit=5):
        return []

    monkeypatch.setattr(ProductDiscoveryService, "discover_candidates", none)

    async def fail(*a, **k):
        raise AssertionError("DeepSeek must not be called")

    monkeypatch.setattr("app.services.trendera_workflow.generate_article_text", fail)
    result = await TrenderaWorkflow(session).run(publish_now=False)
    assert result["status"] == "skipped"


async def test_one_article_generation_call(session, monkeypatch):
    _configure_blog()
    from app.core.llm import generate_article_text as real

    calls = []

    async def counting(*a, **k):
        calls.append(1)
        return await real(*a, **k)

    monkeypatch.setattr("app.services.trendera_workflow.generate_article_text", counting)
    img_t, _ = _image_transport()
    blog_t, _ = _blogger_transport()
    result = await TrenderaWorkflow(session).run(publish_now=False, image_transport=img_t, blogger_transport=blog_t)
    assert result["status"] == "success"
    assert len(calls) == 1


async def test_image_generated_once(session):
    _configure_blog()
    img_t, img_calls = _image_transport()
    blog_t, _ = _blogger_transport()
    await TrenderaWorkflow(session).run(publish_now=False, image_transport=img_t, blogger_transport=blog_t)
    assert img_calls["count"] == 1


async def test_qa_failure_blocks_publish_and_image(session, monkeypatch):
    _configure_blog()

    async def short(*a, **k):
        return "too short"

    monkeypatch.setattr("app.services.trendera_workflow.generate_article_text", short)
    img_t, img_calls = _image_transport()
    blog_t, captured = _blogger_transport()
    result = await TrenderaWorkflow(session).run(publish_now=False, image_transport=img_t, blogger_transport=blog_t)
    assert result["status"] == "failed"
    assert "QA" in result["error"]
    assert img_calls["count"] == 0
    assert captured == {}


async def test_no_deepseek_request(session, monkeypatch):
    _configure_blog()

    async def fail(*a, **k):
        raise AssertionError("DeepSeek must not be called")

    monkeypatch.setattr("app.core.llm._deepseek_completion", fail)
    img_t, _ = _image_transport()
    blog_t, _ = _blogger_transport()
    result = await TrenderaWorkflow(session).run(publish_now=False, image_transport=img_t, blogger_transport=blog_t)
    assert result["status"] == "success"


def test_image_after_introduction():
    md = "# Gadget Review\n\nThis is the introduction paragraph.\n\nMore details here.\n"
    content = insert_image_after_intro(md, "https://example.com/img.png", "Gadget image")
    html = markdown_to_blogger_html(content)
    assert '<img src="https://example.com/img.png" alt="Gadget image"/>' in html
    assert html.index("<img") > html.index("<p")


def test_local_path_rejected():
    assert is_public_url("https://example.com/img.png") is True
    assert is_public_url("/tmp/img.png") is False
    assert is_public_url("file:///x.png") is False
    assert is_public_url("C:\\img.png") is False
    errors = validate_publication_html("<p>x</p>", "/tmp/img.png", "alt")
    assert any("public" in e for e in errors)
