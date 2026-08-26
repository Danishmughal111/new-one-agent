"""Tests for the deterministic affiliate CTA system."""

import httpx
import pytest

from app.repositories.article import ArticleRepository
from app.schemas.product import ProductCreate
from app.services.affiliate_service import add_affiliate_cta, is_valid_affiliate_url
from app.services.html_converter import markdown_to_blogger_html
from app.services.product_discovery import ProductDiscoveryService
from app.services.product_service import ProductService
from app.services.trendera_workflow import TrenderaWorkflow

VALID_URL = "https://affiliate.test/check-price"


@pytest.mark.parametrize(
    "url",
    [VALID_URL, "http://localhost:8000/x", "https://partner.test/product-123"],
)
def test_valid_affiliate_urls(url):
    assert is_valid_affiliate_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        None,
        "",
        "   ",
        "not-a-url",
        "ftp://files.test/x",
        "javascript:alert(1)",
        "https://",
        "https://no-dot-host",
        "shop.test/product",
        "/relative/path",
        "file:///etc/passwd",
    ],
)
def test_invalid_affiliate_urls(url):
    assert is_valid_affiliate_url(url) is False


def test_cta_inserted_when_url_valid():
    content = "# Gadget Review\n\nIntro text.\n\n## Final verdict\n\nGood."
    out = add_affiliate_cta(content, VALID_URL)
    assert f"[Check Price / View Product]({VALID_URL})" in out
    assert "---" in out  # clearly separated from editorial content


def test_cta_skipped_without_url():
    content = "# Gadget Review\n\nIntro text.\n"
    assert add_affiliate_cta(content, None) == content
    assert add_affiliate_cta(content, "") == content


def test_cta_skipped_with_invalid_url():
    content = "# Gadget Review\n\nIntro text.\n"
    assert add_affiliate_cta(content, "not-a-url") == content


def test_cta_uses_exact_product_name():
    content = "# Gadget Review\n\nIntro text.\n"
    out = add_affiliate_cta(content, VALID_URL, product_name="Logitech MX Master 3S")
    assert "[Check current price for Logitech MX Master 3S](" in out
    assert "Check Price / View Product" not in out


def test_cta_survives_html_conversion():
    content = add_affiliate_cta("# Gadget Review\n\nIntro text.\n", VALID_URL)
    html = markdown_to_blogger_html(content)
    assert f'<a href="{VALID_URL}">Check Price / View Product</a>' in html
    assert "<hr>" in html


async def test_affiliate_url_survives_persistence(session):
    created = await ProductService(session).create(
        ProductCreate(name="Affiliate Gadget", category="Electronics", affiliate_url=VALID_URL)
    )
    loaded = await ProductService(session).get(created.id)
    assert loaded.affiliate_url == VALID_URL


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
            return httpx.Response(200, content=b"img-bytes", headers={"content-type": "image/jpeg"})
        return httpx.Response(404, json={"error": "unexpected"})

    return httpx.MockTransport(handler)


def _candidate(affiliate_url=None):
    return {
        "name": "Affiliate Gadget",
        "brand": "TestBrand",
        "category": "Electronics",
        "region": "GLOBAL",
        "description": "A test gadget.",
        "features": ["Feature A", "Feature B"],
        "specs": {"type": "test"},
        "limitations": ["None"],
        "affiliate_url": affiliate_url,
        "discovery_source": "catalog",
    }


async def test_workflow_inserts_cta_when_affiliate_url(session, monkeypatch):
    _stub_research(monkeypatch)

    async def discover(self, limit=5):
        return [_candidate(VALID_URL)]

    monkeypatch.setattr(ProductDiscoveryService, "discover_candidates", discover)

    result = await TrenderaWorkflow(session).run(publish_now=False, image_transport=_image_transport())
    assert result["status"] == "success"
    article = await ArticleRepository(session).get(result["article_id"])
    assert f"[Check current price for Affiliate Gadget]({VALID_URL})" in article.content


async def test_workflow_skips_cta_without_affiliate_url(session, monkeypatch):
    _stub_research(monkeypatch)

    async def discover(self, limit=5):
        return [_candidate(None)]

    monkeypatch.setattr(ProductDiscoveryService, "discover_candidates", discover)

    result = await TrenderaWorkflow(session).run(publish_now=False, image_transport=_image_transport())
    assert result["status"] == "success"
    article = await ArticleRepository(session).get(result["article_id"])
    assert "Check Price / View Product" not in article.content
