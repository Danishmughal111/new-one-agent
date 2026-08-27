"""Tests for the affiliate discovery architecture (all external calls mocked)."""

import httpx
import pytest

from app.core.config import settings
from app.models.affiliate_offer import AffiliateOfferRecord
from app.repositories.affiliate_offer import AffiliateOfferRepository
from app.services.affiliate_matching import ProductMatchService
from app.services.affiliate_providers import AffiliateDiscoveryService

SONY_XM5 = {"name": "Sony WH-1000XM5 Wireless Headphones", "brand": "Sony", "category": "Headphones"}


def test_exact_match_scores_high():
    result = ProductMatchService().match(SONY_XM5, {"name": "Sony WH-1000XM5 Wireless Headphones", "brand": "Sony"})
    assert result["match_score"] >= settings.min_affiliate_match_score


def test_wrong_generation_rejected():
    result = ProductMatchService().match(SONY_XM5, {"name": "Sony WH-1000XM4 Wireless Headphones", "brand": "Sony"})
    assert result["match_score"] < settings.min_affiliate_match_score


def test_brand_mismatch_rejected():
    result = ProductMatchService().match(SONY_XM5, {"name": "Apple AirPods Pro", "brand": "Apple"})
    assert result["match_score"] < settings.min_affiliate_match_score


def test_model_mismatch_rejected():
    result = ProductMatchService().match(
        {"name": "Kindle Paperwhite", "brand": "Amazon"},
        {"name": "Kindle Scribe", "brand": "Amazon"},
    )
    assert result["match_score"] < settings.min_affiliate_match_score


def test_generation_normalized_to_number():
    result = ProductMatchService().match(
        {"name": "Apple AirPods Pro (2nd Generation)", "brand": "Apple"},
        {"name": "Apple AirPods Pro 2", "brand": "Apple"},
    )
    assert result["match_score"] >= settings.min_affiliate_match_score
def _search_transport(offers):
    def handler(request):
        return httpx.Response(200, json={"offers": offers})

    return httpx.MockTransport(handler)


async def test_manual_priority(session, monkeypatch):
    monkeypatch.setattr(settings, "affiliate_provider", "product_search")
    monkeypatch.setattr(settings, "affiliate_api_base_url", "https://affiliate.test")
    offer = await AffiliateDiscoveryService(session).resolve(
        product_id="p1", identity=SONY_XM5, manual_url="https://affiliate.test/manual"
    )
    assert offer.source == "manual"
    assert offer.url == "https://affiliate.test/manual"


async def test_cached_offer_reused(session):
    record = AffiliateOfferRecord(
        product_id="p1",
        affiliate_url="https://affiliate.test/cached",
        provider="product_search",
        provider_product_name="Sony WH-1000XM5 Wireless Headphones",
        match_score=100,
        status="verified",
    )
    await AffiliateOfferRepository(session).save(record)
    await session.commit()
    offer = await AffiliateDiscoveryService(session).resolve(product_id="p1", identity=SONY_XM5)
    assert offer.source == "cached"
    assert offer.url == "https://affiliate.test/cached"


async def test_automatic_finds_exact(session, monkeypatch):
    monkeypatch.setattr(settings, "affiliate_provider", "product_search")
    monkeypatch.setattr(settings, "affiliate_api_base_url", "https://affiliate.test")
    transport = _search_transport(
        [{"name": "Sony WH-1000XM5 Wireless Headphones", "brand": "Sony", "url": "https://affiliate.test/xm5"}]
    )
    offer = await AffiliateDiscoveryService(session).resolve(product_id="p1", identity=SONY_XM5, transport=transport)
    assert offer.status == "found"
    assert offer.url == "https://affiliate.test/xm5"
    assert offer.match_score >= settings.min_affiliate_match_score
    cached = await AffiliateOfferRepository(session).get_by_product("p1")
    assert cached is not None and cached.affiliate_url == "https://affiliate.test/xm5"


async def test_wrong_product_rejected(session, monkeypatch):
    monkeypatch.setattr(settings, "affiliate_provider", "product_search")
    monkeypatch.setattr(settings, "affiliate_api_base_url", "https://affiliate.test")
    transport = _search_transport(
        [{"name": "Logitech MX Master 3S", "brand": "Logitech", "url": "https://affiliate.test/wrong"}]
    )
    offer = await AffiliateDiscoveryService(session).resolve(product_id="p1", identity=SONY_XM5, transport=transport)
    assert offer.status == "not_found"


async def test_brand_mismatch_rejected(session, monkeypatch):
    monkeypatch.setattr(settings, "affiliate_provider", "product_search")
    monkeypatch.setattr(settings, "affiliate_api_base_url", "https://affiliate.test")
    transport = _search_transport(
        [{"name": "Apple AirPods Pro", "brand": "Apple", "url": "https://affiliate.test/wrong"}]
    )
    offer = await AffiliateDiscoveryService(session).resolve(product_id="p1", identity=SONY_XM5, transport=transport)
    assert offer.status == "not_found"


