# Browser Task Sidebar

Chrome extension with a Python backend for detecting tasks from page text, URL,
and title, with optional screenshot fallback. See [the design](BACKEND_DESIGN.md).

## Development

Install Python 3.12+ and uv, then run:

```sh
uv sync --locked
uv run --locked black --check .
uv run --locked isort --check-only .
uv run --locked mypy .
```

Apply formatting with `uv run isort .` followed by `uv run black .`.
Commit `uv.lock` when updating dependencies. CI runs the same checks on Python 3.12
for pushes and pull requests. Google-style Python docstrings are required by
[CLAUDE.md](CLAUDE.md); the three CI tools do not check docstring style.

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
- `tests/fixtures/`: sanitized page observations and expected outcomes.

This is a folder and tooling scaffold. No runnable API, extension, or Trigger.dev
integration is implemented yet.
