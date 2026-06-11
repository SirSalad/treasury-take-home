"""Demo seeding for the review queue.

``python -m app.seed`` (or ``SEED_DEMO=1`` on the container) populates an
*empty* database with a handful of labels run through the real verification
pipeline — synthetic corpus labels spanning pass/warning/fail plus one real
COLA artwork — and records reviewer decisions on a couple of them, so the
queue, stat cards, and audit trail all demo with realistic data.

Seeding is a no-op when any submission already exists: it never touches a
database with real work in it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from importlib import resources
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.audit import record_event
from app.api.schemas import ApplicationInput
from app.api.verify import _store_upload
from app.models.application import Application
from app.models.enums import SubmissionStatus
from app.models.submission import Submission
from app.ocr.service import OcrResult
from app.verify import verify_label


class SupportsExtract(Protocol):
    """The one OCR method the seeder needs (real service or a test fake)."""

    def extract(self, image: bytes) -> OcrResult: ...


def seed_demo(db: Session, ocr: SupportsExtract, upload_dir: str = "uploads") -> int:
    """Seed demo submissions through the real pipeline; returns rows created.

    Skips (returning 0) when the submissions table is non-empty, so it is safe
    to run on every container boot.
    """
    existing = db.scalar(select(func.count()).select_from(Submission)) or 0
    if existing:
        return 0

    data = resources.files("app.seed") / "data"
    manifest = json.loads((data / "manifest.json").read_text())

    created = 0
    for case in manifest["cases"]:
        image_bytes = (data / case["image"]).read_bytes()
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
        created += 1

    db.commit()
    return created
