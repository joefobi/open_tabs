"""Database engine and session management."""

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db.models import Base


class Database:
    """SQLAlchemy database handle used by API dependencies.

    Attributes:
        engine: SQLAlchemy engine bound to the configured database URL.
        session_factory: Factory for short-lived ORM sessions.
    """

    def __init__(self, database_url: str) -> None:
        """Initialize the database handle.

        Args:
            database_url: SQLAlchemy database URL.
        """

        connect_args = (
            {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        )
        self.engine: Engine = create_engine(database_url, connect_args=connect_args)
        self.session_factory: sessionmaker[Session] = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )

    def create_schema(self) -> None:
        """Create database tables for local development and tests."""

        Base.metadata.create_all(self.engine)

    def drop_schema(self) -> None:
        """Drop database tables for isolated tests."""

        Base.metadata.drop_all(self.engine)

    def session(self) -> Iterator[Session]:
        """Yield a short-lived database session.

        Yields:
            A SQLAlchemy ORM session.
        """

        with self.session_factory() as session:
            yield session
