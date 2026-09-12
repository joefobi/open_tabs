"""Routes for owner-scoped scan ingestion and polling."""

import hashlib
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.auth.anonymous import require_owner
from backend.app.db.models import Image, Observation, Owner, Scan, ScanItem, Source
from backend.app.db.url_identity import normalize_source_url
from backend.app.dependencies import get_session
from backend.app.schemas.observations import ObservationInput
from backend.app.schemas.scans import (
    ScanCounts,
    ScanCreateRequest,
    ScanCreateResponse,
    ScanItemResponse,
    ScanItemState,
    ScanResponse,
    ScanState,
)

router = APIRouter(prefix="/v1/scans", tags=["scans"])


@router.post(
    "",
    response_model=ScanCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_scan(
    request: ScanCreateRequest,
    owner: Owner = Depends(require_owner),
    session: Session = Depends(get_session),
) -> ScanCreateResponse:
    """Accept an idempotent batch of page observations.

    Args:
        request: Scan request from the extension service worker.
        owner: Authenticated owner resolved from bearer credentials.
        session: Database session used to persist scan state.

    Returns:
        Accepted scan identifier and aggregate state.

    Raises:
        HTTPException: Raised when an observation or screenshot reference is invalid.
    """

    for attempt in range(2):
        try:
            return _create_scan_once(request, owner, session)
        except IntegrityError as exc:
            session.rollback()
            existing = _scan_by_client_request_id(session, owner, request)
            if existing is not None:
                return ScanCreateResponse(
                    scan_id=UUID(existing.id), state=ScanState(existing.state)
                )
            if attempt == 0:
                continue
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scan conflicts with existing owner-scoped idempotency data.",
            ) from exc

    raise RuntimeError("Scan retry loop exited unexpectedly.")


@router.get("/{scan_id}", response_model=ScanResponse)
def get_scan(
    scan_id: UUID,
    owner: Owner = Depends(require_owner),
    session: Session = Depends(get_session),
) -> ScanResponse:
    """Return scan status and item outcomes for the authenticated owner.

    Args:
        scan_id: Scan identifier from the URL.
        owner: Authenticated owner resolved from bearer credentials.
        session: Database session used to load scan state.

    Returns:
        Owner-scoped scan status and per-item outcomes.

    Raises:
        HTTPException: Raised when the scan is absent for this owner.
    """

    scan = session.scalar(
        select(Scan).where(Scan.id == str(scan_id), Scan.owner_id == owner.id)
    )
    if scan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found."
        )

    return _scan_response(session, scan)


def _create_scan_once(
    request: ScanCreateRequest,
    owner: Owner,
    session: Session,
) -> ScanCreateResponse:
    """Create or replay a scan within one transaction attempt.

    Args:
        request: Scan request from the extension service worker.
        owner: Authenticated owner resolved from bearer credentials.
        session: Database session used to persist scan state.

    Returns:
        Accepted scan identifier and aggregate state.

    Raises:
        IntegrityError: Raised when a concurrent unique constraint race is lost.
        HTTPException: Raised when the request conflicts with existing observations.
    """

    existing = _scan_by_client_request_id(session, owner, request)
    if existing is not None:
        return ScanCreateResponse(
            scan_id=UUID(existing.id), state=ScanState(existing.state)
        )

    scan = Scan(
        owner_id=owner.id,
        client_request_id=request.client_request_id,
        state=ScanState.QUEUED.value,
    )
    session.add(scan)
    session.flush()

    for observation in request.observations:
        _ingest_observation(session, owner, scan, observation)

    _refresh_scan_counts(session, scan)
    session.commit()
    session.refresh(scan)
    return ScanCreateResponse(scan_id=UUID(scan.id), state=ScanState(scan.state))


def _scan_by_client_request_id(
    session: Session,
    owner: Owner,
    request: ScanCreateRequest,
) -> Scan | None:
    """Return an existing owner-scoped scan with the client request ID.

    Args:
        session: Database session used to load the scan.
        owner: Authenticated owner that owns the scan.
        request: Request carrying the client idempotency key.

    Returns:
        Existing scan row or None.
    """

    return session.scalar(
        select(Scan).where(
            Scan.owner_id == owner.id,
            Scan.client_request_id == request.client_request_id,
        )
    )


