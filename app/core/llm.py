"""LLM integration for TrendEra article generation.

Supports DeepSeek's OpenAI-compatible chat completions API via environment
variables. When ``DEEPSEEK_API_KEY`` is unset, a deterministic mock is used so
the full flow remains testable without credentials.

Contract: ONE article generation produces exactly ONE LLM request.
"""

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("core.llm")


def _build_prompt(product_name: str, extra: list[str] | None = None) -> str:
    """Build the single focused generation prompt for a product."""
    lines = [
        f"Write a detailed TrendEra affiliate article about the product: {product_name}.",
        "Include an engaging introduction, key features, benefits, and a conclusion.",
    ]
    if extra:
        lines.extend(extra)
    return "\n".join(lines)


def _mock_completion(product_name: str) -> str:
    """Deterministic placeholder article that intentionally names the product."""
    return (
        f"# {product_name} Review\n\n"
        f"{product_name} is a standout product that deserves attention. "
        "In this TrendEra article we take a close look at what makes it a "
        "worthwhile option for shoppers in the region.\n\n"
        "The product delivers solid build quality, practical features, and "
        "excellent value for money. Users can expect dependable everyday "
        "performance and a smooth experience from the moment they unbox it.\n\n"
        "Key benefits include ease of use, durability, and strong overall "
        "utility. Whether you are a first-time buyer or upgrading, "
        f"{product_name} offers a compelling mix of quality and affordability.\n\n"
        "Final verdict: if you are looking for a reliable and well-rounded "
        f"choice, {product_name} is easy to recommend."
    )


async def _deepseek_completion(product_name: str, extra: list[str] | None) -> str:
    """Call DeepSeek chat completions exactly once and return the content."""
    url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {
                "role": "system",
                "content": "You are a professional affiliate content writer for TrendEra.",
            },
            {"role": "user", "content": _build_prompt(product_name, extra)},
        ],
        "temperature": 0.7,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def _is_llm_configured() -> bool:
    return bool(settings.deepseek_api_key.strip())


async def generate_article_text(
    product_name: str,
    extra: list[str] | None = None,
) -> str:
    """Generate article text using one LLM call (or the mock fallback)."""
    if _is_llm_configured():
        logger.info("Using DeepSeek for article generation")
        return await _deepseek_completion(product_name, extra)

    logger.info("Using deterministic mock for article generation")
    return _mock_completion(product_name)