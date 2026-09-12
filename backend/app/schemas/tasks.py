"""Schemas for task card API responses."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
