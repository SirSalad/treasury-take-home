"""Fuzzy matching of free-text label fields (brand name, class/type).

Public API:

* :func:`match_field` — fuzzy-match an expected value against a text block.
* :func:`match_from_ocr` — match against an :class:`~app.ocr.schemas.OcrResult`.
* :func:`score_presence` — the field-agnostic grader behind the above, reused by
  the verification engine for the other free-text fields.
* :class:`FieldMatch`, :class:`MatchStatus`, :class:`FuzzyFieldName`,
  :class:`PresenceScore` — output schemas.
"""

from app.match.matcher import (
    HIGH_THRESHOLD,
    LOW_THRESHOLD,
    PresenceScore,
    match_field,
    match_from_ocr,
    score_presence,
)
from app.match.schemas import FieldMatch, FuzzyFieldName, MatchStatus

__all__ = [
    "HIGH_THRESHOLD",
    "LOW_THRESHOLD",
    "FieldMatch",
    "FuzzyFieldName",
    "MatchStatus",
    "PresenceScore",
    "match_field",
    "match_from_ocr",
    "score_presence",
]
