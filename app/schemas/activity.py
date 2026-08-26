"""TrendEra activity feed schemas."""

from datetime import datetime

from app.schemas.common import ORMModel


class ActivityResponse(ORMModel):
    """A single activity/workflow event shown in the frontend."""

    id: str
    message: str
    type: str | None = None
    created_at: datetime
    resource_id: str | None = None
