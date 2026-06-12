"""Unit tests for the verification engine (:mod:`app.verify.engine`).

These exercise the field-routing and aggregation logic *without* running OCR:
synthetic :class:`OcrResult` objects are built from each corpus case's printed
``label`` data, so the engine sees exactly the text a perfect OCR pass would
recover. That isolates the engine's verdict logic from OCR noise and keeps the
test fast — the real-OCR end-to-end check lives in ``tests/perf``.

Because the synthetic text is what the engine *should* recover, reproducing the
golden verdict here pins the engine to the corpus' documented expectations.
"""

from __future__ import annotations

import pytest

from app.models.application import Application
from app.ocr.schemas import BoundingBox, OcrResult, TextLine
from app.verify import FieldStatus, OverallVerdict, WarningVerdict, verify_label
from tests.corpus import load_corpus

CASES = load_corpus().cases
CASE_PARAMS = [pytest.param(c, id=c.id) for c in CASES]

# Logical field key -> the label dict key(s) that carry its printed text.
_LABEL_KEYS = (
    "brand_name",
    "class_type",
    "alcohol_content_text",
    "net_contents",
    "name_and_address",
    "country_of_origin",
    "vintage",
    "government_warning",
)


def _line(text: str, top: float) -> TextLine:
    """A synthetic OCR line: the given text in a box stacked at ``top``."""
    box = BoundingBox(x_min=0.0, y_min=top, x_max=400.0, y_max=top + 20.0)
    polygon = [(0.0, top), (400.0, top), (400.0, top + 20.0), (0.0, top + 20.0)]
    return TextLine(text=text, confidence=0.99, polygon=polygon, box=box)


def _synthetic_ocr(label: dict) -> OcrResult:
    """Build an OcrResult from a corpus case's printed-label fields."""
    lines = [
        _line(str(label[key]), i * 24.0) for i, key in enumerate(_LABEL_KEYS) if label.get(key)
    ]
    return OcrResult(lines=lines, elapsed_ms=0.0)


def _application(case_application: dict) -> Application:
    """An (unsaved) Application instance from a corpus case's application dict."""
    return Application(**case_application)


@pytest.mark.parametrize("case", CASE_PARAMS)
def test_engine_reproduces_golden_overall(case) -> None:
    result = verify_label(_application(case.application), _synthetic_ocr(case.label))
    assert result.overall is OverallVerdict(case.golden.overall.value), case.golden.rationale


@pytest.mark.parametrize("case", CASE_PARAMS)
def test_engine_reproduces_golden_fields(case) -> None:
    result = verify_label(_application(case.application), _synthetic_ocr(case.label))
    got = {f.field: f.status.value for f in result.fields}
    # The engine checks exactly the fields the application supplies.
    assert set(got) == set(case.golden.fields)
    for field_key, expected in case.golden.fields.items():
        assert got[field_key] == expected.value, f"{case.id}/{field_key}"


@pytest.mark.parametrize("case", CASE_PARAMS)
def test_engine_reproduces_golden_warning(case) -> None:
    result = verify_label(_application(case.application), _synthetic_ocr(case.label))
    assert result.government_warning.verdict is WarningVerdict(case.golden.government_warning.value)


def test_summary_counts_match_fields() -> None:
    case = next(c for c in CASES if c.id == "stones_throw_case_diff")
    result = verify_label(_application(case.application), _synthetic_ocr(case.label))
    summary = result.summary
    total = summary.match + summary.soft_warning + summary.mismatch + summary.not_checked
    assert total == len(result.fields)
    assert summary.soft_warning >= 1  # the case-only brand difference


def test_field_results_carry_highlight_boxes() -> None:
    """Located fields should expose a source box for the comparison UI."""
    case = next(c for c in CASES if c.id == "old_tom_clean_pass")
    result = verify_label(_application(case.application), _synthetic_ocr(case.label))
    brand = next(f for f in result.fields if f.field == "brand_name")
    assert brand.status is FieldStatus.MATCH
    assert brand.box is not None
    assert brand.span is not None and brand.span.line_index == 0


