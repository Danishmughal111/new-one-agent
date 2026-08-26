"""End-to-end integration test for the autonomous TrendEra content pipeline.

Runs discovery -> research -> opportunity -> content -> image -> Blogger publish
with every external service mocked, asserting the pipeline works end to end:
image generated AND inserted into final HTML, required sections present,
Blogger receives title + content(<img>) + labels, and publishing is only
claimed when Blogger returns a successful response. No external API credits are
consumed (DEEPSEEK_API_KEY="" forces the deterministic mock LLM; transports
stub the image/Blogger HTTP calls).
"""

import json

import httpx
import pytest

from app.core.config import settings
from app.models.blogger_connection import BloggerConnection
from app.repositories.article import ArticleRepository
from app.services.html_converter import markdown_to_blogger_html
from app.services.seo_service import validate_structure
from app.services.trendera_workflow import TrenderaWorkflow


@pytest.fixture(autouse=True)
def _stub_research(monkeypatch):
    async def fake_research(self, candidate, transport=None):
        return {
            "status": "partial",
            "sources_attempted": 1,
            "sources_succeeded": 1,
            "sources": [{"name": "Catalog", "url": "https://example.com/catalog", "type": "catalog", "fetched": True}],
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
    def handler(request):
        if request.url.host == "image.pollinations.ai":
            return httpx.Response(200, content=b"img-bytes", headers={"content-type": "image/jpeg"})
        return httpx.Response(404, json={"error": "unexpected"})

    return httpx.MockTransport(handler)


def _blogger_transport():
    captured = {}

    def handler(request):
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "test-token"})
        if request.url.host == "www.googleapis.com":
            captured["body"] = json.loads(request.read())
            return httpx.Response(200, json={"id": "post-1", "url": "http://blog/x", "status": "LIVE"})
        return httpx.Response(404, json={"error": "unexpected"})

    return httpx.MockTransport(handler), captured


async def test_full_pipeline_publishes_with_image_and_sections(session):
    _configure_blog()
    await _seed_connection(session)

    blog_t, captured = _blogger_transport()
    result = await TrenderaWorkflow(session).run(
        publish_now=True, image_transport=_image_transport(), blogger_transport=blog_t
    )

    assert result["status"] == "success"
    assert result["published"] is True
    assert result["publish_status"] == "live"
    assert result["blogger_result"]["url"] == "http://blog/x"

    article = await ArticleRepository(session).get(result["article_id"])
    assert article is not None

    image_url = result["image_url"]
    assert image_url and image_url.startswith("https://")
    alt = f"{result['selected_product']} product illustration"
    assert f"![{alt}]({image_url})" in article.content

    html = markdown_to_blogger_html(article.content)
    assert "<img" in html
    assert html.index("<img") > html.index("<p")

    structure = validate_structure(article.content)
    assert structure["complete"] is True, f"missing sections: {structure['missing']}"

    body = captured["body"]
    assert body["title"] == article.title
    assert "<img" in body["content"]
    assert body["labels"]


async def test_blogger_failure_reports_partial_not_published(session):
    _configure_blog()
    await _seed_connection(session)

    def handler(request):
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "test-token"})
        return httpx.Response(500, json={"error": "boom"})

    result = await TrenderaWorkflow(session).run(
        publish_now=True, image_transport=_image_transport(), blogger_transport=httpx.MockTransport(handler)
    )
    assert result["published"] is False
    assert result["publish_status"] == "failed"
    assert "Blogger publishing failed" in result["error"]
    assert result["status"] == "partial_success"


async def test_no_connection_reports_partial_not_published(session):
    _configure_blog()
    result = await TrenderaWorkflow(session).run(publish_now=True, image_transport=_image_transport())
    assert result["published"] is False
    assert result["publish_status"] == "failed"
    assert "not connected" in (result["error"] or "").lower()
