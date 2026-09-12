"""Define persistence models for owner-scoped task data."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class ProcessingState(StrEnum):
    """Enumerate asynchronous processing states for a task."""

    QUEUED = "queued"
    RUNNING = "running"
    READY = "ready"
    FAILED = "failed"


class TaskOrigin(StrEnum):
    """Enumerate the source that created a task."""

    MANUAL = "manual"
    DETECTED = "detected"


class TaskStatus(StrEnum):
    """Enumerate user-visible task workflow states."""

    IN_PROGRESS = "in_progress"
    NEEDS_ATTENTION = "needs_attention"
    ACTION_COMPLETE = "action_complete"
    ERROR = "error"


class TaskType(StrEnum):
    """Enumerate supported task categories."""

    MANUAL = "manual"
    GITHUB = "github"
    RESEARCH = "research"
    EMAIL = "email"
    TRAVEL = "travel"
    SHOPPING = "shopping"
    OTHER = "other"


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(UTC)


@dataclass(slots=True)
class OwnerRecord:
    """Store an anonymous owner and its installation credential.

    Attributes:
        owner_id: The owner boundary used for all scoped records.
        installation_id: The public installation identifier.
        installation_token: The bearer credential stored by the extension.
        created_at: The UTC time when the owner was created.
    """

    owner_id: str
    installation_id: str
    installation_token: str
    created_at: datetime


@dataclass(slots=True)
class TaskRecord:
    """Store a task owned by an anonymous installation.

    Attributes:
        task_id: The server-generated task identifier.
        owner_id: The owner boundary for access checks.
        origin: The source that created this task.
        source_key: The owner-scoped detected source key, if any.
        source_url: The detected source URL, if any.
        task_type: The task category.
        title: The user-visible task title.
        status: The user-visible task workflow state.
        status_reason: The reason for the task status, if available.
        summary: The one- or two-sentence task summary.
        processing_state: The background processing state.
        processing_error_code: The last processing error code, if any.
        observed_at: The latest source observation time, if any.
        updated_at: The latest task update time.
        client_request_id: The owner-scoped idempotency key for manual tasks.
    """

    task_id: str
    owner_id: str
    origin: TaskOrigin
    source_key: str | None
    source_url: str | None
    task_type: TaskType
    title: str
    status: TaskStatus
    status_reason: str | None
    summary: str
    processing_state: ProcessingState
    processing_error_code: str | None
    observed_at: datetime | None
    updated_at: datetime
    client_request_id: str | None
