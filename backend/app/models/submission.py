"""Submission model: a single label-verification job.

One filing's label image set (front/back/neck — see
:class:`app.models.submission_image.SubmissionImage`), the expected
:class:`Application` it is checked against (optional), processing
status/timing, and the verification ``result`` JSON produced by the OCR +
matching pipeline. Submissions are used both for single uploads and as the
unit of work inside a batch (see :class:`BatchItem`).
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import SubmissionStatus
from app.models.types import JSONType, TimestampMixin

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.batch import BatchItem
    from app.models.submission_image import SubmissionImage


class Submission(TimestampMixin, Base):
    """A single label image verification job and its result."""

    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True)

    application_id: Mapped[int | None] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )

    # Reference to the stored image (path or object-store key) plus metadata.
    # For multi-image submissions these mirror the first image of ``images``;
    # single-image writers (seed, batch ingest) populate only these columns.
    image_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    image_filename: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(128))

    status: Mapped[SubmissionStatus] = mapped_column(
        SAEnum(SubmissionStatus, native_enum=False, length=16),
        nullable=False,
        default=SubmissionStatus.PENDING,
        index=True,
    )

    # Timing: wall-clock markers plus a denormalized duration for quick queries.
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_ms: Mapped[int | None] = mapped_column(Integer)

    # Verification output: extracted fields, per-field matches, overall verdict.
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    error: Mapped[str | None] = mapped_column(Text)

    # Reviewer decision (the human judgment recorded on top of the automated
    # verdict): approve / request_changes / request_info. Null = still in queue.
    decision: Mapped[str | None] = mapped_column(String(32), index=True)
    decision_note: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    application: Mapped["Application | None"] = relationship(back_populates="submissions")
    # The filing's full label set (front/back/neck), in upload order. Empty for
    # legacy/single-image rows, whose image lives on ``image_ref`` directly.
    images: Mapped[list["SubmissionImage"]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="SubmissionImage.position",
    )
    # Deleting a submission removes its batch link; submissions themselves are
    # durable verification records and outlive the batch that grouped them.
    batch_item: Mapped["BatchItem | None"] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
        uselist=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Submission id={self.id} status={self.status.value}>"
