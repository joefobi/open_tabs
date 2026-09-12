"""Trigger.dev entry point for detection jobs."""

import json
import sys
from collections.abc import Sequence

from pydantic import ValidationError

from backend.app.config import get_settings
from backend.app.db.session import Database
from backend.app.workflows import DetectionJobResult, run_detection_job
from backend.jobs.payloads import DetectionJobPayload


def run(payload: DetectionJobPayload) -> DetectionJobResult:
    """Run detection for one scan item.

    Args:
        payload: Validated detection job payload.

    Returns:
        Detection job result.
    """

    database = Database(payload.database_url or get_settings().database_url)
    with database.session_factory() as session:
        return run_detection_job(session, payload.scan_item_id)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the detection entry point from the command line.

    Args:
        argv: Optional command-line arguments. The first argument must be JSON.

    Returns:
        Process exit code.
    """

    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("Missing detection job payload JSON.", file=sys.stderr)
        return 2

    try:
        payload = DetectionJobPayload.model_validate_json(args[0])
        result = run(payload)
    except (ValidationError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "scan_item_id": str(result.scan_item_id),
                "outcome": result.outcome,
                "task_id": str(result.task_id) if result.task_id is not None else None,
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
