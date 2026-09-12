"""Authenticate anonymous installation credentials."""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.db.repository import TaskRepository, get_repository

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class AuthenticatedOwner:
    """Represent the owner authenticated for a request.

    Attributes:
        owner_id: The server-generated owner identifier.
        installation_id: The installation identifier bound to the owner.
    """

    owner_id: str
    installation_id: str


async def require_owner(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    repository: TaskRepository = Depends(get_repository),
) -> AuthenticatedOwner:
    """Resolve the request bearer token to an owner boundary.

    Args:
        credentials: The bearer credentials parsed from the request.
        repository: The task repository used to resolve installation credentials.

    Returns:
        The authenticated owner for the request.

    Raises:
        HTTPException: Raised with 401 when the credential is missing or invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing anonymous installation credential.",
        )

    owner = repository.get_owner_by_token(credentials.credentials)
    if owner is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid anonymous installation credential.",
        )

    return AuthenticatedOwner(
        owner_id=owner.owner_id,
        installation_id=owner.installation_id,
    )
