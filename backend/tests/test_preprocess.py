"""Tests for the OCR preprocessing step (decode + resolution cap).

Fast, model-free unit tests: they exercise the geometry and decode paths without
touching the ONNX engine. The end-to-end timing of preprocess+OCR lives in
``tests/perf``.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from app.ocr.preprocess import (
    DEFAULT_MAX_SIDE,
    decode_image,
    downscale_to_max_side,
    preprocess_image,
)

CORPUS_IMAGE = Path(__file__).parent / "corpus" / "images" / "old_tom_clean_pass.png"


def _canvas(h: int, w: int) -> np.ndarray:
    return np.full((h, w, 3), 255, dtype=np.uint8)


def test_downscale_caps_longest_side() -> None:
    out = downscale_to_max_side(_canvas(1000, 4000), max_side=1600)
    assert max(out.shape[:2]) == 1600
    # Aspect ratio preserved (4:1).
    assert out.shape[1] == 1600 and out.shape[0] == 400


def test_downscale_is_noop_when_within_cap() -> None:
    img = _canvas(680, 900)
    out = downscale_to_max_side(img, max_side=1600)
    # Same array returned untouched — small labels keep full fidelity.
    assert out is img


def test_downscale_portrait_caps_height() -> None:
    out = downscale_to_max_side(_canvas(4000, 1000), max_side=1600)
    assert out.shape[0] == 1600 and out.shape[1] == 400


def test_decode_passes_ndarray_through() -> None:
    img = _canvas(10, 10)
    assert decode_image(img) is img


def test_decode_bytes_roundtrip() -> None:
    img = _canvas(20, 30)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    decoded = decode_image(buf.tobytes())
    assert decoded.shape == img.shape


def test_decode_path_reads_corpus_image() -> None:
    decoded = decode_image(CORPUS_IMAGE)
    assert decoded.shape[:2] == (900, 680)


def test_decode_bad_bytes_raises() -> None:
    with pytest.raises(ValueError):
        decode_image(b"not an image")


def test_decode_missing_file_raises() -> None:
    with pytest.raises(ValueError):
        decode_image("/nonexistent/label.png")


def test_preprocess_decodes_and_caps() -> None:
    img = _canvas(2000, 3000)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    out = preprocess_image(buf.tobytes(), max_side=1000)
    assert max(out.shape[:2]) == 1000


def test_default_max_side_leaves_corpus_untouched() -> None:
    decoded = decode_image(CORPUS_IMAGE)
    out = preprocess_image(CORPUS_IMAGE, max_side=DEFAULT_MAX_SIDE)
    assert out.shape == decoded.shape
