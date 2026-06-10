"""Pydantic schemas describing OCR output.

These are the stable, serialisable shapes the rest of the pipeline (field
extraction, the verification API) consumes — independent of the underlying OCR
engine. A detection is one line of recognised text plus where it sits on the
image and how confident the model is.
"""

from pydantic import BaseModel, Field

# A detection polygon as returned by the detector: four ``[x, y]`` corner points
# in (top-left, top-right, bottom-right, bottom-left) order.
Polygon = list[tuple[float, float]]


class BoundingBox(BaseModel):
    """Axis-aligned bounding box, derived from a detection polygon.

    Most downstream logic (reading order, region matching) only needs an
    axis-aligned box; the original :attr:`TextLine.polygon` is kept for callers
    that care about rotation.
    """

    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    @classmethod
    def from_polygon(cls, polygon: Polygon) -> "BoundingBox":
        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        return cls(x_min=min(xs), y_min=min(ys), x_max=max(xs), y_max=max(ys))


class TextLine(BaseModel):
    """One recognised line of text and its location on the image."""

    text: str
    # Recognition confidence in [0, 1].
    confidence: float = Field(ge=0.0, le=1.0)
    polygon: Polygon
    box: BoundingBox


class OcrResult(BaseModel):
    """The full OCR output for a single image."""

    lines: list[TextLine] = Field(default_factory=list)
    # Total OCR wall-clock time in milliseconds (detection + classification +
    # recognition), useful for the 5-second latency budget.
    elapsed_ms: float = 0.0

    @property
    def full_text(self) -> str:
        """All recognised lines joined top-to-bottom with newlines."""
        return "\n".join(line.text for line in self.lines)
