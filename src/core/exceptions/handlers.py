from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.core.exceptions import AppException
from src.shared.schemas import ErrorResponse, ErrorDetail


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle application exceptions."""
    field = exc.details.get("field")
    errors = [ErrorDetail(field=field, message=exc.message)]

    response = ErrorResponse(
        message=exc.message,
        errors=errors,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(),
    )


def _format_validation_errors(errors: list[dict]) -> list[ErrorDetail]:
    details: list[ErrorDetail] = []
    for error in errors:
        loc = error.get("loc", ())
        # Drop top-level "body" for cleaner field paths
        if loc and loc[0] == "body":
            loc = loc[1:]
        field = ".".join(str(part) for part in loc) if loc else None
        details.append(ErrorDetail(field=field, message=error.get("msg", "Invalid value")))
    return details


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle FastAPI validation errors."""
    response = ErrorResponse(
        message="Validation error",
        errors=_format_validation_errors(exc.errors()),
    )
    return JSONResponse(
        status_code=422,
        content=response.model_dump(),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle generic HTTP exceptions."""
    errors = [ErrorDetail(field=None, message=str(exc.detail) if exc.detail else "HTTP error")]
    response = ErrorResponse(
        message=str(exc.detail) if exc.detail else "HTTP error",
        errors=errors,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(),
    )


def _friendly_db_error(exc: Exception) -> tuple[str, str | None, int]:
    """
    Convert common DB constraint errors to a stable, user-facing message.

    Note: we intentionally do not expose full DB error details unless debug is enabled.
    """
    raw = str(getattr(exc, "orig", exc))
    lower = raw.lower()

    if "does not exist" in lower and "column" in lower:
        # Typical after deploying code without running Alembic migrations.
        return (
            "Database schema is out of date. Run the latest migrations and try again.",
            None,
            500,
        )

    if ("users" in lower and "role" in lower) and (
        "invalid input value for enum" in lower
        or ("violates check constraint" in lower and "role" in lower)
        or ("violates" in lower and "constraint" in lower and "role" in lower)
    ):
        return (
            "Database schema does not allow this role value. Run the latest migrations and try again.",
            "role",
            400,
        )

    if settings.debug:
        return (raw, None, 500)

    return ("Database error", None, 500)


async def sqlalchemy_db_error_handler(request: Request, exc: Exception) -> JSONResponse:
    message, field, status_code = _friendly_db_error(exc)
    response = ErrorResponse(
        message=message,
        errors=[ErrorDetail(field=field, message=message)],
    )
    return JSONResponse(status_code=status_code, content=response.model_dump())