def _ingest_observation(
    session: Session,
    owner: Owner,
    scan: Scan,
    observation_input: ObservationInput,
) -> None:
    """Persist one observation or attach an unchanged/superseded scan item.

    Args:
        session: Database session used for persistence.
        owner: Authenticated owner that owns the data.
        scan: Scan row receiving the item.
        observation_input: Validated observation payload.

    Raises:
        HTTPException: Raised for invalid source URLs or other-owner screenshots.
    """

    source_url = str(observation_input.source_url)
    try:
        source_key = normalize_source_url(source_url)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    _validate_screenshot_ownership(session, owner, observation_input)

    source = _get_or_create_source(session, owner, source_key)
    content_hash = _content_hash(observation_input, source_key)
    existing_observation = _observation_by_client_id(session, owner, observation_input)
    if existing_observation is not None:
        _add_existing_observation_item(
            session, scan, source_key, content_hash, existing_observation
        )
        return

    latest_observation = _latest_observation(session, source)

    if (
        source.observed_at is not None
        and latest_observation is not None
        and _as_utc_aware(observation_input.observed_at)
        < _as_utc_aware(source.observed_at)
    ):
        session.add(
            ScanItem(
                scan_id=scan.id,
                observation_id=latest_observation.id,
                processing_state=ScanItemState.SUPERSEDED.value,
                detection_outcome=ScanItemState.SUPERSEDED.value,
            )
        )
        return

    if (
        latest_observation is not None
        and latest_observation.content_hash == content_hash
    ):
        session.add(
            ScanItem(
                scan_id=scan.id,
                observation_id=latest_observation.id,
                processing_state=ScanItemState.UNCHANGED.value,
                detection_outcome=ScanItemState.UNCHANGED.value,
            )
        )
        return

    observation = Observation(
        owner_id=owner.id,
        source_id=source.id,
        revision=source.latest_revision + 1,
        client_observation_id=observation_input.client_observation_id,
        source_url=source_url,
        title=observation_input.title,
        text=observation_input.text,
        extraction_state=observation_input.extraction_state.value,
        truncated=observation_input.truncated,
        content_hash=content_hash,
        screenshot_id=observation_input.screenshot_id,
        captured_at=observation_input.observed_at,
    )
    session.add(observation)
    session.flush()

    source.latest_observation_id = observation.id
    source.latest_revision = observation.revision
    source.observed_at = observation_input.observed_at
    session.add(
        ScanItem(
            scan_id=scan.id,
            observation_id=observation.id,
            processing_state=ScanItemState.QUEUED.value,
        )
    )


def _get_or_create_source(session: Session, owner: Owner, source_key: str) -> Source:
    """Return an owner-scoped source, creating it when absent.

    Args:
        session: Database session used to load or create the source.
        owner: Authenticated owner that owns the source.
        source_key: Normalized owner-scoped source URL key.

    Returns:
        Existing or newly created source row.
    """

    source = session.scalar(
        select(Source).where(
            Source.owner_id == owner.id, Source.source_key == source_key
        )
    )
    if source is not None:
        return source

    source = Source(owner_id=owner.id, source_key=source_key)
    session.add(source)
    session.flush()
    return source


def _latest_observation(session: Session, source: Source) -> Observation | None:
    """Return the source's latest accepted observation, if any.

    Args:
        session: Database session used to load the observation.
        source: Source whose latest observation should be loaded.

    Returns:
        The latest observation row or None.
    """

    if source.latest_observation_id is None:
        return None
    return session.get(Observation, source.latest_observation_id)


def _observation_by_client_id(
    session: Session,
    owner: Owner,
    observation_input: ObservationInput,
) -> Observation | None:
    """Return an existing owner-scoped observation with the client ID.

    Args:
        session: Database session used to load the observation.
        owner: Authenticated owner that owns the observation.
        observation_input: Observation payload with the client observation ID.

    Returns:
        Existing observation row or None.
    """

    return session.scalar(
        select(Observation).where(
            Observation.owner_id == owner.id,
            Observation.client_observation_id
            == observation_input.client_observation_id,
        )
    )


def _add_existing_observation_item(
    session: Session,
    scan: Scan,
    source_key: str,
    content_hash: str,
    observation: Observation,
) -> None:
    """Attach a scan item to an already accepted observation.

    Args:
        session: Database session used to load the observation source.
        scan: Scan row receiving the item.
        source_key: Source key derived from the current observation payload.
        content_hash: Content hash derived from the current observation payload.
        observation: Previously accepted observation with the same client ID.

    Raises:
        HTTPException: Raised when the reused client observation ID conflicts.
    """

    existing_source = session.get(Source, observation.source_id)
    if (
        existing_source is None
        or existing_source.source_key != source_key
        or observation.content_hash != content_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="client_observation_id conflicts with an existing observation.",
        )

    session.add(
        ScanItem(
            scan_id=scan.id,
            observation_id=observation.id,
            processing_state=ScanItemState.UNCHANGED.value,
            detection_outcome=ScanItemState.UNCHANGED.value,
        )
    )


