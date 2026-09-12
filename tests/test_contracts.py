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
