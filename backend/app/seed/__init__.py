"""Demo seeding for the review queue.

``python -m app.seed`` (or ``SEED_DEMO=1`` on the container) populates the
database with labels run through the real verification pipeline so the queue,
stat cards, and audit trail all demo with realistic data:

* a curated set of synthetic corpus labels spanning pass/warning/fail, with
  reviewer decisions recorded on a few (``data/manifest.json``); and
* 30 real COLA labels scraped from the TTB Public COLA Registry — front-label
  artwork plus the filed application fields (``data/cola_manifest.json``).

Seeding is **idempotent per case**: a case whose image is already present as a
submission is skipped, so it is safe to run on every container boot and to
re-run after adding new cases (it tops up rather than duplicating). It also
**self-heals** — if a seeded row's image file is missing (e.g. a redeploy
recreated the container and its uploads were not on a persistent volume), the
file is restored from the packaged bytes so the review screen renders again.
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
from app.ocr.service import OcrResult
from app.verify import verify_label

# Each entry: (manifest filename, sub-directory holding that manifest's images).
_MANIFESTS: list[tuple[str, str]] = [
    ("manifest.json", "."),
    ("cola_manifest.json", "cola"),
]


class SupportsExtract(Protocol):
    """The one OCR method the seeder needs (real service or a test fake)."""

    def extract(self, image: bytes) -> OcrResult: ...


def _seed_case(
    db: Session,
    ocr: SupportsExtract,
    upload_dir: str,
    image_dir: Traversable,
    case: dict,
) -> None:
    """Run one case through the pipeline and persist it + its audit events."""
    image_bytes = (image_dir / case["image"]).read_bytes()
    application = ApplicationInput(**case["application"])

    started = datetime.now(UTC)
    ocr_result = ocr.extract(image_bytes)
    result = verify_label(application, ocr_result)

    app_row = Application(**application.model_dump())
    db.add(app_row)
    db.flush()

    submission = Submission(
        application=app_row,
        image_ref=_store_upload(upload_dir, case["image"], image_bytes),
        image_filename=case["image"],
        content_type="image/jpeg" if case["image"].endswith(".jpg") else "image/png",
        status=SubmissionStatus.COMPLETED,
        started_at=started,
        completed_at=datetime.now(UTC),
        processing_ms=int(ocr_result.elapsed_ms),
        result=result.model_dump(mode="json"),
    )
    db.add(submission)
    db.flush()
    record_event(
        db,
        "verification.completed",
        submission_id=submission.id,
        detail={
            "brand_name": application.brand_name,
            "image_filename": case["image"],
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

    Idempotent per case: any case whose image is already a submission is
    skipped, so re-running tops the queue up rather than duplicating.
    """
    data = resources.files("app.seed") / "data"
    # Existing seeded rows, keyed by image filename, so we can both skip
    # already-seeded cases and heal ones whose image file has gone missing
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
            prior = existing.get(case["image"])
            if prior is None:
                _seed_case(db, ocr, upload_dir, image_dir, case)
                created += 1
            elif not Path(prior.image_ref).is_file():
                # Row survived but its image file did not — restore it from the
                # packaged bytes so the review screen renders again.
                prior.image_ref = _store_upload(
                    upload_dir, case["image"], (image_dir / case["image"]).read_bytes()
                )

    db.commit()
    return created
