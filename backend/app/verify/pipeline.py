"""Adaptive multi-pass verification: label image → verdict.

:func:`verify_label_image` is the image-in entry point the API and evals share.
Pass 1 is the standard *preprocess → OCR → verify* path. When that pass leaves
mandatory content unrecovered, conditional **rescue passes** re-read the same
pixels harder — fixing the two failure families the real-COLA eval exposed:

* **Rotation rescue** — on can wraps and keg collars the text (and almost
  always the Government Warning) runs 90° to the artwork, which the detector
  cannot see at all. The whole image is re-OCR'd rotated ±90° and the per-field
  results merged, with every box mapped back to the original orientation so the
  UI overlay still lands on the right pixels.
* **Warning zoom rescue** — the Government Warning is the smallest print on the
  label, and at native resolution the detector routinely drops one of its lines
  (turning a word-perfect statement into "altered"). The region around the
  located ``GOVERNMENT WARNING`` header is cropped, upscaled, and re-OCR'd, and
  the warning re-verified on that focused read.

Rescue passes can only *recover what is printed* — they re-read the same
pixels with more effort, exactly as a human reviewer rotates a can wrap or
leans in to squint at the fine print. A genuinely missing warning stays missing
in every orientation; a tampered statement reads as tampered however large it
is rendered. Merging takes the best verdict per field, mirroring how the eval
(and a reviewer) treats the set of label images on one COLA.

Both rescues are conditional, so clean labels stay a single OCR pass and the
hot path keeps its latency; the extra passes are paid only on labels that
would otherwise fail — where a false MISMATCH costs an agent far more than a
second of compute.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence

import cv2
import numpy as np

from app.ocr.preprocess import preprocess_image
from app.ocr.schemas import BoundingBox, OcrResult, TextLine
from app.ocr.service import ImageInput, OcrService, get_ocr_service
from app.verify.aggregate import build_result
from app.verify.engine import ExpectedFields, verify_label
from app.verify.schemas import (
    FieldResult,
    FieldStatus,
    GovernmentWarningResult,
    VerificationResult,
    WarningVerdict,
)
from app.verify.warning import verify_government_warning, verify_warning_from_ocr

# Maps a point in a rescue frame (rotated/cropped image) back to coordinates on
# the original (preprocessed) image, so boxes always overlay the upload.
_PointMapper = Callable[[float, float], tuple[float, float]]

# Verdict preference when merging passes (lower is better). A rescue pass only
# replaces a field when it read the label strictly better.
_FIELD_RANK = {
    FieldStatus.MATCH: 0,
    FieldStatus.SOFT_WARNING: 1,
    FieldStatus.MISMATCH: 2,
    FieldStatus.NOT_CHECKED: 3,
}
_WARNING_RANK = {
    WarningVerdict.COMPLIANT: 0,
    WarningVerdict.ALTERED: 1,
    WarningVerdict.MISSING: 2,
}

# An ALTERED warning at/above this similarity means the statement was located
# and substantially read in this orientation — only the zoom rescue can help.
# Below it, the header match is likely incidental (the body runs rotated), so
# the rotation rescue is still worth paying for.
_ROTATION_SIMILARITY_CEILING = 0.7

# Warning zoom rescue: crop from just above the header down far enough to cover
# the wrapped statement (it spans ~5 printed lines; 14 header-heights is
# generous without pulling in half the label), then upscale so the line height
# approaches what the recogniser was trained on.
_WARNING_PAD_ABOVE_LINES = 1.5
_WARNING_REGION_LINES = 14.0
_WARNING_TARGET_LINE_PX = 48.0
_ZOOM_MIN_SCALE = 1.5
_ZOOM_MAX_SCALE = 3.0


def verify_label_image(
    expected: ExpectedFields,
    image: ImageInput,
    *,
    ocr: OcrService | None = None,
) -> tuple[VerificationResult, OcrResult]:
    """Verify a label image against the expected COLA, with rescue passes.

    Returns ``(result, primary_ocr)``: the merged verification result and the
    first-pass OCR output (whose lines/boxes describe the upload as-is — used
    for the unreadable-image check and the image-quality assessment).
    """
    ocr = ocr or get_ocr_service()
    base = preprocess_image(image, max_side=ocr.max_side)

    primary = ocr.extract(base)
    result = verify_label(expected, primary)
    if not primary.lines:
        return result, primary

    # Frames the warning may live in: (image, frame→original mapper, OCR read).
    frames: list[tuple[np.ndarray, _PointMapper | None, OcrResult]] = [(base, None, primary)]

    def _rotate_and_merge(
        current: VerificationResult,
        still_wanted: Callable[[VerificationResult], bool] = _wants_rotation_rescue,
    ) -> VerificationResult:
        for rotated, mapper in _rotations(base):
            frame_ocr = ocr.extract(rotated)
            if not frame_ocr.lines:
                continue
            frames.append((rotated, mapper, frame_ocr))
            rescue = verify_label(expected, _remap_result(frame_ocr, mapper))
            current = _merge_results(current, rescue)
            if not still_wanted(current):
                break
        return current

    if _wants_rotation_rescue(result):
        result = _rotate_and_merge(result)

    if result.government_warning.verdict is not WarningVerdict.COMPLIANT:
        rescued = _zoom_rescue_warning(frames, result.government_warning, ocr)
        if rescued is not None:
            result = build_result(result.fields, rescued)

    # The warning must not depend on *other* fields failing to earn its rescue:
    # when it is still ALTERED after the zoom and the rotation frames were never
    # produced (every other field verified cleanly), rotate now for the
    # warning's own sake and re-run the zoom over the new frames — a rotated
    # read often recovers the statement line the straight pass dropped.
    if result.government_warning.verdict is not WarningVerdict.COMPLIANT and len(frames) == 1:
        result = _rotate_and_merge(
            result,
            still_wanted=lambda r: r.government_warning.verdict is not WarningVerdict.COMPLIANT,
        )
        if result.government_warning.verdict is not WarningVerdict.COMPLIANT and len(frames) > 1:
            rescued = _zoom_rescue_warning(frames[1:], result.government_warning, ocr)
            if rescued is not None:
                result = build_result(result.fields, rescued)

    # Last resort for circular layouts (keg collars / cap rings): the warning
    # follows an arc, unreadable in any straight orientation. Unwrap the label
    # around its detected circle so the arc becomes a horizontal line.
    if result.government_warning.verdict is not WarningVerdict.COMPLIANT:
        rescued = _arc_rescue_warning(base, result.government_warning, ocr)
        if rescued is not None:
            result = build_result(result.fields, rescued)

    return result, primary


def verify_label_images(
    expected: ExpectedFields,
    images: Sequence[ImageInput],
    *,
    ocr: OcrService | None = None,
) -> tuple[VerificationResult, list[OcrResult]]:
    """Verify a filing's *full label set* against the expected COLA.

    A COLA filing comprises several label images — front, back, neck — and the
    mandatory content is split across them (the Government Warning usually sits
    on the back label, ABV on the front). Each image runs through
    :func:`verify_label_image`; the per-field results merge on best verdict,
    the way a reviewer reads the whole filing: content recovered on *any* label
    is on the filing, and the warning is MISSING only when no label carries it.

    One guard the best-verdict merge alone would lose: when two images yield
    *different concrete readings* of the same field (front prints 40 % ABV,
    back prints 45 %), a clean match would silently forgive a contradictory
    filing — that field is downgraded to a soft warning instead, so a human
    looks at it.

    Every field/warning result carries ``image_index`` — which image its
    verdict (and box) came from. Returns the merged result plus each image's
    first-pass OCR read, in input order.
    """
    if not images:
        raise ValueError("verify_label_images requires at least one image")
    ocr = ocr or get_ocr_service()

    per_image: list[VerificationResult] = []
    reads: list[OcrResult] = []
    for index, image in enumerate(images):
        result, primary = verify_label_image(expected, image, ocr=ocr)
        reads.append(primary)
        per_image.append(_tag_image_index(result, index) if len(images) > 1 else result)

    merged = per_image[0]
    for nxt in per_image[1:]:
        merged = _merge_results(merged, nxt)
    if len(per_image) > 1:
        merged = _flag_image_disagreements(merged, per_image)
    return merged, reads


def _tag_image_index(result: VerificationResult, index: int) -> VerificationResult:
    """``result`` with every field and the warning stamped as read from image
    ``index``, so the merged verdict keeps box provenance per image."""
    fields = [field.model_copy(update={"image_index": index}) for field in result.fields]
    warning = result.government_warning.model_copy(update={"image_index": index})
    return result.model_copy(update={"fields": fields, "government_warning": warning})


def _flag_image_disagreements(
    merged: VerificationResult, per_image: list[VerificationResult]
) -> VerificationResult:
    """Downgrade a merged MATCH to SOFT_WARNING when another image disagrees.

    Applies when a field matched on one image while another image yielded a
    *located, different* reading (MISMATCH with ``found`` set — the valued
    fields, e.g. ABV, keep their conflicting reading; fuzzy presence fields
    blank ``found`` on a confirmed miss, so absence alone never counts as a
    disagreement). The filing then prints two different values for one field,
    which deserves a human glance, not a silent pass on the matching one.
    """
    conflicts: dict[str, FieldResult] = {}
    for result in per_image:
        for field in result.fields:
            if field.status is FieldStatus.MISMATCH and field.found is not None:
                conflicts.setdefault(field.field, field)

    fields: list[FieldResult] = []
    changed = False
    for field in merged.fields:
        conflict = conflicts.get(field.field)
        if field.status is FieldStatus.MATCH and conflict is not None:
            where = (
                f"image {conflict.image_index + 1}"
                if conflict.image_index is not None
                else "another image"
            )
            field = field.model_copy(
                update={
                    "status": FieldStatus.SOFT_WARNING,
                    "reason": (
                        f"{field.reason}; but {where} shows a different reading "
                        f"({conflict.found!r}) — the filing's labels disagree, "
                        "flagged for review"
                    ),
                }
            )
            changed = True
        fields.append(field)
    if not changed:
        return merged
    return build_result(fields, merged.government_warning)


def _wants_rotation_rescue(result: VerificationResult) -> bool:
    """Whether re-reading the image rotated ±90° could still improve ``result``.

    True when the Government Warning was not found (or only incidentally — its
    body unread), or when a checked field mismatched with *nothing located on
    the label*: the signatures of text running across the artwork. A genuine
    value disagreement (the label legibly shows a different ABV) does not
    trigger a rescue — rotating it would re-read the same disagreement.
    """
    warning = result.government_warning
    if warning.verdict is WarningVerdict.MISSING:
        return True
    if (
        warning.verdict is WarningVerdict.ALTERED
        and warning.similarity < _ROTATION_SIMILARITY_CEILING
    ):
        return True
    return any(
        field.status is FieldStatus.MISMATCH and field.found is None for field in result.fields
    )


def _rotations(image: np.ndarray) -> Iterator[tuple[np.ndarray, _PointMapper]]:
    """The ±90° rotations of ``image``, each with its frame→original mapper."""
    height, width = image.shape[:2]
    yield (
        cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE),
        lambda x, y: (width - 1 - y, x),
    )
    yield (
        cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE),
        lambda x, y: (y, height - 1 - x),
    )


def _remap_result(result: OcrResult, mapper: _PointMapper) -> OcrResult:
    """``result`` with every polygon/box mapped back to original coordinates.

    Text, confidences, and line order are untouched — the lines were read in
    the rescue frame's (correct) reading order; only the geometry moves.
    """
    lines: list[TextLine] = []
    for line in result.lines:
        polygon = [mapper(x, y) for x, y in line.polygon]
        lines.append(
            TextLine(
                text=line.text,
                confidence=line.confidence,
                polygon=polygon,
                box=BoundingBox.from_polygon(polygon),
            )
        )
    return OcrResult(lines=lines, elapsed_ms=result.elapsed_ms)


def _merge_results(primary: VerificationResult, rescue: VerificationResult) -> VerificationResult:
    """Best verdict per field (and for the warning) across the two passes.

    Mirrors how a reviewer treats multiple looks at the same label: content
    recovered in *any* orientation is on the label. The roll-up (overall
    verdict, summary, rationale) is rebuilt from the merged parts.
    """
    rescued_fields = {field.field: field for field in rescue.fields}
    fields: list[FieldResult] = []
    for field in primary.fields:
        candidate = rescued_fields.get(field.field)
        if candidate is not None and _FIELD_RANK[candidate.status] < _FIELD_RANK[field.status]:
            field = candidate
        fields.append(field)

    warning = primary.government_warning
    if _warning_improves(rescue.government_warning, over=warning):
        warning = rescue.government_warning

    return build_result(fields, warning)


def _warning_improves(candidate: GovernmentWarningResult, *, over: GovernmentWarningResult) -> bool:
    """Whether ``candidate`` is a strictly better read of the warning.

    A better verdict wins outright; at the same verdict a higher wording
    similarity means more of the statement was actually recovered.
    """
    if _WARNING_RANK[candidate.verdict] != _WARNING_RANK[over.verdict]:
        return _WARNING_RANK[candidate.verdict] < _WARNING_RANK[over.verdict]
    return candidate.similarity > over.similarity


# Arc rescue bounds: how many candidate circles to unwrap, and the angular
# sampling of the polar strip (≈ one sample per circumference pixel at the
# radii keg collars use).
_ARC_MAX_CIRCLES = 3
_ARC_ANGULAR_SAMPLES = 3600

# Words that mark a strip line as part of the warning statement, for locating
# the block to re-read tightly.
_ARC_WARNING_KEYWORDS = (
    "government",
    "warning",
    "surgeon",
    "pregnancy",
    "birth",
    "consumption",
    "machinery",
    "health",
)


def _arc_rescue_warning(
    image: np.ndarray,
    current: GovernmentWarningResult,
    ocr: OcrService,
) -> GovernmentWarningResult | None:
    """Re-read a circular label by unwrapping it around its detected circle.

    Keg collars and cap rings print the Government Warning along an arc —
    every word at a different angle, unreadable in any straight orientation.
    The label's circular cutout/rim is a true circle in flat artwork, so a
    Hough detection gives the arc's center; a polar unwrap around it turns the
    arc into a horizontal line of text. The strip is tiled half a turn past
    360° so a line crossing the polar seam appears contiguous in the copy
    (word coverage is set-based, so the duplicated words are harmless).

    Returns the improved verdict, or ``None`` when no circle helps. Like every
    rescue, it can only recover printed words — a dropped or reworded clause is
    absent at any unwrap angle and still fails the coverage check.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    height, width = gray.shape[:2]
    shortest = min(height, width)
    circles = cv2.HoughCircles(
        cv2.medianBlur(gray, 5),
        cv2.HOUGH_GRADIENT,
        dp=1.5,
        minDist=shortest // 4,
        param1=120,
        param2=80,
        minRadius=shortest // 8,
        maxRadius=int(shortest * 0.6),
    )
    if circles is None:
        return None

    best: GovernmentWarningResult | None = None
    texts: list[str] = []
    for cx, cy, radius in circles[0][:_ARC_MAX_CIRCLES]:
        corner = max(float(np.hypot(x - cx, y - cy)) for x in (0, width) for y in (0, height))
        max_radius = min(radius * 2.2, corner)
        strip = cv2.warpPolar(
            image,
            (int(max_radius), _ARC_ANGULAR_SAMPLES),
            (float(cx), float(cy)),
            max_radius,
            cv2.WARP_POLAR_LINEAR,
        )
        strip = cv2.rotate(strip, cv2.ROTATE_90_COUNTERCLOCKWISE)  # angle → x-axis

        # Whole-strip read: detection sees the (downscaled) full strip, which
        # groups the long unwrapped lines well; recognition still works from
        # the strip's native resolution. A half-turn roll re-reads the strip
        # with the polar seam moved, so a line the seam cut lands contiguous.
        read = ocr.extract(strip)
        if not read.lines:
            continue
        texts.append(read.full_text)
        rolled = ocr.extract(np.roll(strip, strip.shape[1] // 2, axis=1))
        if rolled.lines:
            texts.append(rolled.full_text)

        # Tight re-read of the warning block: detection drops lines in the
        # densely-stacked statement at strip scale, so crop the block (the
        # extract above reports boxes in its downscaled frame — scale back),
        # read it both ways up, slightly enlarged. Unwrapped arc text comes out
        # upside-down whenever the arc runs the lower half of the circle.
        scale_back = strip.shape[1] / max(1, ocr.max_side)
        keyword_boxes = [
            line.box
            for line in read.lines
            if any(k in line.text.lower() for k in _ARC_WARNING_KEYWORDS)
        ]
        if keyword_boxes and scale_back > 0:
            x0 = max(0, int(min(b.x_min for b in keyword_boxes) * scale_back) - 20)
            x1 = min(strip.shape[1], int(max(b.x_max for b in keyword_boxes) * scale_back) + 20)
            y0 = max(0, int(min(b.y_min for b in keyword_boxes) * scale_back) - 20)
            y1 = min(strip.shape[0], int(max(b.y_max for b in keyword_boxes) * scale_back) + 20)
            block = strip[y0:y1, x0:x1]
            if block.size:
                # Two scales x both orientations: detection on dense curved
                # stacks is fickle, and any one read recovering a line is
                # enough for the union's word coverage.
                for scale in (1.5, 2.0):
                    zoomed = cv2.resize(
                        block, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
                    )
                    for oriented in (zoomed, cv2.rotate(zoomed, cv2.ROTATE_180)):
                        reread = ocr.extract(oriented, max_side=max(oriented.shape[:2]))
                        if reread.lines:
                            texts.append(reread.full_text)

        # Verify over the union of every arc read so far: each pass recovers a
        # different stretch of the circle, and the word-coverage check needs
        # the full inventory, not any single read. Tampering stays caught — a
        # dropped or reworded word is absent from every read.
        rescued = verify_government_warning("\n".join(texts))
        if rescued.verdict is WarningVerdict.MISSING:
            continue
        # The strip's geometry has no meaning on the original image.
        rescued.box = None
        rescued.span = None
        rescued.limitations = [
            *rescued.limitations,
            "Read by unwrapping the label's circular layout; the highlight box is "
            "unavailable for arc text.",
        ]
        if _warning_improves(rescued, over=best or current):
            best = rescued
            if best.verdict is WarningVerdict.COMPLIANT:
                break
    return best


def _zoom_rescue_warning(
    frames: list[tuple[np.ndarray, _PointMapper | None, OcrResult]],
    current: GovernmentWarningResult,
    ocr: OcrService,
) -> GovernmentWarningResult | None:
    """Re-read the warning region cropped + upscaled, in every frame it appears.

    Returns the improved :class:`GovernmentWarningResult` (box mapped back to
    original coordinates), or ``None`` when no frame's zoomed read beats
    ``current``.
    """
    best: GovernmentWarningResult | None = None
    for frame_image, frame_mapper, frame_ocr in frames:
        located = verify_warning_from_ocr(frame_ocr)
        if located.box is None:
            continue
        rescued = _zoom_read(frame_image, located.box, ocr, frame_mapper)
        if rescued is None:
            continue
        if _warning_improves(rescued, over=best or current):
            best = rescued
            if best.verdict is WarningVerdict.COMPLIANT:
                break
    return best


def _zoom_read(
    frame_image: np.ndarray,
    header_box: BoundingBox,
    ocr: OcrService,
    frame_mapper: _PointMapper | None,
) -> GovernmentWarningResult | None:
    """One zoomed re-read: crop around ``header_box``, upscale, OCR, re-verify.

    The crop spans the frame's full width (the statement wraps wider than the
    header) from just above the header through the statement's expected depth.
    The upscale targets a recogniser-friendly line height; ``max_side`` is
    lifted past the service cap so the gained resolution is not resized away
    (detection cost stays bounded by the engine's own limit).
    """
    height, width = frame_image.shape[:2]
    line_height = max(header_box.height, 1.0)
    y0 = max(0, int(header_box.y_min - _WARNING_PAD_ABOVE_LINES * line_height))
    y1 = min(height, int(header_box.y_min + _WARNING_REGION_LINES * line_height))
    if y1 - y0 < 2:
        return None
    crop = frame_image[y0:y1, 0:width]

    scale = min(_ZOOM_MAX_SCALE, max(_ZOOM_MIN_SCALE, _WARNING_TARGET_LINE_PX / line_height))
    zoomed = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    read = ocr.extract(zoomed, max_side=max(zoomed.shape[:2]))
    if not read.lines:
        return None
    rescued = verify_warning_from_ocr(read)
    if rescued.verdict is WarningVerdict.MISSING:
        return None

    if rescued.box is not None:
        corners = [
            (rescued.box.x_min, rescued.box.y_min),
            (rescued.box.x_max, rescued.box.y_min),
            (rescued.box.x_max, rescued.box.y_max),
            (rescued.box.x_min, rescued.box.y_max),
        ]
        points = [(x / scale, y0 + y / scale) for x, y in corners]
        if frame_mapper is not None:
            points = [frame_mapper(x, y) for x, y in points]
        rescued.box = BoundingBox.from_polygon(points)
    return rescued
