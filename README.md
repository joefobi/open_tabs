# Browser Task Sidebar

Chrome extension with a Python backend for detecting tasks from page text, URL,
and title, with optional screenshot fallback. See [the design](BACKEND_DESIGN.md).

## Development

Install Python 3.12+ and uv, then run:

```sh
uv sync --locked
uv run uvicorn backend.app.main:app --reload
uv run --locked black --check .
uv run --locked isort --check-only .
uv run --locked mypy .
uv run --locked pytest
```

Apply formatting with `uv run isort .` followed by `uv run black .`.
Commit `uv.lock` when updating dependencies. CI runs Black, isort, mypy, and
pytest as separate jobs on pull requests and manual workflow dispatch. Google-style
Python docstrings are required by [AGENTS.md](AGENTS.md); the CI tools do not
check docstring style.

## Current implementation

The Python backend currently exposes anonymous installation onboarding,
structured error responses, and owner-scoped manual task endpoints:

- `POST /v1/installations`
- `GET /v1/tasks`
- `POST /v1/tasks`
- `PATCH /v1/tasks/{task_id}`
- `DELETE /v1/tasks/{task_id}`
- `DELETE /v1/data`

Use the installation credential returned by `POST /v1/installations` as a bearer
token on owner-scoped endpoints:

```http
Authorization: Bearer <installation_credential>
```

The checked-in OpenAPI contract lives at `contracts/openapi.json`.
Tests cover the anonymous identity boundary, manual task lifecycle, idempotent
manual creation, validation errors, owner isolation, clear-data behavior, and
OpenAPI contract freshness.

The intended extension collection model is automatic page-text observation from
permitted HTTP(S) pages as the user visits, activates, or navigates tabs. The
service worker will flush changed observations to the backend as internal scan
batches. Screenshots are not automatic or periodic; optional screenshot fallback
should only happen after a user action for the active visible page.

The extension middle layer, automatic observation collection, scan ingestion
routes, Trigger.dev workflows, model-backed detection, summarization, image
upload, and optional screenshot fallback are not implemented yet.

## Layout

- `apps/extension/src/background/`: collection scheduling, API client, tab routing.
- `apps/extension/src/collector/`: generic text extraction and optional screenshots.
- `apps/extension/src/sidebar/`: sidebar UI.
- `backend/app/routes/`: HTTP endpoints.
- `backend/app/auth/`: identity and owner-scoped authorization.
- `backend/app/schemas/`: request, response, and observation schemas.
- `backend/app/db/`: persistence and migrations.
- `backend/app/detection/`: model-based task detection.
- `backend/app/summarization/`: summary generation.
- `backend/jobs/`: Python background-job entry points.
- `contracts/`: shared OpenAPI and extension message contracts.
- `trigger/`: TypeScript wrappers for Python jobs.
- `tests/fixtures/`: sanitized API/page observations and expected outcomes.
