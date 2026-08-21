"""Agent schemas (input vs response)."""

from pydantic import Field

from app.models.enums import AgentStatus
from app.schemas.common import BaseResponse, ORMModel


class AgentCreate(ORMModel):
    """Request payload for registering an agent."""

    name: str = Field(min_length=1, max_length=255)
    role: str = Field(min_length=1, max_length=255)
    department_id: str | None = None
    status: AgentStatus = AgentStatus.ACTIVE
    capabilities: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    configuration: dict = Field(default_factory=dict)


class AgentUpdate(ORMModel):
    """Request payload for updating an agent (all fields optional)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    role: str | None = Field(default=None, min_length=1, max_length=255)
    department_id: str | None = None
    status: AgentStatus | None = None
    capabilities: list[str] | None = None
    permissions: list[str] | None = None
    configuration: dict | None = None


class AgentResponse(BaseResponse):
    """Agent response."""

    name: str
    role: str
    department_id: str | None = None
    status: AgentStatus
    capabilities: list[str]
    permissions: list[str]
    configuration: dict