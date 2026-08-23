"""TrendEra article schemas."""

from typing import Any

from pydantic import Field

from app.schemas.common import BaseResponse, ORMModel


class ArticleResponse(BaseResponse):
    """Article response."""

    product_id: str
    title: str
    content: str
    status: str
    labels: list[str] | None = None


class BloggerDraftPayload(ORMModel):
    """Blogger draft-ready payload (no OAuth/publishing)."""

    title: str
    content: str
    labels: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "content": self.content, "labels": self.labels}


class BloggerPublishRequest(ORMModel):
    """Request to publish a QA-passed article as a draft or live post."""

    publish_now: bool = False


class BloggerPublishResponse(ORMModel):
    """Result of publishing an article to Blogger."""

    id: str
    url: str | None = None
    status: str | None = None
    published: bool


class BloggerAuthUrlResponse(ORMModel):
    """Authorization URL returned to start the OAuth flow."""

    authorization_url: str
