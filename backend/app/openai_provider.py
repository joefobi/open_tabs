"""Minimal OpenAI Responses API JSON client."""

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

JsonObject = dict[str, Any]
OpenAITransport = Callable[[urllib.request.Request, float], bytes]


class OpenAIProviderError(RuntimeError):
    """Raised when the OpenAI provider cannot return usable JSON.

    Attributes:
        retryable: Whether retrying the request may succeed.
    """

    retryable: bool

    def __init__(self, message: str, *, retryable: bool) -> None:
        """Initialize the provider error.

        Args:
            message: Human-readable failure reason.
            retryable: Whether retrying the request may succeed.
        """

        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class OpenAIResponsesClient:
    """HTTP client for structured JSON calls to the OpenAI Responses API.

    Attributes:
        api_key: OpenAI API key.
        model: Model used for response generation.
        endpoint: Responses API endpoint URL.
        timeout_seconds: HTTP timeout in seconds.
        transport: Optional injectable HTTP transport for tests.
    """

    api_key: str
    model: str
    endpoint: str
    timeout_seconds: float
    transport: OpenAITransport | None = None

    def generate_json(
        self,
        *,
        schema_name: str,
        schema: Mapping[str, Any],
        system_prompt: str,
        user_prompt: str,
    ) -> JsonObject:
        """Generate a structured JSON object using the Responses API.

        Args:
            schema_name: Name for the structured output schema.
            schema: JSON schema the response must match.
            system_prompt: System instructions for the model.
            user_prompt: User content for the model.

        Returns:
            Parsed JSON object produced by the model.

        Raises:
            OpenAIProviderError: Raised when the provider call fails or returns
                unusable JSON.
        """

        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": dict(schema),
                    "strict": True,
                }
            },
        }
        response = self._post_json(payload)
        output_text = _extract_output_text(response)
        return _parse_json_object(output_text)

    def _post_json(self, payload: Mapping[str, Any]) -> JsonObject:
        """Post JSON to the OpenAI endpoint and parse the JSON response.

        Args:
            payload: Request payload to send.

        Returns:
            Parsed provider response body.

        Raises:
            OpenAIProviderError: Raised when the request fails or returns invalid
                JSON.
        """

        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            raw = self._send(request)
        except urllib.error.HTTPError as exc:
            raise OpenAIProviderError(
                f"OpenAI request failed with status {exc.code}.",
                retryable=exc.code == 429 or exc.code >= 500,
            ) from exc
        except urllib.error.URLError as exc:
            raise OpenAIProviderError(
                "OpenAI request failed before a response was received.",
                retryable=True,
            ) from exc

        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OpenAIProviderError(
                "OpenAI returned invalid JSON.",
                retryable=True,
            ) from exc

        if not isinstance(parsed, dict):
            raise OpenAIProviderError(
                "OpenAI returned a non-object response.",
                retryable=True,
            )
        return cast(JsonObject, parsed)

    def _send(self, request: urllib.request.Request) -> bytes:
        """Send one HTTP request using the configured transport.

        Args:
            request: Prepared HTTP request.

        Returns:
            Raw response bytes.
        """

        if self.transport is not None:
            return self.transport(request, self.timeout_seconds)
        return _default_transport(request, self.timeout_seconds)


def _default_transport(
    request: urllib.request.Request, timeout_seconds: float
) -> bytes:
    """Send a request with urllib.

    Args:
        request: Prepared HTTP request.
        timeout_seconds: Request timeout in seconds.

    Returns:
        Raw response bytes.
    """

    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return cast(bytes, response.read())


def _extract_output_text(response: Mapping[str, Any]) -> str:
    """Extract generated text from a Responses API response.

    Args:
        response: Parsed OpenAI response object.

    Returns:
        Text content generated by the model.

    Raises:
        OpenAIProviderError: Raised when no generated text can be found.
    """

    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text:
        return output_text

    output = response.get("output")
    if isinstance(output, Sequence):
        for item in output:
            text = _text_from_output_item(item)
            if text:
                return text

    raise OpenAIProviderError("OpenAI response did not contain text.", retryable=True)


def _text_from_output_item(item: object) -> str | None:
    """Extract text from one Responses API output item.

    Args:
        item: One item from the response output array.

    Returns:
        Text content when present, otherwise None.
    """

    if not isinstance(item, dict):
        return None
    content = item.get("content")
    if not isinstance(content, Sequence):
        return None
    for content_item in content:
        if not isinstance(content_item, dict):
            continue
        text = content_item.get("text")
        if isinstance(text, str) and text:
            return text
    return None


def _parse_json_object(text: str) -> JsonObject:
    """Parse a generated JSON object.

    Args:
        text: Generated response text.

    Returns:
        Parsed JSON object.

    Raises:
        OpenAIProviderError: Raised when the generated text is not a JSON object.
    """

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OpenAIProviderError(
            "OpenAI returned text that was not valid JSON.",
            retryable=True,
        ) from exc
    if not isinstance(parsed, dict):
        raise OpenAIProviderError(
            "OpenAI returned structured output that was not an object.",
            retryable=True,
        )
    return cast(JsonObject, parsed)
