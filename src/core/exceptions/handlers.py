from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

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
