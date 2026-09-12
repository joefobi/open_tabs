"""Schemas for scan request and response contracts."""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.observations import ObservationInput


class ScanState(StrEnum):
    """Allowed scan processing states."""

    QUEUED = "queued"
    RUNNING = "running"
    READY = "ready"
    FAILED = "failed"


class ScanCreateRequest(BaseModel):
    """Request body used to submit a batch scan.

    Attributes:
        client_request_id: Extension-generated idempotency identifier.
        observations: Observations included in the scan.
    """

    model_config = ConfigDict(extra="forbid")

    client_request_id: str = Field(min_length=1, max_length=128)
    observations: list[ObservationInput] = Field(min_length=1, max_length=20)


class ScanCreateResponse(BaseModel):
    """Response returned after accepting a scan.

    Attributes:
        scan_id: Backend scan identifier.
        state: Initial processing state.
    """

    model_config = ConfigDict(extra="forbid")

    scan_id: UUID
    state: ScanState
