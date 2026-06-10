"""Fuzzy matching of free-text label fields (brand name, class/type).

Public API:

* :func:`match_field` — fuzzy-match an expected value against a text block.
* :func:`match_from_ocr` — match against an :class:`~app.ocr.schemas.OcrResult`.
* :class:`FieldMatch`, :class:`MatchStatus`, :class:`FuzzyFieldName` — output
  schemas.
"""

from app.match.matcher import (
    HIGH_THRESHOLD,
    LOW_THRESHOLD,
    match_field,
    match_from_ocr,
)
from app.match.schemas import FieldMatch, FuzzyFieldName, MatchStatus

__all__ = [
    "HIGH_THRESHOLD",
    "LOW_THRESHOLD",
    "FieldMatch",
    "FuzzyFieldName",
    "MatchStatus",
    "match_field",
    "match_from_ocr",
]
