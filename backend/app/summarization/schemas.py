"""Validated summarization model output schemas."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

SummaryText = Annotated[str, Field(min_length=1, max_length=300)]


class SummaryOutput(BaseModel):
    """Summary model output.

    Attributes:
        summary: One- or two-sentence summary grounded in task evidence.
    """

    model_config = ConfigDict(extra="forbid")

    summary: SummaryText


def validate_summary_output(value: object) -> SummaryOutput:
    """Validate raw model output as a summary.

    Args:
        value: Raw model output.

    Returns:
        Validated summary output.

    Raises:
        pydantic.ValidationError: Raised when the output does not match the schema.
    """

    return SummaryOutput.model_validate(value)
