"""Image-quality assessment derived from the OCR result.

Real-world photos (a phone shot in a liquor store) are often blurry, angled, or
badly lit. Rather than silently returning a weak verdict on an unreadable image,
the API surfaces a quality signal so the UI can ask for a better photo. The
signal is read straight off the OCR output — no extra model pass — using the
recognition confidence the engine already reports per line.

This is deliberately *not* image preprocessing: PP-OCRv4 is a deep-learning
engine already robust to lighting/noise/skew, and classic binarise/threshold
preprocessing was measured to give no accuracy lift in front of it. Telling the
user to retake a genuinely poor photo is the higher-value intervention.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.ocr.schemas import OcrResult

# A character read below this confidence is treated as "garbled".
LOW_CONFIDENCE_CHAR = 0.6
# Length-weighted mean confidence below this flags a poor read overall.
LOW_MEAN_CONFIDENCE = 0.85
# Fraction of recognised characters that may be garbled before we flag the image.
MAX_LOW_CONFIDENCE_FRACTION = 0.15
# Fewer detected text regions than this on a label suggests detection largely
# failed (heavy blur / glare).
MIN_TEXT_REGIONS = 3

RETAKE_MESSAGE = (
    "Some of the label was hard to read. For the most reliable check, retake the "
    "photo in even lighting, straight-on, with the label in focus and filling the "
    "frame."
)
NO_TEXT_MESSAGE = "No readable text was found on the image. " + RETAKE_MESSAGE


class ImageQuality(BaseModel):
    """How readable the uploaded image was, for retake guidance in the UI."""

    level: Literal["ok", "low"]
    # Length-weighted mean recognition confidence over all detected text, [0, 1].
    mean_confidence: float = Field(ge=0.0, le=1.0)
    # Number of detected text regions (lines).
    text_regions: int = Field(ge=0)
    # A human-facing retake prompt when ``level`` is "low"; ``None`` when "ok".
    message: str | None = None


def assess_image_quality(ocr: OcrResult) -> ImageQuality:
    """Grade how readable ``ocr``'s source image was, for retake guidance.

    Flags the image as ``low`` when the engine read little/garbled text — low
    length-weighted mean confidence, a sizeable fraction of garbled characters,
    or too few detected regions — any of which means the verdict below should be
    treated cautiously and a clearer photo would help.
    """
    lines = ocr.lines
    if not lines:
        return ImageQuality(
            level="low", mean_confidence=0.0, text_regions=0, message=NO_TEXT_MESSAGE
        )

    total_chars = sum(len(line.text) for line in lines) or 1
    weighted_confidence = (
        sum(line.confidence * len(line.text) for line in lines) / total_chars
    )
    garbled_chars = sum(len(line.text) for line in lines if line.confidence < LOW_CONFIDENCE_CHAR)
    garbled_fraction = garbled_chars / total_chars

    poor = (
        weighted_confidence < LOW_MEAN_CONFIDENCE
        or garbled_fraction > MAX_LOW_CONFIDENCE_FRACTION
        or len(lines) < MIN_TEXT_REGIONS
    )
    return ImageQuality(
        level="low" if poor else "ok",
        mean_confidence=round(weighted_confidence, 3),
        text_regions=len(lines),
        message=RETAKE_MESSAGE if poor else None,
    )
