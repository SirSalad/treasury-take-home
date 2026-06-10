"""Application configuration via pydantic-settings.

Settings are read from the environment (and an optional ``.env`` file). See
``.env.example`` for the supported variables and local defaults.
"""

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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
    # NoDecode: pydantic-settings otherwise JSON-decodes list fields from the
    # environment before validators run, which would reject the documented
    # comma-separated form (e.g. CORS_ORIGINS=http://a,http://b). With NoDecode
    # the raw string reaches `_split_origins` below.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    # Warm the OCR model at startup so the first request isn't slow. Disable in
    # tests or fast-iteration runs where the startup cost isn't worth paying.
    ocr_warmup: bool = True

    # Longest-side cap (px) applied to uploads before OCR. Bounds worst-case
    # latency on large phone photos without touching already-small labels; see
    # app.ocr.preprocess. Default leaves the ~900px corpus untouched.
    ocr_max_side: int = 1600

    # Recognition batch size. Multi-line labels (the corpus tops out at ~13
    # lines) recognise faster when their text crops are batched through the
    # recogniser together rather than in the RapidOCR default groups of 6.
    ocr_rec_batch_num: int = 8

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
