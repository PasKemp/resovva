"""
Central exception hierarchy for Resovva.

Follows the structure defined in docs/CODE_STYLE_GUIDE.md (Section 5).
Base class is ResovvaError, with specialized subclasses for common error types.
"""



class ResovvaError(Exception):
    """Base exception for all Resovva application errors."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.detail = message
        self.status_code = status_code
        super().__init__(self.message)


class APIError(ResovvaError):
    """General API exception with HTTP status mapping information."""
    pass


class ValidationError(APIError):
    """Raised for input validation failures (HTTP 400)."""

    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, status_code=400)


class AuthenticationError(APIError):
    """Raised for authentication failures (HTTP 401)."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class PermissionError(APIError):
    """Raised for authorization failures (HTTP 403)."""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, status_code=403)


class NotFoundError(APIError):
    """Raised when a resource is not found (HTTP 404)."""

    def __init__(self, resource: str, identifier: str):
        message = f"{resource} with {identifier} not found"
        super().__init__(message, status_code=404)


class ConflictError(APIError):
    """Raised when an operation conflicts with existing state (HTTP 409)."""

    def __init__(self, message: str = "Conflict occurred"):
        super().__init__(message, status_code=409)


class InternalServerError(APIError):
    """Raised for unexpected server errors (HTTP 500)."""

    def __init__(self, message: str = "Internal server error"):
        super().__init__(message, status_code=500)
