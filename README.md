# Browser Task Sidebar

Chrome extension with a Python backend for detecting tasks from page text, URL,
and title, with optional screenshot fallback. See [the design](BACKEND_DESIGN.md).

## Local setup

The extension is not published in the Chrome Web Store yet. Test it locally by
running the API yourself and loading the built extension as an unpacked
development extension.

Install Python 3.12+ and uv, then run:

```sh
uv sync --locked
uv run uvicorn backend.app.main:app --reload
```

The API should be available at:

```text
http://127.0.0.1:8000
```

The root path returns `{"detail":"Not Found"}` because there is no homepage on
the API. Use these URLs instead:

```text
http://127.0.0.1:8000/healthz
http://127.0.0.1:8000/docs
```

Build and load the extension:

```sh
cd apps/extension
npm install
npm run build
```

Open `chrome://extensions`, enable **Developer mode**, choose **Load unpacked**,
then select:

```text
apps/extension/dist
```

After every rebuild, click the reload icon on the `OpenTabs AI` extension card
before testing again. In Chrome, use the pinned toolbar icon to open the
extension UI. Chrome may show it as a side panel or popup. Arc is Chromium-based
but its side panel behavior differs from Chrome, so Arc should use the toolbar
popup path.

For sidebar-only development, you can also run Vite:

```sh
cd apps/extension
npm run dev
```

Then open:

```text
http://127.0.0.1:5173/
```

The Vite page can test backend connectivity for installation creation and manual
task create/list behavior. It cannot scan browser tabs because ordinary
webpages do not have extension tab permissions. Tab observation only runs from
the loaded unpacked extension.

## Development checks

Run the Python checks from the repository root:

```sh
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

The Vite sidebar can call the backend directly during local development. The API
allows configured loopback CORS origins, including fallback Vite ports, and the
sidebar recreates its anonymous installation credential once if a stored
credential becomes stale after a local database reset.

## OpenAI model provider

Detection and summary jobs use deterministic local heuristics by default. To run
those jobs with OpenAI instead, set:

```sh
export OPEN_TABS_MODEL_PROVIDER=openai
export OPENAI_API_KEY=sk-...
```

You can also use `OPEN_TABS_OPENAI_API_KEY` if you prefer the project-specific
environment variable. The default text model is `gpt-4.1-mini`; override it with:

```sh
export OPEN_TABS_OPENAI_MODEL=gpt-4.1-mini
```

The OpenAI provider is used by the Python detection and summarization job entry
points. Scans still need job execution through Trigger.dev or direct job entry
point invocation before detected task cards appear in the sidebar.

## Current implementation

The Python backend currently exposes anonymous installation onboarding,
structured error responses, and owner-scoped manual task endpoints:

- `POST /v1/installations`
- `POST /v1/scans`
- `GET /v1/scans/{scan_id}`
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
service worker flushes changed observations to the backend as internal scan
batches, using persisted content fingerprints to avoid resubmitting unchanged
pages. Screenshots are not automatic or periodic; optional screenshot fallback
should only happen after a user action for the active visible page.

The extension middle layer and scan ingestion routes are implemented for the
text-first path, including automatic event-driven collection and single-flight
background submission. The Vite-launched sidebar can connect directly to the
local backend for development; the Chrome extension side panel connects through
its service worker. Trigger.dev wrappers and Python job entry points are
implemented for detection and summarization. OpenAI-backed text detection and
summarization are available behind explicit environment configuration. Image
upload and optional screenshot fallback are not implemented yet.

Trigger.dev wrappers live in `trigger/` and execute Python job entry points in
`backend/jobs/`. Configure `TRIGGER_PROJECT_REF` before running Trigger commands.

## Layout

- `apps/extension/src/background/`: collection scheduling, API client, tab routing.
- `apps/extension/src/collector/`: generic text extraction and optional screenshots.
- `apps/extension/src/sidebar/`: sidebar UI.
- `backend/app/routes/`: HTTP endpoints.
- `backend/app/auth/`: identity and owner-scoped authorization.
- `backend/app/schemas/`: request, response, and observation schemas.
- `backend/app/db/`: persistence and migrations.
- `backend/app/detection/`: model-output validation and task detection.
- `backend/app/summarization/`: summary output validation and generation.
- `backend/jobs/`: Python background-job entry points.
- `contracts/`: shared OpenAPI and extension message contracts.
- `trigger/`: TypeScript wrappers for Python jobs.
- `tests/fixtures/`: sanitized API/page observations and expected outcomes.
