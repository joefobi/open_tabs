"""Workflow operations for detection and summarization jobs."""

from dataclasses import dataclass
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.config import Settings, get_settings
from backend.app.db.models import Observation, Scan, ScanItem, Source, Task
from backend.app.detection.model import (
    DetectionModelClient,
    HeuristicDetectionClient,
    ModelCallError,
    ObservationContext,
    OpenAIDetectionClient,
)
from backend.app.detection.schemas import DetectionTaskResult
from backend.app.openai_provider import OpenAIResponsesClient
from backend.app.schemas.observations import ExtractionState
from backend.app.schemas.tasks import ProcessingState, TaskOrigin
from backend.app.summarization.model import (
    HeuristicSummaryClient,
    OpenAISummaryClient,
    SummaryContext,
    SummaryModelCallError,
    SummaryModelClient,
)

TERMINAL_STATES = {ProcessingState.READY.value, ProcessingState.FAILED.value}


@dataclass(frozen=True, slots=True)
class DetectionJobResult:
    """Result returned after a detection job step.

    Attributes:
        scan_item_id: Processed scan item identifier.
        outcome: Detection outcome discriminator.
        task_id: Task identifier when a task was detected.
        observation_id: Observation identifier used for detection.
        processing_state: Scan item processing state after detection.
        error_code: Optional machine-readable error code.
    """

    scan_item_id: UUID
    outcome: str
    task_id: UUID | None
    observation_id: UUID
    processing_state: ProcessingState
    error_code: str | None


@dataclass(frozen=True, slots=True)
class SummaryJobResult:
    """Result returned after a summary job step.

    Attributes:
        task_id: Task identifier requested for summarization.
        observation_id: Observation identifier used for summary grounding.
        processing_state: Task processing state after summarization.
        error_code: Optional machine-readable error code.
    """

    task_id: UUID
    observation_id: UUID
    processing_state: ProcessingState
    error_code: str | None


def run_detection_job(
    session: Session,
    scan_item_id: UUID,
    *,
    detection_client: DetectionModelClient | None = None,
) -> DetectionJobResult:
    """Run detection for a scan item and queue summary work when needed.

    Args:
        session: Database session for workflow persistence.
        scan_item_id: Scan item to process.
        detection_client: Optional detection model client override.

    Returns:
        Detection job result for Trigger.dev output.

    Raises:
        ValueError: Raised when the scan item or observation cannot be found.
    """

    client = detection_client or _default_detection_client(get_settings())
    item = _require_scan_item(session, scan_item_id)
    observation = _require_observation(session, UUID(item.observation_id))
    source = _require_source(session, UUID(observation.source_id))
    scan = _require_scan(session, UUID(item.scan_id))

    item.processing_state = ProcessingState.RUNNING.value
    scan.state = ProcessingState.RUNNING.value
    session.commit()

    if _is_stale_fresh(session, source, observation):
        return _complete_detection(
            session,
            item,
            scan,
            outcome="superseded",
            task=None,
            observation=observation,
        )

    try:
        detection = client.detect(_observation_context(observation))
    except ModelCallError:
        session.rollback()
        raise
    except ValidationError:
        item.processing_state = ProcessingState.FAILED.value
        item.error_code = "detection_failed"
        _refresh_scan(session, scan)
        session.commit()
        return DetectionJobResult(
            scan_item_id=scan_item_id,
            outcome="failed",
            task_id=None,
            observation_id=UUID(observation.id),
            processing_state=ProcessingState.FAILED,
            error_code="detection_failed",
        )

    if _is_stale_fresh(session, source, observation):
        return _complete_detection(
            session,
            item,
            scan,
            outcome="superseded",
            task=None,
            observation=observation,
        )

    if not isinstance(detection, DetectionTaskResult):
        return _complete_detection(
            session,
            item,
            scan,
            outcome=detection.result_type,
            task=None,
            observation=observation,
        )

    if _is_stale_fresh(session, source, observation):
        return _complete_detection(
            session,
            item,
            scan,
            outcome="superseded",
            task=None,
            observation=observation,
        )

    task = _upsert_detected_task(session, observation, source, detection)
    item.task_id = task.id
    item.detection_outcome = detection.result_type
    item.processing_state = ProcessingState.QUEUED.value
    item.error_code = None
    _refresh_scan(session, scan)
    session.commit()
    session.refresh(task)

    return DetectionJobResult(
        scan_item_id=scan_item_id,
        outcome=detection.result_type,
        task_id=UUID(task.id),
        observation_id=UUID(observation.id),
        processing_state=ProcessingState.QUEUED,
        error_code=None,
    )


