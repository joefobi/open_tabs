"""Configuration helpers for the backend API."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables.

    Attributes:
        database_url: SQLAlchemy database URL used by the API.
        cors_origins: Browser origins allowed to call the API directly.
        cors_origin_regex: Regex for loopback development origins.
    """

    model_config = SettingsConfigDict(env_prefix="OPEN_TABS_")

    database_url: str = Field(default="sqlite+pysqlite:///./.context/dev.db")
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    cors_origin_regex: str | None = Field(
        default=r"^http://(localhost|127\.0\.0\.1):[0-9]+$",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached runtime settings.

    Returns:
        The process-wide settings object.
    """

    return Settings()
