"""Verify owner-scoped manual task API behavior."""

from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

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
def app_harness(tmp_path: Path) -> Generator[AppHarness, None, None]:
    """Create an isolated API app for a test.

    Args:
        tmp_path: Pytest-provided temporary directory.

    Yields:
        A test harness containing the API client and database handle.
    """

    database = Database(f"sqlite+pysqlite:///{tmp_path / 'manual_task_api.db'}")
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


def _install(client: TestClient) -> str:
    """Create an anonymous installation and return its credential.

    Args:
        client: The test HTTP client.

    Returns:
        The created installation bearer credential.
    """

    response = client.post("/v1/installations")
    body = _json_body(response.json())

    assert response.status_code == 201
    assert body["token_type"] == "bearer"
    credential = body["installation_credential"]
    assert isinstance(credential, str)
    return credential


def _headers(credential: str) -> dict[str, str]:
    """Build authorization headers for a credential.

    Args:
        credential: The bearer credential.

    Returns:
        HTTP headers containing the bearer credential.
    """

    return {"Authorization": f"Bearer {credential}"}


def _create_task(
    client: TestClient,
    credential: str,
    *,
    client_request_id: str,
    title: str,
) -> dict[str, Any]:
    """Create a manual task and return its response body.

    Args:
        client: The test HTTP client.
        credential: The owner bearer credential.
        client_request_id: The idempotency key for the request.
        title: The manual task title.

    Returns:
        The task response body.
    """

    response = client.post(
        "/v1/tasks",
        headers=_headers(credential),
        json={"client_request_id": client_request_id, "title": title},
    )
    assert response.status_code == 201
    return _json_body(response.json())


def test_manual_task_lifecycle_is_owner_scoped(app_harness: AppHarness) -> None:
    """Create, update, list, and delete a task within one owner boundary."""

    owner_credential = _install(app_harness.client)
    other_credential = _install(app_harness.client)

    created = _create_task(
        app_harness.client,
        owner_credential,
        client_request_id="manual-001",
        title="Review sidebar integration",
    )

    assert created["origin"] == "manual"
    assert created["type"] == "manual"
    assert created["title"] == "Review sidebar integration"
    assert created["status"] == "in_progress"
    assert created["summary"] == "Review sidebar integration"
    assert created["processing_state"] == "ready"

    other_list = app_harness.client.get("/v1/tasks", headers=_headers(other_credential))
    assert other_list.status_code == 200
    assert other_list.json() == {"tasks": []}

    blocked_update = app_harness.client.patch(
        f"/v1/tasks/{created['id']}",
        headers=_headers(other_credential),
        json={"status": "action_complete"},
    )
    assert blocked_update.status_code == 404

    updated = app_harness.client.patch(
        f"/v1/tasks/{created['id']}",
        headers=_headers(owner_credential),
        json={
            "title": "Review manual task API",
            "status": "action_complete",
            "status_reason": "Finished by the user.",
        },
    )
    assert updated.status_code == 200
    updated_body = _json_body(updated.json())
    assert updated_body["title"] == "Review manual task API"
    assert updated_body["status"] == "action_complete"
    assert updated_body["status_reason"] == "Finished by the user."
    assert updated_body["summary"] == "Review manual task API"

    title_only = app_harness.client.patch(
        f"/v1/tasks/{created['id']}",
        headers=_headers(owner_credential),
        json={"title": "Review manual task API once more"},
    )
    assert title_only.status_code == 200
    assert title_only.json()["status_reason"] == "Finished by the user."

    listed = app_harness.client.get("/v1/tasks", headers=_headers(owner_credential))
    assert listed.status_code == 200
    listed_body = _json_body(listed.json())
    assert [task["id"] for task in listed_body["tasks"]] == [created["id"]]

    forbidden_delete = app_harness.client.delete(
        f"/v1/tasks/{created['id']}",
        headers=_headers(other_credential),
    )
    assert forbidden_delete.status_code == 404

    deleted = app_harness.client.delete(
        f"/v1/tasks/{created['id']}",
        headers=_headers(owner_credential),
    )
    assert deleted.status_code == 204

    empty = app_harness.client.get("/v1/tasks", headers=_headers(owner_credential))
    assert empty.status_code == 200
    assert empty.json() == {"tasks": []}


def test_manual_task_create_is_idempotent_per_owner(
    app_harness: AppHarness,
) -> None:
    """Replay matching manual add requests without duplicating task cards."""

    owner_credential = _install(app_harness.client)
    other_credential = _install(app_harness.client)

    first = _create_task(
        app_harness.client,
        owner_credential,
        client_request_id="same-request",
        title="Original title",
    )
    replay = _create_task(
        app_harness.client,
        owner_credential,
        client_request_id="same-request",
        title="Changed title ignored by idempotency",
    )
    other_owner = _create_task(
        app_harness.client,
        other_credential,
        client_request_id="same-request",
        title="Other owner title",
    )

    assert replay["id"] == first["id"]
    assert replay["title"] == "Original title"
    assert other_owner["id"] != first["id"]

    listed = app_harness.client.get("/v1/tasks", headers=_headers(owner_credential))
    assert listed.status_code == 200
    assert len(listed.json()["tasks"]) == 1


def test_clear_data_deletes_only_authenticated_owner_tasks(
    app_harness: AppHarness,
) -> None:
    """Clear retained task data without crossing owner boundaries."""

    owner_credential = _install(app_harness.client)
    other_credential = _install(app_harness.client)
    _create_task(
        app_harness.client,
        owner_credential,
        client_request_id="owner-task",
        title="Owner task",
    )
    _create_task(
        app_harness.client,
        other_credential,
        client_request_id="other-task",
        title="Other task",
    )

    cleared = app_harness.client.delete("/v1/data", headers=_headers(owner_credential))

    assert cleared.status_code == 200
    assert cleared.json() == {"deleted_tasks": 1}
    assert app_harness.client.get(
        "/v1/tasks", headers=_headers(owner_credential)
    ).json() == {"tasks": []}
    other_tasks = app_harness.client.get(
        "/v1/tasks", headers=_headers(other_credential)
    ).json()["tasks"]
    assert len(other_tasks) == 1


def test_empty_patch_is_rejected(app_harness: AppHarness) -> None:
    """Reject a patch that would mutate nothing."""

    owner_credential = _install(app_harness.client)
    task = _create_task(
        app_harness.client,
        owner_credential,
        client_request_id="manual-002",
        title="Review empty patch behavior",
    )

    response = app_harness.client.patch(
        f"/v1/tasks/{task['id']}",
        headers=_headers(owner_credential),
        json={},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
