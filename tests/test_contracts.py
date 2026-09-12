"""Tests for generated API contracts."""

import json
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
    """Verify the extension message contract lists implemented message types."""

    schema = _extension_message_schema()
    variants = cast(list[dict[str, Any]], schema["oneOf"])
    message_types = {
        cast(str, cast(dict[str, Any], variant["properties"])["type"]["const"])
        for variant in variants
    }

    assert message_types == {
        "ADD_MANUAL_TASK",
        "CLEAR_DATA",
        "DELETE_TASK",
        "GET_SCAN",
        "LIST_TASKS",
        "OPEN_TASK_SOURCE",
        "UPDATE_MANUAL_TASK",
    }
