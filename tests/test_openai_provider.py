"""Tests for OpenAI-backed model clients."""

import json
import urllib.request
from typing import Any, cast

import pytest

from backend.app.config import Settings
from backend.app.detection.model import (
    ModelCallError,
    ObservationContext,
    OpenAIDetectionClient,
)
from backend.app.openai_provider import OpenAIResponsesClient
from backend.app.schemas.observations import ExtractionState
from backend.app.schemas.tasks import TaskStatus, TaskType
from backend.app.summarization.model import (
    OpenAISummaryClient,
    SummaryContext,
    SummaryModelCallError,
)
from backend.app.workflows import _default_detection_client, _default_summary_client


def test_openai_responses_client_posts_structured_output_request() -> None:
    """Verify the OpenAI client posts a structured-output Responses request."""

    captured: dict[str, Any] = {}

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        """Capture the request and return a provider response.

        Args:
            request: Prepared OpenAI HTTP request.
            timeout: Request timeout in seconds.

        Returns:
            Encoded fake OpenAI response body.
        """

        captured["timeout"] = timeout
        captured["url"] = request.full_url
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(cast(bytes, request.data or b"{}"))
        return json.dumps({"output_text": '{"summary": "Ready for review."}'}).encode()

    client = OpenAIResponsesClient(
        api_key="test-key",
        model="gpt-test",
        endpoint="https://api.openai.test/v1/responses",
        timeout_seconds=4.0,
        transport=transport,
    )

    result = client.generate_json(
        schema_name="summary",
        schema={"type": "object", "properties": {"summary": {"type": "string"}}},
        system_prompt="Summarize.",
        user_prompt="Evidence.",
    )

    assert result == {"summary": "Ready for review."}
    assert captured["timeout"] == 4.0
    assert captured["url"] == "https://api.openai.test/v1/responses"
    assert captured["authorization"] == "Bearer test-key"
    assert captured["body"]["model"] == "gpt-test"
    assert captured["body"]["text"]["format"]["type"] == "json_schema"
    assert captured["body"]["text"]["format"]["strict"] is True


def test_openai_detection_client_validates_task_output() -> None:
    """Verify OpenAI detection output maps into the app detection schema."""

    def transport(_: urllib.request.Request, __: float) -> bytes:
        """Return a fake detection response.

        Args:
            _: Ignored request.
            __: Ignored timeout.

        Returns:
            Encoded fake OpenAI response body.
        """

        output = {
            "result_type": "task",
            "task_type": "github",
            "title": "Review pull request",
            "status": "needs_attention",
            "status_reason": "The PR has requested changes.",
            "evidence": "Requested changes are visible in the page text.",
            "reason": None,
        }
        return json.dumps({"output_text": json.dumps(output)}).encode()

    client = OpenAIDetectionClient(
        OpenAIResponsesClient(
            api_key="test-key",
            model="gpt-test",
            endpoint="https://api.openai.test/v1/responses",
            timeout_seconds=4.0,
            transport=transport,
        )
    )

    result = client.detect(
        ObservationContext(
            source_url="https://github.com/example/project/pull/1",
            title="Review pull request",
            text="Requested changes are visible in the page text.",
            extraction_state=ExtractionState.READY,
            truncated=False,
        )
    )

    assert result.result_type == "task"
    assert result.task_type == TaskType.GITHUB
    assert result.status == TaskStatus.NEEDS_ATTENTION


def test_openai_summary_client_validates_summary_output() -> None:
    """Verify OpenAI summary output maps into the app summary schema."""

    def transport(_: urllib.request.Request, __: float) -> bytes:
        """Return a fake summary response.

        Args:
            _: Ignored request.
            __: Ignored timeout.

        Returns:
            Encoded fake OpenAI response body.
        """

        return json.dumps(
            {"output": [{"content": [{"text": '{"summary": "Review requested."}'}]}]}
        ).encode()

    client = OpenAISummaryClient(
        OpenAIResponsesClient(
            api_key="test-key",
            model="gpt-test",
            endpoint="https://api.openai.test/v1/responses",
            timeout_seconds=4.0,
            transport=transport,
        )
    )

    result = client.summarize(
        SummaryContext(
            title="Review pull request",
            status_reason="The PR has requested changes.",
            evidence="Requested changes are visible in the page text.",
            observation_text="Requested changes are visible in the page text.",
        )
    )

    assert result.summary == "Review requested."


def test_openai_provider_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify OpenAI provider selection requires an API key."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = Settings(model_provider="openai", openai_api_key=None)

    with pytest.raises(ModelCallError):
        _default_detection_client(settings)

    with pytest.raises(SummaryModelCallError):
        _default_summary_client(settings)
