class MechbaseError(Exception):
    """Base class for all SDK errors."""

    def __init__(self, message: str, *, status: int | None = None, body=None, retry_after: float | None = None):
        super().__init__(message)
        self.status = status
        self.body = body
        # Seconds the server asked to wait (a 429's Retry-After); None when it gave none.
        self.retry_after = retry_after

    @property
    def detail(self) -> str:
        """The server's `detail` message alone, without the status prefix str(error) carries."""
        if isinstance(self.body, dict) and isinstance(self.body.get("detail"), str):
            return self.body["detail"]
        message = str(self)
        return message.removeprefix(f"{self.status} ") if self.status is not None else message


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
