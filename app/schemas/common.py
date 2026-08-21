"""Shared Pydantic schema utilities."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """Base schema with ORM-compatible serialization configuration."""

    model_config = ConfigDict(from_attributes=True)


class BaseResponse(ORMModel):
    """Common response fields shared by all resource responses."""

    id: str
    created_at: datetime
    updated_at: datetime


class Message(BaseModel):
    """Generic informational response."""

    message: str