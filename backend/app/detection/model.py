"""Model-call abstraction for task detection."""

from dataclasses import dataclass
from typing import Protocol

from backend.app.detection.schemas import (
    DetectionInsufficientEvidenceResult,
    DetectionNoTaskResult,
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

        if observation.extraction_state != ExtractionState.READY:
            return DetectionInsufficientEvidenceResult(
                result_type="insufficient_evidence",
                reason="The page text was not available for analysis.",
            )

        if len(observation.text.strip()) < 20:
            return DetectionInsufficientEvidenceResult(
                result_type="insufficient_evidence",
                reason="The captured page text is too short to identify a task.",
            )

        if "github.com" in normalized and any(
            marker in normalized for marker in ("pull request", "review", "issue")
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

        if any(
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

        return DetectionNoTaskResult(
            result_type="no_task",
            reason="The page content does not match a supported task category.",
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
