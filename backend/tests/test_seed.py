"""Tests for the demo seeder (`app.seed`)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.submission import Submission
from app.seed import seed_demo
from tests.test_api_verify import _FakeOcr

# Whatever the fake OCR "reads", every seeded label persists a full pipeline
# result; the per-case verdicts just come out mostly mismatched, which is fine.
_LINES = ["OLD TOM DISTILLERY", "45% Alc./Vol.", "750 mL"]

# 7 curated corpus cases + 30 real COLA cases.
_TOTAL = 37


def test_seed_populates_empty_database(db_session: Session, tmp_path) -> None:
    created = seed_demo(db_session, _FakeOcr(_LINES), upload_dir=str(tmp_path))
    assert created == _TOTAL

    submissions = db_session.scalars(select(Submission)).all()
    assert len(submissions) == _TOTAL
    assert all(s.result is not None and s.application is not None for s in submissions)

    # Decisions recorded on the curated cases that declare one (2 approve, 1 changes).
    decided = [s for s in submissions if s.decision]
    assert sorted(s.decision for s in decided) == ["approve", "approve", "request_changes"]
    assert all(s.decided_at is not None for s in decided)

    # One verification event per case plus one per recorded decision.
    actions = [e.action for e in db_session.scalars(select(AuditEvent))]
    assert actions.count("verification.completed") == _TOTAL
    assert actions.count("decision.recorded") == 3


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
    from pathlib import Path

    seed_demo(db_session, _FakeOcr(_LINES), upload_dir=str(tmp_path))
    submissions = db_session.scalars(select(Submission)).all()
    for s in submissions:
        Path(s.image_ref).unlink()
    assert not any(Path(s.image_ref).is_file() for s in submissions)

    created = seed_demo(db_session, _FakeOcr(_LINES), upload_dir=str(tmp_path))
    assert created == 0  # no new rows
    db_session.expire_all()
    restored = db_session.scalars(select(Submission)).all()
    assert all(Path(s.image_ref).is_file() for s in restored)
