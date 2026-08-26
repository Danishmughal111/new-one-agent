"""SEO planning, validation, Blogger labels, and link helpers."""

import re

# Curated, human-readable label suggestions per category (specific over generic).
CATEGORY_LABELS: dict[str, list[str]] = {
    "Headphones": ["Wireless Headphones", "Noise Cancelling Headphones"],
    "Earbuds": ["Wireless Earbuds", "Noise Cancelling Earbuds"],
    "E-reader": ["E-Reader", "Reading Device"],
    "Computer mouse": ["Wireless Mouse", "Ergonomic Mouse", "Productivity Mouse"],
    "Power bank": ["Portable Charger", "USB-C Charger"],
    "Smartwatch": ["Fitness Tracking", "Wearable Tech"],
    "Smartphone": ["Android Phone", "5G Phone"],
}


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return slug[:80] or "product"


def build_seo_plan(research: dict) -> dict:
    """Build a structured SEO plan from research data (deterministic)."""
    data = research.get("data") or {}
    name = data.get("name", "product")
    brand = data.get("brand") or ""
    category = data.get("category") or "product"

    return {
        "primary_keyword": name,
        "secondary_keywords": [f"{brand} {category}".strip(), f"best {category.lower()}", f"{category.lower()} review"],
        "long_tail_keywords": [f"is the {name} worth it", f"{name} pros and cons", f"{name} alternatives"],
        "search_intent": "commercial investigation",
        "seo_title": f"{name} Review: Features, Pros, Cons, and Who It's For",
        "slug": slugify(name),
        "meta_description": f"Honest {name} review covering key features, pros and cons, and who it is for.",
        "target_audience": data.get("target_audience") or [],
        "questions": data.get("faqs") or [],
        "structure": ["Introduction", "Why this product matters", "Key Features", "Real-world use cases", "Pros", "Cons / limitations", "Who should buy it", "Alternatives", "FAQ", "Final verdict"],
    }


def build_labels(research: dict, plan: dict | None = None) -> list[str]:
    """Generate 5-10 high-quality, de-duplicated Blogger labels."""
    data = research.get("data") or {}
    name = data.get("name")
    brand = data.get("brand")
    category = data.get("category")

    labels: list[str] = []
    for label in (name, brand, category):
        if label:
            labels.append(label)
    if category:
        labels.append(f"Best {category}")
        labels.append(f"{category} Review")
    for label in CATEGORY_LABELS.get(category or "", []):
        labels.append(label)

    seen: set[str] = set()
    deduped: list[str] = []
    for label in labels:
        key = label.strip().lower()
        if label.strip() and key not in seen:
            seen.add(key)
            deduped.append(label.strip())
    return deduped[:10]


def validate_seo(content: str, plan: dict) -> dict:
    """Return an advisory SEO report (score 0-100, issues, suggestions)."""
    issues: list[str] = []
    suggestions: list[str] = []

    title = plan.get("seo_title")
    primary = plan.get("primary_keyword", "")
    lower = (content or "").lower()

    if not title:
        issues.append("missing SEO title")
    if primary and primary.lower() not in lower:
        issues.append("primary keyword not present in article")
    if not plan.get("meta_description"):
        issues.append("missing meta description")
    if not plan.get("slug"):
        issues.append("missing slug")
    if "##" not in content:
        issues.append("no h2 headings found")

    if "pros" not in lower or "cons" not in lower:
        suggestions.append("add a pros and cons section")
    if "faq" not in lower:
        suggestions.append("add an FAQ section")
    if "limitations" not in lower and "cons" not in lower:
        suggestions.append("add a limitations section")

    if len((content or "").strip()) < 500:
        issues.append("thin content")

    occurrences = lower.count(primary.lower()) if primary else 0
    if occurrences > 8:
        issues.append("possible keyword stuffing")

    score = max(0, 100 - len(issues) * 15)
    passed = score >= 60 and not any(i.startswith("missing") for i in issues)
    return {"seo_score": score, "passed": passed, "issues": issues, "suggestions": suggestions}


REQUIRED_SECTIONS = [
    "introduction",
    "why this product matters",
    "key features",
    "use cases",
    "pros",
    "cons",
    "who should buy",
    "alternatives",
    "faq",
    "verdict",
]


def validate_structure(content: str) -> dict:
    """Check which required article sections are present in the markdown.

    "introduction" is treated as the opening prose before the first ``##``
    section heading rather than a literal heading, so a natural lead paragraph
    satisfies it.
    """
    lower = (content or "").lower()
    lines = (content or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    has_intro = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("##"):
            break
        if stripped and not stripped.startswith("#"):
            has_intro = True

    present = ["introduction"] if has_intro else []
    missing = [] if has_intro else ["introduction"]
    for section in REQUIRED_SECTIONS[1:]:
        if section in lower:
            present.append(section)
        else:
            missing.append(section)
    return {"present": present, "missing": missing, "complete": not missing}


def add_internal_links(content: str, links: list[tuple[str, str]]) -> str:
    """Append up to 3 relevant internal links (no duplicates)."""
    unique: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor, url in links[:3]:
        if url not in seen:
            seen.add(url)
            unique.append((anchor, url))
    if not unique:
        return content

    lines = ["", "## Related Articles", ""]
    for anchor, url in unique:
        lines.append(f"- [{anchor}]({url})")
    return content.rstrip() + "\n" + "\n".join(lines) + "\n"


def add_sources_section(content: str, sources: list[str]) -> str:
    """Append a small Sources section using only real fetched URLs."""
    if not sources:
        return content
    lines = ["", "## Sources", ""]
    for url in sources:
        lines.append(f"- {url}")
    return content.rstrip() + "\n" + "\n".join(lines) + "\n"
