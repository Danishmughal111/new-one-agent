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
        f"Write a detailed, useful TrendEra affiliate article about: {product_name}.",
        "Use the research context as your ONLY source of facts. Do NOT invent specifications, prices, or claims.",
        "Write in a direct, human, commercial voice. Avoid filler like \"in today's fast-paced world\" or \"in the ever-evolving landscape\".",
        "Structure the article with these markdown sections (use ## headings):",
        "Introduction, Why this product matters, Key features, Real-world use cases, Pros, Cons / limitations, Who should buy it, Alternatives, FAQ, Final verdict.",
        "Use the provided keywords naturally; do not keyword-stuff.",
    ]
    if extra:
        lines.extend(extra)
    return "\n".join(lines)


def _mock_completion(product_name: str) -> str:
    """Deterministic placeholder article with the full required section structure."""
    return (
        f"# {product_name} Review\n\n"
        f"{product_name} is a capable option in its category, and this review "
        "breaks down what it offers, who it suits, and whether it is worth buying.\n\n"
        f"## Why this product matters\n\n"
        f"{product_name} addresses a common need with a practical, well-rounded feature set.\n\n"
        f"## Key features\n\n"
        "- Practical everyday functionality\n- Durable, dependable build\n- Easy to use out of the box\n\n"
        f"## Real-world use cases\n\n"
        f"{product_name} fits daily routines, first-time buyers, and anyone upgrading from an older option.\n\n"
        "## Pros\n\n- Solid build quality\n- Good value for money\n- Straightforward to use\n\n"
        "## Cons / limitations\n\n- May lack advanced extras\n- Premium positioning for some buyers\n\n"
        "## Who should buy it\n\n"
        f"People who want a dependable, no-fuss {product_name.lower()} for everyday use.\n\n"
        "## Alternatives\n\n"
        "Other options in the same category offer different trade-offs, so compare before buying.\n\n"
        "## FAQ\n\n"
        f"**Is the {product_name} worth buying?** Yes, for most buyers looking for a reliable choice.\n\n"
        "## Final verdict\n\n"
        f"If you want a well-rounded, reliable option, {product_name} is easy to recommend."
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