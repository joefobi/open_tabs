"""Routes for anonymous installation onboarding."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.auth.anonymous import (
    generate_installation_credential,
    hash_installation_credential,
)
from backend.app.db.models import Owner
from backend.app.dependencies import get_session
from backend.app.schemas.identity import InstallationResponse

router = APIRouter(prefix="/v1/installations", tags=["installations"])


@router.post(
    "",
    response_model=InstallationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_installation(
    session: Session = Depends(get_session),
) -> InstallationResponse:
    """Issue an anonymous installation credential.

    Args:
        session: Database session used to persist the owner.

    Returns:
        The owner identifier and one-time bearer credential for the extension.
    """

    credential = generate_installation_credential()
    owner = Owner(installation_credential_hash=hash_installation_credential(credential))
    session.add(owner)
    session.commit()
    session.refresh(owner)

    return InstallationResponse(
        owner_id=UUID(owner.id),
        installation_credential=credential,
    )
