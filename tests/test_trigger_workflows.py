"""Verify Trigger.dev detection and summary workflow behavior."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from backend.app.db.models import Observation, Owner, Scan, ScanItem, Source, Task
from backend.app.db.session import Database
from backend.app.detection.model import ModelCallError, ObservationContext
from backend.app.detection.schemas import (
    DetectionNoTaskResult,
    DetectionResult,
    DetectionTaskResult,
)
from backend.app.schemas.observations import ExtractionState
from backend.app.schemas.tasks import ProcessingState, TaskStatus, TaskType
from backend.app.summarization.model import SummaryContext, SummaryModelCallError
from backend.app.summarization.schemas import SummaryOutput
from backend.app.workflows import run_detection_job, run_summary_job


@dataclass(frozen=True)
class WorkflowRows:
    """Identifiers for rows created by workflow test setup.

    Attributes:
        owner_id: Owner identifier.
        source_id: Source identifier.
        observation_id: Observation identifier.
        scan_id: Scan identifier.
        scan_item_id: Scan item identifier.
    """

    owner_id: UUID
    source_id: UUID
    observation_id: UUID
    scan_id: UUID
    scan_item_id: UUID


class FailingDetectionClient:
    """Detection client that simulates a transient provider failure."""

    def detect(self, observation: ObservationContext) -> DetectionResult:
        """Raise a transient detection failure.

        Args:
            observation: Observation context that would be sent to the provider.

        Raises:
            ModelCallError: Always raised to simulate a retryable outage.
        """

        raise ModelCallError("provider timed out")


class NoTaskDetectionClient:
    """Detection client that returns an explicit no-task outcome."""

    def detect(self, observation: ObservationContext) -> DetectionResult:
        """Return a no-task result for workflow behavior tests.

        Args:
            observation: Observation context that would be sent to the provider.

        Returns:
            A validated no-task detection result.
        """

        return DetectionNoTaskResult(
            result_type="no_task",
            reason=f"No task is needed for {observation.title}.",
        )


class FailingSummaryClient:
    """Summary client that simulates a transient provider failure."""

    def summarize(self, context: SummaryContext) -> SummaryOutput:
        """Raise a transient summary failure.

        Args:
            context: Summary context that would be sent to the provider.

        Raises:
            SummaryModelCallError: Always raised to simulate a retryable outage.
        """

        raise SummaryModelCallError("provider timed out")


@dataclass(frozen=True, slots=True)
class StaleMutation:
    """Information needed to supersede an observation from another session.

    Attributes:
        database: Database handle used to open a separate session.
        rows: Original workflow row identifiers.
    """

    database: Database
    rows: WorkflowRows


class MutatingDetectionClient:
    """Detection client that advances the source while detection is running."""

    def __init__(self, mutation: StaleMutation) -> None:
        """Initialize the client with the stale mutation target.

        Args:
            mutation: Information needed to create a newer observation.
        """

        self._mutation = mutation

    def detect(self, observation: ObservationContext) -> DetectionResult:
        """Advance the source in a separate session and return stale output.

        Args:
            observation: Observation context being analyzed.

        Returns:
            A task result that must be ignored because it is stale.
        """

        _advance_source_revision(self._mutation.database, self._mutation.rows)
        return DetectionTaskResult(
            result_type="task",
            task_type=TaskType.GITHUB,
            title=observation.title,
            status=TaskStatus.IN_PROGRESS,
            status_reason="This stale output should not be committed.",
            evidence=observation.text,
        )


class MutatingSummaryClient:
    """Summary client that advances the source while summarization is running."""

    def __init__(self, mutation: StaleMutation) -> None:
        """Initialize the client with the stale mutation target.

        Args:
            mutation: Information needed to create a newer observation.
        """

        self._mutation = mutation

    def summarize(self, context: SummaryContext) -> SummaryOutput:
        """Advance the source in a separate session and return stale output.

        Args:
            context: Summary context being analyzed.

        Returns:
            A summary that must not be persisted.
        """

        _advance_source_revision(self._mutation.database, self._mutation.rows)
        return SummaryOutput(summary="This stale summary should not be committed.")


@pytest.fixture
def database(tmp_path: Path) -> Database:
    """Create an isolated workflow database.

    Args:
        tmp_path: Pytest-provided temporary directory.

    Returns:
        Database handle with schema created.
    """

    database = Database(f"sqlite+pysqlite:///{tmp_path / 'workflow.db'}")
    database.create_schema()
    return database


def _create_scan_item(
    session: Session,
    *,
    source_url: str = "https://github.com/example/project/pull/1",
    title: str = "Review pull request",
    text: str = "Pull request review is in progress and waiting on tests.",
    extraction_state: ExtractionState = ExtractionState.READY,
) -> WorkflowRows:
    """Create owner, source, observation, scan, and scan item rows.

    Args:
        session: Database session used to create rows.
        source_url: Observation source URL.
        title: Observation page title.
        text: Observation captured text.
        extraction_state: Observation extraction state.

    Returns:
        Identifiers for the created rows.
    """

    owner = Owner(installation_credential_hash="hash-for-workflow-test")
    session.add(owner)
    session.flush()

    source = Source(owner_id=owner.id, source_key=source_url, latest_revision=1)
    session.add(source)
    session.flush()

    observation = Observation(
        owner_id=owner.id,
        source_id=source.id,
        revision=1,
        client_observation_id="observation-1",
        source_url=source_url,
        title=title,
        text=text,
        extraction_state=extraction_state.value,
        truncated=False,
        content_hash="content-hash-1",
        captured_at=datetime.now(UTC),
    )
    session.add(observation)
    session.flush()
    source.latest_observation_id = observation.id

    scan = Scan(
        owner_id=owner.id,
        client_request_id="scan-1",
        state=ProcessingState.QUEUED.value,
        item_count=1,
        completed_count=0,
    )
    session.add(scan)
    session.flush()

    item = ScanItem(
        scan_id=scan.id,
        observation_id=observation.id,
        processing_state=ProcessingState.QUEUED.value,
    )
    session.add(item)
    session.commit()

    return WorkflowRows(
        owner_id=UUID(owner.id),
        source_id=UUID(source.id),
        observation_id=UUID(observation.id),
        scan_id=UUID(scan.id),
        scan_item_id=UUID(item.id),
    )


def _advance_source_revision(database: Database, rows: WorkflowRows) -> None:
    """Create a newer observation and mark the source as advanced.

    Args:
        database: Database handle used for a separate worker session.
        rows: Original workflow rows to supersede.
    """

    with database.session_factory() as session:
        source = session.get(Source, str(rows.source_id))
        assert source is not None
        newer_observation = Observation(
            owner_id=str(rows.owner_id),
            source_id=str(rows.source_id),
            revision=2,
            client_observation_id="observation-2",
            source_url="https://github.com/example/project/pull/1",
            title="Review pull request",
            text="Pull request review has newer page text.",
            extraction_state=ExtractionState.READY.value,
            truncated=False,
            content_hash="content-hash-2",
            captured_at=datetime.now(UTC),
        )
        session.add(newer_observation)
        session.flush()
        source.latest_observation_id = newer_observation.id
        source.latest_revision = 2
        session.commit()


def test_detection_and_summary_create_ready_task(database: Database) -> None:
    """Create a detected task and complete its summary."""

    with database.session_factory() as session:
        rows = _create_scan_item(session)

        detection = run_detection_job(session, rows.scan_item_id)
        assert detection.outcome == "task"
        assert detection.task_id is not None
        assert detection.processing_state == ProcessingState.QUEUED

        task = session.get(Task, str(detection.task_id))
        assert task is not None
        assert task.processing_state == ProcessingState.QUEUED.value
        assert task.detection_revision == 1

        summary = run_summary_job(
            session,
            detection.task_id,
            detection.observation_id,
        )
        assert summary.processing_state == ProcessingState.READY

        session.refresh(task)
        scan = session.get(Scan, str(rows.scan_id))
        item = session.get(ScanItem, str(rows.scan_item_id))
        assert scan is not None
        assert item is not None
        assert task.summary is not None
        assert task.summary_revision == 1
        assert task.processing_state == ProcessingState.READY.value
        assert item.processing_state == ProcessingState.READY.value
        assert scan.state == ProcessingState.READY.value
        assert scan.completed_count == 1


def test_heuristic_detection_creates_generic_page_card(database: Database) -> None:
    """Create a generic page card when a readable page has no task markers."""

    with database.session_factory() as session:
        rows = _create_scan_item(
            session,
            source_url="https://example.com/recipe",
            title="Sourdough notes",
            text="This article explains a neutral recipe with no supported task context.",
        )

        detection = run_detection_job(session, rows.scan_item_id)

        assert detection.outcome == "task"
        assert detection.task_id is not None
        task = session.get(Task, str(detection.task_id))
        assert task is not None
        assert task.type == TaskType.PAGE.value
        assert task.title == "Sourdough notes"


def test_detection_records_explicit_no_task_without_creating_card(
    database: Database,
) -> None:
    """Complete an explicit no-task scan item without creating a task card."""

    with database.session_factory() as session:
        rows = _create_scan_item(
            session,
            source_url="https://example.com/recipe",
            title="Sourdough notes",
            text="This article explains a neutral recipe with no supported task context.",
        )

        detection = run_detection_job(
            session,
            rows.scan_item_id,
            detection_client=NoTaskDetectionClient(),
        )

        assert detection.outcome == "no_task"
        assert detection.task_id is None
        assert session.query(Task).count() == 0
        item = session.get(ScanItem, str(rows.scan_item_id))
        assert item is not None
        assert item.processing_state == ProcessingState.READY.value
        assert item.detection_outcome == "no_task"


def test_detection_skips_stale_observation(database: Database) -> None:
    """Prevent older observations from creating tasks after source revision advances."""

    with database.session_factory() as session:
        rows = _create_scan_item(session)
        source = session.get(Source, str(rows.source_id))
        assert source is not None

        newer_observation = Observation(
            owner_id=str(rows.owner_id),
            source_id=str(rows.source_id),
            revision=2,
            client_observation_id="observation-2",
            source_url="https://github.com/example/project/pull/1",
            title="Review pull request",
            text="Pull request review has newer page text.",
            extraction_state=ExtractionState.READY.value,
            truncated=False,
            content_hash="content-hash-2",
            captured_at=datetime.now(UTC),
        )
        session.add(newer_observation)
        session.flush()
        source.latest_observation_id = newer_observation.id
        source.latest_revision = 2
        session.commit()

        detection = run_detection_job(session, rows.scan_item_id)

        assert detection.outcome == "superseded"
        assert detection.task_id is None
        assert session.query(Task).count() == 0
        item = session.get(ScanItem, str(rows.scan_item_id))
        assert item is not None
        assert item.processing_state == ProcessingState.READY.value
        assert item.detection_outcome == "superseded"


def test_detection_refreshes_revision_state_before_committing(
    database: Database,
) -> None:
    """Skip stale detection output when another worker advances the source."""

    with database.session_factory() as session:
        rows = _create_scan_item(session)

        detection = run_detection_job(
            session,
            rows.scan_item_id,
            detection_client=MutatingDetectionClient(
                StaleMutation(database=database, rows=rows)
            ),
        )

        assert detection.outcome == "superseded"
        assert detection.task_id is None
        assert session.query(Task).count() == 0


def test_summary_refreshes_revision_state_before_committing(
    database: Database,
) -> None:
    """Skip stale summary output when another worker advances the source."""

    with database.session_factory() as session:
        rows = _create_scan_item(session)
        detection = run_detection_job(session, rows.scan_item_id)
        assert detection.task_id is not None

        summary = run_summary_job(
            session,
            detection.task_id,
            detection.observation_id,
            summary_client=MutatingSummaryClient(
                StaleMutation(database=database, rows=rows)
            ),
        )

        assert summary.processing_state == ProcessingState.READY
        task = session.get(Task, str(detection.task_id))
        item = session.get(ScanItem, str(rows.scan_item_id))
        assert task is not None
        assert item is not None
        assert task.summary is None
        assert task.summary_revision is None
        assert item.detection_outcome == "superseded"


def test_transient_detection_failure_reaches_trigger_retry(
    database: Database,
) -> None:
    """Raise retryable detection failures instead of returning success."""

    with database.session_factory() as session:
        rows = _create_scan_item(session)

        with pytest.raises(ModelCallError):
            run_detection_job(
                session,
                rows.scan_item_id,
                detection_client=FailingDetectionClient(),
            )

        item = session.get(ScanItem, str(rows.scan_item_id))
        assert item is not None
        assert item.processing_state == ProcessingState.RUNNING.value
        assert item.error_code is None


def test_transient_summary_failure_reaches_trigger_retry(database: Database) -> None:
    """Raise retryable summary failures instead of returning success."""

    with database.session_factory() as session:
        rows = _create_scan_item(session)
        detection = run_detection_job(session, rows.scan_item_id)
        assert detection.task_id is not None

        with pytest.raises(SummaryModelCallError):
            run_summary_job(
                session,
                detection.task_id,
                detection.observation_id,
                summary_client=FailingSummaryClient(),
            )

        task = session.get(Task, str(detection.task_id))
        item = session.get(ScanItem, str(rows.scan_item_id))
        assert task is not None
        assert item is not None
        assert task.processing_state == ProcessingState.RUNNING.value
        assert task.processing_error_code is None
        assert item.processing_state == ProcessingState.RUNNING.value
        assert item.error_code is None
