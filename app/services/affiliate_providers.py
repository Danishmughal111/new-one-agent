"""Modular affiliate offer discovery.

Providers are consulted in priority order:
    1. ManualAffiliateProvider  (explicitly configured affiliate_url)
    2. CachedAffiliateProvider  (previously verified offer in the DB)
    3. ProductSearchAffiliateProvider (automatic search via a configured API)

Every provider returns a structured ``AffiliateOffer`` and never invents URLs.
"""

import httpx
from dataclasses import dataclass

from app.core.config import settings
from app.models.affiliate_offer import AffiliateOfferRecord
from app.models.base import utcnow
from app.repositories.affiliate_offer import AffiliateOfferRepository
from app.services.affiliate_matching import ProductMatchService
from app.services.affiliate_service import is_valid_affiliate_url


@dataclass
class AffiliateOffer:
    """Structured result from an affiliate provider."""

    status: str  # "found" | "not_found" | "failed"
    url: str | None = None
    product_name: str | None = None
    brand: str | None = None
    source: str | None = None
    match_score: int = 0
    reason: str | None = None


class AffiliateProvider:
    """Base provider contract (all providers are async)."""

    name = "base"

    async def discover(self, product: dict, session=None, transport=None) -> AffiliateOffer:
        raise NotImplementedError


class ManualAffiliateProvider(AffiliateProvider):
    """Uses an explicitly configured affiliate URL (highest priority)."""

    name = "manual"

    async def discover(self, product, session=None, transport=None) -> AffiliateOffer:
        url = product.get("affiliate_url")
        url = url.strip() if isinstance(url, str) else None
        if is_valid_affiliate_url(url):
            return AffiliateOffer(
                status="found",
                url=url,
                product_name=product.get("name"),
                source="manual",
                match_score=100,
                reason="manually configured affiliate URL",
            )
        return AffiliateOffer(status="not_found", source="manual", reason="no manual affiliate URL")


class CachedAffiliateProvider(AffiliateProvider):
    """Reuses a previously verified offer persisted in the database."""

    name = "cached"

    async def discover(self, product, session=None, transport=None) -> AffiliateOffer:
        product_id = product.get("product_id")
        if not product_id or session is None:
            return AffiliateOffer(status="not_found", source="cached", reason="no cached offer")
        record = await AffiliateOfferRepository(session).get_by_product(product_id)
        if record and record.status == "verified" and is_valid_affiliate_url(record.affiliate_url):
            return AffiliateOffer(
                status="found",
                url=record.affiliate_url,
                product_name=record.provider_product_name,
                source="cached",
                match_score=int(record.match_score),
                reason=f"previously verified by {record.provider}",
            )
        return AffiliateOffer(status="not_found", source="cached", reason="no verified cached offer")


class ProductSearchAffiliateProvider(AffiliateProvider):
    """Searches a configured affiliate/product API for a matching offer.

    Requires ``AFFILIATE_PROVIDER`` and ``AFFILIATE_API_BASE_URL`` to be set.
    Otherwise it gracefully returns ``not_found`` (never crashes the workflow).
    """

    name = "product_search"

    async def discover(self, product, session=None, transport=None) -> AffiliateOffer:
        if not settings.affiliate_provider.strip() or not settings.affiliate_api_base_url.strip():
            return AffiliateOffer(
                status="not_found", source="product_search", reason="no affiliate provider configured"
            )

        url = f"{settings.affiliate_api_base_url.rstrip('/')}/search"
        headers = {"Authorization": f"Bearer {settings.affiliate_api_key}"} if settings.affiliate_api_key.strip() else {}
        params = {"query": product.get("name", "")}
        if settings.affiliate_partner_id.strip():
            params["partner_id"] = settings.affiliate_partner_id

        try:
            async with httpx.AsyncClient(transport=transport, timeout=30) as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:  # noqa: BLE001 - provider failures are non-fatal
            return AffiliateOffer(
                status="failed", source="product_search", reason=f"affiliate search failed: {exc}"
            )

        offers = data.get("offers") or []
        if not offers:
            return AffiliateOffer(status="not_found", source="product_search", reason="no offers returned")

        first = offers[0]
        return AffiliateOffer(
            status="found",
            url=first.get("url"),
            product_name=first.get("name"),
            brand=first.get("brand"),
            source="product_search",
            match_score=0,
            reason="candidate offer (unverified)",
        )


class AffiliateDiscoveryService:
    """Runs providers in priority order and validates automatic matches."""

    def __init__(self, session) -> None:
        self.session = session
        self._matcher = ProductMatchService()
        self._repo = AffiliateOfferRepository(session)

    async def resolve(
        self,
        *,
        product_id: str,
        identity: dict,
        manual_url: str | None = None,
        transport=None,
    ) -> AffiliateOffer:
        """Return the best offer using manual > cached > automatic priority."""
        product = {**identity, "product_id": product_id, "affiliate_url": manual_url}

        manual = await ManualAffiliateProvider().discover(product)
        if manual.status == "found":
            return manual

        cached = await CachedAffiliateProvider().discover(product, session=self.session)
        if cached.status == "found":
            return cached

        automatic = await ProductSearchAffiliateProvider().discover(product, session=self.session, transport=transport)
        if automatic.status != "found":
            return automatic

        match = self._matcher.match(
            {"name": identity.get("name", ""), "brand": identity.get("brand", "")},
            {"name": automatic.product_name or "", "brand": automatic.brand or ""},
        )
        if match["match_score"] < settings.min_affiliate_match_score:
            return AffiliateOffer(
                status="not_found",
                source="product_search",
                match_score=match["match_score"],
                reason=(
                    f"offer below match threshold "
                    f"({match['match_score']} < {settings.min_affiliate_match_score})"
                ),
            )

        automatic.match_score = match["match_score"]
        await self._cache(product_id, automatic)
        return automatic

    async def _cache(self, product_id: str, offer: AffiliateOffer) -> None:
        """Persist a verified offer so it can be reused later."""
        if not product_id or not offer.url:
            return
        record = AffiliateOfferRecord(
            product_id=product_id,
            affiliate_url=offer.url,
            provider=offer.source or "product_search",
            provider_product_name=offer.product_name,
            match_score=offer.match_score,
            status="verified",
            verified_at=utcnow(),
        )
        await self._repo.save(record)  # flushes; caller commits

