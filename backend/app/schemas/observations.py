"""Schemas for page observation submissions."""

from datetime import datetime
from enum import StrEnum

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


class ExtractionState(StrEnum):
    """Extension collection states for page text extraction."""

    READY = "ready"
    INACCESSIBLE = "inaccessible"
    UNLOADED = "unloaded"
    ERROR = "error"


class ObservationInput(BaseModel):
    """Observation submitted by the extension for scan ingestion.

    Attributes:
        client_observation_id: Extension-generated idempotency identifier.
        source_url: Captured page URL.
        title: Captured page title.
        observed_at: Timestamp when the extension observed the page.
        text: Bounded rendered page text.
        extraction_state: Collection outcome from the extension.
        truncated: Whether text was truncated before submission.
        screenshot_id: Optional backend image identifier for screenshot fallback.
    """

    model_config = ConfigDict(extra="forbid")

    client_observation_id: str = Field(min_length=1, max_length=128)
    source_url: AnyHttpUrl
    title: str = Field(max_length=512)
    observed_at: datetime
    text: str = Field(max_length=12_000)
    extraction_state: ExtractionState
    truncated: bool
    screenshot_id: str | None = Field(default=None, max_length=36)
