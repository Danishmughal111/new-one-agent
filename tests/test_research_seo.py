"""Tests for research, opportunity scoring, SEO, labels, and internal links."""

import json

import httpx

from app.core.config import settings
from app.models.blogger_connection import BloggerConnection
from app.schemas.product import ProductCreate
from app.services.opportunity_service import score_opportunity
from app.services.product_service import ProductService
from app.services.research_service import ResearchService
from app.services.seo_service import (
    add_internal_links,
    add_sources_section,
    build_labels,
    build_seo_plan,
    validate_seo,
)
from app.services.trendera_workflow import TrenderaWorkflow

CATALOG = [
    {
        "name": "Test Headphones",
        "brand": "TestBrand",
        "category": "Headphones",
        "description": "A test pair of headphones.",
        "features": ["Noise cancelling", "Wireless"],
        "specs": {"type": "Over-ear"},
        "limitations": ["Pricey"],
    }
]


async def test_research_live_success():
    def handler(request):
        if "wikipedia" in str(request.url):
            return httpx.Response(200, json={"extract": "A real summary.", "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Test_Headphones"}}})
        if "duckduckgo" in str(request.url):
            return httpx.Response(200, json={"Abstract": "Duck summary.", "AbstractURL": "https://duckduckgo.com/Test"})
        return httpx.Response(404)

    result = await ResearchService(CATALOG).research(CATALOG[0], transport=httpx.MockTransport(handler))
    assert result["status"] == "success"
    assert result["sources_succeeded"] == 3
    urls = [s["url"] for s in result["sources"] if s["fetched"] and s["url"]]
    assert "https://en.wikipedia.org/wiki/Test_Headphones" in urls
    assert result["data"]["live_summary"] == "A real summary."


async def test_research_fallback_on_failure():
    def handler(request):
        return httpx.Response(404)

    result = await ResearchService(CATALOG).research(CATALOG[0], transport=httpx.MockTransport(handler))
    assert result["status"] == "partial"
    assert result["sources_succeeded"] == 1  # only the catalog fallback
    assert result["data"]["description"] == "A test pair of headphones."


async def test_research_one_provider_fails_one_succeeds():
    def handler(request):
        if "wikipedia" in str(request.url):
            return httpx.Response(500)
        if "duckduckgo" in str(request.url):
            return httpx.Response(200, json={"Abstract": "Only Duck.", "AbstractURL": "https://duckduckgo.com/Test"})
        return httpx.Response(404)

    result = await ResearchService(CATALOG).research(CATALOG[0], transport=httpx.MockTransport(handler))
    assert result["status"] == "partial"
    assert result["sources_succeeded"] == 2  # DuckDuckGo + catalog
    assert result["sources_attempted"] == 3
    # only real URLs are reported (Wikipedia failed -> no URL)
    assert all(s["url"] for s in result["sources"] if s["fetched"] and s["type"] != "fallback")


def test_opportunity_scoring_and_rating():
    research = {
        "status": "success",
        "sources": [],
        "data": {
            "name": "X",
            "features": ["a", "b", "c"],
            "specs": {"x": "y"},
            "description": "d",
            "alternatives": ["alt"],
            "target_audience": ["people"],
        },
    }
    result = score_opportunity(research)
    assert 0 <= result["score"] <= 100
    assert result["total"] == result["score"]
    assert result["rating"] in ("Low Opportunity", "Moderate Opportunity", "Strong Opportunity", "High Potential")
    assert set(result["factors"].keys()) == {
        "source_quality", "audience_clarity", "feature_richness", "comparison_potential",
        "faq_potential", "trend_evidence", "uniqueness", "content_depth",
    }
    assert result["factors"]["trend_evidence"] == 0  # never claims "trending" without evidence

    weak = score_opportunity({"status": "failed", "sources": [], "data": {"features": [], "specs": {}}})
    assert weak["rating"] == "Low Opportunity"


