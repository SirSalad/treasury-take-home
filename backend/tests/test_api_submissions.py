"""API tests for the review-queue endpoints (`/api/submissions`, `/api/audit`).

Reuses the verify-endpoint harness: a fake OCR seeds real submissions through
``POST /api/verify``, then the queue endpoints are exercised over them.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.db import Base, get_db
from app.main import app
from app.ocr import get_ocr_service
from app.verify.schemas import GOVERNMENT_WARNING_TEXT
from tests.test_api_verify import _FakeOcr, _form, _valid_png

_PASS_LINES = [
    "OLD TOM DISTILLERY",
    "Kentucky Straight Bourbon Whiskey",
    "45% Alc./Vol. (90 Proof)",
    "750 mL",
    "Bottled by Old Tom Distillery, Bardstown, KY",
    GOVERNMENT_WARNING_TEXT,
]

# Wrong ABV on the label -> overall fail -> lands in the "flagged" bucket.
_FAIL_LINES = ["OLD TOM DISTILLERY", "40% Alc./Vol.", GOVERNMENT_WARNING_TEXT]


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _client(session_factory: sessionmaker[Session], ocr_texts: list[str], tmp_path) -> TestClient:
    def _override_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_ocr_service] = lambda: _FakeOcr(ocr_texts)
    app.dependency_overrides[get_settings] = lambda: Settings(
        upload_dir=str(tmp_path / "uploads"), ocr_warmup=False
    )
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


def _seed_one(client: TestClient) -> int:
    resp = client.post(
        "/api/verify",
        data=_form(),
        files={"image": ("label.png", _valid_png(), "image/png")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["submission_id"]


def test_queue_lists_seeded_submissions_newest_first(session_factory, tmp_path) -> None:
    client = _client(session_factory, _PASS_LINES, tmp_path)
    first = _seed_one(client)
    second = _seed_one(client)

    rows = client.get("/api/submissions").json()
    assert [r["id"] for r in rows] == [second, first]
    top = rows[0]
    assert top["brand_name"] == "OLD TOM DISTILLERY"
    assert top["applicant"] == "Bottled by Old Tom Distillery, Bardstown, KY"
    assert top["overall"] == "pass"
    assert top["warning_verdict"] == "compliant"
    assert top["decision"] is None


def test_stats_count_pending_flagged_and_cleared(session_factory, tmp_path) -> None:
    client = _client(session_factory, _PASS_LINES, tmp_path)
    pass_id = _seed_one(client)
    client = _client(session_factory, _FAIL_LINES, tmp_path)
    _seed_one(client)  # flagged: overall fail, undecided

    stats = client.get("/api/submissions/stats").json()
    assert stats["pending"] == 2
    assert stats["flagged"] == 1
    assert stats["cleared_week"] == 0
    assert stats["median_scan_ms"] is not None

    client.post(f"/api/submissions/{pass_id}/decision", json={"decision": "approve"})
    stats = client.get("/api/submissions/stats").json()
    assert stats["pending"] == 1
    assert stats["cleared_week"] == 1


def test_detail_returns_result_and_application(session_factory, tmp_path) -> None:
    client = _client(session_factory, _PASS_LINES, tmp_path)
    sid = _seed_one(client)

    detail = client.get(f"/api/submissions/{sid}").json()
    assert detail["result"]["overall"] == "pass"
    assert detail["application"]["brand_name"] == "OLD TOM DISTILLERY"
    assert detail["application"]["alcohol_content_pct"] == 45.0
    assert any(f["field"] == "brand_name" for f in detail["result"]["fields"])


def test_image_roundtrip(session_factory, tmp_path) -> None:
    client = _client(session_factory, _PASS_LINES, tmp_path)
    sid = _seed_one(client)

    resp = client.get(f"/api/submissions/{sid}/image")
    assert resp.status_code == 200
    assert resp.content == _valid_png()


def test_decision_persists_and_audits(session_factory, tmp_path) -> None:
    client = _client(session_factory, _PASS_LINES, tmp_path)
    sid = _seed_one(client)

    resp = client.post(
        f"/api/submissions/{sid}/decision",
        json={"decision": "request_changes", "note": "ABV is blurry"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "request_changes"
    assert body["decision_note"] == "ABV is blurry"
    assert body["decided_at"] is not None

    events = client.get("/api/audit", params={"submission_id": sid}).json()
    actions = [e["action"] for e in events]
    assert "decision.recorded" in actions
    assert "verification.completed" in actions
    decision_event = next(e for e in events if e["action"] == "decision.recorded")
    assert decision_event["detail"]["decision"] == "request_changes"


def test_decision_on_missing_submission_is_404(session_factory, tmp_path) -> None:
    client = _client(session_factory, _PASS_LINES, tmp_path)
    resp = client.post("/api/submissions/9999/decision", json={"decision": "approve"})
    assert resp.status_code == 404


def test_invalid_decision_value_is_422(session_factory, tmp_path) -> None:
    client = _client(session_factory, _PASS_LINES, tmp_path)
    sid = _seed_one(client)
    resp = client.post(f"/api/submissions/{sid}/decision", json={"decision": "yolo"})
    assert resp.status_code == 422