def run_summary_job(
    session: Session,
    task_id: UUID,
    observation_id: UUID,
    *,
    summary_client: SummaryModelClient | None = None,
) -> SummaryJobResult:
    """Run summarization for a detected task using stale revision guards.

    Args:
        session: Database session for workflow persistence.
        task_id: Task to summarize.
        observation_id: Observation used as summary grounding.
        summary_client: Optional summary model client override.

    Returns:
        Summary job result for Trigger.dev output.

    Raises:
        ValueError: Raised when required task or observation rows are missing.
    """

    client = summary_client or _default_summary_client(get_settings())
    task = _require_task(session, task_id)
    observation = _require_observation(session, observation_id)
    source = _require_source(session, UUID(observation.source_id))
    item = _scan_item_for_summary(session, task_id, observation_id)
    scan = _require_scan(session, UUID(item.scan_id)) if item is not None else None

    session.refresh(task)
    session.refresh(source)
    if (
        _is_stale(source, observation)
        or task.detection_revision != observation.revision
    ):
        if item is not None:
            item.processing_state = ProcessingState.READY.value
            item.detection_outcome = "superseded"
            item.error_code = None
        if scan is not None:
            _refresh_scan(session, scan)
        session.commit()
        return SummaryJobResult(
            task_id=task_id,
            observation_id=observation_id,
            processing_state=ProcessingState.READY,
            error_code=None,
        )

    previous_task_state = task.processing_state
    previous_task_error_code = task.processing_error_code
    task.processing_state = ProcessingState.RUNNING.value
    if item is not None:
        item.processing_state = ProcessingState.RUNNING.value
    if scan is not None:
        scan.state = ProcessingState.RUNNING.value
    session.commit()

    try:
        summary = client.summarize(_summary_context(task, observation))
    except SummaryModelCallError:
        session.rollback()
        raise
    except ValidationError:
        task.processing_state = ProcessingState.FAILED.value
        task.processing_error_code = "summary_failed"
        if item is not None:
            item.processing_state = ProcessingState.FAILED.value
            item.error_code = "summary_failed"
        if scan is not None:
            _refresh_scan(session, scan)
        session.commit()
        return SummaryJobResult(
            task_id=task_id,
            observation_id=observation_id,
            processing_state=ProcessingState.FAILED,
            error_code="summary_failed",
        )

    session.refresh(task)
    session.refresh(source)
    if (
        _is_stale(source, observation)
        or task.detection_revision != observation.revision
    ):
        if task.detection_revision == observation.revision:
            task.processing_state = previous_task_state
            task.processing_error_code = previous_task_error_code
        if item is not None:
            item.processing_state = ProcessingState.READY.value
            item.detection_outcome = "superseded"
            item.error_code = None
        if scan is not None:
            _refresh_scan(session, scan)
        session.commit()
        return SummaryJobResult(
            task_id=task_id,
            observation_id=observation_id,
            processing_state=ProcessingState.READY,
            error_code=None,
        )

    task.summary = summary.summary
    task.summary_revision = observation.revision
    task.processing_state = ProcessingState.READY.value
    task.processing_error_code = None
    if item is not None:
        item.processing_state = ProcessingState.READY.value
        item.detection_outcome = "task"
        item.error_code = None
    if scan is not None:
        _refresh_scan(session, scan)
    session.commit()

    return SummaryJobResult(
        task_id=task_id,
        observation_id=observation_id,
        processing_state=ProcessingState.READY,
        error_code=None,
    )


def _complete_detection(
    session: Session,
    item: ScanItem,
    scan: Scan,
    *,
    outcome: str,
    task: Task | None,
    observation: Observation,
) -> DetectionJobResult:
    """Mark a detection-only terminal outcome.

    Args:
        session: Database session for workflow persistence.
        item: Scan item being completed.
        scan: Scan that owns the item.
        outcome: Detection outcome discriminator.
        task: Optional task associated with the item.
        observation: Observation processed by detection.

    Returns:
        Detection job result.
    """

    item.processing_state = ProcessingState.READY.value
    item.detection_outcome = outcome
    item.error_code = None
    item.task_id = task.id if task is not None else None
    _refresh_scan(session, scan)
    session.commit()
    return DetectionJobResult(
        scan_item_id=UUID(item.id),
        outcome=outcome,
        task_id=UUID(task.id) if task is not None else None,
        observation_id=UUID(observation.id),
        processing_state=ProcessingState.READY,
        error_code=None,
    )


