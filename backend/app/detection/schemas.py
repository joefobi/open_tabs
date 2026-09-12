"""Validated detection model output schemas."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from backend.app.schemas.tasks import TaskStatus, TaskType

TaskTitle = Annotated[str, Field(min_length=1, max_length=200)]
DetectionText = Annotated[str, Field(min_length=1, max_length=1000)]


class DetectionTaskResult(BaseModel):
    """Detection result describing an observed task.

    Attributes:
        result_type: Discriminator identifying a detected task.
        task_type: High-level task category.
        title: User-visible title for the detected task.
        status: User-visible task status.
        status_reason: Grounded reason for the task status.
        evidence: Evidence from the submitted observation.
    """

    model_config = ConfigDict(extra="forbid")

    result_type: Literal["task"]
    task_type: TaskType
    title: TaskTitle
    status: TaskStatus
    status_reason: DetectionText
    evidence: DetectionText


class DetectionNoTaskResult(BaseModel):
    """Detection result for pages with no supported task.

    Attributes:
        result_type: Discriminator identifying a no-task result.
        reason: Grounded reason no supported task was found.
    """

    model_config = ConfigDict(extra="forbid")

    result_type: Literal["no_task"]
    reason: DetectionText


class DetectionInsufficientEvidenceResult(BaseModel):
    """Detection result for pages that cannot support a task decision.

    Attributes:
        result_type: Discriminator identifying insufficient evidence.
        reason: Grounded reason the observation is not enough.
    """

    model_config = ConfigDict(extra="forbid")

    result_type: Literal["insufficient_evidence"]
    reason: DetectionText


DetectionResult = Annotated[
    DetectionTaskResult | DetectionNoTaskResult | DetectionInsufficientEvidenceResult,
    Field(discriminator="result_type"),
]

DetectionResultAdapter: TypeAdapter[DetectionResult] = TypeAdapter(DetectionResult)


def validate_detection_result(value: object) -> DetectionResult:
    """Validate raw model output as a detection result.

    Args:
        value: Raw model output.

    Returns:
        A validated detection result.

    Raises:
        pydantic.ValidationError: Raised when the output does not match the schema.
    """

    return DetectionResultAdapter.validate_python(value)
