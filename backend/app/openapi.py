"""OpenAPI export helper."""

import json
from pathlib import Path

from backend.app.main import create_app


def export_openapi(path: Path) -> None:
    """Write the API OpenAPI schema to a JSON file.

    Args:
        path: Destination path for the JSON schema.
    """

    schema = create_app().openapi()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")


def main() -> None:
    """Export the OpenAPI schema to the contracts directory."""

    export_openapi(Path("contracts/openapi.json"))


if __name__ == "__main__":
    main()