async def test_below_threshold_rejected(session, monkeypatch):
    monkeypatch.setattr(settings, "affiliate_provider", "product_search")
    monkeypatch.setattr(settings, "affiliate_api_base_url", "https://affiliate.test")
    monkeypatch.setattr(settings, "min_affiliate_match_score", 999)
    transport = _search_transport(
        [{"name": "Sony WH-1000XM5 Wireless Headphones", "brand": "Sony", "url": "https://affiliate.test/xm5"}]
    )
    offer = await AffiliateDiscoveryService(session).resolve(product_id="p1", identity=SONY_XM5, transport=transport)
    assert offer.status == "not_found"
    assert "below match threshold" in offer.reason


async def test_no_provider_configured(session, monkeypatch):
    monkeypatch.setattr(settings, "affiliate_provider", "")
    monkeypatch.setattr(settings, "affiliate_api_base_url", "")
    offer = await AffiliateDiscoveryService(session).resolve(product_id="p1", identity=SONY_XM5)
    assert offer.status == "not_found"
    assert offer.source == "amazon"


async def test_provider_failure_returns_failed(session, monkeypatch):
    monkeypatch.setattr(settings, "affiliate_provider", "product_search")
    monkeypatch.setattr(settings, "affiliate_api_base_url", "https://affiliate.test")

    def handler(request):
        raise httpx.ConnectError("boom")

    offer = await AffiliateDiscoveryService(session).resolve(
        product_id="p1", identity=SONY_XM5, transport=httpx.MockTransport(handler)
    )
    assert offer.status == "failed"
from app.models.blogger_connection import BloggerConnection
from app.repositories.article import ArticleRepository
from app.services.product_discovery import ProductDiscoveryService
from app.services.trendera_workflow import TrenderaWorkflow


def _stub_research(monkeypatch):
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


def _image_transport():
    def handler(request):
        if request.url.host == "image.pollinations.ai":
            return httpx.Response(200, content=b"img", headers={"content-type": "image/jpeg"})
        return httpx.Response(404, json={"error": "unexpected"})

    return httpx.MockTransport(handler)


def _candidate(affiliate_url=None):
    return {
        "name": "Sony WH-1000XM5 Wireless Headphones",
        "brand": "Sony",
        "category": "Headphones",
        "region": "GLOBAL",
        "description": "Test headphones.",
        "features": ["ANC", "Bluetooth"],
        "specs": {"type": "over-ear"},
        "limitations": ["Pricey"],
        "affiliate_url": affiliate_url,
        "discovery_source": "catalog",
    }


async def _discover_none(self, limit=5):
    return [_candidate(None)]


async def test_workflow_generates_without_affiliate(session, monkeypatch):
    _stub_research(monkeypatch)
    monkeypatch.setattr(ProductDiscoveryService, "discover_candidates", _discover_none)
    monkeypatch.setattr(settings, "affiliate_provider", "")
    monkeypatch.setattr(settings, "affiliate_api_base_url", "")
    result = await TrenderaWorkflow(session).run(publish_now=False, image_transport=_image_transport())
    assert result["status"] == "success"
    assert result["affiliate_status"] == "not_found"
    assert result["affiliate_cta_inserted"] is False
    article = await ArticleRepository(session).get(result["article_id"])
    assert "Check current price" not in article.content


async def test_workflow_provider_failure_no_crash(session, monkeypatch):
    _stub_research(monkeypatch)
    monkeypatch.setattr(ProductDiscoveryService, "discover_candidates", _discover_none)
    monkeypatch.setattr(settings, "affiliate_provider", "product_search")
    monkeypatch.setattr(settings, "affiliate_api_base_url", "https://affiliate.test")

    def handler(request):
        raise httpx.ConnectError("boom")

    result = await TrenderaWorkflow(session).run(
        publish_now=False, image_transport=_image_transport(), affiliate_transport=httpx.MockTransport(handler)
    )
    assert result["status"] == "success"
    assert result["affiliate_status"] == "failed"


async def test_workflow_blogger_publishes_without_affiliate(session, monkeypatch):
    _stub_research(monkeypatch)
    monkeypatch.setattr(ProductDiscoveryService, "discover_candidates", _discover_none)
    monkeypatch.setattr(settings, "affiliate_provider", "")
    monkeypatch.setattr(settings, "affiliate_api_base_url", "")
    monkeypatch.setattr(settings, "google_blog_id", "blog-1")
    session.add(BloggerConnection(refresh_token="test-refresh-token", blog_id="blog-1"))
    await session.commit()

    def handler(request):
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "test-token"})
        if request.url.host == "www.googleapis.com":
            return httpx.Response(200, json={"id": "post-1", "url": "http://blog/x", "status": "LIVE"})
        return httpx.Response(404, json={"error": "unexpected"})

    result = await TrenderaWorkflow(session).run(
        publish_now=True, image_transport=_image_transport(), blogger_transport=httpx.MockTransport(handler)
    )
    assert result["published"] is True
    assert result["affiliate_status"] == "not_found"
    assert result["affiliate_cta_inserted"] is False

