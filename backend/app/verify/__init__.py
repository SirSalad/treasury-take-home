"""Verification of label artwork against expected (application) data.

This package compares recovered label text against the COLA an agent filed. The
mandatory Government Health Warning is checked here on a dedicated exact-match
path (the rest of the engine uses fuzzy field matching), and per-field results
are rolled up into a single overall verdict.

Public API:

* :func:`verify_government_warning` — verify the warning in a string of OCR text.
* :func:`verify_warning_from_ocr` — verify over an :class:`~app.ocr.schemas.OcrResult`,
  attaching the source line/box.
* :func:`verify_label` — the end-to-end engine: compare an OCR result against the
  expected COLA and return a :class:`VerificationResult`.
* :func:`verify_label_image` — the image-in entry point: OCR + verify with
  adaptive rotation/zoom rescue passes (what the API and evals run).
* :func:`build_result` — roll per-field results + the warning into the stable
  :class:`VerificationResult` contract.
* :func:`aggregate_verdict` — the overall PASS / WARNING / FAIL rule on its own.
* :func:`field_result_from_match` — adapt a fuzzy :class:`~app.match.FieldMatch`
  into a :class:`FieldResult`.
* :class:`GovernmentWarningResult`, :class:`WarningVerdict` — warning schemas.
* :class:`VerificationResult`, :class:`FieldResult`, :class:`FieldStatus`,
  :class:`OverallVerdict`, :class:`VerdictSummary` — the aggregation contract.
* :data:`GOVERNMENT_WARNING_TEXT` — the canonical 27 CFR 16.21 statement.
"""

from app.verify.aggregate import (
    aggregate_verdict,
    build_result,
    field_result_from_match,
    summarise,
)
from app.verify.engine import ExpectedFields, verify_label
from app.verify.pipeline import verify_label_image
from app.verify.schemas import (
    GOVERNMENT_WARNING_TEXT,
    RESULT_SCHEMA_VERSION,
    FieldResult,
    FieldStatus,
    GovernmentWarningResult,
    OverallVerdict,
    VerdictSummary,
    VerificationResult,
    WarningVerdict,
)
from app.verify.warning import verify_government_warning, verify_warning_from_ocr

__all__ = [
    "GOVERNMENT_WARNING_TEXT",
    "RESULT_SCHEMA_VERSION",
    "ExpectedFields",
    "FieldResult",
    "FieldStatus",
    "GovernmentWarningResult",
    "OverallVerdict",
    "VerdictSummary",
    "VerificationResult",
    "WarningVerdict",
    "aggregate_verdict",
    "build_result",
    "field_result_from_match",
    "summarise",
    "verify_government_warning",
    "verify_label",
    "verify_label_image",
    "verify_warning_from_ocr",
]
