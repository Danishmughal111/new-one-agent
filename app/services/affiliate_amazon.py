"""Amazon Product Advertising API 5.0 affiliate provider.

Finds a real Amazon offer for the selected product via ``SearchItems`` (AWS
Signature V4 signed). Requires env credentials; never invents URLs (uses
Amazon's returned ``DetailPageURL`` or the deterministic ``/dp/{ASIN}?tag=``
form with YOUR real Associates tag).

    AFFILIATE_PROVIDER=amazon
    AFFILIATE_API_KEY      (Access Key ID)
    AFFILIATE_API_SECRET   (Secret Access Key)
    AFFILIATE_PARTNER_ID   (Associates tag, e.g. "mytag-21")
    AFFILIATE_MARKETPLACE  (e.g. "www.amazon.sa" or "www.amazon.com")
"""

import hashlib
import hmac
import json
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.services.affiliate_providers import AffiliateOffer, AffiliateProvider

SERVICE = "ProductAdvertisingAPI"
TARGET = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"

# marketplace -> (API host, signing region)
_MARKETPLACES = {
    "www.amazon.com": ("webservices.amazon.com", "us-east-1"),
    "amazon.com": ("webservices.amazon.com", "us-east-1"),
    "www.amazon.sa": ("webservices.amazon.sa", "eu-west-1"),
    "amazon.sa": ("webservices.amazon.sa", "eu-west-1"),
    "www.amazon.ae": ("webservices.amazon.ae", "eu-west-1"),
    "amazon.ae": ("webservices.amazon.ae", "eu-west-1"),
    "www.amazon.co.uk": ("webservices.amazon.co.uk", "eu-west-1"),
}


def marketplace_config(marketplace: str) -> tuple[str, str] | None:
    """Return (api_host, region) for a marketplace, or None if unsupported."""
    return _MARKETPLACES.get((marketplace or "").strip().lower())


def build_affiliate_url(host: str, asin: str, tag: str) -> str:
    """Deterministic affiliate URL using the caller's real Associates tag."""
    return f"https://{host}/dp/{asin}?tag={tag}"


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret_key: str, date_stamp: str, region: str) -> bytes:
    k_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, SERVICE)
    return _sign(k_service, "aws4_request")


def sign_search_request(
    *, host: str, region: str, access_key: str, secret_key: str, payload: str
) -> dict:
    """Return AWS Signature V4 signed headers for a PA-API 5.0 SearchItems POST."""
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    canonical_headers = (
        f"content-type:application/json; charset=UTF-8\n"
        f"host:{host}\n"
        f"x-amz-date:{amz_date}\n"
        f"x-amz-target:{TARGET}\n"
    )
    signed_headers = "content-type;host;x-amz-date;x-amz-target"
    payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    canonical_request = "\n".join(
        ["POST", "/paapi5/searchitems", "", canonical_headers, signed_headers, payload_hash]
    )
    credential_scope = f"{date_stamp}/{region}/{SERVICE}/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    key = _signing_key(secret_key, date_stamp, region)
    signature = hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return {
        "content-type": "application/json; charset=UTF-8",
        "host": host,
        "x-amz-date": amz_date,
        "x-amz-target": TARGET,
        "authorization": authorization,
    }


class AmazonAffiliateProvider(AffiliateProvider):
    """Searches Amazon PA-API 5.0 and returns the matching product offer."""

    name = "amazon"

    async def discover(self, product, session=None, transport=None) -> AffiliateOffer:
        access_key = settings.affiliate_api_key.strip()
        secret_key = settings.affiliate_api_secret.strip()
        tag = settings.affiliate_partner_id.strip()
        marketplace = settings.affiliate_marketplace.strip()

        if not (access_key and secret_key and tag and marketplace):
            return AffiliateOffer(
                status="not_found",
                source="amazon",
                reason="Amazon PA-API not configured (AFFILIATE_API_KEY/SECRET/PARTNER_ID/MARKETPLACE)",
            )

        cfg = marketplace_config(marketplace)
        if not cfg:
            return AffiliateOffer(
                status="not_found", source="amazon", reason=f"unsupported marketplace: {marketplace}"
            )
        host, region = cfg

        full_marketplace = marketplace if marketplace.startswith("www.") else f"www.{marketplace}"
        body = {
            "Keywords": product.get("name", ""),
            "ItemCount": 5,
            "SearchIndex": "All",
            "Resources": ["ItemInfo.Title", "ItemInfo.ByLineInfo"],
            "PartnerTag": tag,
            "PartnerType": "Associates",
            "Marketplace": full_marketplace,
        }
        payload = json.dumps(body)
        headers = sign_search_request(
            host=host, region=region, access_key=access_key, secret_key=secret_key, payload=payload
        )
        url = f"https://{host}/paapi5/searchitems"

        try:
            async with httpx.AsyncClient(transport=transport, timeout=30) as client:
                response = await client.post(url, headers=headers, content=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:  # noqa: BLE001 - provider failures are non-fatal
            return AffiliateOffer(status="failed", source="amazon", reason=f"Amazon search failed: {exc}")

        items = ((data.get("SearchResult") or {}).get("Items")) or []
        if not items:
            return AffiliateOffer(status="not_found", source="amazon", reason="no Amazon results")

        first = items[0]
        asin = first.get("ASIN")
        item_info = first.get("ItemInfo") or {}
        title = (item_info.get("Title") or {}).get("DisplayValue")
        brand = (item_info.get("ByLineInfo") or {}).get("Brand", {}).get("DisplayValue")
        offer_url = first.get("DetailPageURL") or (build_affiliate_url(host, asin, tag) if asin else None)

        if not offer_url:
            return AffiliateOffer(status="not_found", source="amazon", reason="Amazon item missing URL/ASIN")

        return AffiliateOffer(
            status="found",
            url=offer_url,
            product_name=title,
            brand=brand,
            source="amazon",
            match_score=0,
            reason="Amazon candidate offer",
        )

