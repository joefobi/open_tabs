"""Routes for owner-scoped task cards."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.anonymous import require_owner
from backend.app.db.models import Owner, Task
from backend.app.dependencies import get_session
from backend.app.schemas.tasks import (
    ProcessingState,
    TaskCard,
    TaskListResponse,
    TaskOrigin,
    TaskStatus,
    TaskType,
)

router = APIRouter(prefix="/v1/tasks", tags=["tasks"])


@router.get("", response_model=TaskListResponse)
def list_tasks(
    owner: Owner = Depends(require_owner),
    session: Session = Depends(get_session),
) -> TaskListResponse:
    """Return task cards visible to the authenticated owner.

    Args:
        owner: Authenticated owner resolved from bearer credentials.
        session: Database session used to load tasks.

    Returns:
        Owner-scoped task cards ordered by most recently updated first.
    """

    tasks = session.scalars(
        select(Task).where(Task.owner_id == owner.id).order_by(Task.updated_at.desc())
    ).all()

    return TaskListResponse(
        tasks=[
            TaskCard(
                id=UUID(task.id),
                origin=TaskOrigin(task.origin),
                source_key=task.source_key,
                source_url=task.source_url,
                type=TaskType(task.type),
                title=task.title,
                status=TaskStatus(task.status),
                status_reason=task.status_reason,
                summary=task.summary,
                processing_state=ProcessingState(task.processing_state),
                processing_error_code=task.processing_error_code,
                observed_at=task.observed_at,
                updated_at=task.updated_at,
            )
            for task in tasks
        ]
    )
