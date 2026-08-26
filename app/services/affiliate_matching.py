"""Deterministic product matching for affiliate offers.

Scores how closely a discovered affiliate/product offer matches the selected
product so the workflow never attaches a link for a similar-but-wrong product.
"""

from app.services.product_discovery import normalize_name


class ProductMatchService:
    """Transparent 0-100 scoring across brand, model, generation, similarity."""

    BRAND_POINTS = 30
    MODEL_POINTS = 30
    GENERATION_POINTS = 20
    SIMILARITY_POINTS = 20

    def match(self, product: dict, offer: dict) -> dict:
        """Return a breakdown dict including ``match_score`` (0-100)."""
        p_name = normalize_name(product.get("name", ""))
        o_name = normalize_name(offer.get("name", ""))
        p_brand = (product.get("brand") or "").lower().strip()
        o_brand = (offer.get("brand") or "").lower().strip()

        brand_match = bool(p_brand) and p_brand == o_brand

        p_tokens = set(p_name.split())
        o_tokens = set(o_name.split())
        p_core = p_tokens - set(p_brand.split())
        o_core = o_tokens - set(o_brand.split())

        # Model must match exactly (word + version tokens). This rejects
        # "MX Master 3S" vs "MX Master 3" and "Paperwhite" vs "Scribe".
        model_match = bool(p_core) and p_core == o_core

        p_numbers = {t for t in p_core if any(c.isdigit() for c in t)}
        o_numbers = {t for t in o_core if any(c.isdigit() for c in t)}
        generation_match = bool(p_numbers) and bool(o_numbers) and p_numbers == o_numbers

        union = p_core | o_core
        name_similarity = (2 * len(p_core & o_core) / len(union)) if union else 0.0

        brand_score = self.BRAND_POINTS if brand_match else 0
        model_score = self.MODEL_POINTS if model_match else 0
        generation_score = self.GENERATION_POINTS if generation_match else 0
        similarity_score = round(name_similarity * self.SIMILARITY_POINTS)

        total = brand_score + model_score + generation_score + similarity_score

        return {
            "match_score": max(0, min(100, total)),
            "brand_match": brand_match,
            "model_match": model_match,
            "generation_match": generation_match,
            "name_similarity": round(name_similarity, 3),
            "components": {
                "brand_match": brand_score,
                "model_match": model_score,
                "generation_match": generation_score,
                "name_similarity": similarity_score,
            },
        }
