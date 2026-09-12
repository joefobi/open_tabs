"""Expose anonymous installation onboarding routes."""

from fastapi import APIRouter, Depends, status

from backend.app.db.repository import TaskRepository, get_repository
from backend.app.schemas.installations import InstallationResponse

router = APIRouter(prefix="/v1/installations", tags=["installations"])


@router.post(
    "", response_model=InstallationResponse, status_code=status.HTTP_201_CREATED
)
async def create_installation(
    repository: TaskRepository = Depends(get_repository),
) -> InstallationResponse:
    """Create an anonymous installation credential.

    Args:
        repository: The repository that persists the owner boundary.

    Returns:
        The installation credential and owner identifier.
    """
    owner = repository.create_owner()
    return InstallationResponse(
        installation_id=owner.installation_id,
        installation_token=owner.installation_token,
        owner_id=owner.owner_id,
        created_at=owner.created_at,
    )
