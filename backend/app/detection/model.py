"""Model-call abstraction for task detection."""

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

from backend.app.detection.schemas import (
    DetectionResult,
    DetectionTaskResult,
    validate_detection_result,
)
from backend.app.schemas.observations import ExtractionState
from backend.app.schemas.tasks import TaskStatus, TaskType


class ModelCallError(RuntimeError):
    """Raised when a model call fails transiently or returns unusable output."""


@dataclass(frozen=True, slots=True)
class ObservationContext:
    """Observation data sent to a detection model.

    Attributes:
        source_url: Captured source URL.
        title: Captured page title.
        text: Bounded rendered page text.
        extraction_state: Collection outcome from the extension.
        truncated: Whether text was truncated before submission.
    """

    source_url: str
    title: str
    text: str
    extraction_state: ExtractionState
    truncated: bool


class DetectionModelClient(Protocol):
    """Protocol implemented by detection model clients."""

    def detect(self, observation: ObservationContext) -> DetectionResult:
        """Detect a task from one observation.

        Args:
            observation: Observation data to analyze.

        Returns:
            Validated detection result.

        Raises:
            ModelCallError: Raised for transient provider failures.
        """


class HeuristicDetectionClient:
    """Deterministic placeholder detection client for local development."""

    def detect(self, observation: ObservationContext) -> DetectionResult:
        """Detect a likely task using conservative local heuristics.

        Args:
            observation: Observation data to analyze.

        Returns:
            Validated detection result.
        """

        normalized = f"{observation.source_url} {observation.title} {observation.text}"
        normalized = normalized.lower()

        if (
            observation.extraction_state == ExtractionState.READY
            and "github.com" in normalized
            and any(
                marker in normalized for marker in ("pull request", "review", "issue")
            )
        ):
            return validate_detection_result(
                {
                    "result_type": "task",
                    "task_type": TaskType.GITHUB.value,
                    "title": observation.title or "Review GitHub work",
                    "status": _status_for_text(normalized).value,
                    "status_reason": "The page appears to be GitHub work with review or issue context.",
                    "evidence": _evidence(observation.text),
                }
            )

        if observation.extraction_state == ExtractionState.READY and any(
            marker in normalized for marker in ("docs", "stackoverflow", "research")
        ):
            return validate_detection_result(
                {
                    "result_type": "task",
                    "task_type": TaskType.RESEARCH.value,
                    "title": observation.title or "Continue research",
                    "status": _status_for_text(normalized).value,
                    "status_reason": "The page appears to be research or documentation context.",
                    "evidence": _evidence(observation.text),
                }
            )

        return validate_detection_result(
            {
                "result_type": "task",
                "task_type": TaskType.PAGE.value,
                "title": _page_title(observation),
                "status": TaskStatus.IN_PROGRESS.value,
                "status_reason": _page_status_reason(observation),
                "evidence": _page_evidence(observation),
            }
        )


def _status_for_text(text: str) -> TaskStatus:
    """Infer a conservative task status from normalized page text.

    Args:
        text: Normalized page text.

    Returns:
        The inferred task status.
    """

    if any(marker in text for marker in ("error", "failed", "exception")):
        return TaskStatus.ERROR
    if any(
        marker in text for marker in ("blocked", "needs attention", "requested changes")
    ):
        return TaskStatus.NEEDS_ATTENTION
    if any(marker in text for marker in ("merged", "closed", "completed", "done")):
        return TaskStatus.ACTION_COMPLETE
    return TaskStatus.IN_PROGRESS


def _evidence(text: str) -> str:
    """Return bounded evidence text for local deterministic detection.

    Args:
        text: Captured page text.

    Returns:
        Bounded evidence string.
    """

    stripped = " ".join(text.split())
    if len(stripped) <= 240:
        return stripped
    return f"{stripped[:237]}..."


def _page_title(observation: ObservationContext) -> str:
    """Return a bounded display title for a generic scanned page.

    Args:
        observation: Observation to title.

    Returns:
        A non-empty task card title for the scanned page.
    """

    title = observation.title.strip() or _hostname(observation.source_url)
    if len(title) <= 200:
        return title
    return f"{title[:197]}..."


def _page_status_reason(observation: ObservationContext) -> str:
    """Describe generic scanned-page processing status.

    Args:
        observation: Observation being summarized.

    Returns:
        A short status reason for the sidebar card.
    """

    if observation.extraction_state != ExtractionState.READY:
        return "The page was scanned, but readable text was not available."
    if len(observation.text.strip()) < 20:
        return "The page was scanned with limited readable text."
    return "The page was scanned and added for review."


def _page_evidence(observation: ObservationContext) -> str:
    """Return bounded evidence for a generic scanned page.

    Args:
        observation: Observation being summarized.

    Returns:
        Evidence text or source URL for the sidebar card.
    """

    text = _evidence(observation.text)
    if text:
        return text
    return observation.source_url


def _hostname(source_url: str) -> str:
    """Return a hostname fallback for a source URL.

    Args:
        source_url: URL captured by the extension.

    Returns:
        Hostname when available, otherwise the original URL.
    """

    parsed = urlsplit(source_url)
    return parsed.netloc or source_url
