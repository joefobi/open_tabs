"""Schemas for scan request and response contracts."""

from datetime import datetime
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


class ScanItemState(StrEnum):
    """Allowed per-observation scan item states."""

    QUEUED = "queued"
    RUNNING = "running"
    READY = "ready"
    FAILED = "failed"
    UNCHANGED = "unchanged"
    SUPERSEDED = "superseded"


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


class ScanCounts(BaseModel):
    """Aggregated item counts for a submitted scan.

    Attributes:
        total: Number of scan items in the scan.
        accepted: Items accepted for detection or already ready.
        unchanged: Items matching the latest accepted source content.
        superseded: Items older than the latest accepted source observation.
        failed: Items that failed before terminal processing.
    """

    model_config = ConfigDict(extra="forbid")

    total: int
    accepted: int
    unchanged: int
    superseded: int
    failed: int


class ScanItemResponse(BaseModel):
    """Per-observation scan item returned while polling.

    Attributes:
        observation_id: Observation associated with the item.
        task_id: Task produced by detection, when available.
        source_key: Owner-scoped normalized URL key.
        processing_state: Item processing state.
        detection_outcome: Detection outcome discriminator, when available.
        error_code: Stable item-level error code, when available.
    """

    model_config = ConfigDict(extra="forbid")

    observation_id: UUID
    task_id: UUID | None
    source_key: str
    processing_state: ScanItemState
    detection_outcome: str | None
    error_code: str | None


class ScanResponse(BaseModel):
    """Poll response for a submitted scan.

    Attributes:
        scan_id: Backend scan identifier.
        client_request_id: Extension-generated idempotency identifier.
        state: Scan processing state.
        counts: Aggregated item counts.
        items: Per-observation item state.
        error_code: Optional scan-level error code.
        created_at: Timestamp when the scan was created.
        updated_at: Timestamp when the scan last changed.
    """

    model_config = ConfigDict(extra="forbid")

    scan_id: UUID
    client_request_id: str
    state: ScanState
    counts: ScanCounts
    items: list[ScanItemResponse]
    error_code: str | None
    created_at: datetime
    updated_at: datetime


class ScanSubmitResult(BaseModel):
    """Internal helper result for accepted scan submissions.

    Attributes:
        scan_id: Backend scan identifier.
        state: Scan processing state.
        was_created: Whether this request inserted a new scan.
    """

    model_config = ConfigDict(extra="forbid")

    scan_id: UUID
    state: ScanState
    was_created: bool
