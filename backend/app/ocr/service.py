"""RapidOCR (ONNXRuntime) text-extraction service.

Wraps :class:`rapidocr_onnxruntime.RapidOCR` behind a small, typed interface
that returns :class:`~app.ocr.schemas.OcrResult`. Two requirements shape this
module:

* **No network at runtime.** The TTB network blocks outbound traffic, so the
  detection/classification/recognition ONNX models are vendored in
  ``app/ocr/models`` and loaded by explicit path — RapidOCR never reaches out
  to download anything.
* **Warm start.** The first inference pays a one-time cost to build the ONNX
  sessions and allocate buffers. :meth:`OcrService.warmup` runs a tiny labelled
  image through the full pipeline at application startup so the first real
  request stays inside the ~5s latency budget agents expect.
"""

from __future__ import annotations

import logging
import time
from functools import lru_cache
from pathlib import Path

import numpy as np
from rapidocr_onnxruntime import RapidOCR

from app.config import get_settings
from app.ocr.preprocess import preprocess_image
from app.ocr.schemas import BoundingBox, OcrResult, TextLine

logger = logging.getLogger(__name__)

# Vendored model files (shipped in the repo; see module docstring).
MODELS_DIR = Path(__file__).parent / "models"
DET_MODEL = MODELS_DIR / "ch_PP-OCRv3_det_infer.onnx"
REC_MODEL = MODELS_DIR / "ch_PP-OCRv3_rec_infer.onnx"
CLS_MODEL = MODELS_DIR / "ch_ppocr_mobile_v2.0_cls_infer.onnx"

# Accepted image inputs: a filesystem path, raw encoded bytes (upload body), or
# a decoded BGR/grayscale ndarray (e.g. after preprocessing).
ImageInput = str | Path | bytes | np.ndarray


class OcrService:
    """Stateful wrapper around a RapidOCR engine with pinned local models.

    The engine is relatively expensive to construct (it loads three ONNX
    models), so a single instance is shared across requests via
    :func:`get_ocr_service`.
    """

    def __init__(
        self,
        *,
        use_cls: bool = True,
        max_side: int | None = None,
        rec_batch_num: int | None = None,
    ) -> None:
        for model in (DET_MODEL, REC_MODEL, CLS_MODEL):
            if not model.exists():
                raise FileNotFoundError(
                    f"OCR model missing: {model}. Models must be vendored locally "
                    "(no runtime download is permitted)."
                )
        settings = get_settings()
        self._max_side = settings.ocr_max_side if max_side is None else max_side
        rec_batch = settings.ocr_rec_batch_num if rec_batch_num is None else rec_batch_num
        # use_cls enables the angle classifier so text photographed upside-down
        # or sideways is still read — labels are often shot at odd angles.
        #
        # det_limit_type="max" bounds the detector's working resolution by the
        # *longest* side (the default "min" pads the shortest side up to 736,
        # needlessly upscaling small labels). Paired with the preprocess cap this
        # keeps OCR cost — and latency — bounded; see the 5s budget harness.
        self._engine = RapidOCR(
            det_model_path=str(DET_MODEL),
            rec_model_path=str(REC_MODEL),
            cls_model_path=str(CLS_MODEL),
            use_cls=use_cls,
            det_limit_type="max",
            det_limit_side_len=float(self._max_side),
            rec_batch_num=rec_batch,
        )

    def extract(self, image: ImageInput) -> OcrResult:
        """Run OCR on ``image`` and return recognised lines with boxes.

        ``image`` may be a path, raw encoded bytes, or a decoded ndarray. It is
        run through :func:`app.ocr.preprocess.preprocess_image` first (decode +
        resolution cap) so the timed path matches production's
        *preprocess → OCR → extract* pipeline.
        """
        start = time.perf_counter()
        payload = preprocess_image(image, max_side=self._max_side)
        raw, _ = self._engine(payload)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        lines: list[TextLine] = []
        # ``raw`` is None when nothing is detected (e.g. a blank image).
        for polygon, text, confidence in raw or []:
            points = [(float(x), float(y)) for x, y in polygon]
            lines.append(
                TextLine(
                    text=text,
                    confidence=float(confidence),
                    polygon=points,
                    box=BoundingBox.from_polygon(points),
                )
            )

        return OcrResult(lines=lines, elapsed_ms=elapsed_ms)

    def warmup(self) -> None:
        """Force ONNX session init by running a small labelled image through.

        Uses a synthetic image with text so every stage (detection,
        classification, recognition) is exercised — a blank image would only
        warm the detector.
        """
        start = time.perf_counter()
        self.extract(_warmup_image())
        logger.info(
            "OCR warmup complete in %.0f ms (models pinned at %s)",
            (time.perf_counter() - start) * 1000.0,
            MODELS_DIR,
        )


def _warmup_image() -> np.ndarray:
    """A tiny white canvas with dark text, as a BGR ndarray.

    Built with numpy/OpenCV (no Pillow dependency) so warmup has no extra
    imports. The content only needs to make the recogniser fire.
    """
    import cv2

    canvas = np.full((48, 160, 3), 255, dtype=np.uint8)
    cv2.putText(canvas, "WARMUP 123", (6, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    return canvas


@lru_cache
def get_ocr_service() -> OcrService:
    """Return the process-wide :class:`OcrService` (built on first use)."""
    return OcrService()
