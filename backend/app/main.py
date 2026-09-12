"""Create and configure the FastAPI backend application."""

from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.app.routes import installations, tasks
from backend.app.schemas.common import ErrorBody, ErrorResponse


def _error_code(status_code: int) -> str:
    """Return the API error code for an HTTP status.

    Args:
        status_code: The HTTP status code.

    Returns:
        The stable API error code.
    """
    codes = {
        400: "bad_request",
        401: "unauthorized",
        404: "not_found",
        422: "invalid_request",
        429: "rate_limited",
    }
    return codes.get(status_code, "internal_error")


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    retryable: bool = False,
) -> JSONResponse:
    """Build a public API error response.

    Args:
        status_code: The HTTP status code for the response.
        code: The stable machine-readable error code.
        message: The user-safe error message.
        retryable: Whether the client should retry the same request later.

    Returns:
        The serialized JSON error response.
    """
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            error=ErrorBody(code=code, message=message, retryable=retryable)
        ).model_dump(),
    )


def _validation_message(errors: Sequence[dict[str, Any]]) -> str:
    """Summarize request validation failures.

    Args:
        errors: The validation errors emitted by FastAPI.

    Returns:
        A concise public error message.
    """
    if not errors:
        return "Request validation failed."

    first_error = errors[0]
    location = ".".join(str(part) for part in first_error.get("loc", ()))
    message = str(first_error.get("msg", "Invalid value."))
    if location:
        return f"{location}: {message}"
    return message


def create_app() -> FastAPI:
    """Create the FastAPI application.

    Returns:
        The configured FastAPI application.
    """
    app = FastAPI(
        title="Browser Task Sidebar API",
        version="0.1.0",
        description="Owner-scoped API for browser task sidebar cards and onboarding.",
        responses={
            400: {"model": ErrorResponse},
            401: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
        },
    )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(
        _request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        """Convert FastAPI HTTP exceptions into the API error envelope.

        Args:
            _request: The request that raised the exception.
            exc: The FastAPI exception.

        Returns:
            The public JSON error response.
        """
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return _error_response(
            status_code=exc.status_code,
            code=_error_code(exc.status_code),
            message=message,
            retryable=exc.status_code == 429,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """Convert validation errors into the API error envelope.

        Args:
            _request: The request that raised the exception.
            exc: The validation exception.

        Returns:
            The public JSON error response.
        """
        return _error_response(
            status_code=422,
            code="invalid_request",
            message=_validation_message(exc.errors()),
        )

    app.include_router(installations.router)
    app.include_router(tasks.router)
    return app


app = create_app()
