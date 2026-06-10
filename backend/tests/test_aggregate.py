"""Tests for result aggregation and the verdict schema.

Four layers:

* **Aggregation rules** — the PASS / WARNING / FAIL roll-up over per-field
  statuses and the warning verdict, including precedence (a warning fault fails
  the label regardless of fields) and that ``NOT_CHECKED`` is inert.
* **Golden parity** — the rules reproduce the overall verdict the labelled
  corpus expects for every case, so the engine and golden data cannot drift.
* **Adapter** — a fuzzy ``FieldMatch`` maps onto the per-field contract row.
* **Result shape** — ``build_result`` assembles a stable, serialisable
  ``VerificationResult`` (overall, fields, warning, summary, rationale).
"""

from __future__ import annotations

import pytest

from app.extract.schemas import SourceSpan
from app.match.schemas import FieldMatch, FuzzyFieldName, MatchStatus
from app.ocr.schemas import BoundingBox
from app.verify import (
    RESULT_SCHEMA_VERSION,
    FieldResult,
    FieldStatus,
    GovernmentWarningResult,
    OverallVerdict,
    VerificationResult,
    WarningVerdict,
    aggregate_verdict,
    build_result,
    field_result_from_match,
    summarise,
)
from tests.corpus import FieldVerdict, load_corpus
from tests.corpus import OverallVerdict as CorpusOverall
from tests.corpus import WarningVerdict as CorpusWarning


def _field(name: str, status: FieldStatus) -> FieldResult:
    return FieldResult(field=name, status=status, expected="x", found="x", score=1.0)


def _warning(verdict: WarningVerdict) -> GovernmentWarningResult:
    return GovernmentWarningResult(verdict=verdict)


COMPLIANT = _warning(WarningVerdict.COMPLIANT)


# --- Aggregation rules -------------------------------------------------------


def test_all_match_and_compliant_warning_is_pass() -> None:
    fields = [_field("brand_name", FieldStatus.MATCH), _field("net_contents", FieldStatus.MATCH)]
    assert aggregate_verdict(fields, COMPLIANT) is OverallVerdict.PASS


def test_soft_warning_field_is_warning() -> None:
    fields = [
        _field("brand_name", FieldStatus.SOFT_WARNING),
        _field("net_contents", FieldStatus.MATCH),
    ]
    assert aggregate_verdict(fields, COMPLIANT) is OverallVerdict.WARNING


def test_field_mismatch_is_fail() -> None:
    fields = [
        _field("alcohol_content", FieldStatus.MISMATCH),
        _field("brand_name", FieldStatus.MATCH),
    ]
    assert aggregate_verdict(fields, COMPLIANT) is OverallVerdict.FAIL


@pytest.mark.parametrize("verdict", [WarningVerdict.ALTERED, WarningVerdict.MISSING])
def test_bad_warning_fails_even_when_all_fields_match(verdict: WarningVerdict) -> None:
    # Jenny's catch / missing warning: a warning fault fails the label outright.
    fields = [_field("brand_name", FieldStatus.MATCH), _field("net_contents", FieldStatus.MATCH)]
    assert aggregate_verdict(fields, _warning(verdict)) is OverallVerdict.FAIL


def test_mismatch_outranks_soft_warning() -> None:
    fields = [_field("brand_name", FieldStatus.SOFT_WARNING), _field("abv", FieldStatus.MISMATCH)]
    assert aggregate_verdict(fields, COMPLIANT) is OverallVerdict.FAIL


def test_not_checked_fields_do_not_affect_verdict() -> None:
    fields = [
        _field("brand_name", FieldStatus.MATCH),
        _field("country_of_origin", FieldStatus.NOT_CHECKED),
        _field("vintage", FieldStatus.NOT_CHECKED),
    ]
    assert aggregate_verdict(fields, COMPLIANT) is OverallVerdict.PASS


def test_no_fields_with_compliant_warning_is_pass() -> None:
    assert aggregate_verdict([], COMPLIANT) is OverallVerdict.PASS


# --- Golden parity: rules reproduce the corpus overall verdicts --------------

CORPUS = load_corpus()

_CORPUS_TO_OVERALL = {
    CorpusOverall.PASS: OverallVerdict.PASS,
    CorpusOverall.WARNING: OverallVerdict.WARNING,
    CorpusOverall.FAIL: OverallVerdict.FAIL,
}
_FIELD_VERDICT_TO_STATUS = {
    FieldVerdict.MATCH: FieldStatus.MATCH,
    FieldVerdict.SOFT_WARNING: FieldStatus.SOFT_WARNING,
    FieldVerdict.MISMATCH: FieldStatus.MISMATCH,
    FieldVerdict.NOT_CHECKED: FieldStatus.NOT_CHECKED,
}
_WARNING_VERDICT = {
    CorpusWarning.COMPLIANT: WarningVerdict.COMPLIANT,
    CorpusWarning.ALTERED: WarningVerdict.ALTERED,
    CorpusWarning.MISSING: WarningVerdict.MISSING,
}


