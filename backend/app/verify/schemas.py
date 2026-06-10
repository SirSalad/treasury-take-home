"""Schemas for the mandatory Government Health Warning verifier.

The warning gets a dedicated, exact-match verification path (see
:mod:`app.verify.warning`) separate from the fuzzy field matching used for
brand/class-type. It must be **present**, carry the required statement
**verbatim**, and render its ``GOVERNMENT WARNING:`` header in **all caps**
(27 CFR 16.21). Three outcomes mirror the corpus golden data: a clean
``COMPLIANT``, an ``ALTERED`` warning (tampered wording or a title-case header —
Jenny's catch), and an entirely ``MISSING`` warning.
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

# Word-level wording match threshold against the canonical statement. OCR
# introduces minor noise (an "O"/"0" slip within one word), so an exact compare
# is too brittle; a real evasion (a dropped sentence, a reworded clause — several
# words gone) drops the word-level score well below this. The check is
# deliberately conservative: a wording deviation it cannot attribute to noise is
# flagged ALTERED for human review rather than passed. Tunable. See
# :func:`app.verify.warning._wording_similarity`.
DEFAULT_SIMILARITY_THRESHOLD = 0.95

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
