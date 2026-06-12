"""Demo seeding for the review queue.

``python -m app.seed`` (or ``SEED_DEMO=1`` on the container) populates the
database with labels run through the real verification pipeline so the queue,
stat cards, and audit trail all demo with realistic data:

* a curated set of synthetic corpus labels spanning pass/warning/fail, with
  reviewer decisions recorded on a few (``data/manifest.json``); and
* 30 real COLA filings scraped from the TTB Public COLA Registry — the **full
  label set** filed with each application (front + back/neck where the filing
  carries them) plus the filed application fields (``data/cola_manifest.json``).

The COLA set mirrors the ``tests/eval_cola`` golden eval one-for-one (same TTB
IDs, same image sets), so a seeded filing is the *same* multi-image submission
the eval scores: a COLA is the set of affixed labels (warning on the back, ABV
on the front), and the demo queue shows it that way rather than front-only.

Seeding is **idempotent per case**: a case whose front image is already present
as a submission is skipped, so it is safe to run on every container boot and to
re-run after adding new cases (it tops up rather than duplicating). It also
**self-heals** — if a seeded row's image files are missing (e.g. a redeploy
recreated the container and its uploads were not on a persistent volume), they
are restored from the packaged bytes so the review screen renders again.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.audit import record_event
from app.api.schemas import ApplicationInput
from app.api.verify import _store_upload
from app.models.application import Application
from app.models.enums import SubmissionStatus
from app.models.submission import Submission
from app.models.submission_image import SubmissionImage
from app.ocr.service import ImageInput, OcrResult
from app.verify import verify_label_images

# Each entry: (manifest filename, sub-directory holding that manifest's images).
_MANIFESTS: list[tuple[str, str]] = [
    ("manifest.json", "."),
    ("cola_manifest.json", "cola"),
]


class SupportsExtract(Protocol):
    """The OCR surface the verification pipeline needs (real service or a test fake).

    The seeder runs each filing through :func:`verify_label_images`, the same
    adaptive multi-image pipeline the API uses, so it needs the full service
    surface (``max_side`` plus ``extract``), not just a one-shot ``extract``.
    """

    max_side: int

    def extract(self, image: ImageInput, *, max_side: int | None = None) -> OcrResult: ...


def _case_images(case: dict) -> list[str]:
    """The filenames of a case's label set, front first.

    Multi-image filings list every label under ``images``; single-image cases
    (the synthetic corpus) carry a lone ``image``.
    """
    images = case.get("images")
    return list(images) if images else [case["image"]]


def _content_type(filename: str) -> str:
    return "image/jpeg" if filename.endswith((".jpg", ".jpeg")) else "image/png"


def _seed_case(
    db: Session,
    ocr: SupportsExtract,
    upload_dir: str,
    image_dir: Traversable,
    case: dict,
) -> None:
    """Run one filing's full label set through the pipeline and persist it."""
    filenames = _case_images(case)
    datas = [(image_dir / name).read_bytes() for name in filenames]
    application = ApplicationInput(**case["application"])

    started = datetime.now(UTC)
    # The same adaptive, multi-image pipeline the API uses: each label is read,
    # then per-field verdicts merge on the best read across the filing's set.
    result, reads = verify_label_images(application, datas, ocr=ocr)

    app_row = Application(**application.model_dump())
    db.add(app_row)
    db.flush()

    refs = [_store_upload(upload_dir, name, data) for name, data in zip(filenames, datas, strict=True)]
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
        },
    )

    decision = case.get("decision")
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
    """Seed demo submissions through the real pipeline; returns rows created.

    Idempotent per case: any case whose front image is already a submission is
    skipped, so re-running tops the queue up rather than duplicating.
    """
    data = resources.files("app.seed") / "data"
    # Existing seeded rows, keyed by front-image filename, so we can both skip
    # already-seeded cases and heal ones whose image files have gone missing
    # (e.g. a redeploy recreated the container before uploads were on a volume).
    existing: dict[str, Submission] = {
        s.image_filename: s
        for s in db.scalars(select(Submission).where(Submission.image_filename.is_not(None)))
        if s.image_filename is not None
    }

    created = 0
    for manifest_name, subdir in _MANIFESTS:
        manifest = json.loads((data / manifest_name).read_text())
        image_dir = data if subdir == "." else data / subdir
        for case in manifest["cases"]:
            filenames = _case_images(case)
            prior = existing.get(filenames[0])
            if prior is None:
                _seed_case(db, ocr, upload_dir, image_dir, case)
                created += 1
            else:
                _heal_missing_files(prior, upload_dir, image_dir)

    db.commit()
    return created


def _heal_missing_files(
    prior: Submission, upload_dir: str, image_dir: Traversable
) -> None:
    """Restore any of a seeded row's image files that have gone missing on disk.

    Covers both the legacy ``image_ref`` (front image) and every label of a
    multi-image filing, so the review screen renders again after the uploads
    directory was lost.
    """
    if not Path(prior.image_ref).is_file() and prior.image_filename:
        prior.image_ref = _store_upload(
            upload_dir, prior.image_filename, (image_dir / prior.image_filename).read_bytes()
        )
    for img in prior.images:
        if not Path(img.image_ref).is_file() and img.image_filename:
            img.image_ref = _store_upload(
                upload_dir, img.image_filename, (image_dir / img.image_filename).read_bytes()
            )
