"""Department ORM model."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, new_uuid
from app.models.enums import DepartmentStatus


class Department(Base, TimestampMixin):
    """An organizational department within the AI company."""

    __tablename__ = "departments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=DepartmentStatus.ACTIVE.value
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Department id={self.id} name={self.name!r} status={self.status}>"