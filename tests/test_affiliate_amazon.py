"""Tests for the Amazon Creators API affiliate provider (mocked HTTP)."""

import json

import httpx

from app.core.config import settings
from app.services.affiliate_amazon import AmazonAffiliateProvider, marketplace_config
from app.services.affiliate_providers import AffiliateDiscoveryService


def test_marketplace_config():
    assert marketplace_config("www.amazon.com") == ("https://api.amazon.com/auth/o2/token", "NA")
    assert marketplace_config("amazon.sa") == ("https://api.amazon.co.uk/auth/o2/token", "EU")
    assert marketplace_config("www.amazon.com.au") == ("https://api.amazon.co.jp/auth/o2/token", "FE")
    assert marketplace_config("bogus") is None


def _creators_transport(items, *, access_token="Atc|TEST", marketplace="www.amazon.sa"):
    def handler(request):
        if request.url.path == "/auth/o2/token":
            return httpx.Response(
                200,
                json={
                    "access_token": access_token,
                    "token_type": "bearer",
                    "expires_in": 3600,
                },
            )
        if request.url.host == "creatorsapi.amazon" and request.url.path == "/catalog/v1/searchItems":
            body = json.loads(request.content.decode() or "{}")
            assert body["keywords"] == "Sony WH-1000XM5"
            assert body["marketplace"] == marketplace
            assert body["partnerTag"] == "mytag-21"
            assert body["brand"] == "Sony"
            assert request.headers["authorization"] == f"Bearer {access_token}"
            assert request.headers["x-marketplace"] == marketplace
            return httpx.Response(200, json={"searchResult": {"items": items}})
        return httpx.Response(404, json={"error": "unexpected"})

    return httpx.MockTransport(handler)


def _configure_amazon(monkeypatch, *, version=""):
    monkeypatch.setattr(settings, "affiliate_provider", "amazon")
    monkeypatch.setattr(settings, "affiliate_api_key", "CID_TEST")
    monkeypatch.setattr(settings, "affiliate_api_secret", "CSECRET_TEST")
    monkeypatch.setattr(settings, "affiliate_api_version", version)
    monkeypatch.setattr(settings, "affiliate_partner_id", "mytag-21")
    monkeypatch.setattr(settings, "affiliate_marketplace", "www.amazon.sa")


async def test_amazon_not_configured_returns_not_found(monkeypatch):
    monkeypatch.setattr(settings, "affiliate_api_key", "")
    offer = await AmazonAffiliateProvider().discover({"name": "Sony WH-1000XM5"})
    assert offer.status == "not_found"
    assert offer.source == "amazon"


async def test_amazon_finds_exact_offer(monkeypatch):
    _configure_amazon(monkeypatch)
    items = [
        {
            "asin": "B0WRONG",
            "detailPageURL": "https://www.amazon.sa/dp/B0WRONG?tag=mytag-21",
            "itemInfo": {
                "title": {"displayValue": "Logitech MX Master 3S"},
                "byLineInfo": {"brand": {"displayValue": "Logitech"}},
            },
        },
        {
            "asin": "B0TEST",
            "detailPageURL": "https://www.amazon.sa/dp/B0TEST?tag=mytag-21",
            "itemInfo": {
                "title": {"displayValue": "Sony WH-1000XM5 Wireless Headphones"},
                "byLineInfo": {"brand": {"displayValue": "Sony"}},
            },
        },
    ]
    offer = await AmazonAffiliateProvider().discover(
        {"name": "Sony WH-1000XM5 Wireless Headphones", "brand": "Sony"},
        transport=_creators_transport(items),
    )
    assert offer.status == "found"
    assert offer.source == "amazon"
    assert offer.url == "https://www.amazon.sa/dp/B0TEST?tag=mytag-21"
    assert offer.product_name == "Sony WH-1000XM5 Wireless Headphones"
    assert offer.brand == "Sony"
    assert offer.match_score >= settings.min_affiliate_match_score
    assert "strict match" in (offer.reason or "")


async def test_amazon_rejects_non_matching_offer(monkeypatch):
    _configure_amazon(monkeypatch)
    items = [
        {
            "asin": "B0WRONG",
            "detailPageURL": "https://www.amazon.sa/dp/B0WRONG?tag=mytag-21",
            "itemInfo": {
                "title": {"displayValue": "Logitech MX Master 3S"},
                "byLineInfo": {"brand": {"displayValue": "Logitech"}},
            },
        }
    ]
    offer = await AmazonAffiliateProvider().discover(
        {"name": "Sony WH-1000XM5 Wireless Headphones", "brand": "Sony"},
        transport=_creators_transport(items),
    )
    assert offer.status == "not_found"
    assert offer.source == "amazon"
    assert offer.url is None
    assert offer.match_score < settings.min_affiliate_match_score


async def test_discovery_uses_amazon_provider(session, monkeypatch):
    _configure_amazon(monkeypatch)
    items = [
        {
            "asin": "B0TEST",
            "detailPageURL": "https://www.amazon.sa/dp/B0TEST?tag=mytag-21",
            "itemInfo": {
                "title": {"displayValue": "Sony WH-1000XM5 Wireless Headphones"},
                "byLineInfo": {"brand": {"displayValue": "Sony"}},
            },
        }
    ]
    identity = {"name": "Sony WH-1000XM5 Wireless Headphones", "brand": "Sony"}
    offer = await AffiliateDiscoveryService(session).resolve(
        product_id="p1",
        identity=identity,
        transport=_creators_transport(items),
    )
    assert offer.status == "found"
    assert offer.source == "amazon"
    assert offer.url == "https://www.amazon.sa/dp/B0TEST?tag=mytag-21"
    assert offer.match_score >= settings.min_affiliate_match_score

