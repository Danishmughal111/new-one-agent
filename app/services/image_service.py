"""Pollinations AI image generation with retry + exponential backoff."""

import asyncio
import hashlib
import random
from urllib.parse import quote

import httpx

from app.core.logging import get_logger

logger = get_logger("trendera.image")

POLLINATIONS_IMAGE_URL = "https://image.pollinations.ai/prompt"

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (2, 5)  # wait before attempt 2, wait before attempt 3
_RETRY_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def build_image_prompt(product_name: str, category: str | None) -> str:
    parts = [f"Clean minimalist product illustration of {product_name}"]
    if category:
        parts.append(category)
    parts.append("studio lighting, simple neutral background, no text, no watermark, no logo")
    return ", ".join(parts)


def _deterministic_seed(product_name: str) -> int:
    return int(hashlib.sha256(product_name.encode("utf-8")).hexdigest()[:8], 16)


def build_image_url(product_name: str, category: str | None, seed: int | None = None) -> str:
    """Return a publicly usable Pollinations image URL for the given seed."""
    prompt = build_image_prompt(product_name, category)
    if seed is None:
        seed = _deterministic_seed(product_name)
    return (
        f"{POLLINATIONS_IMAGE_URL}/{quote(prompt)}"
        f"?width=1024&height=1024&nologo=true&seed={seed}"
    )


def _new_seed() -> int:
    return random.randint(0, 2_147_483_647)


class ImageService:
    """Generates one Pollinations image, retrying transient failures.

    Each attempt uses a fresh random seed so retried requests are never
    identical. Retries cover HTTP 408/429/500/502/503/504, timeouts, and
    connection errors; other (permanent) HTTP errors fail immediately.
    """

    async def generate(
        self,
        *,
        product_name: str,
        category: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> str:
        last_error: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            logger.info("Image generation attempt %d/%d", attempt, MAX_ATTEMPTS)
            url = build_image_url(product_name, category, seed=_new_seed())
            try:
                async with httpx.AsyncClient(transport=transport, timeout=60) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                logger.info("Image generation succeeded")
                return url
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code not in _RETRY_STATUS_CODES:
                    raise  # permanent HTTP error; do not retry
                logger.warning("Image generation attempt %d failed: HTTP %d", attempt, exc.response.status_code)
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning("Image generation attempt %d failed: timeout", attempt)
            except httpx.TransportError as exc:
                last_error = exc
                logger.warning("Image generation attempt %d failed: %s", attempt, exc)

            if attempt < MAX_ATTEMPTS:
                wait = BACKOFF_SECONDS[attempt - 1]
                logger.info("Retrying image generation with a new seed (waiting %ds)", wait)
                await asyncio.sleep(wait)

        raise last_error if last_error is not None else RuntimeError(
            "Image generation failed after all attempts"
        )
