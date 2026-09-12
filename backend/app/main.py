"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from backend.app.db.session import Database
from backend.app.dependencies import get_database
from backend.app.errors import http_exception_handler, validation_exception_handler
from backend.app.routes.health import router as health_router
from backend.app.routes.installations import router as installations_router
from backend.app.routes.scans import router as scans_router
from backend.app.routes.tasks import router as tasks_router


def create_app(database: Database | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        database: Optional database handle for tests or custom runtimes.

    Returns:
        Configured FastAPI application.
    """

    active_database = database

    if active_database is None:
        from backend.app.dependencies import build_database

        active_database = build_database()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """Create local database schema and run the application lifespan.

        Args:
            _: FastAPI application instance.

        Yields:
            Control to FastAPI while the application is running.
        """

        active_database.create_schema()
        yield

    def database_override() -> Database:
        """Return the database bound to this app instance.

        Returns:
            The database handle configured for this app.
        """

        return active_database

    app = FastAPI(
        title="Browser Task Sidebar API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.dependency_overrides[get_database] = database_override
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.include_router(health_router)
    app.include_router(installations_router)
    app.include_router(scans_router)
    app.include_router(tasks_router)
    return app


app = create_app()
