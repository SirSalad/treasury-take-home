"""Generate the synthetic distilled-spirits label used in OCR tests.

Run to (re)create ``sample_label.png``::

    python tests/fixtures/generate_sample_label.py

The image mirrors the example label fields from the project brief (OLD TOM
DISTILLERY) plus the mandatory government health warning, so tests can assert
the OCR pipeline recovers the fields an agent verifies. Kept as a committed PNG
so the test suite stays deterministic and font-independent.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUTPUT = Path(__file__).parent / "sample_label.png"

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def generate() -> Path:
    width, height = 640, 820
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    fields = [
        (50, "OLD TOM DISTILLERY", 46),
        (140, "Kentucky Straight Bourbon Whiskey", 30),
        (330, "45% Alc./Vol. (90 Proof)", 32),
        (390, "750 mL", 32),
    ]
    for y, text, size in fields:
        draw.text((50, y), text, fill="black", font=_font(size))

    warning = (
        "GOVERNMENT WARNING: (1) According to the Surgeon General, women should "
        "not drink alcoholic beverages during pregnancy because of the risk of "
        "birth defects. (2) Consumption of alcoholic beverages impairs your "
        "ability to drive a car or operate machinery, and may cause health "
        "problems."
    )
    y = 580
    for line in textwrap.wrap(warning, width=52):
        draw.text((50, y), line, fill="black", font=_font(17))
        y += 26

    img.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    path = generate()
    print(f"wrote {path}")
