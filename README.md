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
```

Apply formatting with `uv run isort .` followed by `uv run black .`.
Commit `uv.lock` when updating dependencies. CI runs the same checks on Python 3.12
for pushes and pull requests. Google-style Python docstrings are required by
[AGENTS.md](AGENTS.md); the three CI tools do not check docstring style.
The API currently exposes anonymous installation onboarding, owner-scoped manual
task endpoints, and scan ingestion:

- `POST /v1/installations`
- `POST /v1/scans`
- `GET /v1/scans/{scan_id}`
- `GET /v1/tasks`
- `POST /v1/tasks`
- `PATCH /v1/tasks/{task_id}`
- `DELETE /v1/tasks/{task_id}`
- `DELETE /v1/data`

The checked-in OpenAPI contract lives at `contracts/openapi.json`.

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

The extension service worker now owns credential storage, tab scanning, content
extraction, pending submission persistence, tab source routing, and scan API
calls. Trigger.dev detection/summarization and sidebar UI integration are still
pending.
