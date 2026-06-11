"""Review-queue endpoints over persisted submissions.

The verify endpoint records every check as a :class:`Submission`; these
endpoints surface that audit trail as the reviewer's working queue:

* ``GET  /api/submissions``                — recent submissions, newest first
* ``GET  /api/submissions/stats``          — queue counts for the stat cards
* ``GET  /api/submissions/{id}``           — one submission with its full result
* ``GET  /api/submissions/{id}/image``     — the first stored label image
* ``GET  /api/submissions/{id}/images/{index}`` — one image of the label set
* ``POST /api/submissions/{id}/decision``  — record the reviewer's judgment
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import median
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
    # Median, not mean: rescue passes give scan time a long tail (a handful of
    # hard labels run 20s+), and the mean would overstate the typical scan.
    median_scan_ms: int | None


class SubmissionImageRow(BaseModel):
    """One image of the submission's label set (``index`` = display order)."""

    index: int
    filename: str | None
    kind: str | None


class SubmissionDetail(SubmissionRow):
    """Full submission: the persisted verification result and application."""

    result: dict[str, Any] | None
    error: str | None
    decision_note: str | None
    application: dict[str, Any] | None
    # The filing's label set; the result's ``image_index`` values refer to
    # these. Legacy single-image rows surface their one image here too.
    images: list[SubmissionImageRow] = Field(default_factory=list)


class DecisionInput(BaseModel):
    """The reviewer's decision plus an optional internal note."""

    decision: ReviewDecision
    note: str | None = Field(default=None, max_length=4000)


def _applicant(submission: Submission) -> str | None:
    app_row = submission.application
    return app_row.name_and_address if app_row else None


def _image_set(submission: Submission) -> list[tuple[str, str | None, str | None, str | None]]:
    """The submission's ordered images as ``(ref, filename, content_type, kind)``.

    Multi-image submissions read from ``submission.images``; legacy rows (seed,
    batch, pre-migration data) fall back to the single denormalised image on
    the submission itself, so every submission exposes a uniform image list.
    """
    if submission.images:
        return [
            (img.image_ref, img.image_filename, img.content_type, img.kind)
            for img in submission.images
        ]
    return [(submission.image_ref, submission.image_filename, submission.content_type, None)]


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
    limit: Annotated[int, Query(ge=1, le=1000)] = 50,
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
    # In Python (not percentile_cont) so the in-memory SQLite tests behave the
    # same as Postgres; the completed set is small at this scale.
    times = sorted(
        t
        for t in db.scalars(
            select(Submission.processing_ms).where(
                Submission.status == SubmissionStatus.COMPLETED,
                Submission.processing_ms.is_not(None),
            )
        )
        if t is not None  # the SQL filter already excludes these; this narrows the type
    )
    return QueueStats(
        pending=pending,
        flagged=flagged,
        cleared_week=cleared_week,
        median_scan_ms=int(median(times)) if times else None,
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
        images=[
            SubmissionImageRow(index=i, filename=filename, kind=kind)
            for i, (_, filename, _, kind) in enumerate(_image_set(submission))
        ],
    )


@router.get("/{submission_id}/image")
def get_submission_image(
    submission_id: int, db: Annotated[Session, Depends(get_db)]
) -> FileResponse:
    """The first stored label image (legacy single-image clients)."""
    return get_submission_image_at(submission_id, 0, db)


@router.get("/{submission_id}/images/{index}")
def get_submission_image_at(
    submission_id: int, index: int, db: Annotated[Session, Depends(get_db)]
) -> FileResponse:
    """One image of the submission's label set, by display order."""
    submission = _get_or_404(db, submission_id)
    images = _image_set(submission)
    if not 0 <= index < len(images):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission {submission_id} has no image {index}.",
        )
    ref, filename, content_type, _ = images[index]
    path = Path(ref)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored image is no longer available.",
        )
    return FileResponse(
        path,
        media_type=content_type or "application/octet-stream",
        filename=filename or path.name,
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
