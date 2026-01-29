"""Custom exceptions for LogosAPI."""

from fastapi import HTTPException, status


class LogosAPIException(HTTPException):
    """Base exception for LogosAPI."""

    def __init__(
        self,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: str = "An error occurred",
    ):
        super().__init__(status_code=status_code, detail=detail)


class AuthenticationError(LogosAPIException):
    """Authentication failed."""

    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class AuthorizationError(LogosAPIException):
    """Authorization failed."""

    def __init__(self, detail: str = "Not authorized"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class NotFoundError(LogosAPIException):
    """Resource not found."""

    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ValidationError(LogosAPIException):
    """Validation failed."""

    def __init__(self, detail: str = "Validation failed"):
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


class ConflictError(LogosAPIException):
    """Resource conflict."""

    def __init__(self, detail: str = "Resource conflict"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class ExternalServiceError(LogosAPIException):
    """External service error."""

    def __init__(self, detail: str = "External service error"):
        super().__init__(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
