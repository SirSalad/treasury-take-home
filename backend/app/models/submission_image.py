"""SubmissionImage model: one label image within a submission's image set.

A COLA filing comprises *several* label images — front, back, neck, keg collar —
and the mandatory content is split across them (the Government Warning usually
sits on the back label, ABV on the front). A :class:`Submission` therefore owns
an ordered set of images; verification reads them all and merges per-field best
verdicts, the way a reviewer reads the whole filing.

``Submission.image_ref`` (and filename/content type) remain as a denormalised
mirror of the first image, so single-image writers (seed, batch ingest) and
older rows keep working unchanged.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.types import TimestampMixin

if TYPE_CHECKING:
    from app.models.submission import Submission


class SubmissionImage(TimestampMixin, Base):
    """One stored label image of a submission, in display/verification order."""

    __tablename__ = "submission_images"
    __table_args__ = (
        UniqueConstraint("submission_id", "position", name="uq_submission_image_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # Zero-based order within the submission; ``image_index`` in the result
    # contract refers to this position.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # What the image shows, mirroring the COLA form's attachment types
    # ("front", "back", "neck", "other"). Free-form; informational.
    kind: Mapped[str | None] = mapped_column(String(32))

    image_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    image_filename: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(128))

    submission: Mapped["Submission"] = relationship(back_populates="images")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<SubmissionImage submission={self.submission_id} position={self.position}>"
