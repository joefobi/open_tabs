"""Tests for generated API contracts."""

import json
import re
from pathlib import Path
from typing import Any, cast

from backend.app.main import create_app


def _contract_schema() -> dict[str, Any]:
    """Load the committed OpenAPI contract.

    Returns:
        The committed OpenAPI contract as a dictionary.
    """

    contract_path = Path("contracts/openapi.json")
    return cast(dict[str, Any], json.loads(contract_path.read_text()))


def _extension_message_schema() -> dict[str, Any]:
    """Load the committed extension message schema.

    Returns:
        The committed extension message contract as a dictionary.
    """

    contract_path = Path("contracts/extension-messages.schema.json")
    return cast(dict[str, Any], json.loads(contract_path.read_text()))


def _extension_schema_message_types() -> set[str]:
    """Return message types declared by the extension message JSON schema.

    Returns:
        Message type constants from the JSON schema variants.
    """

    schema = _extension_message_schema()
    variants = cast(list[dict[str, Any]], schema["oneOf"])
    return {
        cast(str, cast(dict[str, Any], variant["properties"])["type"]["const"])
        for variant in variants
    }


def _typescript_extension_message_types() -> set[str]:
    """Return message types declared by the TypeScript union.

    Returns:
        Message type constants from the ExtensionMessage union.
    """

    source = Path("apps/extension/src/background/types.ts").read_text()
    union = source.split("export type ExtensionMessage =", maxsplit=1)[1]
    return set(re.findall(r'\|\s*\{\s*type: "([^"]+)"', union))


def _service_worker_message_cases() -> set[str]:
    """Return message types handled by the service worker dispatcher.

    Returns:
        Message type constants from switch cases in the dispatcher.
    """

    source = Path("apps/extension/src/background/service-worker.ts").read_text()
    return set(re.findall(r'case "([^"]+)":', source))


def test_openapi_contract_is_fresh() -> None:
    """Verify the committed OpenAPI contract matches the application schema."""

    assert _contract_schema() == create_app().openapi()


def test_openapi_contract_contains_foundation_endpoints() -> None:
    """Verify the OpenAPI contract includes foundation routes."""

    paths = cast(dict[str, Any], _contract_schema()["paths"])

    assert "/v1/data" in paths
    assert "/healthz" in paths
    assert "/v1/installations" in paths
    assert "/v1/tasks" in paths
    assert "/v1/tasks/{task_id}" in paths


def test_extension_message_contract_matches_implemented_messages() -> None:
    """Verify extension message schema, types, and dispatcher stay aligned."""

    message_types = _extension_schema_message_types()

    assert "SCAN_NOW" not in message_types
    assert message_types == _typescript_extension_message_types()
    assert message_types == _service_worker_message_cases()


def test_extension_observation_flushes_are_single_flight() -> None:
    """Verify automatic observation flush scheduling cannot overlap submissions."""

    source = Path("apps/extension/src/background/service-worker.ts").read_text()

    assert "let observationFlushInFlight = false;" in source
    assert "let observationFlushRequested = false;" in source
    assert "void drainObservationFlush();" in source
    assert "void flushChangedObservations();" not in source
    assert ".then(() => orchestrator.retryPending())" not in source


def test_extension_submits_only_changed_observations() -> None:
    """Verify extension submissions skip pages already submitted successfully."""

    orchestrator = Path("apps/extension/src/background/scanOrchestrator.ts").read_text()
    observation_state = Path(
        "apps/extension/src/background/observationState.ts",
    ).read_text()

    assert "filterChanged(pages)" in orchestrator
    assert "no_changed_observations" in orchestrator
    assert "markSubmittedPages(changedPages)" in orchestrator
    assert "palenque.submittedObservations" in observation_state
    assert "sourceKeyForUrl" in observation_state
