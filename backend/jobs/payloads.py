"""Shared payload schemas for background job entry points."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DetectionJobPayload(BaseModel):
    """Payload accepted by the detection job.

    Attributes:
        scan_item_id: Scan item to process.
        database_url: Optional database URL override for worker environments.
    """

    model_config = ConfigDict(extra="forbid")

    scan_item_id: UUID
    database_url: str | None = None


class SummaryJobPayload(BaseModel):
    """Payload accepted by the summary job.

    Attributes:
        task_id: Task to summarize.
        observation_id: Observation used for summary grounding.
        database_url: Optional database URL override for worker environments.
    """

    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    observation_id: UUID
    database_url: str | None = None
