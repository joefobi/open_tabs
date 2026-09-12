"""Schemas for API error envelopes."""

from pydantic import BaseModel, ConfigDict


class ErrorDetail(BaseModel):
    """Structured API error detail.

    Attributes:
        code: Stable machine-readable error code.
        message: Human-readable error message.
        retryable: Whether the client can retry the request unchanged.
    """

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    retryable: bool


class ErrorEnvelope(BaseModel):
    """Top-level structured API error response.

    Attributes:
        error: Structured error details.
    """

    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail
