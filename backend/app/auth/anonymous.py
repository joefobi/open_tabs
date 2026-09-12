"""Anonymous installation credential helpers."""

from __future__ import annotations

from hashlib import sha256
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import Owner
from backend.app.dependencies import get_session


def generate_installation_credential() -> str:
    """Generate a bearer credential for an anonymous installation.

    Returns:
        A URL-safe bearer credential.
    """

    from secrets import token_urlsafe

    return token_urlsafe(32)


def hash_installation_credential(credential: str) -> str:
    """Hash an installation credential for server-side storage.

    Args:
        credential: Raw bearer credential.

    Returns:
        Hex-encoded SHA-256 digest.
    """

    return sha256(credential.encode("utf-8")).hexdigest()


def parse_bearer_token(authorization: str | None) -> str:
    """Extract a bearer token from an Authorization header.

    Args:
        authorization: Raw Authorization header value.

    Returns:
        The bearer token.

    Raises:
        HTTPException: Raised when the header is missing or malformed.
    """

    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing anonymous installation credentials.",
        )

    scheme, separator, token = authorization.partition(" ")
    if separator == "" or scheme.lower() != "bearer" or token.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid anonymous installation credentials.",
        )

    return token.strip()


def require_owner(
    authorization: Annotated[str | None, Header()] = None,
    session: Session = Depends(get_session),
) -> Owner:
    """Resolve the authenticated owner from a bearer credential.

    Args:
        authorization: Authorization header containing the bearer credential.
        session: Database session used to look up the owner.

    Returns:
        The owner associated with the credential.

    Raises:
        HTTPException: Raised when credentials are absent or do not match an owner.
    """

    token = parse_bearer_token(authorization)
    credential_hash = hash_installation_credential(token)
    owner = session.scalar(
        select(Owner).where(Owner.installation_credential_hash == credential_hash)
    )

    if owner is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid anonymous installation credentials.",
        )

    return owner