@pytest.mark.parametrize("case", [pytest.param(c, id=c.id) for c in CORPUS.cases])
def test_aggregation_reproduces_golden_overall(case) -> None:
    """Rolling up each case's golden field/warning verdicts yields its overall."""
    fields = [
        FieldResult(field=key, status=_FIELD_VERDICT_TO_STATUS[v])
        for key, v in case.golden.fields.items()
    ]
    warning = _warning(_WARNING_VERDICT[case.golden.government_warning])
    expected = _CORPUS_TO_OVERALL[case.golden.overall]
    assert aggregate_verdict(fields, warning) is expected


# --- Summary -----------------------------------------------------------------


def test_summarise_counts_each_status() -> None:
    fields = [
        _field("a", FieldStatus.MATCH),
        _field("b", FieldStatus.MATCH),
        _field("c", FieldStatus.SOFT_WARNING),
        _field("d", FieldStatus.MISMATCH),
        _field("e", FieldStatus.NOT_CHECKED),
    ]
    summary = summarise(fields)
    assert (summary.match, summary.soft_warning, summary.mismatch, summary.not_checked) == (
        2,
        1,
        1,
        1,
    )


# --- Adapter: FieldMatch -> FieldResult --------------------------------------


@pytest.mark.parametrize(
    "match_status,field_status",
    [
        (MatchStatus.MATCH, FieldStatus.MATCH),
        (MatchStatus.SOFT_WARNING, FieldStatus.SOFT_WARNING),
        (MatchStatus.MISMATCH, FieldStatus.MISMATCH),
    ],
)
def test_field_result_from_match_maps_status(match_status, field_status) -> None:
    match = FieldMatch(
        field=FuzzyFieldName.BRAND_NAME,
        status=match_status,
        expected="Stone's Throw",
        matched_text="STONE'S THROW",
        score=0.9,
        reason="case/punctuation-only difference",
    )
    result = field_result_from_match(match)
    assert result.status is field_status
    assert result.field == "brand_name"
    assert result.expected == "Stone's Throw"
    assert result.found == "STONE'S THROW"
    assert result.score == 0.9
    assert result.reason == "case/punctuation-only difference"


def test_field_result_from_match_empty_match_has_no_found() -> None:
    match = FieldMatch(
        field=FuzzyFieldName.CLASS_TYPE,
        status=MatchStatus.MISMATCH,
        expected="London Dry Gin",
        matched_text="",
        score=0.1,
        reason="not found",
    )
    assert field_result_from_match(match).found is None


def test_field_result_from_match_carries_location() -> None:
    match = FieldMatch(
        field=FuzzyFieldName.BRAND_NAME,
        status=MatchStatus.MATCH,
        expected="OLD TOM DISTILLERY",
        matched_text="OLD TOM DISTILLERY",
        score=1.0,
    )
    span = SourceSpan(line_index=2, start=0, end=18)
    box = BoundingBox(x_min=1, y_min=2, x_max=3, y_max=4)
    result = field_result_from_match(match, span=span, box=box)
    assert result.span == span
    assert result.box == box


# --- build_result: full contract assembly ------------------------------------


def test_build_result_assembles_full_contract() -> None:
    fields = [
        _field("brand_name", FieldStatus.SOFT_WARNING),
        _field("net_contents", FieldStatus.MATCH),
    ]
    result = build_result(fields, COMPLIANT)
    assert isinstance(result, VerificationResult)
    assert result.overall is OverallVerdict.WARNING
    assert result.schema_version == RESULT_SCHEMA_VERSION
    assert result.fields == fields
    assert result.government_warning is COMPLIANT
    assert result.summary.soft_warning == 1 and result.summary.match == 1
    assert result.rationale  # non-empty explanation


def test_build_result_rationale_names_the_fault() -> None:
    missing = _warning(WarningVerdict.MISSING)
    result = build_result([_field("brand_name", FieldStatus.MATCH)], missing)
    assert result.overall is OverallVerdict.FAIL
    assert "warning" in result.rationale.lower()

    mismatch_result = build_result([_field("alcohol_content", FieldStatus.MISMATCH)], COMPLIANT)
    assert "alcohol_content" in mismatch_result.rationale


def test_result_is_json_serialisable_and_round_trips() -> None:
    fields = [_field("brand_name", FieldStatus.MATCH)]
    result = build_result(fields, COMPLIANT)
    dumped = result.model_dump(mode="json")
    # Stable top-level contract keys for the UI / batch consumers.
    assert set(dumped) == {
        "schema_version",
        "overall",
        "fields",
        "government_warning",
        "summary",
        "rationale",
    }
    assert dumped["overall"] == "pass"
    # Round-trips back into the model unchanged.
    assert VerificationResult.model_validate(dumped) == result
