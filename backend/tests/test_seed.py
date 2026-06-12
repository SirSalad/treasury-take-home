"""Tests for the demo seeder (`app.seed`), a filtered view over the data pool."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.submission import Submission
from app.pool import load_pool, record_images
from app.seed import seed_demo
from app.verify import GOVERNMENT_WARNING_TEXT
from tests.test_api_verify import _FakeOcr

# Whatever the fake OCR "reads", every seeded label persists a full pipeline
# result; the per-case verdicts just come out mostly mismatched, which is fine.
# The compliant warning line keeps the fake's reads off the adaptive rescue
# passes (rotation/zoom/arc), which a warning-less read would trigger on every
# one of the COLA set's images — the seeder exercises plumbing, not OCR.
_LINES = ["OLD TOM DISTILLERY", "45% Alc./Vol.", "750 mL", GOVERNMENT_WARNING_TEXT]

# Every distinct pool record seeds one submission: 30 real COLA + 18 OCR-stress
# + 10 synthetic corpus (6 of which double as the base demo set) + 1 base-only
# real COLA (jb_kirk) = 59. The base/corpus reuse is deduped, not double-seeded.
_TOTAL = 59


def test_seed_populates_empty_database(db_session: Session, tmp_path) -> None:
    created = seed_demo(db_session, _FakeOcr(_LINES), upload_dir=str(tmp_path))
    assert created == _TOTAL

    submissions = db_session.scalars(select(Submission)).all()
    assert len(submissions) == _TOTAL
    assert all(s.result is not None and s.application is not None for s in submissions)

    # Decisions recorded on the curated corpus cases that declare one
    # (2 approve, 1 request_changes) so the queue demos the full workflow.
    decided = [s for s in submissions if s.decision]
    assert sorted(s.decision for s in decided) == ["approve", "approve", "request_changes"]
    assert all(s.decided_at is not None for s in decided)

    # One verification event per case plus one per recorded decision.
    actions = [e.action for e in db_session.scalars(select(AuditEvent))]
    assert actions.count("verification.completed") == _TOTAL
    assert actions.count("decision.recorded") == 3


def test_seed_preserves_multi_image_filings(db_session: Session, tmp_path) -> None:
    # A COLA filing is its full label set (warning on the back, ABV on the
    # front); the seed must mirror the multi-image pool records, not flatten.
    multi = {
        record_images(r)[0]: record_images(r) for r in load_pool() if len(record_images(r)) > 1
    }
    assert multi, "expected multi-image records in the pool"

    seed_demo(db_session, _FakeOcr(_LINES), upload_dir=str(tmp_path))
    by_front = {s.image_filename: s for s in db_session.scalars(select(Submission))}

    # Every multi-image filing seeded its whole label set, in order, with the
    # files actually written to disk so the review screen can serve each one.
    for front, files in multi.items():
        sub = by_front[front]
        assert [img.image_filename for img in sub.images] == files
        assert [img.position for img in sub.images] == list(range(len(files)))
        assert all(Path(img.image_ref).is_file() for img in sub.images)

    # Single-image cases stay legacy rows (image on ``image_ref``, no image set).
    single_front = next(record_images(r)[0] for r in load_pool() if len(record_images(r)) == 1)
    assert by_front[single_front].images == []


def test_seed_is_idempotent_per_case(db_session: Session, tmp_path) -> None:
    assert seed_demo(db_session, _FakeOcr(_LINES), upload_dir=str(tmp_path)) == _TOTAL
    # Re-running tops up nothing — every case is already a submission.
    assert seed_demo(db_session, _FakeOcr(_LINES), upload_dir=str(tmp_path)) == 0
    assert len(db_session.scalars(select(Submission)).all()) == _TOTAL


def test_seed_tops_up_after_partial(db_session: Session, tmp_path) -> None:
    # Simulate an earlier partial seed: drop one case's submission, reseed, and
    # only the missing one should be (re)created.
    seed_demo(db_session, _FakeOcr(_LINES), upload_dir=str(tmp_path))
    one = db_session.scalars(select(Submission).limit(1)).one()
    db_session.delete(one)
    db_session.commit()

    assert seed_demo(db_session, _FakeOcr(_LINES), upload_dir=str(tmp_path)) == 1
    assert len(db_session.scalars(select(Submission)).all()) == _TOTAL


def test_seed_heals_missing_image_files(db_session: Session, tmp_path) -> None:
    # Rows survive but their image files are wiped (a redeploy with no uploads
    # volume): reseeding creates nothing new but restores every file on disk.
    seed_demo(db_session, _FakeOcr(_LINES), upload_dir=str(tmp_path))
    submissions = db_session.scalars(select(Submission)).all()
    # Wipe every file: the front (image_ref) plus each label of multi-image rows.
    # A multi-image row's image_ref mirrors images[0], so dedupe to one set.
    refs = {Path(s.image_ref) for s in submissions}
    refs |= {Path(img.image_ref) for s in submissions for img in s.images}
    for ref in refs:
        ref.unlink()
    assert not any(ref.is_file() for ref in refs)

    created = seed_demo(db_session, _FakeOcr(_LINES), upload_dir=str(tmp_path))
    assert created == 0  # no new rows
    db_session.expire_all()
    restored = db_session.scalars(select(Submission)).all()
    assert all(Path(s.image_ref).is_file() for s in restored)
    assert all(Path(img.image_ref).is_file() for s in restored for img in s.images)