def _default_detection_client(settings: Settings) -> DetectionModelClient:
    """Return the configured detection client.

    Args:
        settings: Runtime settings used to choose the provider.

    Returns:
        OpenAI-backed or heuristic detection client.
    """

    if settings.model_provider == "openai":
        api_key = _openai_api_key(settings)
        if api_key is None:
            raise ModelCallError(
                "OPEN_TABS_MODEL_PROVIDER=openai requires OPENAI_API_KEY "
                "or OPEN_TABS_OPENAI_API_KEY.",
            )
        return OpenAIDetectionClient(_openai_responses_client(settings, api_key))
    return HeuristicDetectionClient()


def _default_summary_client(settings: Settings) -> SummaryModelClient:
    """Return the configured summary client.

    Args:
        settings: Runtime settings used to choose the provider.

    Returns:
        OpenAI-backed or heuristic summary client.
    """

    if settings.model_provider == "openai":
        api_key = _openai_api_key(settings)
        if api_key is None:
            raise SummaryModelCallError(
                "OPEN_TABS_MODEL_PROVIDER=openai requires OPENAI_API_KEY "
                "or OPEN_TABS_OPENAI_API_KEY.",
            )
        return OpenAISummaryClient(_openai_responses_client(settings, api_key))
    return HeuristicSummaryClient()


def _openai_api_key(settings: Settings) -> str | None:
    """Return the configured OpenAI API key.

    Args:
        settings: Runtime settings containing provider configuration.

    Returns:
        The resolved API key, or None when no key is configured.
    """

    return settings.resolved_openai_api_key()


def _openai_responses_client(
    settings: Settings,
    api_key: str,
) -> OpenAIResponsesClient:
    """Build an OpenAI Responses API client from settings.

    Args:
        settings: Runtime settings containing provider configuration.
        api_key: OpenAI API key.

    Returns:
        OpenAI Responses API client.
    """

    return OpenAIResponsesClient(
        api_key=api_key,
        model=settings.openai_model,
        endpoint=settings.openai_responses_url,
        timeout_seconds=settings.openai_timeout_seconds,
    )


def _upsert_detected_task(
    session: Session,
    observation: Observation,
    source: Source,
    detection: DetectionTaskResult,
) -> Task:
    """Create or update a detected task for an owner-scoped source.

    Args:
        session: Database session for workflow persistence.
        observation: Observation that produced the detection.
        source: Source associated with the observation.
        detection: Validated task detection result.

    Returns:
        Created or updated task row.
    """

    task = session.scalar(
        select(Task).where(
            Task.owner_id == observation.owner_id,
            Task.source_key == source.source_key,
        )
    )
    if task is None:
        task = Task(
            owner_id=observation.owner_id,
            origin=TaskOrigin.DETECTED.value,
            source_key=source.source_key,
            source_url=observation.source_url,
            type=detection.task_type.value,
            title=detection.title,
            status=detection.status.value,
            status_reason=detection.status_reason,
            summary=None,
            processing_state=ProcessingState.QUEUED.value,
            processing_error_code=None,
            detection_revision=observation.revision,
            observed_at=observation.captured_at,
        )
        session.add(task)
        session.flush()
        return task

    task.source_url = observation.source_url
    task.type = detection.task_type.value
    task.title = detection.title
    task.status = detection.status.value
    task.status_reason = detection.status_reason
    task.processing_state = ProcessingState.QUEUED.value
    task.processing_error_code = None
    task.detection_revision = observation.revision
    task.observed_at = observation.captured_at
    return task


def _refresh_scan(session: Session, scan: Scan) -> None:
    """Refresh scan counts and aggregate state from its scan items.

    Args:
        session: Database session for workflow persistence.
        scan: Scan to refresh.
    """

    session.flush()
    completed_count = session.scalar(
        select(func.count()).where(
            ScanItem.scan_id == scan.id,
            ScanItem.processing_state.in_(TERMINAL_STATES),
        )
    )
    failed_count = session.scalar(
        select(func.count()).where(
            ScanItem.scan_id == scan.id,
            ScanItem.processing_state == ProcessingState.FAILED.value,
        )
    )
    scan.completed_count = int(completed_count or 0)
    if failed_count:
        scan.state = ProcessingState.FAILED.value
    elif scan.completed_count >= scan.item_count:
        scan.state = ProcessingState.READY.value
    else:
        scan.state = ProcessingState.RUNNING.value