def test_seo_plan_and_labels_no_duplicates():
    research = {
        "status": "success",
        "sources": [],
        "data": {"name": "Logitech MX Master 3S", "brand": "Logitech", "category": "Computer mouse", "features": [], "specs": {}, "faqs": ["Q?"]},
    }
    plan = build_seo_plan(research)
    assert plan["primary_keyword"] == "Logitech MX Master 3S"
    assert plan["search_intent"]
    assert plan["slug"]
    assert plan["meta_description"]

    labels = build_labels(research, plan)
    assert 5 <= len(labels) <= 10
    assert len(labels) == len({l.lower() for l in labels})  # no duplicate labels
    assert "Logitech MX Master 3S" in labels
    assert "Logitech" in labels


def test_seo_validation_scores_and_issues():
    research = {"status": "success", "sources": [], "data": {"name": "X", "brand": "B", "category": "C", "faqs": ["Q?"]}}
    plan = build_seo_plan(research)
    content = "# X Review\n\nX is great.\n\n## Features\n\nPros and cons here. FAQ included."
    report = validate_seo(content, plan)
    assert 0 <= report["seo_score"] <= 100
    assert isinstance(report["passed"], bool)
    assert isinstance(report["issues"], list)


def test_internal_links_and_sources_sections():
    content = "# X\n\nBody."
    content = add_internal_links(content, [("A", "http://a"), ("A", "http://a"), ("B", "http://b")])
    assert "Related Articles" in content
    assert content.count("http://a") == 1  # dedupe

    content = add_sources_section(content, ["https://src.example"])
    assert "Sources" in content
    assert "https://src.example" in content


async def test_labels_passed_to_blogger_payload(session):
    settings.google_blog_id = "blog-1"
    session.add(BloggerConnection(refresh_token="rt", blog_id="blog-1"))
    await session.commit()

    def research_handler(request):
        return httpx.Response(
            200,
            json={"extract": "Summary.", "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Test"}}},
        )

    def image_handler(request):
        return httpx.Response(200, content=b"img", headers={"content-type": "image/jpeg"})

    captured = {}

    def blogger_handler(request):
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "at"})
        if request.url.host == "www.googleapis.com":
            captured["body"] = json.loads(request.read())
            return httpx.Response(200, json={"id": "post-1", "url": "http://blog/x", "status": "LIVE"})
        return httpx.Response(404)

    result = await TrenderaWorkflow(session).run(
        publish_now=True,
        research_transport=httpx.MockTransport(research_handler),
        image_transport=httpx.MockTransport(image_handler),
        blogger_transport=httpx.MockTransport(blogger_handler),
    )

    assert result["status"] == "success"
    assert result["published"] is True
    labels = captured["body"]["labels"]
    assert len(labels) >= 5
    assert result["selected_product"] in labels
    assert result["labels"] == labels


async def test_weak_opportunity_is_skipped(session, monkeypatch):
    monkeypatch.setattr(settings, "min_opportunity_score", 90)

    async def fake_research(self, candidate, transport=None):
        return {"status": "failed", "sources": [], "data": {"name": candidate["name"], "features": [], "specs": {}}}

    monkeypatch.setattr("app.services.research_service.ResearchService.research", fake_research)

    result = await TrenderaWorkflow(session).run(publish_now=False)
    assert result["status"] == "skipped"
    assert "threshold" in result["error"]


def test_normalize_name_matches_versions():
    from app.services.product_discovery import normalize_name

    assert normalize_name("Apple AirPods Pro 2") == normalize_name("Apple AirPods Pro (2nd Generation)")
    assert normalize_name("Sony WH-1000XM4") != normalize_name("Sony WH-1000XM5")


async def test_duplicate_detection(session):
    from app.services.product_discovery import ProductDiscoveryService

    await ProductService(session).create(ProductCreate(name="Apple AirPods Pro (2nd Generation)", category="Earbuds"))
    svc = ProductDiscoveryService(session)
    is_dup, reason = await svc.is_duplicate("Apple AirPods Pro 2")
    assert is_dup is True
    assert reason == "already stored"
