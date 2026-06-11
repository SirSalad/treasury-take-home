"""Append-only audit log.

Every consequential action — a verification run, a reviewer decision — gets one
immutable row. The submissions table holds the *current* state; this table
holds the *history*, which is what an auditor (or a FOIA request) actually
asks for. Rows are only ever inserted, never updated or deleted by the app.
"""

from typing import Any

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.types import JSONType, TimestampMixin


class AuditEvent(TimestampMixin, Base):
    """One immutable record of an action taken in the system."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)

    # What happened: verification.completed, verification.failed,
    # decision.recorded, ...
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Who did it. The prototype has no auth, so this records the client identity
    # we do have (defaults to "reviewer"); the column exists so wiring real
    # identity in later is a one-line change, not a migration.
    actor: Mapped[str] = mapped_column(String(128), nullable=False, default="reviewer")

    # The submission acted on, when applicable. SET NULL keeps history rows
    # alive even if the submission is purged.
    submission_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("submissions.id", ondelete="SET NULL"), index=True
    )

    # Action-specific context: verdict, decision, filenames, timing.
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONType)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AuditEvent id={self.id} action={self.action}>"
