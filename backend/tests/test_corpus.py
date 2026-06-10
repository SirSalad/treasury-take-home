"""Integrity tests for the labelled test-label corpus.

These do not run OCR or the (not-yet-built) verification engine. They guard the
corpus itself: the committed manifest parses, stays in sync with the case
source, references real images, uses values the ORM accepts, and carries golden
verdicts that are internally consistent with the label-vs-application data they
describe. Downstream extractor/verify/perf tests build on this foundation.
"""

from __future__ import annotations

import pytest

from app.models.application import Application
from app.models.enums import ProductSource, ProductType
from tests.corpus import FieldVerdict, OverallVerdict, WarningVerdict, load_corpus
from tests.corpus.cases import build_manifest
from tests.corpus.schema import GOVERNMENT_WARNING_TEXT

CORPUS = load_corpus()
CASES = CORPUS.cases

# Expose each case to parametrized tests with a readable id.
CASE_PARAMS = [pytest.param(c, id=c.id) for c in CASES]


def test_corpus_is_non_trivial() -> None:
    assert len(CASES) >= 5, "corpus should cover the main verdict scenarios"


def test_manifest_matches_case_source() -> None:
    """The committed manifest must equal a freshly built one (no drift).

    If this fails, someone edited ``cases.py`` without running
    ``python -m tests.corpus.generate`` to regenerate ``manifest.json``.
    """
    assert CORPUS.to_dict() == build_manifest().to_dict()


def test_case_ids_unique() -> None:
    ids = [c.id for c in CASES]
    assert len(ids) == len(set(ids)), "duplicate case ids"


@pytest.mark.parametrize("case", CASE_PARAMS)
def test_image_exists_and_non_empty(case) -> None:
    path = case.image_path()
    assert path.exists(), f"missing corpus image: {path}"
    # A blank canvas would be a few hundred bytes; real labels are larger.
    assert path.stat().st_size > 2_000, f"suspiciously small image: {path}"


@pytest.mark.parametrize("case", CASE_PARAMS)
def test_application_fields_valid(case) -> None:
    """Expected application data uses values the ORM model accepts."""
    app = case.application
    # Enum-backed columns must hold valid members.
    ProductSource(app["source"])
    ProductType(app["product_type"])
    assert app["brand_name"], "brand_name is required on the application"
    # Every application key must be a real Application column.
    columns = set(Application.__table__.columns.keys())
    unknown = set(app) - columns
    assert not unknown, f"unknown application fields: {unknown}"
    # Imported product should declare a country of origin.
    if app["source"] == ProductSource.IMPORTED:
        assert app.get("country_of_origin"), "imported product needs country_of_origin"


@pytest.mark.parametrize("case", CASE_PARAMS)
def test_golden_field_keys_align_with_application(case) -> None:
    """Each checked field maps to a real application field (alias for ABV)."""
    app_keys = set(case.application)
    for field_key in case.golden.fields:
        # 'alcohol_content' is the logical name for the ABV pair of columns.
        if field_key == "alcohol_content":
            assert "alcohol_content_text" in app_keys or "alcohol_content_pct" in app_keys
        else:
            assert field_key in app_keys, f"golden field {field_key!r} not in application"


@pytest.mark.parametrize("case", CASE_PARAMS)
def test_overall_verdict_consistent_with_details(case) -> None:
    """The overall roll-up must follow from the per-field + warning verdicts.

    Rules: a missing/altered warning or any field mismatch -> FAIL; otherwise a
    soft warning -> WARNING; otherwise PASS. This pins the golden data to a
    coherent aggregation the engine can be tested against.
    """
    g = case.golden
    has_mismatch = any(v is FieldVerdict.MISMATCH for v in g.fields.values())
    has_soft = any(v is FieldVerdict.SOFT_WARNING for v in g.fields.values())
    warning_bad = g.government_warning in (WarningVerdict.ALTERED, WarningVerdict.MISSING)

    if has_mismatch or warning_bad:
        expected = OverallVerdict.FAIL
    elif has_soft:
        expected = OverallVerdict.WARNING
    else:
        expected = OverallVerdict.PASS
    assert g.overall is expected, f"{case.id}: overall {g.overall} but details imply {expected}"


@pytest.mark.parametrize("case", CASE_PARAMS)
def test_label_vs_application_supports_field_verdicts(case) -> None:
    """The printed label must actually justify each non-trivial field verdict."""
    label = case.label
    app = case.application
    for field_key, verdict in case.golden.fields.items():
        if field_key == "alcohol_content":
            label_val = label.get("alcohol_content_text")
            app_val = app.get("alcohol_content_text")
        else:
            label_val = label.get(field_key)
            app_val = app.get(field_key)
        if verdict is FieldVerdict.MATCH:
            assert label_val == app_val, f"{case.id}/{field_key}: MATCH but values differ"
        elif verdict is FieldVerdict.MISMATCH:
            assert label_val != app_val, f"{case.id}/{field_key}: MISMATCH but values equal"
        elif verdict is FieldVerdict.SOFT_WARNING:
            # Human-equivalent: differ literally but match case-insensitively.
            assert label_val != app_val, f"{case.id}/{field_key}: SOFT but identical"
            assert (label_val or "").lower() == (app_val or "").lower(), (
                f"{case.id}/{field_key}: SOFT warning should be a case/format-only diff"
            )


@pytest.mark.parametrize("case", CASE_PARAMS)
def test_warning_verdict_matches_printed_warning(case) -> None:
    """The golden warning verdict must reflect what is printed on the label."""
    printed = case.label.get("government_warning")
    verdict = case.golden.government_warning
    if verdict is WarningVerdict.MISSING:
        assert not printed, "MISSING verdict but a warning is printed"
    elif verdict is WarningVerdict.COMPLIANT:
        assert printed == GOVERNMENT_WARNING_TEXT, "COMPLIANT verdict must be the exact text"
    elif verdict is WarningVerdict.ALTERED:
        assert printed, "ALTERED verdict needs a printed (tampered) warning"
        assert printed != GOVERNMENT_WARNING_TEXT, "ALTERED verdict but text is exact"


def test_corpus_covers_each_verdict_scenario() -> None:
    """Sanity: the corpus spans pass, soft-warning, mismatch, and warning faults."""
    overalls = {c.golden.overall for c in CASES}
    assert {OverallVerdict.PASS, OverallVerdict.WARNING, OverallVerdict.FAIL} <= overalls

    warnings = {c.golden.government_warning for c in CASES}
    assert {WarningVerdict.COMPLIANT, WarningVerdict.ALTERED, WarningVerdict.MISSING} <= warnings

    field_verdicts = {v for c in CASES for v in c.golden.fields.values()}
    assert {FieldVerdict.MATCH, FieldVerdict.SOFT_WARNING, FieldVerdict.MISMATCH} <= field_verdicts
