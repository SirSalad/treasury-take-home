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


def test_seed_populates_empty_database(db_session: Session, tmp_path) -> None:
    created = seed_demo(db_session, _FakeOcr(_LINES), upload_dir=str(tmp_path))
    assert created == 7

    submissions = db_session.scalars(select(Submission)).all()
    assert len(submissions) == 7
    assert all(s.result is not None and s.application is not None for s in submissions)

    # Decisions recorded on the cases that declare one (2 approve, 1 changes).
    decided = [s for s in submissions if s.decision]
    assert sorted(s.decision for s in decided) == ["approve", "approve", "request_changes"]
    assert all(s.decided_at is not None for s in decided)

    # One verification event per case plus one per recorded decision.
    actions = [e.action for e in db_session.scalars(select(AuditEvent))]
    assert actions.count("verification.completed") == 7
    assert actions.count("decision.recorded") == 3


def test_seed_is_a_noop_when_data_exists(db_session: Session, tmp_path) -> None:
    assert seed_demo(db_session, _FakeOcr(_LINES), upload_dir=str(tmp_path)) == 7
    assert seed_demo(db_session, _FakeOcr(_LINES), upload_dir=str(tmp_path)) == 0
    assert len(db_session.scalars(select(Submission)).all()) == 7
