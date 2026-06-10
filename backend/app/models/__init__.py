"""ORM models for the label verification service.

Importing this package registers every model on :data:`app.db.Base.metadata`,
which is what Alembic autogenerate and ``create_all`` rely on.
"""

from app.models.application import Application
from app.models.batch import Batch, BatchItem
from app.models.enums import (
    BatchStatus,
    ProductSource,
    ProductType,
    SubmissionStatus,
)
from app.models.submission import Submission

__all__ = [
    "Application",
    "Batch",
    "BatchItem",
    "BatchStatus",
    "ProductSource",
    "ProductType",
    "Submission",
    "SubmissionStatus",
]
