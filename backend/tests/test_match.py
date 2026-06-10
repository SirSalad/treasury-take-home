"""Tests for fuzzy matching of brand name and class/type against OCR text.

Three layers:

* **Status grading** — the core match / soft-warning / mismatch decision over
  representative surface forms (the driving example being Dave's case-only
  ``STONE'S THROW``).
* **Robustness** — smart quotes, OCR noise, word order, and finding the value
  embedded in a larger block of label text.
* **Result shape** — score range, recovered span, and the ``OcrResult`` wrapper.
"""

from __future__ import annotations

import pytest

from app.match import (
    FieldMatch,
    FuzzyFieldName,
    MatchStatus,
    match_field,
    match_from_ocr,
)
from app.ocr.schemas import BoundingBox, OcrResult, TextLine

BRAND = FuzzyFieldName.BRAND_NAME
CLASS = FuzzyFieldName.CLASS_TYPE


def _status(field: FuzzyFieldName, expected: str, text: str) -> MatchStatus:
    return match_field(field, expected, text).status


# --- Exact and whitespace-equivalent matches ---------------------------------


@pytest.mark.parametrize(
    "expected,text",
    [
        ("Stone's Throw", "Stone's Throw"),
        ("Stone's Throw", "  Stone's   Throw  "),
        ("Kentucky Straight Bourbon Whiskey", "Kentucky Straight Bourbon Whiskey"),
        ("London Dry Gin", "London Dry Gin"),
    ],
)
def test_exact_match(expected: str, text: str) -> None:
    assert _status(BRAND, expected, text) is MatchStatus.MATCH


def test_smart_quote_difference_is_a_match() -> None:
    # Curly apostrophe vs straight apostrophe is not a real difference.
    assert _status(BRAND, "Stone's Throw", "Stone’s Throw") is MatchStatus.MATCH


# --- Soft warnings: human-equivalent differences -----------------------------


def test_case_only_difference_is_soft_warning() -> None:
    # Dave's nuance: application "Stone's Throw" vs label "STONE'S THROW".
    result = match_field(BRAND, "Stone's Throw", "STONE'S THROW")
    assert result.status is MatchStatus.SOFT_WARNING
    assert "case" in result.reason.lower()
    # The value is clearly present, so the score stays high.
    assert result.score >= 0.99


def test_punctuation_only_difference_is_soft_warning() -> None:
    # Dropped apostrophe — same words, cosmetic difference.
    assert _status(BRAND, "Stone's Throw", "Stones Throw") is MatchStatus.SOFT_WARNING


def test_near_miss_is_soft_warning() -> None:
    # A one-character OCR slip lands in the mid band, not a clean pass.
    status = _status(BRAND, "Highland Mist", "Highland Mest")
    assert status is MatchStatus.SOFT_WARNING


# --- Mismatches --------------------------------------------------------------


@pytest.mark.parametrize(
    "expected,text",
    [
        ("Stone's Throw", "Silver Creek"),
        ("London Dry Gin", "Kentucky Straight Bourbon Whiskey"),
        ("Coastal Vines", "Highland Mist India Pale Ale"),
    ],
)
def test_clear_mismatch(expected: str, text: str) -> None:
    assert _status(BRAND, expected, text) is MatchStatus.MISMATCH


def test_empty_text_is_mismatch() -> None:
    assert _status(BRAND, "Stone's Throw", "") is MatchStatus.MISMATCH


def test_empty_expected_is_mismatch() -> None:
    assert _status(BRAND, "", "Stone's Throw") is MatchStatus.MISMATCH


# --- Embedded in a larger label block ----------------------------------------


def test_finds_value_within_full_label_text() -> None:
    text = "STONE'S THROW\nLondon Dry Gin\nHand crafted in small batches\n750 mL  •  40% Alc./Vol."
    # Brand present case-shifted -> soft warning; class/type exact -> match.
    assert _status(BRAND, "Stone's Throw", text) is MatchStatus.SOFT_WARNING
    assert _status(CLASS, "London Dry Gin", text) is MatchStatus.MATCH


def test_exact_occurrence_anywhere_outranks_cosmetic_one() -> None:
    # If the value is printed correctly *somewhere* (here in the bottler line),
    # that exact occurrence wins over a louder all-caps display -> clean match.
    text = "STONE'S THROW\nDistilled by Stone's Throw Spirits, Portland OR"
    assert _status(BRAND, "Stone's Throw", text) is MatchStatus.MATCH


def test_class_type_split_across_lines() -> None:
    # The detector often breaks a long class/type across lines.
    text = "Kentucky Straight\nBourbon Whiskey\n45% Alc./Vol."
    assert _status(CLASS, "Kentucky Straight Bourbon Whiskey", text) is MatchStatus.MATCH


def test_word_order_difference_still_found() -> None:
    # Token-level scoring tolerates reordering (graded as a soft warning since
    # the surface form differs).
    status = _status(CLASS, "Straight Bourbon Whiskey", "Whiskey Bourbon Straight")
    assert status in {MatchStatus.MATCH, MatchStatus.SOFT_WARNING}


# --- Result shape ------------------------------------------------------------


def test_result_carries_expected_and_score() -> None:
    result = match_field(BRAND, "Stone's Throw", "STONE'S THROW")
    assert isinstance(result, FieldMatch)
    assert result.field is BRAND
    assert result.expected == "Stone's Throw"
    assert 0.0 <= result.score <= 1.0
    assert result.matched_text  # the recovered span is populated


def test_match_from_ocr_uses_full_text() -> None:
    box = BoundingBox(x_min=0, y_min=0, x_max=10, y_max=5)
    result = OcrResult(
        lines=[
            TextLine(text="STONE'S THROW", confidence=0.9, polygon=[(0, 0)], box=box),
            TextLine(text="London Dry Gin", confidence=0.9, polygon=[(0, 0)], box=box),
        ]
    )
    assert match_from_ocr(BRAND, "Stone's Throw", result).status is MatchStatus.SOFT_WARNING
    assert match_from_ocr(CLASS, "London Dry Gin", result).status is MatchStatus.MATCH
