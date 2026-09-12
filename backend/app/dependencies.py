"""FastAPI dependency providers."""

from collections.abc import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db.session import Database


def build_database() -> Database:
    """Build a database handle from runtime settings.

    Returns:
        A configured database handle.
    """

    return Database(get_settings().database_url)


_database = build_database()


def get_database() -> Database:
    """Return the process-wide database handle.

    Returns:
        The configured database handle.
    """

    return _database


def get_session(database: Database = Depends(get_database)) -> Iterator[Session]:
    """Yield a database session for a request.

    Args:
        database: Database handle resolved from application dependencies.

    Yields:
        A SQLAlchemy ORM session.
    """

    yield from database.session()
