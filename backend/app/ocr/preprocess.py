"""Image preprocessing applied before OCR.

A single, cheap normalisation step sits in front of the OCR engine so the
benchmarked pipeline matches what production runs: *preprocess → OCR → extract*.

The one transform that matters for the 5-second latency budget is **bounding the
working resolution**. OCR cost scales with pixel area, and agents upload anything
from a tight 600px crop to a 4000px phone photo. Downscaling oversized images so
their longest side is at most :data:`DEFAULT_MAX_SIDE` caps the worst-case cost
without touching already-small labels (the synthetic corpus is ~900px, so the
cap is a no-op there) and keeps text large enough to read — the mandatory
Government Health Warning is the smallest print on the label and must survive.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

# Longest-side cap, in pixels. Generous enough to leave the corpus and typical
# label crops untouched while taming multi-megapixel phone photos. Tunable via
# ``Settings.ocr_max_side`` (see :mod:`app.config`).
DEFAULT_MAX_SIDE = 1600

# Same input union the OCR service accepts: a path, raw encoded bytes (an upload
# body), or an already-decoded BGR/grayscale ndarray.
ImageInput = str | Path | bytes | np.ndarray


def decode_image(image: ImageInput) -> np.ndarray:
    """Decode ``image`` to a BGR ndarray.

    Accepts a filesystem path, raw encoded bytes, or an ndarray (returned
    as-is). Raises :class:`ValueError` if bytes/path cannot be decoded so a bad
    upload fails loudly rather than silently OCR-ing nothing.
    """
    if isinstance(image, np.ndarray):
        return image
    if isinstance(image, (str, Path)):
        decoded = cv2.imread(str(image), cv2.IMREAD_COLOR)
        if decoded is None:
            raise ValueError(f"could not read image file: {image}")
        return decoded
    if isinstance(image, (bytes, bytearray)):
        buffer = np.frombuffer(bytes(image), dtype=np.uint8)
        decoded = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if decoded is None:
            raise ValueError("could not decode image bytes")
        return decoded
    raise TypeError(f"unsupported image input type: {type(image)!r}")


def downscale_to_max_side(image: np.ndarray, max_side: int) -> np.ndarray:
    """Downscale ``image`` so its longest side is at most ``max_side``.

    Only ever shrinks (never upscales): small labels keep full fidelity, large
    uploads are capped. Uses ``INTER_AREA``, the right interpolation for
    shrinking — it averages source pixels, preserving small-text legibility
    better than the default bilinear resize.
    """
    height, width = image.shape[:2]
    longest = max(height, width)
    if max_side <= 0 or longest <= max_side:
        return image
    scale = max_side / longest
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)


def preprocess_image(image: ImageInput, *, max_side: int = DEFAULT_MAX_SIDE) -> np.ndarray:
    """Decode and resolution-bound an image for OCR.

    The single entry point used by :class:`app.ocr.service.OcrService`; returns a
    BGR ndarray with its longest side capped at ``max_side``.
    """
    return downscale_to_max_side(decode_image(image), max_side)
