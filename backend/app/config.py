"""Application configuration via pydantic-settings.

Settings are read from the environment (and an optional ``.env`` file). See
``.env.example`` for the supported variables and local defaults.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Backend service configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Postgres connection string. Defaults match docker-compose / local dev.
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/labelverify"

    # Comma-separated list of origins allowed to call the API (CORS).
    cors_origins: list[str] = ["http://localhost:5173"]

    # Warm the OCR model at startup so the first request isn't slow. Disable in
    # tests or fast-iteration runs where the startup cost isn't worth paying.
    ocr_warmup: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string from the environment."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
