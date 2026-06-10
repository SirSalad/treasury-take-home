"""Rule-based extraction of regex-friendly TTB label fields from OCR text.

Public API:

* :func:`extract_fields` — extract all fields from an :class:`~app.ocr.schemas.OcrResult`.
* :func:`extract_from_text` — run the extractors over a bare string.
* :class:`ExtractionResult`, :class:`FieldCandidate`, :class:`FieldName`,
  :class:`SourceSpan` — output schemas.
"""

from app.extract.extractors import extract_fields, extract_from_text
from app.extract.schemas import (
    ExtractionResult,
    FieldCandidate,
    FieldName,
    SourceSpan,
)

__all__ = [
    "ExtractionResult",
    "FieldCandidate",
    "FieldName",
    "SourceSpan",
    "extract_fields",
    "extract_from_text",
]
