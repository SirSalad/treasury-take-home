"""Demo seeding for the review queue.

``python -m app.seed`` (or ``SEED_DEMO=1`` on the container) populates the
database with labels run through the real verification pipeline so the queue,
stat cards, and audit trail all demo with realistic data.

The seed is a **filtered view over the canonical data pool** (:mod:`app.pool`):
it seeds every **COLA application/label** record — the 30 real TTB COLA filings
(the same multi-image sets the golden eval scores), the 10 synthetic
golden-corpus labels (6 of which carry a recorded reviewer decision so the queue
demos the full approve/flag/pending workflow), and the one extra real COLA
(jb_kirk) — for 41 live submissions. The 18 out-of-distribution ``ocr_stress``
records (real-world bottle/RTD photos, deliberately-bad captures) are **excluded**:
they exist only to stress-test OCR as an eval view, not as reviewable COLA
submissions. There is no seed-private copy of the data — the pool is the single
source of truth, and the OCR-stress eval still reads its 18 records from it.

Seeding is **idempotent per case**: a case whose front image is already present
as a submission is skipped, so it is safe to run on every container boot and to
re-run after adding new pool records (it tops up rather than duplicating). It also
**self-heals** — if a seeded row's image files are missing (e.g. a redeploy
recreated the container and its uploads were not on a persistent volume), they
are restored from the packaged bytes so the review screen renders again.
"""

from __future__ import annotations

from datetime import UTC, datetime
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Protocol, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.audit import record_event
from app.api.schemas import ApplicationInput
from app.api.verify import _store_upload
from app.models.application import Application
from app.models.enums import SubmissionStatus
from app.models.submission import Submission
from app.models.submission_image import SubmissionImage
from app.ocr.service import ImageInput, OcrResult, OcrService
from app.pool import OCR_STRESS, load_pool, pool_images, record_images
from app.verify import verify_label_images


class SupportsExtract(Protocol):
    """The OCR surface the verification pipeline needs (real service or a test fake).

    The seeder runs each filing through :func:`verify_label_images`, the same
    adaptive multi-image pipeline the API uses, so it needs the full service
    surface (``max_side`` plus ``extract``), not just a one-shot ``extract``.
    """

    @property
    def max_side(self) -> int: ...

    def extract(self, image: ImageInput, *, max_side: int | None = None) -> OcrResult: ...


def _content_type(filename: str) -> str:
    return "image/jpeg" if filename.endswith((".jpg", ".jpeg")) else "image/png"


def _seed_case(
    db: Session,
    ocr: SupportsExtract,
    upload_dir: str,
    image_dir: Traversable,
    record: dict,
) -> None:
    """Run one pool record's full label set through the pipeline and persist it."""
    filenames = record_images(record)
    datas = [(image_dir / name).read_bytes() for name in filenames]
    application = ApplicationInput(**record["application"])

    started = datetime.now(UTC)
    # The same adaptive, multi-image pipeline the API uses: each label is read,
    # then per-field verdicts merge on the best read across the filing's set.
    # ``ocr`` is the structural OCR surface (real service or a test fake); the
    # pipeline is typed against the concrete service, so narrow it here.
    result, reads = verify_label_images(application, datas, ocr=cast(OcrService, ocr))

    app_row = Application(**application.model_dump())
    db.add(app_row)
    db.flush()

    refs = [
        _store_upload(upload_dir, name, data) for name, data in zip(filenames, datas, strict=True)
    ]
    submission = Submission(
        application=app_row,
        # Legacy columns mirror the front image; the full set lives in ``images``
        # (populated only for multi-image filings — single-image rows fall back
        # to ``image_ref``, matching how the read endpoint resolves the set).
        image_ref=refs[0],
        image_filename=filenames[0],
        content_type=_content_type(filenames[0]),
        status=SubmissionStatus.COMPLETED,
        started_at=started,
        completed_at=datetime.now(UTC),
        processing_ms=int(sum(read.elapsed_ms for read in reads)),
        result=result.model_dump(mode="json"),
        images=[
            SubmissionImage(
                position=position,
                image_ref=ref,
                image_filename=name,
                content_type=_content_type(name),
            )
            for position, (name, ref) in enumerate(zip(filenames, refs, strict=True))
        ]
        if len(filenames) > 1
        else [],
    )
    db.add(submission)
    db.flush()
    record_event(
        db,
        "verification.completed",
        submission_id=submission.id,
        detail={
            "brand_name": application.brand_name,
            "image_filename": filenames[0],
            "processing_ms": submission.processing_ms,
            "overall": result.overall.value,
            "error": None,
            "seeded": True,
            # Which pool view this row came from — flags the OCR-stress set and
            # the corpus/COLA sets without a schema change.
            "use_cases": list(record["use_cases"]),
        },
    )

    decision = record.get("decision")
    if decision:
        submission.decision = decision["decision"]
        submission.decision_note = decision.get("note")
        submission.decided_at = datetime.now(UTC)
        record_event(
            db,
            "decision.recorded",
            submission_id=submission.id,
            detail={
                "decision": decision["decision"],
                "note": decision.get("note"),
                "seeded": True,
            },
        )


def seed_demo(db: Session, ocr: SupportsExtract, upload_dir: str = "uploads") -> int:
    """Seed every pool record through the real pipeline; returns rows created.

    Idempotent per case: any case whose front image is already a submission is
    skipped, so re-running tops the queue up rather than duplicating.
    """
    image_dir = pool_images()
    # Existing seeded rows, keyed by front-image filename, so we can both skip
    # already-seeded cases and heal ones whose image files have gone missing
    # (e.g. a redeploy recreated the container before uploads were on a volume).
    existing: dict[str, Submission] = {
        s.image_filename: s
        for s in db.scalars(select(Submission).where(Submission.image_filename.is_not(None)))
        if s.image_filename is not None
    }

    created = 0
    for record in load_pool():
        # COLA scope only: the review queue is for COLA applications/labels. The
        # OCR-stress records (real-world bottle/RTD photos and deliberately-bad
        # captures) live in the pool solely to exercise OCR robustness as an eval
        # view — they are not reviewable submissions, so the seeder skips them.
        if OCR_STRESS in record["use_cases"]:
            continue
        filenames = record_images(record)
        prior = existing.get(filenames[0])
        if prior is None:
            _seed_case(db, ocr, upload_dir, image_dir, record)
            created += 1
        else:
            _heal_missing_files(prior, upload_dir, image_dir)

    db.commit()
    return created


def _heal_missing_files(prior: Submission, upload_dir: str, image_dir: Traversable) -> None:
    """Restore any of a seeded row's image files that have gone missing on disk.

    Covers every label of a multi-image filing as well as the legacy
    ``image_ref`` (which mirrors the front image), so the review screen renders
    again after the uploads directory was lost.
    """

    def restore(filename: str | None, current: str) -> str:
        if filename and not Path(current).is_file():
            return _store_upload(upload_dir, filename, (image_dir / filename).read_bytes())
        return current

    if prior.images:
        # Multi-image: heal the set, then re-point the legacy column at the
        # (possibly restored) front label so the two never diverge.
        for img in prior.images:
            img.image_ref = restore(img.image_filename, img.image_ref)
        prior.image_ref = prior.images[0].image_ref
    else:
        prior.image_ref = restore(prior.image_filename, prior.image_ref)
