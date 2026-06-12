"""Batch and BatchItem models for bulk label uploads.

Importers drop hundreds of labels at once during peak season (per the
Compliance Division interviews). A :class:`Batch` groups those uploads; each
:class:`BatchItem` orders one :class:`Submission` within the batch.
"""

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import BatchStatus
from app.models.types import TimestampMixin


class Batch(TimestampMixin, Base):
    """A collection of label submissions uploaded together."""

    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255))

    status: Mapped[BatchStatus] = mapped_column(
        SAEnum(BatchStatus, native_enum=False, length=16),
        nullable=False,
        default=BatchStatus.PENDING,
        index=True,
    )

    items: Mapped[list["BatchItem"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="BatchItem.position",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Batch id={self.id} name={self.name!r} status={self.status.value}>"


class BatchItem(Base):
    """Ordered link between a :class:`Batch` and one :class:`Submission`."""

    __tablename__ = "batch_items"
    __table_args__ = (
        UniqueConstraint("batch_id", "position", name="uq_batch_item_position"),
        UniqueConstraint("submission_id", name="uq_batch_item_submission"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False
    )
    # Position within the batch (0-based), for stable ordering in the UI.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    batch: Mapped["Batch"] = relationship(back_populates="items")
    # String-target relationship (no module-level Submission import) keeps the
    # models acyclic; "Submission" resolves via SQLAlchemy's registry. Many-to-one
    # (FK batch_items.submission_id) → scalar.
    submission = relationship("Submission", back_populates="batch_item")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<BatchItem id={self.id} batch={self.batch_id} pos={self.position}>"
