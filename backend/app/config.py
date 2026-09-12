"""Configuration helpers for the backend API."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables.

    Attributes:
        database_url: SQLAlchemy database URL used by the API.
    """

    model_config = SettingsConfigDict(env_prefix="OPEN_TABS_")

    database_url: str = Field(default="sqlite+pysqlite:///./.context/dev.db")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached runtime settings.

    Returns:
        The process-wide settings object.
    """

    return Settings()
