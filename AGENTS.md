# Project instructions

Follow BACKEND_DESIGN.md for architecture and confirmed product decisions.

## Python standards

- Every Python module, class, function, and method must have a docstring, including private helpers and tests.
- Use Google-style docstrings: a concise summary followed by Args, Returns (or Yields), Raises, and Attributes sections when applicable. Simple modules and functions may use a one-line summary when no sections apply.
- Document behavior and meaningful exceptions; keep documentation current when changing code.
- Add type annotations to all function parameters and return values. Use strict mypy checks.
- Format Python with Black and sort imports with isort's Black profile.
- Run the CI checks locally before finishing Python changes:
  - `uv run --locked black --check .`
  - `uv run --locked isort --check-only .`
  - `uv run --locked mypy .`

Example:

```python
def normalize_title(title: str) -> str:
    """Remove surrounding whitespace from a task title.

    Args:
        title: The original task title.

    Returns:
        The title with surrounding whitespace removed.
    """
    return title.strip()
```

Black, isort, and mypy do not enforce docstring completeness or Google style; this is a required authoring and review convention.
