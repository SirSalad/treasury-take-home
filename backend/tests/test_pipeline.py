"""Tests for the adaptive multi-pass verification pipeline.

Three layers:

* **Geometry** — the rotation mappers must round-trip a point exactly, so boxes
  from rescue passes always land on the original upload.
* **Scripted OCR** — a fake service with per-call outputs exercises the rescue
  triggers and the best-verdict merge deterministically.
* **Real OCR end-to-end** — a synthetic label rendered sideways must be rescued
  by the rotation pass, and a tampered warning must stay altered through every
  rescue (the passes re-read pixels; they cannot invent compliance).
"""

from __future__ import annotations

import cv2
import numpy as np

from app.api.schemas import ApplicationInput
from app.ocr.schemas import BoundingBox, OcrResult, TextLine
from app.verify import GOVERNMENT_WARNING_TEXT, FieldStatus, WarningVerdict
from app.verify.pipeline import _remap_result, _rotations, verify_label_image

# --- Geometry: rotation mappers ------------------------------------------------


def _line_at(text: str, x: float, y: float, w: float = 50.0, h: float = 10.0) -> TextLine:
    polygon = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    box = BoundingBox.from_polygon(polygon)
    return TextLine(text=text, confidence=0.9, polygon=polygon, box=box)


def test_rotation_mappers_round_trip() -> None:
    # An asymmetric canvas so axis mix-ups cannot cancel out. A point at
    # original (x, y) lands at (y, W-1-x) in the CCW frame and (H-1-y, x) in
    # the CW frame; each mapper must take the frame point back exactly.
    image = np.zeros((40, 100, 3), dtype=np.uint8)  # H=40, W=100
    x, y = 30.0, 10.0
    frames = list(_rotations(image))
    (ccw_img, ccw_map), (cw_img, cw_map) = frames
    assert ccw_img.shape[:2] == (100, 40)
    assert ccw_map(y, 100 - 1 - x) == (x, y)
    assert cw_map(40 - 1 - y, x) == (x, y)


def test_remap_result_rebuilds_boxes_from_mapped_polygons() -> None:
    image = np.zeros((40, 100, 3), dtype=np.uint8)
    _, mapper = next(iter(_rotations(image)))
    line = _line_at("XYZ", x=5.0, y=8.0)
    remapped = _remap_result(OcrResult(lines=[line]), mapper)
    assert remapped.lines[0].text == "XYZ"
    expected = [mapper(px, py) for px, py in line.polygon]
    assert remapped.lines[0].polygon == expected
    box = remapped.lines[0].box
    assert (box.x_min, box.y_min) == (
        min(p[0] for p in expected),
        min(p[1] for p in expected),
    )


# --- Scripted OCR: rescue trigger + merge ---------------------------------------


class _ScriptedOcr:
    """Fake OCR returning a fixed result per call, recording how it was called."""

    max_side = 1600

    def __init__(self, results: list[OcrResult]) -> None:
        self._results = results
        self.calls = 0

    def extract(self, _image: object, *, max_side: int | None = None) -> OcrResult:
        result = self._results[min(self.calls, len(self._results) - 1)]
        self.calls += 1
        return result


def _application() -> ApplicationInput:
    return ApplicationInput(brand_name="OLD TOM DISTILLERY", alcohol_content_pct=45.0)


def _blank_image() -> np.ndarray:
    return np.full((60, 120, 3), 255, dtype=np.uint8)


def test_rotation_rescue_merges_best_verdicts() -> None:
    # Pass 1 reads only the brand (warning missing -> rescue fires); the first
    # rotated pass reads the warning and ABV. The merge must keep the brand
    # match from pass 1 and take the warning/ABV from the rescue.
    first = OcrResult(lines=[_line_at("OLD TOM DISTILLERY", 0, 0)])
    rotated = OcrResult(
        lines=[
            _line_at("45% Alc./Vol.", 0, 0),
            _line_at(GOVERNMENT_WARNING_TEXT, 0, 20),
        ]
    )
    ocr = _ScriptedOcr([first, rotated])
    result, primary = verify_label_image(_application(), _blank_image(), ocr=ocr)

    assert primary is not None and len(primary.lines) == 1
    assert result.government_warning.verdict is WarningVerdict.COMPLIANT
    by_field = {f.field: f.status for f in result.fields}
    assert by_field["brand_name"] in (FieldStatus.MATCH, FieldStatus.SOFT_WARNING)
    assert by_field["alcohol_content"] is FieldStatus.MATCH


