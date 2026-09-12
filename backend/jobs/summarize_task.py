"""Trigger.dev entry point for task summary jobs."""

import json
import sys
from collections.abc import Sequence

from pydantic import ValidationError

from backend.app.config import get_settings
from backend.app.db.session import Database
from backend.app.workflows import SummaryJobResult, run_summary_job
from backend.jobs.payloads import SummaryJobPayload


def run(payload: SummaryJobPayload) -> SummaryJobResult:
    """Run summarization for one detected task revision.

    Args:
        payload: Validated summary job payload.

    Returns:
        Summary job result.
    """

    database = Database(payload.database_url or get_settings().database_url)
    with database.session_factory() as session:
        return run_summary_job(session, payload.task_id, payload.observation_id)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the summary entry point from the command line.

    Args:
        argv: Optional command-line arguments. The first argument must be JSON.

    Returns:
        Process exit code.
    """

    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("Missing summary job payload JSON.", file=sys.stderr)
        return 2

    try:
        payload = SummaryJobPayload.model_validate_json(args[0])
        result = run(payload)
    except (ValidationError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "task_id": str(result.task_id),
                "observation_id": str(result.observation_id),
                "processing_state": result.processing_state.value,
                "error_code": result.error_code,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