def _brand_only_ocr(text: str, confidence: float) -> OcrResult:
    """A one-line OcrResult carrying a (mis)read of the brand at a given confidence."""
    box = BoundingBox(x_min=0.0, y_min=0.0, x_max=400.0, y_max=20.0)
    polygon = [(0.0, 0.0), (400.0, 0.0), (400.0, 20.0), (0.0, 20.0)]
    line = TextLine(text=text, confidence=confidence, polygon=polygon, box=box)
    return OcrResult(lines=[line], elapsed_ms=0.0)


def test_low_confidence_mismatch_routes_to_review() -> None:
    """A mismatch whose label text was read with low OCR confidence is flagged for
    review, not rejected — graceful degradation for stylised/curved logo fonts."""
    app = Application(brand_name="JACK DANIEL'S")
    # The ornate logo was garbled by OCR and read with low confidence.
    result = verify_label(app, _brand_only_ocr("XQGND BLLZ", confidence=0.40))
    brand = next(f for f in result.fields if f.field == "brand_name")
    assert brand.status is FieldStatus.SOFT_WARNING
    assert "low OCR confidence" in brand.reason


def test_high_confidence_mismatch_is_still_rejected() -> None:
    """Control: a confidently-read mismatch remains a hard mismatch."""
    app = Application(brand_name="JACK DANIEL'S")
    result = verify_label(app, _brand_only_ocr("JIM BEAM", confidence=0.99))
    brand = next(f for f in result.fields if f.field == "brand_name")
    assert brand.status is FieldStatus.MISMATCH


def test_unlocated_brand_mismatch_has_no_found_or_box() -> None:
    """When a free-text value can't be located (e.g. a script-font brand the OCR
    can't read), the mismatch reports "not found" rather than boxing the matcher's
    closest — and meaningless — window."""
    app = Application(brand_name="GIRO SPLENDIDO")
    # None of these lines resemble the brand; the matcher's best window is noise.
    ocr = OcrResult(
        lines=[_line("5.2% ALC./VOL.", 0.0), _line("PACKAGED ON:", 24.0)], elapsed_ms=0.0
    )
    result = verify_label(app, ocr)
    brand = next(f for f in result.fields if f.field == "brand_name")
    assert brand.status is FieldStatus.MISMATCH
    assert brand.found is None
    assert brand.box is None


def test_whitespace_merged_value_boxes_the_right_line() -> None:
    """A present net-contents value the OCR merged into one token boxes the line
    that actually carries it, not whichever window the token scorer preferred."""
    app = Application(brand_name="GIRO SPLENDIDO", net_contents="1/2 BBL (15.5 GALLONS)")
    ocr = OcrResult(
        lines=[
            _line("5.2%ALC./VOL.", 0.0),
            _line("/1/2BBL(15.5GALLONS)", 24.0),
        ],
        elapsed_ms=0.0,
    )
    result = verify_label(app, ocr)
    net = next(f for f in result.fields if f.field == "net_contents")
    assert net.status is FieldStatus.MATCH
    assert net.found is not None and "GALLONS" in net.found
    assert net.box is not None and net.box.y_min == 24.0  # the net-contents line


def test_vintage_exact_year_matches() -> None:
    """The declared vintage present verbatim on the label is a clean match."""
    from app.verify.engine import _verify_vintage

    ocr = OcrResult(lines=[_line("Laurel Creek", 0.0), _line("Vintage 2021", 24.0)], elapsed_ms=0.0)
    result = _verify_vintage("2021", ocr)
    assert result.status is FieldStatus.MATCH


