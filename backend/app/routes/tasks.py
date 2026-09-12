"""Expose owner-scoped task API routes."""

from fastapi import APIRouter, Depends, HTTPException, Response, status

from backend.app.auth.identity import AuthenticatedOwner, require_owner
from backend.app.db.models import TaskRecord
from backend.app.db.repository import TaskRepository, get_repository
from backend.app.schemas.tasks import (
    ClearDataResponse,
    ManualTaskCreateRequest,
    ManualTaskPatchRequest,
    TaskListResponse,
    TaskResponse,
)

router = APIRouter(prefix="/v1", tags=["tasks"])


def _task_response(task: TaskRecord) -> TaskResponse:
    """Convert a task persistence record into an API response.

    Args:
        task: The repository task record.

    Returns:
        The public task response.
    """
    return TaskResponse(
        id=task.task_id,
        origin=task.origin,
        source_key=task.source_key,
        source_url=task.source_url,
        type=task.task_type,
        title=task.title,
        status=task.status,
        status_reason=task.status_reason,
        summary=task.summary,
        processing_state=task.processing_state,
        processing_error_code=task.processing_error_code,
        observed_at=task.observed_at,
        updated_at=task.updated_at,
    )


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(
    owner: AuthenticatedOwner = Depends(require_owner),
    repository: TaskRepository = Depends(get_repository),
) -> TaskListResponse:
    """List task cards for the authenticated owner.

    Args:
        owner: The authenticated owner boundary.
        repository: The repository that stores task data.

    Returns:
        The owner's task cards.
    """
    return TaskListResponse(
        tasks=[_task_response(task) for task in repository.list_tasks(owner.owner_id)]
    )


@router.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_manual_task(
    request: ManualTaskCreateRequest,
    owner: AuthenticatedOwner = Depends(require_owner),
    repository: TaskRepository = Depends(get_repository),
) -> TaskResponse:
    """Create an idempotent manual task for the authenticated owner.

    Args:
        request: The manual task creation payload.
        owner: The authenticated owner boundary.
        repository: The repository that stores task data.

    Returns:
        The created or replayed manual task.
    """
    task = repository.create_manual_task(
        owner_id=owner.owner_id,
        client_request_id=request.client_request_id,
        title=request.title,
    )
    return _task_response(task)


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_manual_task(
    task_id: str,
    request: ManualTaskPatchRequest,
    owner: AuthenticatedOwner = Depends(require_owner),
    repository: TaskRepository = Depends(get_repository),
) -> TaskResponse:
    """Patch a manual task owned by the authenticated owner.

    Args:
        task_id: The task identifier from the URL.
        request: The mutable manual task fields to update.
        owner: The authenticated owner boundary.
        repository: The repository that stores task data.

    Returns:
        The updated task.

    Raises:
        HTTPException: Raised with 400 for empty patches or 404 for absent tasks.
    """
    if not request.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Patch must include at least one mutable field.",
        )

    task = repository.update_manual_task(
        owner_id=owner.owner_id,
        task_id=task_id,
        title=request.title,
        status=request.status,
        status_reason=request.status_reason,
        status_reason_provided="status_reason" in request.model_fields_set,
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found."
        )
    return _task_response(task)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: str,
    owner: AuthenticatedOwner = Depends(require_owner),
    repository: TaskRepository = Depends(get_repository),
) -> Response:
    """Delete one task owned by the authenticated owner.

    Args:
        task_id: The task identifier from the URL.
        owner: The authenticated owner boundary.
        repository: The repository that stores task data.

    Returns:
        An empty 204 response when the task is deleted.

    Raises:
        HTTPException: Raised with 404 when the task is absent for this owner.
    """
    if not repository.delete_task(owner_id=owner.owner_id, task_id=task_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found."
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/data", response_model=ClearDataResponse)
async def clear_data(
    owner: AuthenticatedOwner = Depends(require_owner),
    repository: TaskRepository = Depends(get_repository),
) -> ClearDataResponse:
    """Delete retained task data for the authenticated owner.

    Args:
        owner: The authenticated owner boundary.
        repository: The repository that stores task data.

    Returns:
        Counts for the deleted owner-scoped records.
    """
    return ClearDataResponse(deleted_tasks=repository.clear_owner_data(owner.owner_id))
