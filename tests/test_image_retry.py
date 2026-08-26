"""Tests for Pollinations image retry + workflow image-failure handling."""

import httpx
import pytest

from app.core.config import settings
from app.models.blogger_connection import BloggerConnection
from app.services.image_service import ImageService
from app.services.trendera_workflow import TrenderaWorkflow


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


async def _noop_sleep(seconds):
    return None


async def test_image_succeeds_first_attempt(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _noop_sleep)
    calls = {"count": 0}

    def handler(request):
        calls["count"] += 1
        return httpx.Response(200, content=b"img", headers={"content-type": "image/jpeg"})

    url = await ImageService().generate(product_name="X", category="Y", transport=httpx.MockTransport(handler))
    assert url.startswith("https://image.pollinations.ai/")
    assert calls["count"] == 1


async def test_image_retries_on_500_then_succeeds(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _noop_sleep)
    urls = []

    def handler(request):
        urls.append(str(request.url))
        if len(urls) == 1:
            return httpx.Response(500)
        return httpx.Response(200, content=b"img", headers={"content-type": "image/jpeg"})

    url = await ImageService().generate(product_name="X", category="Y", transport=httpx.MockTransport(handler))
    assert url
    assert len(urls) == 2
    assert urls[0] != urls[1]  # a new random seed is used on retry


async def test_image_fails_after_all_attempts(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _noop_sleep)
    calls = {"count": 0}

    def handler(request):
        calls["count"] += 1
        return httpx.Response(500)

    with pytest.raises(httpx.HTTPStatusError):
        await ImageService().generate(product_name="X", transport=httpx.MockTransport(handler))
    assert calls["count"] == 3


async def test_image_fails_immediately_on_permanent_error(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _noop_sleep)
    calls = {"count": 0}

    def handler(request):
        calls["count"] += 1
        return httpx.Response(404)

    with pytest.raises(httpx.HTTPStatusError):
        await ImageService().generate(product_name="X", transport=httpx.MockTransport(handler))
    assert calls["count"] == 1  # no retry for permanent 404


async def test_workflow_publishes_without_image_on_failure(session, monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _noop_sleep)
    settings.google_blog_id = "blog-1"
    session.add(BloggerConnection(refresh_token="test-token", blog_id="blog-1"))
    await session.commit()

    def image_handler(request):
        return httpx.Response(500)

    def blogger_handler(request):
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "at"})
        if request.url.host == "www.googleapis.com":
            return httpx.Response(200, json={"id": "post-1", "url": "http://blog/x", "status": "LIVE"})
        return httpx.Response(404)

    result = await TrenderaWorkflow(session).run(
        publish_now=True,
        image_transport=httpx.MockTransport(image_handler),
        blogger_transport=httpx.MockTransport(blogger_handler),
    )

    assert result["status"] == "partial_success"
    assert result["article_generated"] is True
    assert result["image_generated"] is False
    assert result["image_status"] == "failed"
    assert result["published"] is True
    assert result["blogger_result"]["url"] == "http://blog/x"
    assert "Image generation failed" in result["error"]


async def test_workflow_draft_saved_without_image(session, monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _noop_sleep)

    def image_handler(request):
        return httpx.Response(500)

    result = await TrenderaWorkflow(session).run(
        publish_now=False,
        image_transport=httpx.MockTransport(image_handler),
    )

    assert result["status"] == "partial_success"
    assert result["article_generated"] is True
    assert result["image_generated"] is False
    assert result["image_status"] == "failed"
    assert result["published"] is False
    assert result["article_id"]  # article is preserved
    assert "Image generation failed" in result["error"]
