"""Schemas for the verification engine: the Government Health Warning verifier
and the result-aggregation contract.

The warning gets a dedicated, exact-match verification path (see
:mod:`app.verify.warning`) separate from the fuzzy field matching used for
brand/class-type. It must be **present**, carry the required statement
**verbatim**, and render its ``GOVERNMENT WARNING:`` header in **all caps**
(27 CFR 16.21). Three outcomes mirror the corpus golden data: a clean
``COMPLIANT``, an ``ALTERED`` warning (tampered wording or a title-case header —
Jenny's catch), and an entirely ``MISSING`` warning.

The aggregation schemas (:class:`FieldStatus`, :class:`OverallVerdict`,
:class:`FieldResult`, :class:`VerificationResult`) define the **stable JSON
contract** the comparison UI and batch results consume — see
:mod:`app.verify.aggregate` for the roll-up rules. Enum string values are kept
identical to ``tests.corpus.schema`` so engine output compares straight against
the golden expectations.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, Field

from app.extract.schemas import SourceSpan
from app.ocr.schemas import BoundingBox

# The exact mandatory Government Health Warning text (27 CFR 16.21). The
# `GOVERNMENT WARNING:` prefix must appear in all caps (and, on the physical
# label, in bold — see the limitations note below).
GOVERNMENT_WARNING_TEXT = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth "
    "defects. (2) Consumption of alcoholic beverages impairs your ability to "
    "drive a car or operate machinery, and may cause health problems."
)

# The header that must render in all caps. Matched case-insensitively to locate
# the warning, then inspected case-sensitively for the all-caps requirement.
WARNING_HEADER = "GOVERNMENT WARNING"

# Wording match threshold against the canonical statement. Compliance also
# requires every mandatory clause to be present (see
# :func:`app.verify.warning._missing_required_phrases`), which is what actually
# catches an evasion (a dropped or reworded clause removes a required phrase);
# this character-level ratio is a secondary guard against broader garbling.
# Calibrated to real OCR: a standard warning read off a real label lands ~0.85+,
# so 0.80 avoids false ALTEREDs on noisy-but-valid statements while the
# phrase check carries the tamper-detection load. Tunable. See
# :func:`app.verify.warning._wording_similarity`.
DEFAULT_SIMILARITY_THRESHOLD = 0.80

# Constraints we cannot verify from OCR *text* alone — surfaced so the verdict is
# honest about its blind spots rather than implying full compliance.
TEXT_ONLY_LIMITATIONS = (
    "Bold type and minimum font size (27 CFR 16.22) are not verifiable from OCR "
    "text alone; checked on a best-effort textual basis only.",
)


class WarningVerdict(enum.StrEnum):
    """Outcome of the Government Health Warning check.

    Mirrors ``tests.corpus.schema.WarningVerdict`` (the golden-data enum) so the
    verifier's output can be compared directly against the corpus expectations.
    """

    COMPLIANT = "compliant"
    ALTERED = "altered"
    MISSING = "missing"


class GovernmentWarningResult(BaseModel):
    """Result of verifying one label's Government Health Warning.

    ``found_text`` is the located warning region (``None`` when no header was
    found). ``header_all_caps`` is ``None`` when there is no header to inspect.
    ``similarity`` is the wording match against :data:`GOVERNMENT_WARNING_TEXT`
    in ``[0, 1]`` (``0.0`` when missing). ``issues`` explains any non-compliance;
    ``limitations`` records what could not be checked from text alone.
    """

    verdict: WarningVerdict
    found_text: str | None = None
    header_all_caps: bool | None = None
    similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    issues: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    # Where the header was located, for highlighting in the comparison UI.
    span: SourceSpan | None = None
    box: BoundingBox | None = None
    # Which of the submission's images carried this verdict (zero-based index
    # into the filing's label set). ``None`` on single-image verifications.
    image_index: int | None = None


# --- Result aggregation contract ---------------------------------------------
#
# Bumped when the wire shape of VerificationResult changes incompatibly, so
# stored Submission.result rows and the UI can detect a schema they predate.
# v2: ``image_index`` provenance on FieldResult / GovernmentWarningResult — a
# submission now carries a filing's whole label set (front/back/neck), and a
# box is meaningless without knowing which image it sits on.
RESULT_SCHEMA_VERSION = 2


class FieldStatus(enum.StrEnum):
    """Per-field outcome of comparing the label against the application.

    String values match ``tests.corpus.schema.FieldVerdict`` and the fuzzy
    matcher's ``app.match.MatchStatus`` (which shares the first three), so a
    :class:`app.match.FieldMatch` maps straight onto a :class:`FieldResult`.

    * ``MATCH`` — present and equivalent.
    * ``SOFT_WARNING`` — present but differing in a human-equivalent way (case /
      punctuation only) or a near miss worth a human glance.
    * ``MISMATCH`` — absent, or too different to be the same value.
    * ``NOT_CHECKED`` — the application did not supply this field, so there was
      nothing to verify against (does not affect the overall verdict).
    """

    MATCH = "match"
    SOFT_WARNING = "soft_warning"
    MISMATCH = "mismatch"
    NOT_CHECKED = "not_checked"


class OverallVerdict(enum.StrEnum):
    """Roll-up verdict for a whole label, surfaced to the agent.

    Mirrors ``tests.corpus.schema.OverallVerdict``. ``WARNING`` is the engine's
    name for the "needs review" middle state: the label is plausibly fine but
    something (a soft field warning) warrants a human glance before approval.
    """

    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


class FieldResult(BaseModel):
    """One field's verification result — the per-field row of the contract.

    ``field`` is the logical comparison key (matching the application columns
    and the corpus golden field keys): ``brand_name``, ``class_type``,
    ``alcohol_content``, ``net_contents``, ``name_and_address``,
    ``country_of_origin``, ``vintage``, … ``expected`` is the application value;
    ``found`` is what was recovered from the label (``None`` when nothing
    plausible was located). ``score`` is the comparison confidence/similarity in
    ``[0, 1]``. ``span``/``box`` locate the matched text for highlighting in the
    comparison UI.
    """

    field: str
    status: FieldStatus
    expected: str | None = None
    found: str | None = None
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    span: SourceSpan | None = None
    box: BoundingBox | None = None
    # Which of the submission's images carried this verdict (zero-based index
    # into the filing's label set). ``None`` on single-image verifications.
    image_index: int | None = None
    # Human-readable explanation of why this status was assigned.
    reason: str = ""


class VerdictSummary(BaseModel):
    """Counts of per-field statuses — a quick at-a-glance roll-up for the UI."""

    match: int = 0
    soft_warning: int = 0
    mismatch: int = 0
    not_checked: int = 0


class VerificationResult(BaseModel):
    """The complete verification output for one label: the stable JSON contract.

    This is what is persisted to ``Submission.result`` and rendered by the
    comparison UI / batch results. It bundles the overall roll-up, every
    per-field result, the dedicated Government Health Warning result (kept
    separate because it carries its own verdict vocabulary), a status summary,
    and a human-readable rationale for the overall verdict.
    """

    schema_version: int = RESULT_SCHEMA_VERSION
    overall: OverallVerdict
    fields: list[FieldResult] = Field(default_factory=list)
    government_warning: GovernmentWarningResult
    summary: VerdictSummary
    # Why the overall verdict came out the way it did (drives the headline).
    rationale: str = ""
