"""Tests for the rule-based field extractors.

Two layers:

* **Fixture strings** — table-driven unit tests over the surface forms each rule
  must handle (and forms it must *not* spuriously match).
* **Real OCR output** — running the extractors over the recognised text of the
  committed sample label, so the rules are exercised against genuine OCR noise.
"""

from pathlib import Path

import pytest

from app.extract import (
    ExtractionResult,
    FieldName,
    extract_fields,
    extract_from_text,
)
from app.ocr import get_ocr_service
from app.ocr.schemas import BoundingBox, OcrResult, TextLine

FIXTURE = Path(__file__).parent / "fixtures" / "sample_label.png"


def _best_value(text: str, field: FieldName) -> str | None:
    result = ExtractionResult(candidates=extract_from_text(text))
    best = result.best(field)
    return best.value if best else None


# --- ABV ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("45% Alc./Vol. (90 Proof)", "45"),
        ("ALC. 45% BY VOL.", "45"),
        ("Alcohol 45.5% by volume", "45.5"),
        ("40% ALC/VOL", "40"),
        ("7.5% Alc. by Vol.", "7.5"),
        # British/EU spirits omit "Alc." — a bare "Vol" anchor (as on a real
        # Jack Daniel's 70cl bottle: "70cl 40% Vol.").
        ("70cl 40% Vol.", "40"),
        ("40% vol", "40"),
        # Craft-beer "ABV" anchor, both orders (real label: Beach Ball "5.1% ABV").
        ("5.1% ABV", "5.1"),
        ("5.1%ABV", "5.1"),
        ("ABV: 5.1%", "5.1"),
        # Spelled-out form with OCR-stripped spaces (real label: Unruly Spirits).
        ("40%ALCOHOLBYVOLUME", "40"),
        ("40% ALCOHOL BY VOLUME", "40"),
        # OCR digit confusion: capital I / lowercase l read where a 1 was
        # printed (real label: Anthony's "I3%ALC/VOL" in a stylised typeface).
        ("I3%ALC/VOL", "13"),
        ("l2% Alc. by Vol.", "12"),
    ],
)
def test_abv_surface_forms(text: str, expected: str) -> None:
    assert _best_value(text, FieldName.ABV) == expected


def test_digit_confusion_fix_does_not_touch_words() -> None:
    # The I→1 normalisation applies only where the letter abuts a digit; words
    # like "Illinois" (or a roman-numeral "Vol. II") are never rewritten.
    assert _best_value("Bottled in Illinois 45% Alc./Vol.", FieldName.ABV) == "45"
    assert _best_value("Vol. II of the series", FieldName.ABV) is None


def test_abv_ignores_unanchored_percentage() -> None:
    # A bare percentage with no alcohol anchor is not ABV.
    assert _best_value("Save 25% today", FieldName.ABV) is None


def test_abv_does_not_capture_proof_number() -> None:
    # "90" belongs to proof, not ABV; only "45" is anchored to Alc./Vol.
    assert _best_value("45% Alc./Vol. (90 Proof)", FieldName.ABV) == "45"


# --- Proof -------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("90 Proof", "90"),
        ("45% Alc./Vol. (90 Proof)", "90"),
        ("100° Proof", "100"),
        ("Proof: 86", "86"),
    ],
)
def test_proof_surface_forms(text: str, expected: str) -> None:
    assert _best_value(text, FieldName.PROOF) == expected


# --- Cross-line assembly (unit-caption adjacency, proof→ABV) -------------------


def _ocr_line(text: str, *, x: float, y: float, w: float = 80.0, h: float = 20.0) -> TextLine:
    polygon = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    box = BoundingBox.from_polygon(polygon)
    return TextLine(text=text, confidence=0.95, polygon=polygon, box=box)


def test_abv_assembled_from_number_next_to_caption() -> None:
    # Stylised spirits layout (real label: Land Run): a big "50" with a small
    # "ALC/VOL" caption beside it, detected as separate lines.
    ocr = OcrResult(
        lines=[
            _ocr_line("STRAIGHT BOURBON WHISKEY", x=10, y=0),
            _ocr_line("50", x=10, y=40, w=60, h=50),
            _ocr_line("ALC/VOL", x=75, y=70),
        ]
    )
    best = extract_fields(ocr).best(FieldName.ABV)
    assert best is not None
    assert best.value == "50"


def test_adjacency_ignores_far_away_numbers() -> None:
    # A bare number elsewhere on the label must not be glued to the caption.
    ocr = OcrResult(
        lines=[
            _ocr_line("12", x=10, y=0),  # plausible as an ABV, but far above
            _ocr_line("ALC/VOL", x=75, y=700),
        ]
    )
    assert extract_fields(ocr).best(FieldName.ABV) is None


def test_adjacency_defers_to_inline_statement() -> None:
    # When an inline ABV exists, adjacency must not add a competing candidate.
    ocr = OcrResult(
        lines=[
            _ocr_line("45% Alc./Vol.", x=10, y=0),
            _ocr_line("50", x=10, y=40),
            _ocr_line("ALC/VOL", x=75, y=45),
        ]
    )
    candidates = extract_fields(ocr).for_field(FieldName.ABV)
    assert [c.value for c in candidates] == ["45"]