def _is_stale(source: Source, observation: Observation) -> bool:
    """Return whether an observation is no longer the source's latest revision.

    Args:
        source: Source that owns the observation.
        observation: Observation being processed.

    Returns:
        True when a newer observation superseded this one.
    """

    return (
        source.latest_observation_id != observation.id
        or source.latest_revision != observation.revision
    )


def _is_stale_fresh(
    session: Session,
    source: Source,
    observation: Observation,
) -> bool:
    """Return whether an observation is stale after refreshing source state.

    Args:
        session: Database session that may contain stale ORM rows.
        source: Source that owns the observation.
        observation: Observation being processed.

    Returns:
        True when a newer observation superseded this one.
    """

    try:
        session.refresh(source)
    except SQLAlchemyError:
        return True
    return _is_stale(source, observation)


def _observation_context(observation: Observation) -> ObservationContext:
    """Build model context from an observation row.

    Args:
        observation: Observation row to convert.

    Returns:
        Detection model context.
    """

    return ObservationContext(
        source_url=observation.source_url,
        title=observation.title,
        text=observation.text,
        extraction_state=ExtractionState(observation.extraction_state),
        truncated=observation.truncated,
    )


def _summary_context(task: Task, observation: Observation) -> SummaryContext:
    """Build model context from task and observation rows.

    Args:
        task: Task row being summarized.
        observation: Observation row used for grounding.

    Returns:
        Summary model context.
    """

    return SummaryContext(
        title=task.title,
        status_reason=task.status_reason or "The task is still being analyzed.",
        evidence=observation.text[:1000],
        observation_text=observation.text,
    )


def _scan_item_for_summary(
    session: Session,
    task_id: UUID,
    observation_id: UUID,
) -> ScanItem | None:
    """Find the scan item associated with a task and observation.

    Args:
        session: Database session to query.
        task_id: Task identifier.
        observation_id: Observation identifier.

    Returns:
        Matching scan item when one exists.
    """

    return session.scalar(
        select(ScanItem).where(
            ScanItem.task_id == str(task_id),
            ScanItem.observation_id == str(observation_id),
        )
    )


def _require_scan_item(session: Session, scan_item_id: UUID) -> ScanItem:
    """Load a scan item or raise a workflow error.

    Args:
        session: Database session to query.
        scan_item_id: Scan item identifier.

    Returns:
        Matching scan item.

    Raises:
        ValueError: Raised when the scan item does not exist.
    """

    item = session.get(ScanItem, str(scan_item_id))
    if item is None:
        raise ValueError(f"Scan item not found: {scan_item_id}")
    return item


def _require_scan(session: Session, scan_id: UUID) -> Scan:
    """Load a scan or raise a workflow error.

    Args:
        session: Database session to query.
        scan_id: Scan identifier.

    Returns:
        Matching scan.

    Raises:
        ValueError: Raised when the scan does not exist.
    """

    scan = session.get(Scan, str(scan_id))
    if scan is None:
        raise ValueError(f"Scan not found: {scan_id}")
    return scan


def _require_observation(session: Session, observation_id: UUID) -> Observation:
    """Load an observation or raise a workflow error.

    Args:
        session: Database session to query.
        observation_id: Observation identifier.

    Returns:
        Matching observation.

    Raises:
        ValueError: Raised when the observation does not exist.
    """

    observation = session.get(Observation, str(observation_id))
    if observation is None:
        raise ValueError(f"Observation not found: {observation_id}")
    return observation


def _require_source(session: Session, source_id: UUID) -> Source:
    """Load a source or raise a workflow error.

    Args:
        session: Database session to query.
        source_id: Source identifier.

    Returns:
        Matching source.

    Raises:
        ValueError: Raised when the source does not exist.
    """

    source = session.get(Source, str(source_id))
    if source is None:
        raise ValueError(f"Source not found: {source_id}")
    return source


def _require_task(session: Session, task_id: UUID) -> Task:
    """Load a task or raise a workflow error.

    Args:
        session: Database session to query.
        task_id: Task identifier.

    Returns:
        Matching task.

    Raises:
        ValueError: Raised when the task does not exist.
    """

    task = session.get(Task, str(task_id))
    if task is None:
        raise ValueError(f"Task not found: {task_id}")
    return task
