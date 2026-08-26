"""Verified affiliate offer cache model."""

from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, new_uuid


class AffiliateOfferRecord(Base, TimestampMixin):
    """A verified affiliate/product offer matched to a TrendEra product."""

    __tablename__ = "trendera_affiliate_offers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    product_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    affiliate_url: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_product_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="verified")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AffiliateOfferRecord id={self.id} product_id={self.product_id!r}>"
