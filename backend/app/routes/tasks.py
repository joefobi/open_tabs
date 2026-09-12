"""Routes for owner-scoped task cards."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.anonymous import require_owner
from backend.app.db.models import Image, Owner, Scan, Source, Task
from backend.app.dependencies import get_session
from backend.app.schemas.tasks import (
    ClearDataResponse,
    ManualTaskCreateRequest,
    ManualTaskPatchRequest,
    ProcessingState,
    TaskCard,
    TaskListResponse,
    TaskOrigin,
    TaskStatus,
    TaskType,
)

router = APIRouter(prefix="/v1", tags=["tasks"])


def _task_card(task: Task) -> TaskCard:
    """Convert a database task row into a task card response.

    Args:
        task: Task row loaded from the database.

    Returns:
        Task card response for the extension sidebar.
    """

    return TaskCard(
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


@router.get("/tasks", response_model=TaskListResponse)
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

    return TaskListResponse(tasks=[_task_card(task) for task in tasks])


@router.post(
    "/tasks",
    response_model=TaskCard,
    status_code=status.HTTP_201_CREATED,
)
def create_manual_task(
    request: ManualTaskCreateRequest,
    owner: Owner = Depends(require_owner),
    session: Session = Depends(get_session),
) -> TaskCard:
    """Create an idempotent manual task for the authenticated owner.

    Args:
        request: Manual task payload with client idempotency key.
        owner: Authenticated owner resolved from bearer credentials.
        session: Database session used to create or load the task.

    Returns:
        Created or replayed manual task card.
    """

    existing = session.scalar(
        select(Task).where(
            Task.owner_id == owner.id,
            Task.client_request_id == request.client_request_id,
        )
    )
    if existing is not None:
        return _task_card(existing)

    task = Task(
        owner_id=owner.id,
        origin=TaskOrigin.MANUAL.value,
        type=TaskType.MANUAL.value,
        title=request.title,
        status=TaskStatus.IN_PROGRESS.value,
        summary=request.title,
        processing_state=ProcessingState.READY.value,
        client_request_id=request.client_request_id,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return _task_card(task)


@router.patch("/tasks/{task_id}", response_model=TaskCard)
def update_manual_task(
    task_id: UUID,
    request: ManualTaskPatchRequest,
    owner: Owner = Depends(require_owner),
    session: Session = Depends(get_session),
) -> TaskCard:
    """Patch a manual task owned by the authenticated owner.

    Args:
        task_id: Task identifier from the URL.
        request: Mutable manual task fields to update.
        owner: Authenticated owner resolved from bearer credentials.
        session: Database session used to update the task.

    Returns:
        Updated manual task card.

    Raises:
        HTTPException: Raised with 400 for empty patches or 404 for absent tasks.
    """

    if not request.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Patch must include at least one mutable field.",
        )

    task = session.scalar(
        select(Task).where(
            Task.id == str(task_id),
            Task.owner_id == owner.id,
            Task.origin == TaskOrigin.MANUAL.value,
        )
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found."
        )

    if request.title is not None:
        task.title = request.title
        task.summary = request.title
    if request.status is not None:
        task.status = request.status.value
    if "status_reason" in request.model_fields_set:
        task.status_reason = request.status_reason

    session.commit()
    session.refresh(task)
    return _task_card(task)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: UUID,
    owner: Owner = Depends(require_owner),
    session: Session = Depends(get_session),
) -> Response:
    """Delete one task owned by the authenticated owner.

    Args:
        task_id: Task identifier from the URL.
        owner: Authenticated owner resolved from bearer credentials.
        session: Database session used to delete the task.

    Returns:
        Empty 204 response when deletion succeeds.

    Raises:
        HTTPException: Raised with 404 when the task is absent for this owner.
    """

    task = session.scalar(
        select(Task).where(Task.id == str(task_id), Task.owner_id == owner.id)
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found."
        )

    session.delete(task)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/data", response_model=ClearDataResponse)
def clear_data(
    owner: Owner = Depends(require_owner),
    session: Session = Depends(get_session),
) -> ClearDataResponse:
    """Delete retained task, scan, source, observation, and image data.

    Args:
        owner: Authenticated owner resolved from bearer credentials.
        session: Database session used to delete owner-scoped records.

    Returns:
        Counts for deleted owner-scoped task records.
    """

    tasks = session.scalars(select(Task).where(Task.owner_id == owner.id)).all()
    scans = session.scalars(select(Scan).where(Scan.owner_id == owner.id)).all()
    sources = session.scalars(select(Source).where(Source.owner_id == owner.id)).all()
    images = session.scalars(select(Image).where(Image.owner_id == owner.id)).all()

    for scan in scans:
        session.delete(scan)
    for task in tasks:
        session.delete(task)
    for source in sources:
        session.delete(source)
    for image in images:
        session.delete(image)

    session.commit()
    return ClearDataResponse(deleted_tasks=len(tasks))
