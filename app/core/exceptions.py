"""Domain-level application exceptions.

Later mapped to HTTP responses by the API layer. Keeping them centralized
avoids coupling services directly to FastAPI/HTTP semantics.
"""


class AppError(Exception):
    """Base class for all application errors."""


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str = "Resource", identifier: str | None = None) -> None:
        self.resource = resource
        self.identifier = identifier
        message = f"{resource} not found"
        if identifier is not None:
            message = f"{message}: {identifier}"
        super().__init__(message)


class ValidationError(AppError):
    """Raised when input data violates a business rule."""


class PermissionDeniedError(AppError):
    """Raised when an agent lacks the required permission for an operation."""

    def __init__(self, permission: str) -> None:
        self.permission = permission
        super().__init__(f"Permission denied: {permission}")


class InvalidStateTransitionError(AppError):
    """Raised when a task status transition is not allowed by the state machine."""

    def __init__(
        self,
        current: str | None,
        target: str,
        allowed: list[str],
    ) -> None:
        self.current = current
        self.target = target
        self.allowed = allowed
        super().__init__(
            f"Invalid task status transition: {current} -> {target}. "
            f"Allowed transitions from {current}: {allowed}"
        )