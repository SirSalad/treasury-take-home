"""OCR text extraction (RapidOCR / ONNXRuntime).

Public API:

* :func:`get_ocr_service` — the shared, warmed :class:`OcrService`.
* :class:`OcrResult`, :class:`TextLine`, :class:`BoundingBox` — output schemas.
"""

from app.ocr.schemas import BoundingBox, OcrResult, TextLine
from app.ocr.service import OcrService, get_ocr_service

__all__ = [
    "BoundingBox",
    "OcrResult",
    "OcrService",
    "TextLine",
    "get_ocr_service",
]
