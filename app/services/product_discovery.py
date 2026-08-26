"""Autonomous TrendEra product discovery + research.

Discovery is deterministic and cost-free: it reads from a curated catalog of
real, well-known products whose facts are drawn from widely published public
information. No DeepSeek/LLM call is used to pick or rank products. Selection
skips products that are already stored (or already processed), so each run
advances to a fresh product without repeated selection.
"""

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.article import ArticleRepository
from app.repositories.product import ProductRepository

MIN_FEATURES = 2

# Curated catalog of real products. Facts are conservative and drawn from
# manufacturer-communicated, widely published public information. Prices are
# intentionally omitted to avoid stale or fabricated pricing.
CATALOG: list[dict] = [
    {
        "name": "Sony WH-1000XM5 Wireless Headphones",
        "brand": "Sony",
        "category": "Headphones",
        "region": "GLOBAL",
        "description": "Over-ear wireless headphones with active noise cancellation and multipoint Bluetooth connectivity.",
        "features": [
            "Active noise cancellation",
            "Multipoint Bluetooth connectivity",
            "Touch controls",
            "USB-C charging",
            "Wired and wireless playback",
        ],
        "specs": {
            "type": "Over-ear wireless headphones",
            "battery": "Up to 30 hours with noise cancellation (manufacturer rated)",
        },
        "limitations": ["Premium price point", "Bulkier than in-ear options"],
    },
    {
        "name": "Apple AirPods Pro (2nd Generation)",
        "brand": "Apple",
        "category": "Earbuds",
        "region": "GLOBAL",
        "description": "True wireless earbuds with active noise cancellation and a transparency mode.",
        "features": [
            "Active noise cancellation",
            "Transparency mode",
            "Water and sweat resistant",
            "USB-C and MagSafe charging case",
            "Adaptive audio",
        ],
        "specs": {"type": "True wireless earbuds", "chip": "Apple H2"},
        "limitations": ["Best experience within the Apple ecosystem"],
    },
    {
        "name": "Kindle Paperwhite",
        "brand": "Amazon",
        "category": "E-reader",
        "region": "GLOBAL",
        "description": "Waterproof e-reader with a glare-free display and adjustable warm light.",
        "features": [
            "Glare-free display",
            "Adjustable warm light",
            "Waterproof (IPX8)",
            "Long battery life",
            "Built-in front light",
        ],
        "specs": {"display": "6.8-inch glare-free", "waterproof": "IPX8"},
        "limitations": ["No color display", "No page-turn buttons on the base model"],
    },
    {
        "name": "Logitech MX Master 3S",
        "brand": "Logitech",
        "category": "Computer mouse",
        "region": "GLOBAL",
        "description": "Wireless ergonomic mouse with quiet clicks and multi-device support.",
        "features": [
            "Quiet clicks",
            "8K DPI sensor",
            "Multi-device pairing",
            "USB-C charging",
            "Ergonomic shape",
        ],
        "specs": {"type": "Wireless mouse", "sensor": "8K DPI", "charging": "USB-C"},
        "limitations": ["Right-handed design"],
    },
    {
        "name": "Anker PowerCore 10000",
        "brand": "Anker",
        "category": "Power bank",
        "region": "GLOBAL",
        "description": "Compact portable power bank with USB-C for charging devices on the go.",
        "features": [
            "10,000 mAh capacity",
            "USB-C port",
            "Compact and portable",
            "Works with a wide range of devices",
        ],
        "specs": {"capacity": "10,000 mAh", "ports": "USB-C and USB-A"},
        "limitations": ["Modest fast-charging output"],
    },
    {
        "name": "Apple Watch Series 9",
        "brand": "Apple",
        "category": "Smartwatch",
        "region": "GLOBAL",
        "description": "Smartwatch with health tracking, an always-on display, and GPS.",
        "features": [
            "Always-on Retina display",
            "Health and fitness tracking",
            "Built-in GPS",
            "Water resistant",
            "S9 chip",
        ],
        "specs": {"chip": "Apple S9", "display": "Always-on Retina"},
        "limitations": ["Requires an iPhone for full functionality"],
    },
    {
        "name": "Samsung Galaxy S24",
        "brand": "Samsung",
        "category": "Smartphone",
        "region": "GLOBAL",
        "description": "Android smartphone with an AMOLED display and a versatile camera system.",
        "features": [
            "AMOLED display",
            "Triple rear camera system",
            "5G connectivity",
            "AI-assisted features",
        ],
        "specs": {"display": "AMOLED", "connectivity": "5G"},
        "limitations": ["Premium price point"],
    },
    {
        "name": "Bose QuietComfort Headphones",
        "brand": "Bose",
        "category": "Headphones",
        "region": "GLOBAL",
        "description": "Over-ear wireless headphones with active noise cancellation.",
        "features": [
            "Active noise cancellation",
            "Bluetooth connectivity",
            "Comfortable over-ear fit",
            "Built-in microphone",
        ],
        "specs": {"type": "Over-ear wireless headphones"},
        "limitations": ["Bulkier than in-ear earbuds"],
    },
]

