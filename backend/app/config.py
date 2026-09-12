"""Configuration helpers for the backend API."""

import os
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables.

    Attributes:
        database_url: SQLAlchemy database URL used by the API.
        cors_origins: Browser origins allowed to call the API directly.
        cors_origin_regex: Regex for loopback development origins.
        model_provider: Provider used for detection and summary jobs.
        openai_api_key: Optional OpenAI API key loaded from prefixed settings.
        openai_model: OpenAI model used for text-only task analysis.
        openai_responses_url: OpenAI Responses API endpoint.
        openai_timeout_seconds: Timeout for OpenAI HTTP requests.
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
    model_provider: Literal["heuristic", "openai"] = Field(default="heuristic")
    openai_api_key: str | None = Field(default=None)
    openai_model: str = Field(default="gpt-4.1-mini")
    openai_responses_url: str = Field(default="https://api.openai.com/v1/responses")
    openai_timeout_seconds: float = Field(default=30.0, gt=0)

    def resolved_openai_api_key(self) -> str | None:
        """Return the configured OpenAI API key.

        Returns:
            The prefixed OpenTabs key, the standard OpenAI key, or None.
        """

        if self.openai_api_key:
            return self.openai_api_key
        return os.environ.get("OPENAI_API_KEY")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached runtime settings.

    Returns:
        The process-wide settings object.
    """

    return Settings()
