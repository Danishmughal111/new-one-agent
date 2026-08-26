"""TrendEra autonomous workflow request/response schemas."""

from typing import Any

from pydantic import Field

from app.schemas.common import ORMModel


class TrenderaRunRequest(ORMModel):
    """Request to trigger one autonomous TrendEra run."""

    publish_now: bool = False


class TrenderaRunResponse(ORMModel):
    """Structured outcome of one autonomous TrendEra run."""

    status: str
    selected_product: str | None = None
    product_id: str | None = None
    research_status: str | None = None
    duplicate_check: str | None = None
    discovery_status: str | None = None
    research: dict[str, Any] | None = None
    opportunity: dict[str, Any] | None = None
    seo_score: int | None = None
    primary_keyword: str | None = None
    labels: list[str] | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    article_id: str | None = None
    article_generated: bool = False
    image_status: str | None = None
    image_url: str | None = None
    image_generated: bool = False
    qa_result: dict[str, Any] = Field(default_factory=dict)
    blogger_result: dict[str, Any] | None = None
    published: bool = False
    publish_status: str | None = None
    error: str | None = None
