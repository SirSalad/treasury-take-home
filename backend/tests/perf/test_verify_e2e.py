"""Real-OCR end-to-end test of ``POST /api/verify`` over the corpus.

Posts each corpus label image through the HTTP endpoint with its expected COLA
fields and asserts the endpoint (a) reproduces the golden *overall* verdict and
(b) returns inside the 5-second SLA. This is the integration counterpart to the
fast, OCR-stubbed ``tests/test_api_verify.py`` and the synthetic-OCR
``tests/test_engine.py``: together they cover wiring, verdict logic, and latency.

Marked ``e2e`` (real OCR is slow); deselect with ``-m 'not e2e'``. The OCR engine
is warmed once up front so first-call ONNX session build never lands in a timed
request — the same discipline the latency harness uses.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - register tables on Base.metadata
from app.config import Settings, get_settings
from app.db import Base, get_db
from app.main import app
from app.ocr import get_ocr_service
from tests.corpus import load_corpus

pytestmark = pytest.mark.e2e

CASES = load_corpus().cases
CASE_PARAMS = [pytest.param(c, id=c.id) for c in CASES]

# Fields the verify endpoint accepts from the application dict.
_ACCEPTED_FORM_FIELDS = {
    "brand_name",
    "source",
    "product_type",
    "class_type",
    "alcohol_content_pct",
    "alcohol_content_text",
    "net_contents",
    "name_and_address",
    "country_of_origin",
    "vintage",
    "serial_number",
    "fanciful_name",
    "appellation",
}

_BUDGET_MS = float(os.environ.get("PERF_BUDGET_MS", "5000"))
# Best-of-N at the HTTP layer, mirroring the pipeline harness: on a shared CI box
# a noisy neighbour can triple a single sample, so we keep the least-perturbed
# run. The authoritative SLA gate is still tests/perf/test_latency_sla.py.
_LATENCY_ATTEMPTS = int(os.environ.get("E2E_LATENCY_ATTEMPTS", "3"))


@pytest.fixture(scope="module")
def client(tmp_path_factory) -> Iterator[TestClient]:
    """A TestClient backed by a throwaway SQLite DB and the real (warmed) OCR."""
    upload_dir = tmp_path_factory.mktemp("uploads")
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def _override_db() -> Iterator[Session]:
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_settings] = lambda: Settings(
        upload_dir=str(upload_dir), ocr_warmup=False
    )

    get_ocr_service().warmup()  # pay session-build cost outside the timed requests
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _form(application: dict) -> dict[str, str]:
    return {k: str(v) for k, v in application.items() if k in _ACCEPTED_FORM_FIELDS}


@pytest.mark.parametrize("case", CASE_PARAMS)
def test_endpoint_reproduces_golden_within_budget(case, client) -> None:
    image_bytes = case.image_path().read_bytes()

    def _post():
        resp = client.post(
            "/api/verify",
            data=_form(case.application),
            files={"image": (f"{case.id}.png", image_bytes, "image/png")},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()

    body = _post()

    # Correctness: the endpoint reproduces the golden verdicts through real OCR.
    assert body["result"]["overall"] == case.golden.overall.value, (
        f"{case.id}: got {body['result']['overall']}, expected "
        f"{case.golden.overall.value} ({case.golden.rationale})"
    )
    assert body["result"]["government_warning"]["verdict"] == case.golden.government_warning.value
    assert body["status"] == "completed"
    assert isinstance(body["submission_id"], int)

    # Latency: best-of-N reported time stays under the 5s SLA. Re-run only if the
    # first (already-warm) sample was over budget, to avoid paying extra OCR when
    # the box isn't loaded.
    best_ms = body["timing"]["total_ms"]
    for _ in range(_LATENCY_ATTEMPTS - 1):
        if best_ms < _BUDGET_MS:
            break
        best_ms = min(best_ms, _post()["timing"]["total_ms"])
    assert best_ms < _BUDGET_MS, (
        f"{case.id}: best of {_LATENCY_ATTEMPTS} was {best_ms} ms, "
        f"over the {_BUDGET_MS:.0f} ms budget"
    )
