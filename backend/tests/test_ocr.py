"""Tests for the RapidOCR text-extraction service.

These exercise the real ONNX models against a synthetic label fixture, so they
double as a smoke test that the vendored models load and run end-to-end without
network access.
"""

from pathlib import Path

import pytest

from app.ocr import OcrResult, get_ocr_service
from app.ocr.schemas import BoundingBox

FIXTURE = Path(__file__).parent / "fixtures" / "sample_label.png"


@pytest.fixture(scope="module")
def service():
    """A single shared OCR service for the module (engine init is expensive)."""
    return get_ocr_service()


@pytest.fixture(scope="module")
def result(service) -> OcrResult:
    return service.extract(FIXTURE)


def test_models_are_vendored_locally() -> None:
    """The ONNX models must ship in-repo so nothing is downloaded at runtime."""
    from app.ocr.service import CLS_MODEL, DET_MODEL, REC_MODEL

    for model in (DET_MODEL, REC_MODEL, CLS_MODEL):
        assert model.exists(), f"missing vendored model: {model}"


def test_extract_recovers_label_fields(result: OcrResult) -> None:
    """Core label fields are recovered from the sample image."""
    # Normalise whitespace: the recogniser occasionally inserts spaces between
    # glyphs, so collapse them before substring checks.
    text = result.full_text.upper().replace(" ", "")

    assert "OLDTOMDISTILLERY" in text
    assert "BOURBONWHISKEY" in text
    assert "750ML" in text
    assert "45%ALC" in text
    # The mandatory government warning must be detectable for compliance checks.
    assert "GOVERNMENTWARNING" in text


def test_lines_have_boxes_and_confidence(result: OcrResult) -> None:
    assert result.lines, "expected at least one detected line"
    for line in result.lines:
        assert line.text
        assert 0.0 <= line.confidence <= 1.0
        # Polygon is four corner points...
        assert len(line.polygon) == 4
        # ...and the derived box is well-formed.
        assert isinstance(line.box, BoundingBox)
        assert line.box.width > 0
        assert line.box.height > 0


def test_elapsed_is_recorded(result: OcrResult) -> None:
    assert result.elapsed_ms > 0


def test_blank_image_returns_no_lines(service) -> None:
    """A blank canvas yields an empty (not error) result."""
    import numpy as np

    blank = np.full((64, 64, 3), 255, dtype=np.uint8)
    result = service.extract(blank)
    assert result.lines == []
    assert result.full_text == ""


def test_warmup_runs(service) -> None:
    """Warmup exercises the full pipeline without raising."""
    service.warmup()
