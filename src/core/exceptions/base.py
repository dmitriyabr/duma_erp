from typing import Any


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(AppException):
    """Resource not found."""

    def __init__(self, resource: str, identifier: Any = None):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} with id={identifier} not found"
        super().__init__(message=message, status_code=404)


class ValidationError(AppException):
    """Validation error."""

    def __init__(self, message: str, field: str | None = None):
        details = {"field": field} if field else {}
        super().__init__(message=message, status_code=422, details=details)


class AuthenticationError(AppException):
    """Authentication failed."""

    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(message=message, status_code=401)


class AuthorizationError(AppException):
    """Not authorized to perform action."""

    def __init__(self, message: str = "Not authorized"):
        super().__init__(message=message, status_code=403)


class InsufficientStockError(AppException):
    """Not enough stock for operation."""

    def __init__(self, item_id: int, requested: float, available: float):
        message = f"Insufficient stock for item {item_id}: requested {requested}, available {available}"
        super().__init__(
            message=message,
            status_code=400,
            details={"item_id": item_id, "requested": requested, "available": available},
        )


class DuplicateError(AppException):
    """Duplicate resource."""

    def __init__(self, resource: str, field: str, value: Any):
        message = f"{resource} with {field}={value} already exists"
        super().__init__(message=message, status_code=409, details={"field": field, "value": value})


class PdfGenerationUnavailableError(AppException):
    """WeasyPrint/system libraries not available (e.g. pango on macOS)."""

    def __init__(self, message: str | None = None):
        msg = message or (
            "PDF generation is not available on this system. "
            "On macOS install: brew install pango glib."
        )
        super().__init__(message=msg, status_code=503)
