"""Roll up per-field results + the warning verdict into an overall verdict.

This module owns the *aggregation rules* — the single, documented policy that
turns the engine's individual checks into the headline verdict an agent acts on.
The output shape (:class:`app.verify.schemas.VerificationResult`) is the stable
contract the comparison UI and batch results consume.

Aggregation rules
-----------------

The overall verdict is the worst outcome implied by the parts:

1. **FAIL** — any field is a ``MISMATCH``, **or** the Government Health Warning
   is ``ALTERED`` or ``MISSING``. A mandatory-warning fault fails the label
   outright regardless of how the other fields compare (Jenny's title-case catch
   and the missing-warning case both land here).
2. **WARNING** — no hard fault, but at least one field is a ``SOFT_WARNING``
   (a human-equivalent difference such as a case-only brand mismatch, or a near
   miss worth a glance). The label is plausibly fine but needs a human look.
3. **PASS** — every checked field is a ``MATCH`` and the warning is
   ``COMPLIANT``.

``NOT_CHECKED`` fields (absent from the application) never affect the verdict.

These rules are pinned by ``tests.test_corpus.test_overall_verdict_consistent_with_details``
so the golden corpus and the engine cannot drift apart.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.extract.schemas import SourceSpan
from app.match.schemas import FieldMatch, MatchStatus
from app.ocr.schemas import BoundingBox
from app.verify.schemas import (
    FieldResult,
    FieldStatus,
    GovernmentWarningResult,
    OverallVerdict,
    VerdictSummary,
    VerificationResult,
    WarningVerdict,
)

# Warning outcomes that fail the whole label on their own.
_FAILING_WARNINGS = frozenset({WarningVerdict.ALTERED, WarningVerdict.MISSING})

# MatchStatus -> FieldStatus. The fuzzy matcher's three states share string
# values with FieldStatus; this makes the (total) mapping explicit.
_MATCH_TO_FIELD_STATUS = {
    MatchStatus.MATCH: FieldStatus.MATCH,
    MatchStatus.SOFT_WARNING: FieldStatus.SOFT_WARNING,
    MatchStatus.MISMATCH: FieldStatus.MISMATCH,
}


def aggregate_verdict(
    fields: Iterable[FieldResult],
    warning: GovernmentWarningResult,
) -> OverallVerdict:
    """Apply the aggregation rules to per-field results + the warning verdict."""
    statuses = [f.status for f in fields]
    warning_bad = warning.verdict in _FAILING_WARNINGS

    if warning_bad or any(s is FieldStatus.MISMATCH for s in statuses):
        return OverallVerdict.FAIL
    if any(s is FieldStatus.SOFT_WARNING for s in statuses):
        return OverallVerdict.WARNING
    return OverallVerdict.PASS


def summarise(fields: Iterable[FieldResult]) -> VerdictSummary:
    """Count per-field statuses for the at-a-glance summary."""
    summary = VerdictSummary()
    for f in fields:
        match f.status:
            case FieldStatus.MATCH:
                summary.match += 1
            case FieldStatus.SOFT_WARNING:
                summary.soft_warning += 1
            case FieldStatus.MISMATCH:
                summary.mismatch += 1
            case FieldStatus.NOT_CHECKED:
                summary.not_checked += 1
    return summary


def _rationale(
    overall: OverallVerdict,
    fields: list[FieldResult],
    warning: GovernmentWarningResult,
) -> str:
    """A short, human-readable explanation of the overall verdict."""
    if overall is OverallVerdict.FAIL:
        reasons: list[str] = []
        if warning.verdict is WarningVerdict.MISSING:
            reasons.append("the mandatory Government Health Warning is missing")
        elif warning.verdict is WarningVerdict.ALTERED:
            reasons.append("the Government Health Warning is altered")
        mismatched = [f.field for f in fields if f.status is FieldStatus.MISMATCH]
        if mismatched:
            reasons.append(f"field mismatch: {', '.join(mismatched)}")
        return "Fails: " + "; ".join(reasons) + "." if reasons else "Fails verification."
    if overall is OverallVerdict.WARNING:
        soft = [f.field for f in fields if f.status is FieldStatus.SOFT_WARNING]
        return f"Needs review: soft warning on {', '.join(soft)}." if soft else "Needs review."
    return "All checked fields match and the warning is compliant."


def build_result(
    fields: Iterable[FieldResult],
    warning: GovernmentWarningResult,
) -> VerificationResult:
    """Assemble the full :class:`VerificationResult` from the engine's parts.

    Computes the overall verdict, the status summary, and a rationale, and bundles
    them with the per-field results and the warning result into the stable
    contract object.
    """
    fields = list(fields)
    overall = aggregate_verdict(fields, warning)
    return VerificationResult(
        overall=overall,
        fields=fields,
        government_warning=warning,
        summary=summarise(fields),
        rationale=_rationale(overall, fields, warning),
    )


def field_result_from_match(
    match: FieldMatch,
    *,
    span: SourceSpan | None = None,
    box: BoundingBox | None = None,
) -> FieldResult:
    """Adapt a fuzzy :class:`FieldMatch` into the per-field contract row.

    The matcher already grades into the same three states the contract uses; this
    carries over the expected/found text, score, and reason. (Fuzzy matches
    always concern a field the application supplied, so the status is never
    ``NOT_CHECKED`` here.) The matcher scores against the joined OCR text and does
    not itself locate the hit, so the caller may pass the ``span``/``box`` of the
    OCR line the matched text came from for highlighting.
    """
    return FieldResult(
        field=match.field.value,
        status=_MATCH_TO_FIELD_STATUS[match.status],
        expected=match.expected,
        found=match.matched_text or None,
        score=match.score,
        span=span,
        box=box,
        reason=match.reason,
    )
