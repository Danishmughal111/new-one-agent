"""Global exception handlers mapping domain errors to HTTP responses.

Returns a consistent error shape and never leaks stack traces or internal
secrets to clients.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.exceptions import (
    AppError,
    InvalidStateTransitionError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)

logger = logging.getLogger("api.errors")


class ErrorBody(BaseModel):
    """Consistent error response body."""

    type: str
    message: str


def _status_for(exc: AppError) -> int:
    if isinstance(exc, NotFoundError):
        return 404
    if isinstance(exc, PermissionDeniedError):
        return 403
    if isinstance(exc, InvalidStateTransitionError):
        return 409
    if isinstance(exc, ValidationError):
        return 422
    return 400


def register_exception_handlers(app: FastAPI) -> None:
    """Attach domain + generic exception handlers to the app."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        status = _status_for(exc)
        logger.warning("Domain error %s on %s %s: %s", type(exc).__name__, request.method, request.url.path, exc)
        return JSONResponse(
            status_code=status,
            content=ErrorBody(type=type(exc).__name__, message=str(exc)).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        # Do NOT expose exception details to clients.
        return JSONResponse(
            status_code=500,
            content=ErrorBody(type="InternalServerError", message="An unexpected error occurred").model_dump(),
        )