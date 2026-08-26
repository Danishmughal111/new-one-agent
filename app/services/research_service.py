"""Multi-source product research with graceful fallback.

Runs free, no-key public providers (Wikipedia + DuckDuckGo), records which
succeeded, and always falls back to the curated catalog. Only URLs actually
fetched are reported; partial research is explicitly marked partial.
"""

from urllib.parse import quote, urlencode

import httpx

from app.core.logging import get_logger

logger = get_logger("trendera.research")

WIKIPEDIA_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
DUCKDUCKGO_URL = "https://api.duckduckgo.com/"


def _derived_target_audience(candidate: dict) -> list[str]:
    category = candidate.get("category") or "product"
    return [
        f"People shopping for a {category.lower()}",
        f"Buyers comparing {category.lower()} options",
    ]


def _derived_faqs(candidate: dict) -> list[str]:
    name = candidate.get("name", "this product")
    category = candidate.get("category") or "product"
    return [
        f"Is the {name} worth buying?",
        f"What should I look for in a {category.lower()}?",
        f"Who is the {name} best for?",
    ]


class ResearchProvider:
    """Base research provider."""

    name = "base"
    source_type = "secondary"  # official | primary | secondary | fallback

    async def fetch(self, candidate: dict, transport=None) -> dict | None:
        raise NotImplementedError


class WikipediaProvider(ResearchProvider):
    """Wikipedia REST summary (secondary source)."""

    name = "Wikipedia"
    source_type = "secondary"

    async def fetch(self, candidate: dict, transport=None) -> dict | None:
        url = WIKIPEDIA_SUMMARY_URL.format(title=quote(candidate.get("name", "")))
        async with httpx.AsyncClient(transport=transport, timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
        extract = payload.get("extract")
        page_url = (payload.get("content_urls") or {}).get("desktop", {}).get("page")
        if extract and page_url:
            return {"summary": extract, "url": page_url}
        return None


class DuckDuckGoProvider(ResearchProvider):
    """DuckDuckGo Instant Answer (secondary source)."""

    name = "DuckDuckGo"
    source_type = "secondary"

    async def fetch(self, candidate: dict, transport=None) -> dict | None:
        params = {"q": candidate.get("name", ""), "format": "json", "no_html": 1, "skip_disambig": 1}
        url = f"{DUCKDUCKGO_URL}?{urlencode(params)}"
        async with httpx.AsyncClient(transport=transport, timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
        abstract = payload.get("Abstract")
        if abstract:
            return {
                "summary": abstract,
                "url": payload.get("AbstractURL") or f"https://duckduckgo.com/?q={quote(candidate.get('name', ''))}",
            }
        return None


class ResearchService:
    """Researches a product across multiple providers, falling back to catalog."""

    def __init__(self, catalog: list[dict]) -> None:
        self._catalog = catalog
        self._providers: list[ResearchProvider] = [WikipediaProvider(), DuckDuckGoProvider()]

    async def research(self, candidate: dict, transport=None) -> dict:
        """Return structured research with per-source status and real URLs."""
        sources: list[dict] = []
        live_summary = None

        for provider in self._providers:
            try:
                result = await provider.fetch(candidate, transport=transport)
                if result and result.get("summary"):
                    sources.append({"name": provider.name, "url": result["url"], "type": provider.source_type, "fetched": True})
                    if live_summary is None:
                        live_summary = result["summary"]
                else:
                    sources.append({"name": provider.name, "url": None, "type": provider.source_type, "fetched": False})
            except Exception as exc:  # noqa: BLE001
                logger.warning("%s research failed for %s: %s", provider.name, candidate.get("name"), exc)
                sources.append({"name": provider.name, "url": None, "type": provider.source_type, "fetched": False})

        sources.append({"name": "Curated Catalog", "url": candidate.get("source_url"), "type": "fallback", "fetched": True})

        features = candidate.get("features") or []
        limitations = candidate.get("limitations") or []

        facts = {
            "name": candidate.get("name"),
            "brand": candidate.get("brand"),
            "category": candidate.get("category"),
            "description": live_summary or candidate.get("description"),
            "features": features,
            "specs": candidate.get("specs") or {},
            "limitations": limitations,
            "advantages": features,
            "disadvantages": limitations,
            "target_audience": _derived_target_audience(candidate),
            "pricing": candidate.get("pricing"),
            "alternatives": candidate.get("alternatives") or [],
            "faqs": _derived_faqs(candidate),
            "live_summary": live_summary,
        }

        missing = []
        if not facts.get("pricing"):
            missing.append("pricing")
        if not facts.get("alternatives"):
            missing.append("alternatives")
        if not facts.get("specs"):
            missing.append("specifications")

        succeeded = sum(1 for s in sources if s["fetched"])
        status = "success" if succeeded == len(sources) else ("partial" if succeeded > 0 else "failed")

        return {
            "status": status,
            "sources_attempted": len(sources),
            "sources_succeeded": succeeded,
            "sources": sources,
            "data": facts,
            "missing_information": missing,
        }
