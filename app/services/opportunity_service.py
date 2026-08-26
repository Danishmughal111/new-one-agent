"""Opportunity scoring for TrendEra product/topic selection.

Produces a transparent, factorized decision signal (0-100). It is an internal
heuristic, not a prediction — and it never claims a product is "trending"
without real source evidence (``trend_evidence`` stays 0 unless a real source
supplies it).
"""


def _rating(score: int) -> str:
    if score < 40:
        return "Low Opportunity"
    if score < 60:
        return "Moderate Opportunity"
    if score < 80:
        return "Strong Opportunity"
    return "High Potential"


def score_opportunity(research: dict) -> dict:
    """Score a researched product from 0-100 with a transparent breakdown."""
    data = research.get("data") or {}
    status = research.get("status") or "failed"

    source_quality = 20 if status == "success" else (10 if status == "partial" else 0)
    audience_clarity = 15 if data.get("target_audience") else 0
    feature_richness = min(len(data.get("features") or []) * 5, 20)
    comparison_potential = 10 if data.get("alternatives") else 0
    faq_potential = 10 if data.get("faqs") else 0
    trend_evidence = 0  # never fabricated; only set from real source evidence
    uniqueness = min(10, len(data.get("specs") or {}) * 3)
    content_depth = 15 if data.get("description") else 0

    factors = {
        "source_quality": source_quality,
        "audience_clarity": audience_clarity,
        "feature_richness": feature_richness,
        "comparison_potential": comparison_potential,
        "faq_potential": faq_potential,
        "trend_evidence": trend_evidence,
        "uniqueness": uniqueness,
        "content_depth": content_depth,
    }
    total = max(0, min(sum(factors.values()), 100))
    return {
        "score": total,   # backwards-compatible alias
        "total": total,
        "rating": _rating(total),
        "factors": factors,
    }

