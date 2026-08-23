"""TrendEra article model."""

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, new_uuid


class Article(Base, TimestampMixin):
    """A generated TrendEra article linked to a product."""

    __tablename__ = "trendera_articles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    product_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("trendera_products.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    labels: Mapped[list | None] = mapped_column("labels", JSON, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Article id={self.id} product_id={self.product_id} status={self.status}>"