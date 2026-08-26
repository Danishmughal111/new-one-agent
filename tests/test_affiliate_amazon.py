"""Tests for the Amazon PA-API 5.0 affiliate provider (mocked HTTP)."""

import httpx
import pytest

from app.core.config import settings
from app.services.affiliate_amazon import (
    AmazonAffiliateProvider,
    build_affiliate_url,
    marketplace_config,
    sign_search_request,
)
from app.services.affiliate_providers import AffiliateDiscoveryService


def test_build_affiliate_url():
    assert build_affiliate_url("www.amazon.sa", "B0TEST", "mytag-21") == "https://www.amazon.sa/dp/B0TEST?tag=mytag-21"


def test_marketplace_config():
    assert marketplace_config("www.amazon.sa") == ("webservices.amazon.sa", "eu-west-1")
    assert marketplace_config("amazon.sa") == ("webservices.amazon.sa", "eu-west-1")
    assert marketplace_config("www.amazon.com") == ("webservices.amazon.com", "us-east-1")
    assert marketplace_config("bogus") is None


def test_sign_request_headers():
    headers = sign_search_request(
        host="webservices.amazon.sa", region="eu-west-1",
        access_key="AKIA_TEST", secret_key="secret", payload='{"Keywords": "x"}',
    )
    assert headers["x-amz-target"].startswith("com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems")
    assert headers["authorization"].startswith("AWS4-HMAC-SHA256 Credential=AKIA_TEST/")
    assert "eu-west-1/ProductAdvertisingAPI/aws4_request" in headers["authorization"]
    assert headers["content-type"] == "application/json; charset=UTF-8"


def _amazon_transport(items):
    def handler(request):
        return httpx.Response(200, json={"SearchResult": {"Items": items}})

    return httpx.MockTransport(handler)


def _configure_amazon(monkeypatch):
    monkeypatch.setattr(settings, "affiliate_provider", "amazon")
    monkeypatch.setattr(settings, "affiliate_api_key", "AKIA_TEST")
    monkeypatch.setattr(settings, "affiliate_api_secret", "secret")
    monkeypatch.setattr(settings, "affiliate_partner_id", "mytag-21")
    monkeypatch.setattr(settings, "affiliate_marketplace", "www.amazon.sa")


async def test_amazon_not_configured_returns_not_found(monkeypatch):
    monkeypatch.setattr(settings, "affiliate_api_key", "")
    offer = await AmazonAffiliateProvider().discover({"name": "Sony WH-1000XM5"})
    assert offer.status == "not_found"
    assert offer.source == "amazon"


async def test_amazon_finds_offer(monkeypatch):
    _configure_amazon(monkeypatch)
    items = [{
        "ASIN": "B0TEST",
        "DetailPageURL": "https://www.amazon.sa/dp/B0TEST?tag=mytag-21",
        "ItemInfo": {
            "Title": {"DisplayValue": "Sony WH-1000XM5 Wireless Headphones"},
            "ByLineInfo": {"Brand": {"DisplayValue": "Sony"}},
        },
    }]
    offer = await AmazonAffiliateProvider().discover(
        {"name": "Sony WH-1000XM5"}, transport=_amazon_transport(items)
    )
    assert offer.status == "found"
    assert offer.url == "https://www.amazon.sa/dp/B0TEST?tag=mytag-21"
    assert offer.product_name == "Sony WH-1000XM5 Wireless Headphones"
    assert offer.brand == "Sony"


async def test_discovery_uses_amazon_provider(session, monkeypatch):
    _configure_amazon(monkeypatch)
    items = [{
        "ASIN": "B0TEST",
        "DetailPageURL": "https://www.amazon.sa/dp/B0TEST?tag=mytag-21",
        "ItemInfo": {
            "Title": {"DisplayValue": "Sony WH-1000XM5 Wireless Headphones"},
            "ByLineInfo": {"Brand": {"DisplayValue": "Sony"}},
        },
    }]
    identity = {"name": "Sony WH-1000XM5 Wireless Headphones", "brand": "Sony"}
    offer = await AffiliateDiscoveryService(session).resolve(
        product_id="p1", identity=identity, transport=_amazon_transport(items)
    )
    assert offer.status == "found"
    assert offer.source == "amazon"
    assert offer.url == "https://www.amazon.sa/dp/B0TEST?tag=mytag-21"
    assert offer.match_score >= settings.min_affiliate_match_score
