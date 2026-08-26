"""Deterministic affiliate CTA handling for TrendEra articles.

Adds a clearly-separated "Check Price / View Product" call-to-action only when
a valid affiliate URL is provided. Never invents URLs and never calls the LLM.
"""

from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"http", "https"}


def is_valid_affiliate_url(url: str | None) -> bool:
    """Return True only for a plain http(s) URL with a real host."""
    if not isinstance(url, str) or not url.strip():
        return False
    url = url.strip()
    if not url.lower().startswith(("http://", "https://")):
        return False
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        return False
    host = parsed.hostname or ""
    if not host:
        return False
    # Reject hosts without a domain-like dot (and allow localhost for tests/dev).
    if "." not in host and host != "localhost":
        return False
    return True


def add_affiliate_cta(content: str, url: str | None, product_name: str | None = None) -> str:
    """Append a product-specific affiliate CTA block, or return unchanged if invalid."""
    if not is_valid_affiliate_url(url):
        return content
    label = "Check Price / View Product"
    if product_name:
        safe = (product_name or "").replace("[", " ").replace("]", " ").strip()
        if safe:
            label = f"Check current price for {safe}"
    block = f"\n\n---\n\n[{label}]({url.strip()})\n"
    return content.rstrip() + block
