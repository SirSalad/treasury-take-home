"""Tests for the Government Health Warning verifier.

Three layers:

* **Fixture strings** — the canonical statement plus the common evasions
  (missing, title-case header, reworded/truncated body) and OCR-noise tolerance.
* **OcrResult path** — the warning split across recognised lines, with the
  source line/box attached.
* **Corpus** — every golden case's printed warning must reproduce its golden
  ``WarningVerdict``, tying this verifier to the shared expectations.
"""

from __future__ import annotations

import pytest

from app.ocr.schemas import BoundingBox, OcrResult, TextLine
from app.verify import (
    GOVERNMENT_WARNING_TEXT,
    GovernmentWarningResult,
    WarningVerdict,
    verify_government_warning,
    verify_warning_from_ocr,
)
from tests.corpus import load_corpus
from tests.corpus.schema import WarningVerdict as CorpusWarningVerdict

# A title-case header (Jenny's catch): body word-perfect, header casing wrong.
TITLECASE_WARNING = GOVERNMENT_WARNING_TEXT.replace("GOVERNMENT WARNING", "Government Warning")

# Wording tampering that keeps the all-caps header: drop the second statement.
TRUNCATED_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth defects."
)


# --- Compliant ---------------------------------------------------------------


def test_exact_warning_is_compliant() -> None:
    result = verify_government_warning(GOVERNMENT_WARNING_TEXT)
    assert result.verdict is WarningVerdict.COMPLIANT
    assert result.header_all_caps is True
    assert result.similarity == 1.0
    assert result.issues == []


def test_warning_embedded_in_label_text_is_compliant() -> None:
    # Trailing label text after the warning must not dilute the match.
    text = (
        "OLD TOM GIN\n750 mL  45% Alc./Vol.\n"
        f"{GOVERNMENT_WARNING_TEXT}\nDISTILLED AND BOTTLED BY ACME, NY"
    )
    result = verify_government_warning(text)
    assert result.verdict is WarningVerdict.COMPLIANT
    assert result.similarity == 1.0


def test_warning_split_across_lines_is_compliant() -> None:
    # OCR routinely breaks the statement across several lines; normalisation of
    # the joined text must still recognise it.
    wrapped = GOVERNMENT_WARNING_TEXT.replace(". ", ".\n").replace(": ", ":\n")
    result = verify_government_warning(wrapped)
    assert result.verdict is WarningVerdict.COMPLIANT


def test_minor_ocr_noise_still_compliant() -> None:
    # A single-character OCR slip stays well above the similarity threshold.
    noisy = GOVERNMENT_WARNING_TEXT.replace("machinery", "machlnery")
    result = verify_government_warning(noisy)
    assert result.verdict is WarningVerdict.COMPLIANT
    assert result.similarity < 1.0


# --- Missing -----------------------------------------------------------------


@pytest.mark.parametrize("text", ["", "OLD TOM GIN\n750 mL 45% Alc./Vol.\nProduct of USA"])
def test_no_warning_is_missing(text: str) -> None:
    result = verify_government_warning(text)
    assert result.verdict is WarningVerdict.MISSING
    assert result.found_text is None
    assert result.header_all_caps is None
    assert result.similarity == 0.0
    assert result.issues


# --- Altered: header casing --------------------------------------------------


def test_titlecase_header_is_altered() -> None:
    result = verify_government_warning(TITLECASE_WARNING)
    assert result.verdict is WarningVerdict.ALTERED
    assert result.header_all_caps is False
    # The wording itself is untouched, so the catch is purely the header casing.
    assert result.similarity == 1.0
    assert any("all caps" in issue for issue in result.issues)


# --- Altered: wording --------------------------------------------------------


def test_truncated_warning_is_altered() -> None:
    result = verify_government_warning(TRUNCATED_WARNING)
    assert result.verdict is WarningVerdict.ALTERED
    assert result.header_all_caps is True
    assert result.similarity < 1.0
    assert any("wording" in issue for issue in result.issues)


def test_reworded_warning_is_altered() -> None:
    reworded = GOVERNMENT_WARNING_TEXT.replace(
        "may cause health problems", "is totally safe and healthy"
    )
    result = verify_government_warning(reworded)
    assert result.verdict is WarningVerdict.ALTERED


