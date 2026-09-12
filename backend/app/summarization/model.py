"""Model-call abstraction for task summarization."""

from dataclasses import dataclass
from typing import Protocol

from backend.app.detection.schemas import DetectionTaskResult
from backend.app.summarization.schemas import SummaryOutput, validate_summary_output


class SummaryModelCallError(RuntimeError):
    """Raised when a summary model call fails or returns unusable output."""


@dataclass(frozen=True, slots=True)
class SummaryContext:
    """Data sent to a summary model.

    Attributes:
        title: Task title.
        status_reason: Reason for the detected task status.
        evidence: Grounded evidence from detection.
        observation_text: Captured page text for additional grounding.
    """

    title: str
    status_reason: str
    evidence: str
    observation_text: str


class SummaryModelClient(Protocol):
    """Protocol implemented by summary model clients."""

    def summarize(self, context: SummaryContext) -> SummaryOutput:
        """Summarize a detected task.

        Args:
            context: Grounded task and observation context.

        Returns:
            Validated summary output.

        Raises:
            SummaryModelCallError: Raised for transient provider failures.
        """


class HeuristicSummaryClient:
    """Deterministic placeholder summary client for local development."""

    def summarize(self, context: SummaryContext) -> SummaryOutput:
        """Create a bounded summary from validated detection context.

        Args:
            context: Grounded task and observation context.

        Returns:
            Validated summary output.
        """

        summary = f"{context.title}: {context.status_reason}"
        return validate_summary_output({"summary": summary[:300]})


def summary_context_from_detection(
    detection: DetectionTaskResult,
    observation_text: str,
) -> SummaryContext:
    """Build summary context from a task detection result.

    Args:
        detection: Validated task detection result.
        observation_text: Captured observation text.

    Returns:
        Summary context for the model client.
    """

    return SummaryContext(
        title=detection.title,
        status_reason=detection.status_reason,
        evidence=detection.evidence,
        observation_text=observation_text,
    )
