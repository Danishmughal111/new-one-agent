"""Amazon Creators API affiliate provider.

This is the official Amazon affiliate integration for TrendEra. It is designed
for the Amazon Creators API, which is the successor to PA-API 5. The provider
uses the OAuth 2.0 client_credentials flow to obtain a bearer token, then calls
Creators API SearchItems and only returns a link when Amazon returned a real
detailPageURL that passes the existing strict product matcher.

Required Amazon env vars:
    AFFILIATE_API_KEY       -> Creators API Credential ID (client_id)
    AFFILIATE_API_SECRET    -> Creators API Credential Secret (client_secret)
    AFFILIATE_PARTNER_ID    -> Amazon Associates Partner Tag
    AFFILIATE_MARKETPLACE   -> Amazon marketplace domain, e.g. www.amazon.com

Optional:
    AFFILIATE_API_VERSION   -> Creators API credential version (3.1 / 3.2 / 3.3)
"""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any

import httpx

from app.core.config import settings
from app.services.affiliate_matching import ProductMatchService
from app.services.affiliate_providers import AffiliateOffer, AffiliateProvider
from app.services.affiliate_service import is_valid_affiliate_url

CREATORS_API_BASE_URL = "https://creatorsapi.amazon"
CREATORS_API_SCOPE = "creatorsapi::default"
CREATORS_SEARCH_PATH = "/catalog/v1/searchItems"

_TOKEN_ENDPOINTS = {
    "NA": "https://api.amazon.com/auth/o2/token",
    "EU": "https://api.amazon.co.uk/auth/o2/token",
    "FE": "https://api.amazon.co.jp/auth/o2/token",
}

_VERSION_TO_REGION = {
    "3.1": "NA",
    "3.2": "EU",
    "3.3": "FE",
}


def _alias_marketplaces(*marketplaces: str) -> set[str]:
    aliases: set[str] = set()
    for marketplace in marketplaces:
        normalized = marketplace.strip().lower()
        aliases.add(normalized)
        if normalized.startswith("www."):
            aliases.add(normalized[4:])
    return aliases


_MARKETPLACES_BY_REGION = {
    "NA": _alias_marketplaces(
        "www.amazon.com",
        "www.amazon.ca",
        "www.amazon.com.mx",
        "www.amazon.com.br",
    ),
    "EU": _alias_marketplaces(
        "www.amazon.co.uk",
        "www.amazon.de",
        "www.amazon.fr",
        "www.amazon.it",
        "www.amazon.es",
        "www.amazon.nl",
        "www.amazon.com.be",
        "www.amazon.eg",
        "www.amazon.in",
        "www.amazon.ie",
        "www.amazon.pl",
        "www.amazon.sa",
        "www.amazon.se",
        "www.amazon.com.tr",
        "www.amazon.ae",
    ),
    "FE": _alias_marketplaces(
        "www.amazon.co.jp",
        "www.amazon.sg",
        "www.amazon.com.au",
    ),
}

_MARKETPLACE_TO_REGION = {
    marketplace: region
    for region, marketplaces in _MARKETPLACES_BY_REGION.items()
    for marketplace in marketplaces
}

_TOKEN_CACHE: dict[tuple[str, str, str], "_TokenCacheEntry"] = {}


@dataclass(slots=True)
class _TokenCacheEntry:
    access_token: str
    expires_at: float


