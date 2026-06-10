"""Shared pytest fixtures."""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base

# Importing models registers all tables on Base.metadata.
import app.models  # noqa: F401


@event.listens_for(Engine, "connect")
def _enable_sqlite_fks(dbapi_connection, _connection_record) -> None:
    """Enforce foreign keys on SQLite (off by default) so cascade tests are real."""
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@pytest.fixture
def db_session() -> Iterator[Session]:
    """A SQLite in-memory session with the full schema created from the ORM."""
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
