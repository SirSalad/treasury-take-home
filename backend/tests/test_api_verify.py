"""API tests for ``POST /api/verify`` (fast: OCR is stubbed).

The OCR engine is replaced with a fake that returns canned text, so these
exercise the endpoint's wiring, validation, persistence, and response shape
without paying real-OCR cost. The real-OCR end-to-end check lives in
``tests/perf/test_verify_e2e.py``.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - register tables on Base.metadata
from app.config import Settings, get_settings
from app.db import Base, get_db
from app.main import app
from app.models.enums import SubmissionStatus
from app.models.submission import Submission
from app.ocr import get_ocr_service
from app.ocr.schemas import BoundingBox, OcrResult, TextLine

# A clean, passing label: brand/class/abv/net/address all present, warning exact.
from app.verify.schemas import GOVERNMENT_WARNING_TEXT

_PASS_LINES = [
    "OLD TOM DISTILLERY",
    "Kentucky Straight Bourbon Whiskey",
    "45% Alc./Vol. (90 Proof)",
    "750 mL",
    "Bottled by Old Tom Distillery, Bardstown, KY",
    GOVERNMENT_WARNING_TEXT,
]


def _valid_png() -> bytes:
    """A small but genuinely decodable PNG (OCR is stubbed, so content is moot)."""
    import cv2
    import numpy as np

    canvas = np.full((16, 32, 3), 255, dtype=np.uint8)
    ok, buffer = cv2.imencode(".png", canvas)
    assert ok
    return buffer.tobytes()


_TINY_PNG = _valid_png()


class _FakeOcr:
    """Stand-in OCR service returning preset lines, ignoring the image bytes.

    Mirrors the :class:`app.ocr.service.OcrService` surface the adaptive
    pipeline uses (``max_side``, ``extract(..., max_side=...)``); every call
    returns the same lines, so rescue passes are idempotent here.
    """

    max_side = 1600

    def __init__(self, texts: list[str]) -> None:
        self._texts = texts

    def extract(self, _image: object, *, max_side: int | None = None) -> OcrResult:
        box = BoundingBox(x_min=0, y_min=0, x_max=100, y_max=10)
        lines = [
            TextLine(
                text=t, confidence=0.99, polygon=[(0, 0), (100, 0), (100, 10), (0, 10)], box=box
            )
            for t in self._texts
        ]
        return OcrResult(lines=lines, elapsed_ms=12.0)


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    """A shared in-memory SQLite, schema created once, persisting across requests."""
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


def _form() -> dict[str, str]:
    return {
        "brand_name": "OLD TOM DISTILLERY",
        "source": "domestic",
        "product_type": "distilled_spirits",
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "alcohol_content_pct": "45.0",
        "alcohol_content_text": "45% Alc./Vol. (90 Proof)",
        "net_contents": "750 mL",
        "name_and_address": "Bottled by Old Tom Distillery, Bardstown, KY",
    }


def test_verify_returns_pass_verdict_and_timing(session_factory, tmp_path) -> None:
    client = _client(session_factory, _PASS_LINES, tmp_path)
    resp = client.post(
        "/api/verify",
        data=_form(),
        files={"image": ("label.png", _TINY_PNG, "image/png")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["result"]["overall"] == "pass"
    assert body["result"]["government_warning"]["verdict"] == "compliant"
    assert body["timing"]["total_ms"] >= 0
    assert body["timing"]["ocr_ms"] == 12
    assert isinstance(body["submission_id"], int)
    # Per-field results are present and keyed by the application fields.
    fields = {f["field"] for f in body["result"]["fields"]}
    assert {"brand_name", "class_type", "alcohol_content", "net_contents"} <= fields


def test_verify_persists_completed_submission(session_factory, tmp_path) -> None:
    client = _client(session_factory, _PASS_LINES, tmp_path)
    resp = client.post(
        "/api/verify", data=_form(), files={"image": ("l.png", _TINY_PNG, "image/png")}
    )
    sub_id = resp.json()["submission_id"]
    with session_factory() as db:
        row = db.scalar(select(Submission).where(Submission.id == sub_id))
        assert row is not None
        assert row.status is SubmissionStatus.COMPLETED
        assert row.result["overall"] == "pass"
        assert row.processing_ms is not None and row.processing_ms >= 0
        assert row.application_id is not None


def test_abv_mismatch_is_failed_verdict(session_factory, tmp_path) -> None:
    """A label whose ABV disagrees with the application fails (not a 500)."""
    lines = list(_PASS_LINES)
    lines[2] = "40% Alc./Vol. (80 Proof)"  # label says 40, application says 45
    client = _client(session_factory, lines, tmp_path)
    resp = client.post(
        "/api/verify", data=_form(), files={"image": ("l.png", _TINY_PNG, "image/png")}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["overall"] == "fail"
    abv = next(f for f in body["result"]["fields"] if f["field"] == "alcohol_content")
    assert abv["status"] == "mismatch"


def test_bad_image_is_422(session_factory, tmp_path) -> None:
    client = _client(session_factory, _PASS_LINES, tmp_path)
    resp = client.post(
        "/api/verify",
        data=_form(),
        files={"image": ("notimage.png", b"this is not an image", "image/png")},
    )
    assert resp.status_code == 422
    assert "readable image" in resp.json()["detail"]


def test_empty_upload_is_400(session_factory, tmp_path) -> None:
    client = _client(session_factory, _PASS_LINES, tmp_path)
    resp = client.post(
        "/api/verify", data=_form(), files={"image": ("empty.png", b"", "image/png")}
    )
    assert resp.status_code == 400


def test_unreadable_image_is_422_and_records_failure(session_factory, tmp_path) -> None:
    """A decodable image with no recognised text is a clean 422 + FAILED record."""
    client = _client(session_factory, [], tmp_path)  # fake OCR returns no lines
    resp = client.post(
        "/api/verify", data=_form(), files={"image": ("blank.png", _TINY_PNG, "image/png")}
    )
    assert resp.status_code == 422
    assert "No text" in resp.json()["detail"]
    with session_factory() as db:
        failed = db.scalars(
            select(Submission).where(Submission.status == SubmissionStatus.FAILED)
        ).all()
        assert len(failed) == 1
        assert failed[0].error


def test_missing_brand_name_is_422(session_factory, tmp_path) -> None:
    client = _client(session_factory, _PASS_LINES, tmp_path)
    form = _form()
    del form["brand_name"]
    resp = client.post("/api/verify", data=form, files={"image": ("l.png", _TINY_PNG, "image/png")})
    assert resp.status_code == 422
