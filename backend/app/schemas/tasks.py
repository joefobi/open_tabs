"""Schemas for task card API requests and responses."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

TaskTitle = Annotated[str, Field(min_length=1, max_length=200)]
ClientRequestId = Annotated[str, Field(min_length=1, max_length=120)]
StatusReason = Annotated[str, Field(min_length=1, max_length=500)]


class TaskOrigin(StrEnum):
    """Allowed task origin values."""

    DETECTED = "detected"
    MANUAL = "manual"


class TaskType(StrEnum):
    """Supported high-level task categories."""

    GITHUB = "github"
    RESEARCH = "research"
    EMAIL = "email"
    TRAVEL = "travel"
    SHOPPING = "shopping"
    MANUAL = "manual"


class TaskStatus(StrEnum):
    """User-visible task status values."""

    IN_PROGRESS = "in_progress"
    NEEDS_ATTENTION = "needs_attention"
    ACTION_COMPLETE = "action_complete"
    ERROR = "error"


class ProcessingState(StrEnum):
    """Background processing state values."""

    QUEUED = "queued"
    RUNNING = "running"
    READY = "ready"
    FAILED = "failed"


class TaskCard(BaseModel):
    """Task card returned to the extension sidebar.

    Attributes:
        id: Stable task identifier.
        origin: Whether the task is detected or manual.
        source_key: Nullable source key for detected tasks.
        source_url: Nullable source URL used for return-to-tab behavior.
        type: Supported task type.
        title: User-visible task title.
        status: User-visible task status.
        status_reason: Optional status explanation.
        summary: Optional grounded summary.
        processing_state: Background processing state.
        processing_error_code: Optional processing error code.
        observed_at: Latest source observation time.
        updated_at: Timestamp when the task last changed.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID
    origin: TaskOrigin
    source_key: str | None
    source_url: str | None
    type: TaskType
    title: str
    status: TaskStatus
    status_reason: str | None
    summary: str | None
    processing_state: ProcessingState
    processing_error_code: str | None
    observed_at: datetime | None
    updated_at: datetime


class TaskListResponse(BaseModel):
    """Response containing owner-scoped task cards.

    Attributes:
        tasks: Task cards visible to the authenticated owner.
    """

    model_config = ConfigDict(extra="forbid")

    tasks: list[TaskCard]


class ManualTaskCreateRequest(BaseModel):
    """Request to create a manual task with an owner-scoped idempotency key.

    Attributes:
        client_request_id: Client-generated idempotency key.
        title: User-visible manual task title.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "client_request_id": "sidebar-manual-001",
                "title": "Review Yokohama tabs before standup",
            }
        },
    )

    client_request_id: ClientRequestId
    title: TaskTitle


class ManualTaskPatchRequest(BaseModel):
    """Request to patch mutable fields on a manual task.

    Attributes:
        title: Optional replacement title.
        status: Optional replacement task status.
        status_reason: Optional replacement or explicit null status reason.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "title": "Review Yokohama tabs after lunch",
                "status": "action_complete",
                "status_reason": "Marked complete by the user.",
            }
        },
    )

    title: TaskTitle | None = None
    status: TaskStatus | None = None
    status_reason: StatusReason | None = None


class ClearDataResponse(BaseModel):
    """Response returned after clearing owner-scoped data.

    Attributes:
        deleted_tasks: Number of task rows deleted.
    """

    model_config = ConfigDict(extra="forbid")

    deleted_tasks: int