def test_vintage_wrong_year_is_hard_mismatch() -> None:
    """A different printed year is a mismatch (not a fuzzy soft warning), and the
    label's actual year is surfaced for the reviewer."""
    from app.verify.engine import _verify_vintage

    ocr = OcrResult(lines=[_line("Laurel Creek", 0.0), _line("Vintage 2020", 24.0)], elapsed_ms=0.0)
    result = _verify_vintage("2021", ocr)
    assert result.status is FieldStatus.MISMATCH
    assert result.found == "2020"


# --- Regulatory semantics: class/type wording and the bottler statement --------


def _ocr_lines(*texts: str) -> OcrResult:
    return OcrResult(lines=[_line(t, float(i) * 24.0) for i, t in enumerate(texts)], elapsed_ms=0.0)


def test_class_type_wording_not_found_goes_to_review_not_fail() -> None:
    """The registry's class wording routinely differs from the label's (a wine
    prints its varietal where the filing says TABLE WHITE WINE) — absence of the
    filed wording is "could not confirm", not a violation."""
    app = Application(brand_name="GRANDFATHER VINEYARD", class_type="TABLE WHITE WINE")
    ocr = _ocr_lines("GRANDFATHER VINEYARD", "PETIT MANSENG", "750 mL")
    result = verify_label(app, ocr)
    class_type = next(f for f in result.fields if f.field == "class_type")
    assert class_type.status is FieldStatus.SOFT_WARNING
    assert "confirm" in class_type.reason


def test_class_type_printed_verbatim_still_matches() -> None:
    app = Application(brand_name="OLD TOM", class_type="Kentucky Straight Bourbon Whiskey")
    ocr = _ocr_lines("OLD TOM", "Kentucky Straight Bourbon Whiskey")
    result = verify_label(app, ocr)
    class_type = next(f for f in result.fields if f.field == "class_type")
    assert class_type.status is FieldStatus.MATCH


def test_name_address_matches_on_name_plus_city_state() -> None:
    """The label rule is name + city/state; the street and ZIP from the permit
    block are optional on the label and must not drag the verdict down."""
    app = Application(
        brand_name="GRANDFATHER VINEYARD",
        name_and_address=(
            "Grandfather Vineyard and Winery LLC, 225 VINEYARD LN, Banner Elk NC 28604"
        ),
    )
    ocr = _ocr_lines(
        "GRANDFATHER VINEYARD",
        "Produced and bottled by Grandfather Vineyard and Winery LLC",
        "Banner Elk, NC",
    )
    result = verify_label(app, ocr)
    address = next(f for f in result.fields if f.field == "name_and_address")
    assert address.status is FieldStatus.MATCH


def test_name_address_name_only_is_review() -> None:
    app = Application(
        brand_name="OLD TOM",
        name_and_address="Old Tom Distillery, 1 Barrel Way, Bardstown KY 40004",
    )
    ocr = _ocr_lines("OLD TOM", "Bottled by Old Tom Distillery")
    result = verify_label(app, ocr)
    address = next(f for f in result.fields if f.field == "name_and_address")
    assert address.status is FieldStatus.SOFT_WARNING
    assert "place" in address.reason


def test_name_address_nothing_found_is_mismatch() -> None:
    app = Application(
        brand_name="OLD TOM",
        name_and_address="Old Tom Distillery, 1 Barrel Way, Bardstown KY 40004",
    )
    ocr = _ocr_lines("OLD TOM", "45% Alc./Vol.", "750 mL")
    result = verify_label(app, ocr)
    address = next(f for f in result.fields if f.field == "name_and_address")
    assert address.status is FieldStatus.MISMATCH


def test_name_address_state_as_own_segment_parses() -> None:
    # "…, Bardstown, KY" — the state arrives as its own comma segment.
    app = Application(brand_name="OLD TOM", name_and_address="Old Tom Distillery, Bardstown, KY")
    ocr = _ocr_lines("OLD TOM", "Bottled by Old Tom Distillery, Bardstown, KY")
    result = verify_label(app, ocr)
    address = next(f for f in result.fields if f.field == "name_and_address")
    assert address.status is FieldStatus.MATCH
