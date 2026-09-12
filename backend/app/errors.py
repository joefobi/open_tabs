"""Application error response helpers."""

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.app.schemas.errors import ErrorDetail, ErrorEnvelope


def error_code_for_status(status_code: int) -> str:
    """Return a stable error code for an HTTP status.

    Args:
        status_code: HTTP status code.

    Returns:
        Machine-readable error code.
    """

    if status_code == 400:
        return "invalid_request"
    if status_code == 401:
        return "unauthorized"
    if status_code == 404:
        return "not_found"
    if status_code == 429:
        return "rate_limited"
    return "request_failed"


def is_retryable_status(status_code: int) -> bool:
    """Return whether a response status is retryable.

    Args:
        status_code: HTTP status code.

    Returns:
        True when the client can retry the request unchanged.
    """

    return status_code in {429, 500, 502, 503, 504}


def make_error_response(status_code: int, message: str) -> JSONResponse:
    """Build a structured JSON error response.

    Args:
        status_code: HTTP status code for the response.
        message: Human-readable error message.

    Returns:
        JSON response using the API error envelope.
    """

    envelope = ErrorEnvelope(
        error=ErrorDetail(
            code=error_code_for_status(status_code),
            message=message,
            retryable=is_retryable_status(status_code),
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(),
    )


async def http_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Convert FastAPI HTTP exceptions to the API error envelope.

    Args:
        _: Request that raised the exception.
        exc: FastAPI HTTP exception.

    Returns:
        Structured JSON error response.
    """

    if not isinstance(exc, HTTPException):
        return make_error_response(500, "Request failed.")

    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return make_error_response(exc.status_code, message)


async def validation_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Convert validation errors to the API error envelope.

    Args:
        _: Request that failed validation.
        exc: FastAPI request validation error.

    Returns:
        Structured JSON error response.
    """

    if not isinstance(exc, RequestValidationError):
        return make_error_response(500, "Request failed.")

    return make_error_response(400, "Invalid request body or parameters.")
