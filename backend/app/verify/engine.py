"""End-to-end verification engine: OCR result + expected COLA -> verdict.

This is the glue that turns the recovered label text into the headline verdict an
agent acts on. It routes each verifiable field to the comparison strategy that
fits it, then hands the per-field results plus the Government Health Warning
verdict to :func:`app.verify.aggregate.build_result` for the roll-up.

Comparison strategies
---------------------

* **Free-text fuzzy** (``brand_name``, ``class_type``) — the expected value is
  looked for *somewhere* in the OCR text and graded into match / soft-warning /
  mismatch (see :mod:`app.match`). Case-only differences become soft warnings.
* **Other free-text** (``net_contents``, ``name_and_address``,
  ``country_of_origin``, ``vintage``) — the same fuzzy presence grader. On the
  label these are printed verbatim, so presence-matching the application value
  against the OCR text is both simple and robust to OCR noise.
* **Numeric** (``alcohol_content``) — ABV is compared *numerically* via the
  deterministic extractor, because a fuzzy string compare cannot tell "45%" from
  "40%" (a one-character, high-similarity difference that is nonetheless the most
  common — and consequential — data-entry error). The extracted percentage is
  compared to the application's within a small tolerance.
* **Government Health Warning** — its own near-exact path (see
  :mod:`app.verify.warning`).

A field is only verified when the application supplies a value for it; fields the
application omits are left out entirely (rather than emitted as ``NOT_CHECKED``),
so the result's field set mirrors the COLA that was filed.
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from app.extract import extract_fields, extract_from_text
from app.extract.schemas import ExtractionResult, FieldName, SourceSpan
from app.match import (
    HIGH_THRESHOLD,
    FuzzyFieldName,
    MatchStatus,
    PresenceScore,
    match_from_ocr,
    score_presence,
)
from app.ocr.schemas import BoundingBox, OcrResult, TextLine
from app.verify.aggregate import build_result, field_result_from_match
from app.verify.schemas import (
    FieldResult,
    FieldStatus,
    VerificationResult,
)
from app.verify.warning import verify_warning_from_ocr

# ABV is printed to a tenth of a percent; anything within this tolerance is the
# same value (and absorbs a trailing-zero / OCR rounding wobble).
ABV_TOLERANCE_PCT = 0.05

# A line "is" the brand/class (its display) — rather than merely mentioning it —
# when the matched text covers most of the line at high similarity. Used to grade
# the brand against how it is *displayed*, so an all-caps brand banner is caught
# as a case difference even when the responsibility statement spells the brand
# correctly ("STONE'S THROW" header vs "...by Stone's Throw Spirits" address).
DISPLAY_MIN_COVERAGE = 0.7

# MatchStatus -> FieldStatus for presence checks (the three fuzzy states share
# string values; this makes the mapping explicit).
_MATCH_TO_FIELD_STATUS = {
    MatchStatus.MATCH: FieldStatus.MATCH,
    MatchStatus.SOFT_WARNING: FieldStatus.SOFT_WARNING,
    MatchStatus.MISMATCH: FieldStatus.MISMATCH,
}


@runtime_checkable
class ExpectedFields(Protocol):
    """The verifiable subset of a COLA the engine reads.

    Satisfied by both the ORM :class:`app.models.application.Application` and the
    API's request model, so the engine is decoupled from either.
    """

    brand_name: str
    class_type: str | None
    alcohol_content_pct: float | None
    alcohol_content_text: str | None
    net_contents: str | None
    name_and_address: str | None
    country_of_origin: str | None
    vintage: str | None


def verify_label(expected: ExpectedFields, ocr_result: OcrResult) -> VerificationResult:
    """Verify a label's OCR output against the expected COLA data.

    Produces a :class:`VerificationResult`: one :class:`FieldResult` per field the
    application supplies, the Government Health Warning verdict, and the overall
    roll-up. Pure and deterministic — OCR (the only slow, non-deterministic step)
    happens upstream and is passed in.
    """
    fields: list[FieldResult] = []
    extraction = extract_fields(ocr_result)

    # brand_name is mandatory on every application, so it is always checked.
    fields.append(_verify_fuzzy(FuzzyFieldName.BRAND_NAME, expected.brand_name, ocr_result))

    if expected.class_type:
        fields.append(_verify_fuzzy(FuzzyFieldName.CLASS_TYPE, expected.class_type, ocr_result))

    if expected.alcohol_content_pct is not None or expected.alcohol_content_text:
        fields.append(_verify_alcohol(expected, extraction))

    if expected.net_contents:
        fields.append(_verify_presence("net_contents", expected.net_contents, ocr_result))

    if expected.name_and_address:
        fields.append(_verify_presence("name_and_address", expected.name_and_address, ocr_result))

    if expected.country_of_origin:
        fields.append(_verify_presence("country_of_origin", expected.country_of_origin, ocr_result))

    if expected.vintage:
        fields.append(_verify_presence("vintage", expected.vintage, ocr_result))

    warning = verify_warning_from_ocr(ocr_result)
    return build_result(fields, warning)


def _verify_fuzzy(field: FuzzyFieldName, expected: str, ocr: OcrResult) -> FieldResult:
    """Verify a named free-text field (brand / class-type) against the label.

    Prefers grading against the *display* line — the line that predominantly is
    this field — so a case-only difference in how the field is printed is caught
    even when the same words appear correctly elsewhere (e.g. inside the
    responsibility statement). Falls back to whole-text matching when no single
    line clearly carries the field (the detector may split it across lines).
    """
    display = _best_display_line(expected, ocr)
    if display is not None:
        index, line, presence = display
        return FieldResult(
            field=field.value,
            status=_MATCH_TO_FIELD_STATUS[presence.status],
            expected=expected,
            found=presence.matched_text or None,
            score=presence.score,
            span=SourceSpan(line_index=index, start=0, end=len(line.text)),
            box=line.box,
            reason=presence.reason,
        )
    match = match_from_ocr(field, expected, ocr)
    span, box = _locate(ocr, match.matched_text)
    return field_result_from_match(match, span=span, box=box)


def _best_display_line(expected: str, ocr: OcrResult) -> tuple[int, TextLine, PresenceScore] | None:
    """The line that predominantly *is* ``expected``, if one stands out.

    A line qualifies when the expected value matches it strongly
    (``score >= HIGH_THRESHOLD``) and the match covers most of the line
    (:data:`DISPLAY_MIN_COVERAGE`) — i.e. the line shows this field rather than
    just mentioning it among other text. Among qualifiers the highest coverage
    then score wins; ties favour a cosmetic (case/punctuation) difference so the
    human still gets the glance the discovery interviews asked for.
    """
    best: tuple[float, float, bool, int, TextLine, PresenceScore] | None = None
    for index, line in enumerate(ocr.lines):
        presence = score_presence(expected, line.text)
        if presence.score < HIGH_THRESHOLD:
            continue
        line_tokens = _word_tokens(line.text)
        if not line_tokens:
            continue
        coverage = len(_word_tokens(presence.matched_text)) / len(line_tokens)
        if coverage < DISPLAY_MIN_COVERAGE:
            continue
        is_cosmetic = presence.status is MatchStatus.SOFT_WARNING
        key = (coverage, presence.score, is_cosmetic, index, line, presence)
        if best is None or key[:3] > best[:3]:
            best = key
    if best is None:
        return None
    _, _, _, index, line, presence = best
    return index, line, presence


def _verify_presence(field: str, expected: str, ocr: OcrResult) -> FieldResult:
    """Verify a free-text field by fuzzy-presence of its value in the OCR text."""
    presence = score_presence(expected, ocr.full_text)
    span, box = _locate(ocr, presence.matched_text)
    return FieldResult(
        field=field,
        status=_MATCH_TO_FIELD_STATUS[presence.status],
        expected=expected,
        found=presence.matched_text or None,
        score=presence.score,
        span=span,
        box=box,
        reason=presence.reason,
    )


def _verify_alcohol(expected: ExpectedFields, extraction: ExtractionResult) -> FieldResult:
    """Verify alcohol content by numeric comparison of ABV percentages.

    The application percentage (parsed from ``alcohol_content_text`` when the
    explicit ``_pct`` column is absent) is compared to the percentage the
    deterministic extractor recovered from the label, within
    :data:`ABV_TOLERANCE_PCT`. A genuine numeric disagreement (45% vs 40%) is a
    hard mismatch; a label with no recoverable ABV is treated as a mismatch
    (the required statement could not be found).
    """
    expected_pct = expected.alcohol_content_pct
    if expected_pct is None and expected.alcohol_content_text:
        expected_pct = _parse_abv_pct(expected.alcohol_content_text)
    display = expected.alcohol_content_text or (
        f"{_fmt_pct(expected_pct)}% Alc./Vol." if expected_pct is not None else None
    )

    best = extraction.best(FieldName.ABV)
    if best is None:
        return FieldResult(
            field="alcohol_content",
            status=FieldStatus.MISMATCH,
            expected=display,
            found=None,
            score=0.0,
            reason="no alcohol content statement found on the label",
        )

    found_pct = float(best.value)
    if expected_pct is None:
        # Present, but nothing numeric to compare against — flag for a glance.
        return FieldResult(
            field="alcohol_content",
            status=FieldStatus.SOFT_WARNING,
            expected=display,
            found=best.text,
            score=best.confidence,
            span=best.span,
            box=best.box,
            reason="alcohol content present but no expected percentage to compare against",
        )

    if abs(found_pct - float(expected_pct)) <= ABV_TOLERANCE_PCT:
        status = FieldStatus.MATCH
        score = 1.0
        reason = f"label ABV {_fmt_pct(found_pct)}% matches application {_fmt_pct(expected_pct)}%"
    else:
        status = FieldStatus.MISMATCH
        score = 0.0
        reason = (
            f"label ABV {_fmt_pct(found_pct)}% does not match application {_fmt_pct(expected_pct)}%"
        )
    return FieldResult(
        field="alcohol_content",
        status=status,
        expected=display,
        found=best.text,
        score=score,
        span=best.span,
        box=best.box,
        reason=reason,
    )


def _parse_abv_pct(text: str) -> float | None:
    """Recover a numeric ABV percentage from a free-text statement, if present."""
    for candidate in extract_from_text(text):
        if candidate.field is FieldName.ABV:
            return float(candidate.value)
    return None


def _fmt_pct(value: float | None) -> str:
    """Format a percentage without trailing zeros ("45.0" -> "45")."""
    return "" if value is None else f"{float(value):g}"


def _locate(ocr: OcrResult, matched_text: str) -> tuple[SourceSpan | None, BoundingBox | None]:
    """Best-effort: find the OCR line the matched text came from, for highlighting.

    The fuzzy matcher scores against the joined text and can return a window that
    spans several detected lines, so an exact offset isn't recoverable. We pick
    the line sharing the most word tokens with ``matched_text`` and span its full
    width — enough for the comparison UI to draw a box around the right region.
    """
    target = _word_tokens(matched_text)
    if not target or not ocr.lines:
        return None, None

    best_index = -1
    best_hits = 0
    for index, line in enumerate(ocr.lines):
        line_tokens = set(_word_tokens(line.text))
        hits = sum(1 for token in target if token in line_tokens)
        if hits > best_hits:
            best_index, best_hits = index, hits

    if best_index < 0:
        return None, None
    line = ocr.lines[best_index]
    return SourceSpan(line_index=best_index, start=0, end=len(line.text)), line.box


def _word_tokens(text: str) -> list[str]:
    """Lowercase alphanumeric tokens (punctuation/casing dropped)."""
    return re.findall(r"[0-9a-z]+", text.casefold())
