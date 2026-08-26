"""Deterministic TrendEra QA validation (no LLM)."""

_MIN_CONTENT_LENGTH = 200


class QAResult:
    """Outcome of deterministic QA."""

    def __init__(self, passed: bool, errors: list[str]) -> None:
        self.passed = passed
        self.errors = errors


def validate_article(*, title: str, content: str, product_name: str) -> QAResult:
    """Validate required fields for a generated article.

    Checks:
    - title exists
    - content exists
    - minimum reasonable content length
    - product name appears in the article
    """
    errors: list[str] = []

    if not title or not title.strip():
        errors.append("title is missing")

    if not content or not content.strip():
        errors.append("content is missing")
    elif len(content.strip()) < _MIN_CONTENT_LENGTH:
        errors.append(
            f"content is too short ({len(content.strip())} chars, need >= {_MIN_CONTENT_LENGTH})"
        )

    if product_name and product_name.strip() and product_name.strip() not in (content or ""):
        errors.append("product name does not appear in the article")

    return QAResult(passed=len(errors) == 0, errors=errors)