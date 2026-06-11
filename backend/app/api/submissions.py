"""Review-queue endpoints over persisted submissions.

The verify endpoint records every check as a :class:`Submission`; these
endpoints surface that audit trail as the reviewer's working queue:

* ``GET  /api/submissions``                — recent submissions, newest first
* ``GET  /api/submissions/stats``          — queue counts for the stat cards
* ``GET  /api/submissions/{id}``           — one submission with its full result
* ``GET  /api/submissions/{id}/image``     — the stored label image
* ``POST /api/submissions/{id}/decision``  — record the reviewer's judgment
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.api.audit import record_event
from app.db import get_db
from app.models.enums import SubmissionStatus
from app.models.submission import Submission

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


class ReviewDecision(enum.StrEnum):
    """The reviewer's judgment on a verified label."""

    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    REQUEST_INFO = "request_info"


class SubmissionRow(BaseModel):
    """One queue row: enough to render the table without the full result."""

    id: int
    created_at: datetime | None
    status: SubmissionStatus
    brand_name: str | None
    applicant: str | None
    class_type: str | None
    overall: str | None
    warning_verdict: str | None
    processing_ms: int | None
    image_filename: str | None
    decision: ReviewDecision | None
    decided_at: datetime | None


class QueueStats(BaseModel):
    """Counts for the stat cards above the queue."""

    pending: int
    flagged: int
    cleared_week: int
    avg_scan_ms: int | None


class SubmissionDetail(SubmissionRow):
    """Full submission: the persisted verification result and application."""

    result: dict[str, Any] | None
    error: str | None
    decision_note: str | None
    application: dict[str, Any] | None


class DecisionInput(BaseModel):
    """The reviewer's decision plus an optional internal note."""

    decision: ReviewDecision
    note: str | None = Field(default=None, max_length=4000)


def _applicant(submission: Submission) -> str | None:
    app_row = submission.application
    return app_row.name_and_address if app_row else None


def _row(submission: Submission) -> SubmissionRow:
    result = submission.result or {}
    app_row = submission.application
    return SubmissionRow(
        id=submission.id,
        created_at=submission.created_at,
        status=submission.status,
        brand_name=app_row.brand_name if app_row else None,
        applicant=_applicant(submission),
        class_type=app_row.class_type if app_row else None,
        overall=result.get("overall"),
        warning_verdict=(result.get("government_warning") or {}).get("verdict"),
        processing_ms=submission.processing_ms,
        image_filename=submission.image_filename,
        decision=ReviewDecision(submission.decision) if submission.decision else None,
        decided_at=submission.decided_at,
    )


@router.get("", response_model=list[SubmissionRow])
def list_submissions(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[SubmissionRow]:
    """Most recent submissions, newest first."""
    rows = db.scalars(
        select(Submission)
        .options(joinedload(Submission.application))
        .order_by(Submission.id.desc())
        .limit(limit)
    ).all()
    return [_row(s) for s in rows]


@router.get("/stats", response_model=QueueStats)
def queue_stats(db: Annotated[Session, Depends(get_db)]) -> QueueStats:
    """Queue counts: pending, flagged for judgment, cleared this week, avg scan."""
    undecided = (Submission.decision.is_(None)) & (Submission.status == SubmissionStatus.COMPLETED)
    pending = db.scalar(select(func.count()).select_from(Submission).where(undecided)) or 0

    flagged = 0
    for s in db.scalars(select(Submission).where(undecided)):
        overall = (s.result or {}).get("overall")
        if overall in ("warning", "fail"):
            flagged += 1

    week_ago = datetime.now(UTC) - timedelta(days=7)
    cleared_week = (
        db.scalar(
            select(func.count())
            .select_from(Submission)
            .where(Submission.decision.is_not(None), Submission.decided_at >= week_ago)
        )
        or 0
    )
    avg_ms = db.scalar(
        select(func.avg(Submission.processing_ms)).where(
            Submission.status == SubmissionStatus.COMPLETED
        )
    )
    return QueueStats(
        pending=pending,
        flagged=flagged,
        cleared_week=cleared_week,
        avg_scan_ms=int(avg_ms) if avg_ms is not None else None,
    )


def _get_or_404(db: Session, submission_id: int) -> Submission:
    submission = db.get(Submission, submission_id, options=[joinedload(Submission.application)])
    if submission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission {submission_id} not found.",
        )
    return submission


@router.get("/{submission_id}", response_model=SubmissionDetail)
def get_submission(submission_id: int, db: Annotated[Session, Depends(get_db)]) -> SubmissionDetail:
    """One submission with its persisted verification result."""
    submission = _get_or_404(db, submission_id)
    base = _row(submission)
    app_row = submission.application
    application = None
    if app_row is not None:
        application = {
            c.key: getattr(app_row, c.key)
            for c in app_row.__table__.columns
            if c.key not in ("id",)
        }
        # JSON-safe: Numeric comes back as Decimal.
        pct = application.get("alcohol_content_pct")
        if pct is not None:
            application["alcohol_content_pct"] = float(pct)
    return SubmissionDetail(
        **base.model_dump(),
        result=submission.result,
        error=submission.error,
        decision_note=submission.decision_note,
        application=application,
    )


@router.get("/{submission_id}/image")
def get_submission_image(
    submission_id: int, db: Annotated[Session, Depends(get_db)]
) -> FileResponse:
    """The stored label image for re-rendering in the review screen."""
    submission = _get_or_404(db, submission_id)
    path = Path(submission.image_ref)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored image is no longer available.",
        )
    return FileResponse(
        path,
        media_type=submission.content_type or "application/octet-stream",
        filename=submission.image_filename or path.name,
    )


@router.post("/{submission_id}/decision", response_model=SubmissionDetail)
def record_decision(
    submission_id: int, body: DecisionInput, db: Annotated[Session, Depends(get_db)]
) -> SubmissionDetail:
    """Record the reviewer's judgment; idempotent overwrite is allowed."""
    submission = _get_or_404(db, submission_id)
    if submission.status != SubmissionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only completed submissions can receive a decision.",
        )
    submission.decision = body.decision.value
    submission.decision_note = body.note
    submission.decided_at = datetime.now(UTC)
    record_event(
        db,
        "decision.recorded",
        submission_id=submission.id,
        detail={"decision": body.decision.value, "note": body.note},
    )
    db.commit()
    db.refresh(submission)
    return get_submission(submission_id, db)
