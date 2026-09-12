"""Define task API request and response schemas."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from backend.app.db.models import ProcessingState, TaskOrigin, TaskStatus, TaskType

TaskTitle = Annotated[str, Field(min_length=1, max_length=200)]
ClientRequestId = Annotated[str, Field(min_length=1, max_length=120)]
StatusReason = Annotated[str, Field(min_length=1, max_length=500)]


class TaskResponse(BaseModel):
    """Return a sidebar task card."""

    id: str
    origin: TaskOrigin
    source_key: str | None
    source_url: str | None
    type: TaskType
    title: str
    status: TaskStatus
    status_reason: str | None
    summary: str
    processing_state: ProcessingState
    processing_error_code: str | None
    observed_at: datetime | None
    updated_at: datetime


class TaskListResponse(BaseModel):
    """Return all task cards visible to the authenticated owner."""

    tasks: list[TaskResponse]


class ManualTaskCreateRequest(BaseModel):
    """Create a manual task with an owner-scoped idempotency key."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "client_request_id": "sidebar-manual-001",
                "title": "Review Yokohama tabs before standup",
            }
        }
    )

    client_request_id: ClientRequestId
    title: TaskTitle


class ManualTaskPatchRequest(BaseModel):
    """Patch mutable fields on a manual task."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Review Yokohama tabs after lunch",
                "status": "action_complete",
                "status_reason": "Marked complete by the user.",
            }
        }
    )

    title: TaskTitle | None = None
    status: TaskStatus | None = None
    status_reason: StatusReason | None = None


class ClearDataResponse(BaseModel):
    """Report owner-scoped data deletion counts."""

    deleted_tasks: int