def _clean(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalize_marketplace(marketplace: str) -> str:
    value = _clean(marketplace).lower()
    if "://" in value:
        value = value.split("://", 1)[1]
    if "/" in value:
        value = value.split("/", 1)[0]
    return value


def marketplace_config(marketplace: str) -> tuple[str, str] | None:
    """Return ``(token_endpoint, region)`` for a supported marketplace."""
    normalized = _normalize_marketplace(marketplace)
    region = _MARKETPLACE_TO_REGION.get(normalized)
    if not region:
        return None
    return _TOKEN_ENDPOINTS[region], region


def _token_endpoint_for_settings(marketplace: str) -> tuple[str, str] | None:
    version = _clean(settings.affiliate_api_version).lstrip("vV")
    if version:
        region = _VERSION_TO_REGION.get(version)
        if not region:
            return None
        return _TOKEN_ENDPOINTS[region], region
    return marketplace_config(marketplace)


def _get_value(data: Any, *names: str) -> Any:
    if not isinstance(data, dict):
        return None

    for name in names:
        if name in data:
            return data[name]

    lowered = {str(key).lower(): value for key, value in data.items()}
    for name in names:
        key = name.lower()
        if key in lowered:
            return lowered[key]
    return None


def _extract_item_info(item: dict) -> tuple[str | None, str | None, str | None]:
    item_info = _get_value(item, "itemInfo", "ItemInfo") or {}
    title_info = _get_value(item_info, "title", "Title") or {}
    brand_info = _get_value(item_info, "byLineInfo", "ByLineInfo") or {}
    brand = _get_value(brand_info, "brand", "Brand") or {}

    title = _get_value(title_info, "displayValue", "DisplayValue")
    brand_value = _get_value(brand, "displayValue", "DisplayValue")
    url = _get_value(item, "detailPageURL", "DetailPageURL")
    return title, brand_value, url


async def _fetch_access_token(
    *,
    token_endpoint: str,
    client_id: str,
    client_secret: str,
    transport=None,
) -> str:
    """Fetch and cache an OAuth token for the configured Creators API app."""
    cache_key = (token_endpoint, client_id, client_secret)
    cached = _TOKEN_CACHE.get(cache_key)
    now = monotonic()
    if cached and cached.expires_at > now:
        return cached.access_token

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": CREATORS_API_SCOPE,
    }

    async with httpx.AsyncClient(transport=transport, timeout=30) as client:
        response = await client.post(
            token_endpoint,
            headers={"Content-Type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    token = _clean(data.get("access_token"))
    expires_in = int(data.get("expires_in") or 0)
    if not token or expires_in <= 0:
        raise ValueError("Creators API token response missing access_token or expires_in")

    _TOKEN_CACHE[cache_key] = _TokenCacheEntry(
        access_token=token,
        expires_at=now + max(0, expires_in - 60),
    )
    return token


async def _search_items(
    *,
    access_token: str,
    marketplace: str,
    partner_tag: str,
    keywords: str,
    brand: str | None = None,
    transport=None,
) -> list[dict]:
    """Search Amazon for matching items using the official Creators API."""
    payload: dict[str, Any] = {
        "keywords": keywords,
        "itemCount": 10,
        "marketplace": marketplace,
        "partnerTag": partner_tag,
        "resources": ["itemInfo.title", "itemInfo.byLineInfo"],
    }
    if brand:
        payload["brand"] = brand

    async with httpx.AsyncClient(transport=transport, timeout=30) as client:
        response = await client.post(
            f"{CREATORS_API_BASE_URL}{CREATORS_SEARCH_PATH}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "x-marketplace": marketplace,
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    search_result = _get_value(data, "searchResult", "SearchResult") or {}
    items = _get_value(search_result, "items", "Items") or []
    return items if isinstance(items, list) else []


class AmazonAffiliateProvider(AffiliateProvider):
    """Search Amazon Creators API and return the strictest matching offer."""

    name = "amazon"

    def __init__(self) -> None:
        self._matcher = ProductMatchService()

    async def discover(self, product, session=None, transport=None) -> AffiliateOffer:
        client_id = _clean(settings.affiliate_api_key)
        client_secret = _clean(settings.affiliate_api_secret)
        partner_tag = _clean(settings.affiliate_partner_id)
        marketplace = _clean(settings.affiliate_marketplace)

        if not (client_id and client_secret and partner_tag and marketplace):
            return AffiliateOffer(
                status="not_found",
                source="amazon",
                reason="Amazon Creators API not configured (AFFILIATE_API_KEY/SECRET/PARTNER_ID/MARKETPLACE)",
            )

        marketplace_details = marketplace_config(marketplace)
        if not marketplace_details:
            return AffiliateOffer(
                status="not_found",
                source="amazon",
                reason=f"unsupported Amazon marketplace: {marketplace}",
            )

        token_endpoint, _ = _token_endpoint_for_settings(marketplace) or (None, None)
        if not token_endpoint:
            return AffiliateOffer(
                status="not_found",
                source="amazon",
                reason="unsupported Amazon Creators API credential version",
            )

        keywords = _clean(product.get("name")) or _clean(product.get("title"))
        if not keywords:
            return AffiliateOffer(
                status="not_found",
                source="amazon",
                reason="missing product name for Amazon search",
            )

        try:
            access_token = await _fetch_access_token(
                token_endpoint=token_endpoint,
                client_id=client_id,
                client_secret=client_secret,
                transport=transport,
            )
            items = await _search_items(
                access_token=access_token,
                marketplace=marketplace,
                partner_tag=partner_tag,
                keywords=keywords,
                brand=_clean(product.get("brand")) or None,
                transport=transport,
            )
        except Exception as exc:  # noqa: BLE001 - provider failures are non-fatal
            return AffiliateOffer(
                status="failed",
                source="amazon",
                reason=f"Amazon Creators API request failed: {exc}",
            )

        if not items:
            return AffiliateOffer(status="not_found", source="amazon", reason="no Amazon results returned")

        selected = {
            "name": _clean(product.get("name")),
            "brand": _clean(product.get("brand")),
        }

        best_offer: AffiliateOffer | None = None
        best_score = -1

        for item in items:
            title, brand, url = _extract_item_info(item)
            if not is_valid_affiliate_url(url):
                continue

            match = self._matcher.match(
                selected,
                {"name": title or "", "brand": brand or ""},
            )
            score = int(match["match_score"])
            candidate = AffiliateOffer(
                status="found",
                url=url,
                product_name=title,
                brand=brand,
                source="amazon",
                match_score=score,
                reason="Amazon Creators API SearchItems candidate",
            )
            if score > best_score:
                best_offer = candidate
                best_score = score
            if score == 100:
                break

        if best_offer is None:
            return AffiliateOffer(
                status="not_found",
                source="amazon",
                reason="Amazon results did not include a valid affiliate URL",
            )

        if best_score < settings.min_affiliate_match_score:
            return AffiliateOffer(
                status="not_found",
                url=None,
                product_name=best_offer.product_name,
                brand=best_offer.brand,
                source="amazon",
                match_score=best_score,
                reason=(
                    "no Amazon result met the strict match threshold "
                    f"({best_score} < {settings.min_affiliate_match_score})"
                ),
            )

        best_offer.reason = "Amazon Creators API SearchItems strict match"
        return best_offer
