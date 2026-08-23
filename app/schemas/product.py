"""TrendEra product schemas."""

from pydantic import Field

from app.schemas.common import BaseResponse, ORMModel


class ProductCreate(ORMModel):
    """Request payload for submitting a product/topic."""

    name: str = Field(min_length=1, max_length=512)
    description: str | None = None
    category: str | None = Field(default=None, max_length=255)
    price_amount: float | None = None
    price_currency: str = "SAR"
    image_url: str | None = None
    region: str | None = Field(default=None, max_length=16)
    metadata: dict = Field(default_factory=dict)


class ProductResponse(BaseResponse):
    """Product response."""

    name: str
    description: str | None = None
    category: str | None = None
    price_amount: float | None = None
    price_currency: str
    image_url: str | None = None
    region: str | None = None
    metadata: dict = Field(validation_alias="metadata_")