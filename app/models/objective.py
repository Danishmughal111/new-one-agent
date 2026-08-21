"""Objective ORM model."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, new_uuid
from app.models.enums import ObjectivePriority, ObjectiveStatus


class Objective(Base, TimestampMixin):
    """A high-level company objective submitted by the human owner.

    Objectives are decomposed by the CEO agent into tasks. Each created task
    links back to its objective via ``Task.parent_objective_id``.
    """

    __tablename__ = "objectives"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ObjectiveStatus.PENDING.value
    )
    priority: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ObjectivePriority.MEDIUM.value
    )
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Objective id={self.id} title={self.title!r} status={self.status}>"
