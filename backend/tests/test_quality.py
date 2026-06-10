"""Tests for OCR-derived image-quality / retake guidance."""

from __future__ import annotations

from app.ocr.quality import assess_image_quality
from app.ocr.schemas import BoundingBox, OcrResult, TextLine


def _line(text: str, confidence: float) -> TextLine:
    box = BoundingBox(x_min=0.0, y_min=0.0, x_max=100.0, y_max=20.0)
    poly = [(0.0, 0.0), (100.0, 0.0), (100.0, 20.0), (0.0, 20.0)]
    return TextLine(text=text, confidence=confidence, polygon=poly, box=box)


def test_clean_read_is_ok() -> None:
    ocr = OcrResult(
        lines=[
            _line("OLD TOM DISTILLERY", 0.98),
            _line("Kentucky Bourbon", 0.97),
            _line("45% Alc./Vol.", 0.96),
            _line("750 mL", 0.99),
        ],
        elapsed_ms=0.0,
    )
    q = assess_image_quality(ocr)
    assert q.level == "ok"
    assert q.message is None


def test_no_text_is_low_with_retake_prompt() -> None:
    q = assess_image_quality(OcrResult(lines=[], elapsed_ms=0.0))
    assert q.level == "low"
    assert q.text_regions == 0
    assert "retake" in (q.message or "").lower()


def test_garbled_low_confidence_read_is_low() -> None:
    # A blurry photo where much of the recognised text is low-confidence.
    ocr = OcrResult(
        lines=[_line("0LD T0M D1ST", 0.41), _line("Kentcky B0urbn", 0.38), _line("45% Alc", 0.95)],
        elapsed_ms=0.0,
    )
    q = assess_image_quality(ocr)
    assert q.level == "low"
    assert q.message and "retake" in q.message.lower()


def test_very_little_text_is_low() -> None:
    # A tilted/foreshortened bad photo where OCR recovers only a few characters,
    # even at decent confidence, should prompt a retake (real Maker's Mark case).
    ocr = OcrResult(
        lines=[_line("Make", 0.94), _line("K", 0.85), _line("WHIIS", 0.80)], elapsed_ms=0.0
    )
    q = assess_image_quality(ocr)
    assert q.level == "low"
