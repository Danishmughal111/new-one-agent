"""Task status history ORM model.

Records every status transition so the full workflow history is preserved
even after a task reaches a terminal state.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, new_uuid, utcnow


class TaskStatusHistory(Base):
    """An immutable record of a single task status transition."""

    __tablename__ = "task_status_history"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    task_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    previous_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by_agent_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<TaskStatusHistory task_id={self.task_id} "
            f"{self.previous_status} -> {self.new_status}>"
        )