def test_clean_label_stays_single_pass() -> None:
    # Everything verifies on the first read: no rescue OCR calls are paid.
    clean = OcrResult(
        lines=[
            _line_at("OLD TOM DISTILLERY", 0, 0),
            _line_at("45% Alc./Vol.", 0, 20),
            _line_at(GOVERNMENT_WARNING_TEXT, 0, 40),
        ]
    )
    ocr = _ScriptedOcr([clean])
    result, _ = verify_label_image(_application(), _blank_image(), ocr=ocr)
    assert result.government_warning.verdict is WarningVerdict.COMPLIANT
    assert ocr.calls == 1


def test_truly_missing_warning_stays_missing() -> None:
    # No pass ever reads a warning: the rescues run and change nothing.
    no_warning = OcrResult(
        lines=[_line_at("OLD TOM DISTILLERY", 0, 0), _line_at("45% Alc./Vol.", 0, 20)]
    )
    ocr = _ScriptedOcr([no_warning])
    result, _ = verify_label_image(_application(), _blank_image(), ocr=ocr)
    assert result.government_warning.verdict is WarningVerdict.MISSING
    assert ocr.calls >= 3  # pass 1 + both rotation rescues were attempted


# --- Real OCR end-to-end ---------------------------------------------------------


def _render_label(warning_text: str) -> np.ndarray:
    """A clean synthetic label: brand, ABV, net contents, wrapped warning."""
    canvas = np.full((640, 1000, 3), 255, dtype=np.uint8)

    def put(text: str, y: int, scale: float, thickness: int = 2) -> None:
        cv2.putText(canvas, text, (40, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thickness)

    put("OLD TOM DISTILLERY", 80, 1.4, 3)
    put("Kentucky Straight Bourbon Whiskey", 140, 0.9)
    put("45% Alc./Vol. (90 Proof)   750 mL", 200, 0.9)
    words = warning_text.split()
    line, y = "", 300
    for word in words:
        if len(line) + len(word) > 55:
            put(line, y, 0.75, 2)
            line, y = "", y + 40
        line = f"{line} {word}".strip()
    if line:
        put(line, y, 0.75, 2)
    return canvas


def test_sideways_label_rescued_by_rotation_pass() -> None:
    # The whole label printed 90 deg to the artwork (a can wrap): the first pass
    # sees nothing useful, the rotation rescue recovers every field, and the
    # merged boxes land inside the original (rotated) upload.
    label = _render_label(GOVERNMENT_WARNING_TEXT)
    sideways = cv2.rotate(label, cv2.ROTATE_90_CLOCKWISE)
    result, _ = verify_label_image(_application(), sideways)

    assert result.government_warning.verdict is WarningVerdict.COMPLIANT
    by_field = {f.field: f.status for f in result.fields}
    assert by_field["alcohol_content"] is FieldStatus.MATCH
    assert by_field["brand_name"] in (FieldStatus.MATCH, FieldStatus.SOFT_WARNING)

    height, width = sideways.shape[:2]
    boxes = [f.box for f in result.fields if f.box is not None]
    assert boxes, "rescued fields should carry remapped boxes"
    for box in boxes + ([result.government_warning.box] if result.government_warning.box else []):
        assert -1.0 <= box.x_min <= box.x_max <= width + 1.0
        assert -1.0 <= box.y_min <= box.y_max <= height + 1.0


def test_tampered_warning_not_rescued_into_compliance() -> None:
    # A dropped second clause is tampering; however many times the pipeline
    # re-reads the pixels, the verdict must stay non-compliant.
    tampered = GOVERNMENT_WARNING_TEXT.replace(
        " (2) Consumption of alcoholic beverages impairs your ability to drive a "
        "car or operate machinery, and may cause health problems.",
        "",
    )
    sideways = cv2.rotate(_render_label(tampered), cv2.ROTATE_90_CLOCKWISE)
    result, _ = verify_label_image(_application(), sideways)
    assert result.government_warning.verdict is not WarningVerdict.COMPLIANT
