"""Agent ORM model."""

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, new_uuid
from app.models.enums import AgentStatus


class Agent(Base, TimestampMixin):
    """A registered AI agent.

    ``capabilities`` and ``permissions`` are stored as JSON lists to keep the
    schema flexible as new agents and permission types are introduced.
    """

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    department_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=AgentStatus.ACTIVE.value
    )
    capabilities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    permissions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    configuration: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Agent id={self.id} name={self.name!r} role={self.role!r}>"