def test_threshold_is_configurable() -> None:
    # A strict threshold rejects what OCR noise would otherwise be forgiven.
    noisy = GOVERNMENT_WARNING_TEXT.replace("machinery", "machlnery")
    assert verify_government_warning(noisy, similarity_threshold=1.0).verdict is (
        WarningVerdict.ALTERED
    )


# --- Limitations are surfaced ------------------------------------------------


def test_limitations_note_bold_and_font() -> None:
    result = verify_government_warning(GOVERNMENT_WARNING_TEXT)
    assert result.limitations
    assert any("font" in note.lower() or "bold" in note.lower() for note in result.limitations)


# --- OcrResult path ----------------------------------------------------------


def _line(text: str, *, y: float) -> TextLine:
    box = BoundingBox(x_min=10.0, y_min=y, x_max=400.0, y_max=y + 20.0)
    polygon = [(10.0, y), (400.0, y), (400.0, y + 20.0), (10.0, y + 20.0)]
    return TextLine(text=text, confidence=0.95, polygon=polygon, box=box)


def test_verify_from_ocr_attaches_source_box() -> None:
    lines = [
        _line("OLD TOM GIN", y=0.0),
        _line("750 mL  45% Alc./Vol.", y=30.0),
        _line(GOVERNMENT_WARNING_TEXT, y=60.0),
    ]
    result = verify_warning_from_ocr(OcrResult(lines=lines))
    assert result.verdict is WarningVerdict.COMPLIANT
    assert result.box is not None
    assert result.span is not None
    assert result.span.line_index == 2
    assert result.box.y_min == 60.0


def test_verify_from_ocr_missing_has_no_box() -> None:
    lines = [_line("OLD TOM GIN", y=0.0), _line("750 mL", y=30.0)]
    result = verify_warning_from_ocr(OcrResult(lines=lines))
    assert result.verdict is WarningVerdict.MISSING
    assert result.box is None


def test_verify_from_ocr_header_split_across_lines() -> None:
    # "GOVERNMENT" and "WARNING" land on separate detected lines.
    lines = [
        _line("GOVERNMENT", y=60.0),
        _line("WARNING: (1) According to the Surgeon General, women should not", y=80.0),
        _line("drink alcoholic beverages during pregnancy because of the risk of", y=100.0),
        _line("birth defects. (2) Consumption of alcoholic beverages impairs your", y=120.0),
        _line("ability to drive a car or operate machinery, and may cause health", y=140.0),
        _line("problems.", y=160.0),
    ]
    result = verify_warning_from_ocr(OcrResult(lines=lines))
    assert result.verdict is WarningVerdict.COMPLIANT
    # Falls back to the line that opens the header.
    assert result.span is not None
    assert result.span.line_index == 0


# --- Corpus integration ------------------------------------------------------

_VERDICT_MAP = {
    CorpusWarningVerdict.COMPLIANT: WarningVerdict.COMPLIANT,
    CorpusWarningVerdict.ALTERED: WarningVerdict.ALTERED,
    CorpusWarningVerdict.MISSING: WarningVerdict.MISSING,
}

_CORPUS_CASES = [pytest.param(c, id=c.id) for c in load_corpus().cases]


@pytest.mark.parametrize("case", _CORPUS_CASES)
def test_corpus_warning_verdicts(case) -> None:
    """The verifier must reproduce each golden warning verdict from its label."""
    printed = case.label.get("government_warning") or ""
    result = verify_government_warning(printed)
    expected = _VERDICT_MAP[case.golden.government_warning]
    assert result.verdict is expected, (
        f"{case.id}: expected {expected} got {result.verdict} (sim={result.similarity:.2f})"
    )


def test_result_serialises_to_json() -> None:
    # The result is the contract for the comparison UI / aggregation; it must
    # round-trip as JSON.
    result = verify_government_warning(GOVERNMENT_WARNING_TEXT)
    restored = GovernmentWarningResult.model_validate_json(result.model_dump_json())
    assert restored == result
