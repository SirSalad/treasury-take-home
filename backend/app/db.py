"""Database engine, session factory, and declarative base.

SQLAlchemy 2.0 style. The engine is built lazily from :class:`app.config.Settings`
so that tests can point ``DATABASE_URL`` at an alternate database before the
first connection is made.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


@lru_cache
def get_engine() -> Engine:
    """Return a cached SQLAlchemy engine built from settings."""
    settings = get_settings()
    # pool_pre_ping guards against stale connections after DB restarts.
    return create_engine(settings.database_url, pool_pre_ping=True, future=True)


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a session that is always closed."""
    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()
