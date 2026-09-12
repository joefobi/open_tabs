"""SQLAlchemy models for owner-scoped task persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _make_uuid() -> str:
    """Return a new UUID string for portable primary keys.

    Returns:
        A random UUID encoded as a string.
    """

    return str(uuid4())


def _utc_now() -> datetime:
    """Return the current UTC timestamp.

    Returns:
        A timezone-aware UTC datetime.
    """

    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy declarative models."""


class Owner(Base):
    """Anonymous installation owner boundary.

    Attributes:
        id: Stable owner identifier.
        installation_credential_hash: SHA-256 hash of the bearer credential.
        created_at: Timestamp when the owner was created.
        sources: Sources owned by this installation.
        tasks: Tasks owned by this installation.
        scans: Scans owned by this installation.
        images: Images owned by this installation.
    """

    __tablename__ = "owners"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_make_uuid)
    installation_credential_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )

    sources: Mapped[list[Source]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    tasks: Mapped[list[Task]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    scans: Mapped[list[Scan]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    images: Mapped[list[Image]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class Source(Base):
    """Owner-scoped normalized page source.

    Attributes:
        id: Stable source identifier.
        owner_id: Owner that can access this source.
        source_key: Owner-scoped normalized URL key.
        latest_observation_id: Latest accepted observation identifier.
        latest_revision: Latest accepted source revision.
        observed_at: Timestamp when the source was last observed.
        owner: Owning installation.
        observations: Observations captured for this source.
    """

    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("owner_id", "source_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_make_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owners.id"), nullable=False)
    source_key: Mapped[str] = mapped_column(String(2048), nullable=False)
    latest_observation_id: Mapped[str | None] = mapped_column(String(36))
    latest_revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    owner: Mapped[Owner] = relationship(back_populates="sources")
    observations: Mapped[list[Observation]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class Observation(Base):
    """Captured page text submitted by the extension.

    Attributes:
        id: Stable observation identifier.
        owner_id: Owner that can access this observation.
        source_id: Source this observation belongs to.
        revision: Monotonic source revision assigned when accepted.
        client_observation_id: Extension-generated idempotency identifier.
        source_url: Captured source URL.
        title: Captured page title.
        text: Bounded rendered page text.
        extraction_state: Collection outcome from the extension.
        truncated: Whether text was truncated before submission.
        content_hash: Backend-derived hash of source content.
        screenshot_id: Optional screenshot image identifier.
        captured_at: Timestamp when the extension captured the page.
        created_at: Timestamp when the backend accepted the observation.
        source: Source this observation belongs to.
    """

    __tablename__ = "observations"
    __table_args__ = (UniqueConstraint("owner_id", "client_observation_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_make_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owners.id"), nullable=False)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    client_observation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    extraction_state: Mapped[str] = mapped_column(String(64), nullable=False)
    truncated: Mapped[bool] = mapped_column(default=False, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    screenshot_id: Mapped[str | None] = mapped_column(ForeignKey("images.id"))
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )

    source: Mapped[Source] = relationship(back_populates="observations")


class Task(Base):
    """Detected or manually added task card.

    Attributes:
        id: Stable task identifier.
        owner_id: Owner that can access this task.
        origin: Whether the task is detected or manual.
        source_key: Nullable source key for detected tasks.
        source_url: Nullable source URL for return-to-tab behavior.
        type: Supported task type.
        title: User-visible task title.
        status: User-visible task status.
        status_reason: Optional status explanation.
        summary: Optional short grounded summary.
        processing_state: Background processing state.
        processing_error_code: Optional processing error code.
        detection_revision: Source revision used for detection.
        summary_revision: Source revision used for summarization.
        observed_at: Latest source observation time.
        updated_at: Timestamp when the task last changed.
        created_at: Timestamp when the task was created.
        client_request_id: Owner-scoped idempotency key for manual tasks.
        owner: Owning installation.
    """

    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("owner_id", "source_key"),
        UniqueConstraint("owner_id", "client_request_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_make_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owners.id"), nullable=False)
    origin: Mapped[str] = mapped_column(String(32), nullable=False)
    source_key: Mapped[str | None] = mapped_column(String(2048))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    status_reason: Mapped[str | None] = mapped_column(String(512))
    summary: Mapped[str | None] = mapped_column(String(512))
    processing_state: Mapped[str] = mapped_column(String(32), nullable=False)
    processing_error_code: Mapped[str | None] = mapped_column(String(64))
    detection_revision: Mapped[int | None] = mapped_column(Integer)
    summary_revision: Mapped[int | None] = mapped_column(Integer)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )
    client_request_id: Mapped[str | None] = mapped_column(String(128))

    owner: Mapped[Owner] = relationship(back_populates="tasks")


class Scan(Base):
    """Batch scan request submitted by the extension.

    Attributes:
        id: Stable scan identifier.
        owner_id: Owner that can access this scan.
        client_request_id: Extension-generated idempotency identifier.
        state: Scan processing state.
        item_count: Number of accepted scan items.
        completed_count: Number of terminal scan items.
        error_code: Optional scan-level error code.
        created_at: Timestamp when the scan was created.
        updated_at: Timestamp when the scan last changed.
        owner: Owning installation.
        items: Scan items included in this request.
    """

    __tablename__ = "scans"
    __table_args__ = (UniqueConstraint("owner_id", "client_request_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_make_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owners.id"), nullable=False)
    client_request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False
    )

    owner: Mapped[Owner] = relationship(back_populates="scans")
    items: Mapped[list[ScanItem]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )


class ScanItem(Base):
    """Per-observation scan processing state.

    Attributes:
        id: Stable scan item identifier.
        scan_id: Scan that owns this item.
        observation_id: Observation being processed.
        task_id: Optional task produced by detection.
        processing_state: Item processing state.
        detection_outcome: Optional detection outcome discriminator.
        error_code: Optional item-level error code.
        created_at: Timestamp when the scan item was created.
        updated_at: Timestamp when the scan item last changed.
        scan: Scan this item belongs to.
    """

    __tablename__ = "scan_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_make_uuid)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id"), nullable=False)
    observation_id: Mapped[str] = mapped_column(
        ForeignKey("observations.id"), nullable=False
    )
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"))
    processing_state: Mapped[str] = mapped_column(String(32), nullable=False)
    detection_outcome: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False
    )

    scan: Mapped[Scan] = relationship(back_populates="items")


class Image(Base):
    """Private screenshot fallback image metadata.

    Attributes:
        id: Stable image identifier.
        owner_id: Owner that can access this image.
        storage_key: Private object storage key.
        content_type: Validated image MIME type.
        size_bytes: Image size in bytes.
        expires_at: Timestamp when raw image data should expire.
        created_at: Timestamp when the image record was created.
        owner: Owning installation.
    """

    __tablename__ = "images"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_make_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owners.id"), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )

    owner: Mapped[Owner] = relationship(back_populates="images")