def test_abv_derived_from_proof_when_absent() -> None:
    # US proof is exactly twice ABV (27 CFR 5.65): "80 PROOF" pins ABV at 40,
    # at a discounted confidence since it is derived rather than read.
    ocr = OcrResult(lines=[_ocr_line("80 PROOF", x=10, y=0)])
    extraction = extract_fields(ocr)
    best = extraction.best(FieldName.ABV)
    assert best is not None
    assert best.value == "40"
    proof = extraction.best(FieldName.PROOF)
    assert proof is not None
    assert best.confidence < proof.confidence


def test_abv_not_derived_when_directly_stated() -> None:
    ocr = OcrResult(lines=[_ocr_line("45% Alc./Vol. (90 Proof)", x=10, y=0)])
    candidates = extract_fields(ocr).for_field(FieldName.ABV)
    assert [c.value for c in candidates] == ["45"]


# --- Net contents ------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("750 mL", "750 mL"),
        ("750ML", "750 mL"),
        ("1.75 L", "1.75 L"),
        ("1 Liter", "1 L"),
        ("12 FL OZ", "12 fl oz"),
        ("700 milliliters", "700 mL"),
        ("1,5 L", "1.5 L"),
    ],
)
def test_net_contents_surface_forms(text: str, expected: str) -> None:
    assert _best_value(text, FieldName.NET_CONTENTS) == expected


def test_net_contents_does_not_match_vol_in_abv() -> None:
    # The "l" in "Vol" must not be read as a litre unit.
    assert _best_value("45% Alc./Vol.", FieldName.NET_CONTENTS) is None


# --- Country of origin -------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Product of France", "France"),
        ("Distilled in Scotland", "Scotland"),
        ("Imported from Mexico", "Mexico"),
        ("Country of Origin: Japan", "Japan"),
        ("Product of the United Kingdom", "the United Kingdom"),
    ],
)
def test_country_surface_forms(text: str, expected: str) -> None:
    assert _best_value(text, FieldName.COUNTRY_OF_ORIGIN) == expected


def test_country_label_outranks_phrase() -> None:
    # An explicit label is the higher-confidence signal.
    text = "Country of Origin: Italy"
    assert _best_value(text, FieldName.COUNTRY_OF_ORIGIN) == "Italy"


# --- Bottler / producer address ----------------------------------------------


@pytest.mark.parametrize(
    "text,phrase",
    [
        ("Bottled by Old Tom Distillery, Louisville, KY", "Bottled by"),
        ("Distilled and bottled by ACME Co., Bardstown KY", "Distilled and bottled by"),
        ("Imported by Global Spirits Inc., New York, NY", "Imported by"),
        ("Produced and bottled for The Whiskey Shop, OR", "Produced and bottled for"),
    ],
)
def test_bottler_captures_phrase_and_address(text: str, phrase: str) -> None:
    candidate = ExtractionResult(candidates=extract_from_text(text)).best(FieldName.BOTTLER_ADDRESS)
    assert candidate is not None
    assert candidate.value.lower().startswith(phrase.lower())
    # The address text after the phrase is retained.
    assert candidate.value.lower() != phrase.lower()


def test_bottler_absent_when_no_signal_phrase() -> None:
    assert _best_value("Old Tom Distillery", FieldName.BOTTLER_ADDRESS) is None


# --- Source positions --------------------------------------------------------


def test_candidate_records_char_span() -> None:
    text = "Net contents 750 mL per bottle"
    candidate = ExtractionResult(candidates=extract_from_text(text)).best(FieldName.NET_CONTENTS)
    assert candidate is not None
    assert text[candidate.span.start : candidate.span.end] == candidate.text


def test_extract_from_text_records_line_index() -> None:
    candidates = extract_from_text("750 mL", line_index=3)
    assert candidates
    assert all(c.span.line_index == 3 for c in candidates)


# --- Real OCR output ---------------------------------------------------------


@pytest.fixture(scope="module")
def ocr_result():
    return get_ocr_service().extract(FIXTURE)


@pytest.fixture(scope="module")
def extracted(ocr_result) -> ExtractionResult:
    return extract_fields(ocr_result)


def test_extracts_abv_from_real_ocr(extracted: ExtractionResult) -> None:
    best = extracted.best(FieldName.ABV)
    assert best is not None
    assert best.value == "45"


def test_extracts_proof_from_real_ocr(extracted: ExtractionResult) -> None:
    best = extracted.best(FieldName.PROOF)
    assert best is not None
    assert best.value == "90"


def test_extracts_net_contents_from_real_ocr(extracted: ExtractionResult) -> None:
    best = extracted.best(FieldName.NET_CONTENTS)
    assert best is not None
    assert best.value == "750 mL"


def test_real_ocr_candidates_carry_line_context(extracted: ExtractionResult) -> None:
    # Every candidate from an OcrResult should trace back to a line and a box.
    assert extracted.candidates
    for candidate in extracted.candidates:
        assert candidate.span.line_index is not None
        assert candidate.box is not None
        assert candidate.box.width > 0
