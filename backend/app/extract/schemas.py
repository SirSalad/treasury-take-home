"""Schemas describing rule-based field extraction over OCR text.

The extractors (see :mod:`app.extract.extractors`) scan recognised text for the
regex-friendly TTB label fields and emit :class:`FieldCandidate` objects: a
normalised value plus *where* it came from (which OCR line and the character
span within it) and *how* confident the rule is. Downstream matching/verifier
logic consumes these candidates rather than re-parsing raw text.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, Field

from app.ocr.schemas import BoundingBox


class FieldName(enum.StrEnum):
    """Label fields recovered by the deterministic extractors.

    These map onto columns on :class:`app.models.application.Application` that an
    agent verifies the artwork against.
    """

    ABV = "abv"
    PROOF = "proof"
    NET_CONTENTS = "net_contents"
    COUNTRY_OF_ORIGIN = "country_of_origin"
    BOTTLER_ADDRESS = "bottler_address"


class SourceSpan(BaseModel):
    """Where a candidate was found in the OCR output.

    ``line_index`` indexes :attr:`app.ocr.schemas.OcrResult.lines` (``None`` when
    a rule was run over a bare string with no line context). ``start``/``end``
    are character offsets into that line's text, so callers can highlight the
    exact substring that matched.
    """

    line_index: int | None = None
    start: int
    end: int


class FieldCandidate(BaseModel):
    """One regex hit for a label field.

    A field may yield several candidates (e.g. two plausible net-contents
    statements on a label); ranking/disambiguation is left to the caller via
    :meth:`ExtractionResult.for_field`.
    """

    field: FieldName
    # Normalised, comparable value: ABV/proof as a numeric string ("45",
    # "45.5"), net contents canonicalised ("750 mL"), country/address cleaned.
    value: str
    # The exact substring that matched, verbatim from the source text.
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    span: SourceSpan
    # Bounding box of the source line, when extracted from an OcrResult.
    box: BoundingBox | None = None


class ExtractionResult(BaseModel):
    """All field candidates recovered from a single label's OCR output."""

    candidates: list[FieldCandidate] = Field(default_factory=list)

    def for_field(self, field: FieldName) -> list[FieldCandidate]:
        """Candidates for ``field``, highest confidence first."""
        matches = [c for c in self.candidates if c.field == field]
        return sorted(matches, key=lambda c: c.confidence, reverse=True)

    def best(self, field: FieldName) -> FieldCandidate | None:
        """The highest-confidence candidate for ``field``, or ``None``."""
        matches = self.for_field(field)
        return matches[0] if matches else None
