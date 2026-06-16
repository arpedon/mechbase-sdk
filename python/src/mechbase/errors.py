class MechbaseError(Exception):
    """Base class for all SDK errors."""

    def __init__(self, message: str, *, status: int | None = None, body=None):
        super().__init__(message)
        self.status = status
        self.body = body


class AuthError(MechbaseError):
    """401 / 403."""


class NotFoundError(MechbaseError):
    """404."""


class ValidationError(MechbaseError):
    """422."""


class ConflictError(MechbaseError):
    """409."""


class PayloadTooLargeError(MechbaseError):
    """413."""