def build_research_lines(candidate: dict) -> list[str]:
    """Turn a catalog entry into prompt-safe research context lines."""
    lines = [
        f"Brand: {candidate['brand']}",
        f"Category: {candidate['category']}",
    ]
    if candidate.get("description"):
        lines.append(f"Description: {candidate['description']}")
    features = candidate.get("features") or []
    if features:
        lines.append("Key features: " + "; ".join(features))
    specs = candidate.get("specs") or {}
    if specs:
        lines.append("Specifications: " + "; ".join(f"{k}: {v}" for k, v in specs.items()))
    limitations = candidate.get("limitations") or []
    if limitations:
        lines.append("Limitations: " + "; ".join(limitations))
    return lines


_ORDINALS = {"first": "1", "second": "2", "third": "3", "fourth": "4", "fifth": "5"}


def normalize_name(name: str) -> str:
    """Normalize a product name for duplicate matching.

    "Apple AirPods Pro 2" and "Apple AirPods Pro (2nd Generation)" both become
    "apple airpods pro 2". Version numbers inside model tokens are preserved so
    distinct models (e.g. "WH-1000XM4" vs "WH-1000XM5") stay distinct.
    """
    name = (name or "").lower()
    name = re.sub(r"\(?(\d+)(st|nd|rd|th)\s+generation\)?", r"\1", name)
    name = re.sub(
        r"(first|second|third|fourth|fifth)\s+generation",
        lambda m: _ORDINALS[m.group(1)],
        name,
    )
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _score(candidate: dict) -> int:
    """Deterministic information-richness score (higher is better)."""
    score = 0
    score += len(candidate.get("features") or []) * 10
    score += len(candidate.get("specs") or {}) * 5
    if candidate.get("description"):
        score += 20
    return score


class ProductDiscoveryService:
    """Discovers multiple candidates and filters out duplicates."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._products = ProductRepository(session)
        self._articles = ArticleRepository(session)

    async def _stored_products(self) -> dict[str, object]:
        return {
            normalize_name(p.name): p
            for p in await self._products.list(limit=10000)
        }

    async def is_duplicate(self, name: str) -> tuple[bool, str]:
        """Return (is_duplicate, reason) for a product name."""
        existing = (await self._stored_products()).get(normalize_name(name))
        if existing is None:
            return False, ""
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            days=settings.product_republish_cooldown_days
        )
        articles = await self._articles.list_by_product(existing.id)
        recently_published = [
            a for a in articles if a.published_at and a.published_at >= cutoff
        ]
        if recently_published:
            return True, "recently published (cooldown)"
        return True, "already stored"

    async def discover_candidates(self, limit: int = 5) -> list[dict]:
        """Return up to ``limit`` non-duplicate catalog candidates."""
        stored = await self._stored_products()
        candidates: list[dict] = []
        for c in CATALOG:
            if normalize_name(c["name"]) in stored:
                continue
            if len(c.get("features") or []) < MIN_FEATURES:
                continue
            candidates.append(
                {
                    **c,
                    "discovery_source": "catalog",
                    "source_url": c.get("source_url"),
                    "affiliate_url": c.get("affiliate_url"),
                    "discovered_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            if len(candidates) >= limit:
                break
        return candidates

    async def select_candidate(self) -> dict | None:
        """Return the first non-duplicate candidate (backwards compatible)."""
        candidates = await self.discover_candidates(limit=1)
        return candidates[0] if candidates else None
