"""Tests for backend foundation routes and anonymous identity."""

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from backend.app.auth.anonymous import hash_installation_credential
from backend.app.db.models import Owner, Task
from backend.app.db.session import Database
from backend.app.main import create_app


@dataclass(frozen=True)
class AppHarness:
    """Test harness for API requests and direct database setup.

    Attributes:
        client: FastAPI test client.
        database: Database handle bound to the app under test.
    """

    client: TestClient
    database: Database


@pytest.fixture
def app_harness(tmp_path: Path) -> Iterator[AppHarness]:
    """Create an isolated API app for a test.

    Args:
        tmp_path: Pytest-provided temporary directory.

    Yields:
        A test harness containing the API client and database handle.
    """

    database = Database(f"sqlite+pysqlite:///{tmp_path / 'test.db'}")
    app = create_app(database)

    with TestClient(app) as client:
        yield AppHarness(client=client, database=database)


def _json_body(response_json: Any) -> dict[str, Any]:
    """Cast response JSON to a dictionary for strict mypy tests.

    Args:
        response_json: Parsed JSON response body.

    Returns:
        Response JSON as a dictionary.
    """

    return cast(dict[str, Any], response_json)


def _fixture(name: str) -> dict[str, Any]:
    """Load a JSON fixture by filename.

    Args:
        name: Fixture filename under tests/fixtures.

    Returns:
        Parsed fixture object.
    """

    fixture_path = Path(__file__).parent / "fixtures" / name
    return cast(dict[str, Any], json.loads(fixture_path.read_text()))


def _create_installation(client: TestClient) -> tuple[str, str]:
    """Create an anonymous installation through the API.

    Args:
        client: API test client.

    Returns:
        The owner ID and bearer credential.
    """

    response = client.post("/v1/installations")
    body = _json_body(response.json())

    assert response.status_code == 201
    assert isinstance(body["owner_id"], str)
    assert isinstance(body["installation_credential"], str)
    return body["owner_id"], body["installation_credential"]


def test_create_installation_returns_bearer_credential(
    app_harness: AppHarness,
) -> None:
    """Verify anonymous installation creation returns the public contract."""

    response = app_harness.client.post("/v1/installations")
    body = _json_body(response.json())
    example = _fixture("installation_response.example.json")

    assert response.status_code == 201
    assert set(body) == set(example)
    assert body["token_type"] == "bearer"
    assert isinstance(body["owner_id"], str)
    assert isinstance(body["installation_credential"], str)
    assert body["installation_credential"] != example["installation_credential"]


def test_list_tasks_requires_installation_credential(
    app_harness: AppHarness,
) -> None:
    """Verify task listing rejects requests without bearer credentials."""

    response = app_harness.client.get("/v1/tasks")
    body = _json_body(response.json())

    assert response.status_code == 401
    assert body == {
        "error": {
            "code": "unauthorized",
            "message": "Missing anonymous installation credentials.",
            "retryable": False,
        }
    }


def test_list_tasks_returns_empty_owner_scoped_response(
    app_harness: AppHarness,
) -> None:
    """Verify a new installation sees an empty task list."""

    _, credential = _create_installation(app_harness.client)
    response = app_harness.client.get(
        "/v1/tasks",
        headers={"Authorization": f"Bearer {credential}"},
    )
    body = _json_body(response.json())

    assert response.status_code == 200
    assert body == _fixture("task_list_empty.example.json")


def test_list_tasks_is_scoped_to_authenticated_owner(
    app_harness: AppHarness,
) -> None:
    """Verify task listing excludes tasks owned by other installations."""

    visible_owner_id, visible_credential = _create_installation(app_harness.client)
    hidden_credential = "hidden-owner-credential"

    with app_harness.database.session_factory() as session:
        hidden_owner = Owner(
            installation_credential_hash=hash_installation_credential(hidden_credential)
        )
        session.add(hidden_owner)
        session.flush()
        session.add(
            Task(
                owner_id=hidden_owner.id,
                origin="manual",
                type="manual",
                title="Hidden manual task",
                status="in_progress",
                processing_state="ready",
            )
        )
        session.add(
            Task(
                owner_id=visible_owner_id,
                origin="manual",
                type="manual",
                title="Visible manual task",
                status="in_progress",
                processing_state="ready",
            )
        )
        session.commit()

    response = app_harness.client.get(
        "/v1/tasks",
        headers={"Authorization": f"Bearer {visible_credential}"},
    )
    body = _json_body(response.json())

    assert response.status_code == 200
    assert len(body["tasks"]) == 1
    task = cast(dict[str, Any], body["tasks"][0])
    assert task["title"] == "Visible manual task"
