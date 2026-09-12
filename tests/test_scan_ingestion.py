"""Verify owner-scoped scan ingestion API behavior."""

import json
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from backend.app.db.models import Observation
from backend.app.db.session import Database
from backend.app.main import create_app


@dataclass(frozen=True)
class AppHarness:
    """Test harness for API requests and direct database access.

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

    database = Database(f"sqlite+pysqlite:///{tmp_path / 'scan_ingestion.db'}")
    app = create_app(database)
    with TestClient(app) as client:
        yield AppHarness(client=client, database=database)


def test_scan_submission_is_owner_idempotent(app_harness: AppHarness) -> None:
    """Submitting the same client request twice returns the same scan."""

    credential = _install(app_harness.client)
    request = _fixture_request()

    first = app_harness.client.post(
        "/v1/scans", headers=_headers(credential), json=request
    )
    replay = app_harness.client.post(
        "/v1/scans", headers=_headers(credential), json=request
    )

    assert first.status_code == 202
    assert replay.status_code == 202
    assert replay.json() == first.json()

    scan = app_harness.client.get(
        f"/v1/scans/{first.json()['scan_id']}", headers=_headers(credential)
    )
    body = _json_body(scan.json())
    assert scan.status_code == 200
    assert body["counts"] == {
        "total": 1,
        "accepted": 1,
        "unchanged": 0,
        "superseded": 0,
        "failed": 0,
    }
    assert body["items"][0]["processing_state"] == "queued"


def test_unchanged_source_does_not_create_new_revision(
    app_harness: AppHarness,
) -> None:
    """A new scan with identical latest content reuses the observation."""

    credential = _install(app_harness.client)
    first_request = _fixture_request()
    second_request = _fixture_request(
        client_request_id="fixture-scan-002",
        client_observation_id="fixture-observation-002",
    )

    first = app_harness.client.post(
        "/v1/scans", headers=_headers(credential), json=first_request
    )
    second = app_harness.client.post(
        "/v1/scans", headers=_headers(credential), json=second_request
    )

    first_scan = _json_body(
        app_harness.client.get(
            f"/v1/scans/{first.json()['scan_id']}", headers=_headers(credential)
        ).json()
    )
    second_scan = _json_body(
        app_harness.client.get(
            f"/v1/scans/{second.json()['scan_id']}", headers=_headers(credential)
        ).json()
    )

    assert second_scan["counts"]["unchanged"] == 1
    assert (
        second_scan["items"][0]["observation_id"]
        == first_scan["items"][0]["observation_id"]
    )

    with app_harness.database.session_factory() as session:
        observations = session.query(Observation).all()
    assert len(observations) == 1


def test_owner_cannot_read_another_owner_scan(app_harness: AppHarness) -> None:
    """A scan lookup is scoped to the authenticated owner."""

    owner_credential = _install(app_harness.client)
    other_credential = _install(app_harness.client)

    created = app_harness.client.post(
        "/v1/scans", headers=_headers(owner_credential), json=_fixture_request()
    )
    scan_id = created.json()["scan_id"]

    blocked = app_harness.client.get(
        f"/v1/scans/{scan_id}", headers=_headers(other_credential)
    )

    assert blocked.status_code == 404


def test_source_key_removes_tracking_query_parameters(
    app_harness: AppHarness,
) -> None:
    """Tracking query parameters are not retained in source keys."""

    credential = _install(app_harness.client)

    created = app_harness.client.post(
        "/v1/scans", headers=_headers(credential), json=_fixture_request()
    )
    scan = app_harness.client.get(
        f"/v1/scans/{created.json()['scan_id']}", headers=_headers(credential)
    )

    assert scan.json()["items"][0]["source_key"] == (
        "https://github.com/example/project/pull/42"
    )


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
        The bearer credential for authenticated requests.
    """

    response = client.post("/v1/installations")
    assert response.status_code == 201
    credential = response.json()["installation_credential"]
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


def _fixture_request(
    *,
    client_request_id: str = "fixture-scan-001",
    client_observation_id: str = "fixture-observation-001",
) -> dict[str, Any]:
    """Load and customize the scan ingestion fixture.

    Args:
        client_request_id: Replacement scan idempotency key.
        client_observation_id: Replacement observation idempotency key.

    Returns:
        The request payload.
    """

    fixture_path = Path("tests/fixtures/scan_ingestion_request.json")
    payload = _json_body(json.loads(fixture_path.read_text(encoding="utf-8")))
    payload["client_request_id"] = client_request_id
    observations = payload["observations"]
    if not isinstance(observations, list):
        raise TypeError("Fixture observations must be a list.")
    observation = observations[0]
    if not isinstance(observation, dict):
        raise TypeError("Fixture observation must be an object.")
    observation["client_observation_id"] = client_observation_id
    return payload
