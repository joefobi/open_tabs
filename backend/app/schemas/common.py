"""Define shared API error schemas."""

from pydantic import BaseModel, ConfigDict


class ErrorBody(BaseModel):
    """Describe a machine-readable API error."""

    code: str
    message: str
    retryable: bool


class ErrorResponse(BaseModel):
    """Wrap API errors in the public response envelope."""

    model_config = ConfigDict(json_schema_extra={"required": ["error"]})

    error: ErrorBody
