"""Department schemas (input vs response)."""

from pydantic import Field

from app.models.enums import DepartmentStatus
from app.schemas.common import BaseResponse, ORMModel


class DepartmentCreate(ORMModel):
    """Request payload for creating a department."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: DepartmentStatus = DepartmentStatus.ACTIVE


class DepartmentUpdate(ORMModel):
    """Request payload for updating a department (all fields optional)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: DepartmentStatus | None = None


class DepartmentResponse(BaseResponse):
    """Department response."""

    name: str
    description: str | None = None
    status: DepartmentStatus