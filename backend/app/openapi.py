"""Export the FastAPI OpenAPI contract."""

import json
from pathlib import Path
from typing import Any

from backend.app.main import create_app


def build_openapi() -> dict[str, Any]:
    """Build the OpenAPI schema.

    Returns:
        The generated OpenAPI schema.
    """
    return create_app().openapi()


def write_openapi(path: Path) -> None:
    """Write the OpenAPI schema to disk.

    Args:
        path: The output path for the OpenAPI JSON file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_openapi(), indent=2, sort_keys=True) + "\n")


def main() -> None:
    """Write the repository's checked-in OpenAPI contract."""
    write_openapi(Path("contracts/openapi.json"))


if __name__ == "__main__":
    main()
