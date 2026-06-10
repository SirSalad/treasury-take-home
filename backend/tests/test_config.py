"""Tests for settings parsing and model registration."""

import app.models  # noqa: F401  (register tables on Base.metadata)
from app.config import Settings
from app.db import Base


def test_cors_origins_parsed_from_comma_separated_string() -> None:
    settings = Settings(cors_origins="http://localhost:5173, https://example.gov")
    assert settings.cors_origins == ["http://localhost:5173", "https://example.gov"]


def test_cors_origins_accepts_list() -> None:
    settings = Settings(cors_origins=["http://a", "http://b"])
    assert settings.cors_origins == ["http://a", "http://b"]


def test_all_core_tables_registered() -> None:
    assert set(Base.metadata.tables) == {
        "applications",
        "submissions",
        "batches",
        "batch_items",
    }