def _validate_screenshot_ownership(
    session: Session,
    owner: Owner,
    observation_input: ObservationInput,
) -> None:
    """Validate an optional screenshot belongs to the authenticated owner.

    Args:
        session: Database session used to look up images.
        owner: Authenticated owner that must own the image.
        observation_input: Observation payload containing an optional screenshot ID.

    Raises:
        HTTPException: Raised when the screenshot is absent or owned by another owner.
    """

    if observation_input.screenshot_id is None:
        return

    image = session.scalar(
        select(Image).where(
            Image.id == observation_input.screenshot_id,
            Image.owner_id == owner.id,
        )
    )
    if image is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Screenshot does not exist for this owner.",
        )


def _refresh_scan_counts(session: Session, scan: Scan) -> None:
    """Refresh denormalized scan counts and aggregate state.

    Args:
        session: Database session used to load scan items.
        scan: Scan whose loaded items should be counted.
    """

    rows = session.scalars(select(ScanItem).where(ScanItem.scan_id == scan.id)).all()
    states = [ScanItemState(item.processing_state) for item in rows]
    terminal_states = {
        ScanItemState.READY,
        ScanItemState.FAILED,
        ScanItemState.UNCHANGED,
        ScanItemState.SUPERSEDED,
    }
    scan.item_count = len(states)
    scan.completed_count = sum(1 for state in states if state in terminal_states)

    if ScanItemState.FAILED in states:
        scan.state = ScanState.FAILED.value
    elif ScanItemState.QUEUED in states or ScanItemState.RUNNING in states:
        scan.state = ScanState.QUEUED.value
    else:
        scan.state = ScanState.READY.value


def _scan_response(session: Session, scan: Scan) -> ScanResponse:
    """Convert a scan row into the polling response.

    Args:
        session: Database session used to load source keys.
        scan: Scan row to serialize.

    Returns:
        Scan polling response.
    """

    items = [_scan_item_response(session, item) for item in scan.items]
    return ScanResponse(
        scan_id=UUID(scan.id),
        client_request_id=scan.client_request_id,
        state=ScanState(scan.state),
        counts=_scan_counts(items),
        items=items,
        error_code=scan.error_code,
        created_at=scan.created_at,
        updated_at=scan.updated_at,
    )


def _scan_item_response(session: Session, item: ScanItem) -> ScanItemResponse:
    """Convert a scan item row into an API response.

    Args:
        session: Database session used to resolve the observation source key.
        item: Scan item row to serialize.

    Returns:
        Scan item response.
    """

    observation = session.get(Observation, item.observation_id)
    if observation is None:
        raise RuntimeError("Scan item observation is missing.")
    source = session.get(Source, observation.source_id)
    if source is None:
        raise RuntimeError("Scan item source is missing.")

    return ScanItemResponse(
        observation_id=UUID(item.observation_id),
        task_id=UUID(item.task_id) if item.task_id is not None else None,
        source_key=source.source_key,
        processing_state=ScanItemState(item.processing_state),
        detection_outcome=item.detection_outcome,
        error_code=item.error_code,
    )


def _scan_counts(items: list[ScanItemResponse]) -> ScanCounts:
    """Count scan items by ingestion outcome.

    Args:
        items: Serialized scan item responses.

    Returns:
        Aggregated scan counts.
    """

    accepted_states = {
        ScanItemState.QUEUED,
        ScanItemState.RUNNING,
        ScanItemState.READY,
    }
    return ScanCounts(
        total=len(items),
        accepted=sum(1 for item in items if item.processing_state in accepted_states),
        unchanged=sum(
            1 for item in items if item.processing_state is ScanItemState.UNCHANGED
        ),
        superseded=sum(
            1 for item in items if item.processing_state is ScanItemState.SUPERSEDED
        ),
        failed=sum(
            1 for item in items if item.processing_state is ScanItemState.FAILED
        ),
    )


def _content_hash(observation_input: ObservationInput, source_key: str) -> str:
    """Hash meaningful submitted content for source revision checks.

    Args:
        observation_input: Observation payload to hash.
        source_key: Normalized source key used for owner-scoped grouping.

    Returns:
        Hex-encoded SHA-256 digest.
    """

    normalized_text = " ".join(observation_input.text.split())
    payload = "\n".join(
        [
            source_key,
            observation_input.title.strip(),
            normalized_text,
            observation_input.extraction_state.value,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _as_utc_aware(value: datetime) -> datetime:
    """Normalize a datetime to timezone-aware UTC.

    Args:
        value: Datetime returned by Pydantic or SQLAlchemy.

    Returns:
        Timezone-aware UTC datetime.
    """

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
