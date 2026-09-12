"""Schemas for anonymous installation identity."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class InstallationResponse(BaseModel):
    """Response returned when issuing an anonymous installation credential.

    Attributes:
        owner_id: Owner identifier created for this installation.
        installation_credential: Bearer credential shown once to the extension.
        token_type: Credential type used in the Authorization header.
    """

    model_config = ConfigDict(extra="forbid")

    owner_id: UUID
    installation_credential: str
    token_type: Literal["bearer"] = "bearer"
