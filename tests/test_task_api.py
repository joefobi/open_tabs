"""Verify owner-scoped manual task API behavior."""

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.db.repository import (
    InMemoryTaskRepository,
    TaskRepository,
    get_repository,
)
from backend.app.main import create_app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create an isolated test client.

    Yields:
        A FastAPI test client with a fresh in-memory repository.
    """
    repository = InMemoryTaskRepository()

    def override_repository() -> TaskRepository:
        """Return the isolated repository for this test client.

        Returns:
            The repository bound to this test client.
        """
        return repository

    app = create_app()
    app.dependency_overrides[get_repository] = override_repository
    with TestClient(app) as test_client:
        yield test_client


def _install(client: TestClient) -> str:
    """Create an anonymous installation and return its token.

    Args:
        client: The test HTTP client.

    Returns:
        The created installation bearer token.
    """
    response = client.post("/v1/installations")
    assert response.status_code == 201
    body = response.json()
    token = body["installation_token"]
    assert isinstance(token, str)
    return token


def _headers(token: str) -> dict[str, str]:
    """Build authorization headers for a token.

    Args:
        token: The bearer token.

    Returns:
        HTTP headers containing the bearer token.
    """
    return {"Authorization": f"Bearer {token}"}


def _create_task(
    client: TestClient,
    token: str,
    *,
    client_request_id: str,
    title: str,
) -> dict[str, Any]:
    """Create a manual task and return its response body.

    Args:
        client: The test HTTP client.
        token: The owner bearer token.
        client_request_id: The idempotency key for the request.
        title: The manual task title.

    Returns:
        The task response body.
    """
    response = client.post(
        "/v1/tasks",
        headers=_headers(token),
        json={"client_request_id": client_request_id, "title": title},
    )
    assert response.status_code == 201
    body = response.json()
    assert isinstance(body, dict)
    return body


def test_list_tasks_requires_authentication(client: TestClient) -> None:
    """Reject unauthenticated task listing."""
    response = client.get("/v1/tasks")

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "unauthorized",
            "message": "Missing anonymous installation credential.",
            "retryable": False,
        }
    }


def test_manual_task_lifecycle_is_owner_scoped(client: TestClient) -> None:
    """Create, update, list, and delete a task within one owner boundary."""
    owner_token = _install(client)
    other_token = _install(client)

    created = _create_task(
        client,
        owner_token,
        client_request_id="manual-001",
        title="Review sidebar integration",
    )

    assert created["origin"] == "manual"
    assert created["type"] == "manual"
    assert created["title"] == "Review sidebar integration"
    assert created["status"] == "in_progress"
    assert created["summary"] == "Review sidebar integration"
    assert created["processing_state"] == "ready"

    other_list = client.get("/v1/tasks", headers=_headers(other_token))
    assert other_list.status_code == 200
    assert other_list.json() == {"tasks": []}

    blocked_update = client.patch(
        f"/v1/tasks/{created['id']}",
        headers=_headers(other_token),
        json={"status": "action_complete"},
    )
    assert blocked_update.status_code == 404

    updated = client.patch(
        f"/v1/tasks/{created['id']}",
        headers=_headers(owner_token),
        json={
            "title": "Review manual task API",
            "status": "action_complete",
            "status_reason": "Finished by the user.",
        },
    )
    assert updated.status_code == 200
    updated_body = updated.json()
    assert updated_body["title"] == "Review manual task API"
    assert updated_body["status"] == "action_complete"
    assert updated_body["status_reason"] == "Finished by the user."
    assert updated_body["summary"] == "Review manual task API"

    title_only = client.patch(
        f"/v1/tasks/{created['id']}",
        headers=_headers(owner_token),
        json={"title": "Review manual task API once more"},
    )
    assert title_only.status_code == 200
    assert title_only.json()["status_reason"] == "Finished by the user."

    listed = client.get("/v1/tasks", headers=_headers(owner_token))
    assert listed.status_code == 200
    assert [task["id"] for task in listed.json()["tasks"]] == [created["id"]]

    forbidden_delete = client.delete(
        f"/v1/tasks/{created['id']}",
        headers=_headers(other_token),
    )
    assert forbidden_delete.status_code == 404

    deleted = client.delete(
        f"/v1/tasks/{created['id']}",
        headers=_headers(owner_token),
    )
    assert deleted.status_code == 204

    empty = client.get("/v1/tasks", headers=_headers(owner_token))
    assert empty.status_code == 200
    assert empty.json() == {"tasks": []}


def test_manual_task_create_is_idempotent_per_owner(client: TestClient) -> None:
    """Replay matching manual add requests without duplicating task cards."""
    owner_token = _install(client)
    other_token = _install(client)

    first = _create_task(
        client,
        owner_token,
        client_request_id="same-request",
        title="Original title",
    )
    replay = _create_task(
        client,
        owner_token,
        client_request_id="same-request",
        title="Changed title ignored by idempotency",
    )
    other_owner = _create_task(
        client,
        other_token,
        client_request_id="same-request",
        title="Other owner title",
    )

    assert replay["id"] == first["id"]
    assert replay["title"] == "Original title"
    assert other_owner["id"] != first["id"]

    listed = client.get("/v1/tasks", headers=_headers(owner_token))
    assert listed.status_code == 200
    assert len(listed.json()["tasks"]) == 1


def test_clear_data_deletes_only_authenticated_owner_tasks(
    client: TestClient,
) -> None:
    """Clear retained task data without crossing owner boundaries."""
    owner_token = _install(client)
    other_token = _install(client)
    _create_task(
        client,
        owner_token,
        client_request_id="owner-task",
        title="Owner task",
    )
    _create_task(
        client,
        other_token,
        client_request_id="other-task",
        title="Other task",
    )

    cleared = client.delete("/v1/data", headers=_headers(owner_token))

    assert cleared.status_code == 200
    assert cleared.json() == {"deleted_tasks": 1}
    assert client.get("/v1/tasks", headers=_headers(owner_token)).json() == {
        "tasks": []
    }
    assert (
        len(client.get("/v1/tasks", headers=_headers(other_token)).json()["tasks"]) == 1
    )


def test_empty_patch_is_rejected(client: TestClient) -> None:
    """Reject a patch that would mutate nothing."""
    owner_token = _install(client)
    task = _create_task(
        client,
        owner_token,
        client_request_id="manual-002",
        title="Review empty patch behavior",
    )

    response = client.patch(
        f"/v1/tasks/{task['id']}",
        headers=_headers(owner_token),
        json={},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"
