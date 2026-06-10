"""Enumerations shared across ORM models.

Stored as portable VARCHAR + CHECK constraints (``native_enum=False``) rather
than native Postgres ENUM types, which keeps Alembic migrations simple and lets
the same models run against SQLite in tests.
"""

import enum


class ProductSource(str, enum.Enum):
    """Origin of the product, per TTB form 5100.31 (OMB 1513-0020)."""

    DOMESTIC = "domestic"
    IMPORTED = "imported"


class ProductType(str, enum.Enum):
    """Class of alcohol beverage governed by TTB labeling rules."""

    WINE = "wine"
    DISTILLED_SPIRITS = "distilled_spirits"
    MALT_BEVERAGE = "malt_beverage"


class SubmissionStatus(str, enum.Enum):
    """Lifecycle of a single label verification job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class BatchStatus(str, enum.Enum):
    """Lifecycle of a batch of label verification jobs."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
