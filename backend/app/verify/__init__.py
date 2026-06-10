"""Verification of label artwork against expected (application) data.

This package compares recovered label text against the COLA an agent filed. The
mandatory Government Health Warning is checked here on a dedicated exact-match
path (the rest of the engine uses fuzzy field matching).

Public API:

* :func:`verify_government_warning` — verify the warning in a string of OCR text.
* :func:`verify_warning_from_ocr` — verify over an :class:`~app.ocr.schemas.OcrResult`,
  attaching the source line/box.
* :class:`GovernmentWarningResult`, :class:`WarningVerdict` — output schemas.
* :data:`GOVERNMENT_WARNING_TEXT` — the canonical 27 CFR 16.21 statement.
"""

from app.verify.schemas import (
    GOVERNMENT_WARNING_TEXT,
    GovernmentWarningResult,
    WarningVerdict,
)
from app.verify.warning import verify_government_warning, verify_warning_from_ocr

__all__ = [
    "GOVERNMENT_WARNING_TEXT",
    "GovernmentWarningResult",
    "WarningVerdict",
    "verify_government_warning",
    "verify_warning_from_ocr",
]
