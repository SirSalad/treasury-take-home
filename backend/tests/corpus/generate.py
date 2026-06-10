"""Render the corpus label images and (re)write ``manifest.json``.

Run after editing :mod:`cases`::

    python -m tests.corpus.generate        # from the backend/ dir

The images are committed PNGs so the test suite stays deterministic and does
not depend on Pillow or system fonts at test time. ``manifest.json`` is derived
straight from :data:`tests.corpus.cases.CASES`, so the two never drift — a test
asserts the committed manifest equals a freshly built one.

Pillow is a dev-only dependency (see ``pyproject.toml``); it is imported lazily
inside :func:`render_image` so simply loading the manifest never requires it.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from .cases import build_manifest
from .schema import IMAGES_DIR, MANIFEST_PATH, CorpusCase

# Fonts vary by machine; try a few common families and fall back to Pillow's
# bundled bitmap font so generation never hard-fails. The OCR pipeline reads the
# rendered glyphs regardless of family.
_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
)

WIDTH, HEIGHT = 680, 900


def _font(size: int):
    from PIL import ImageFont

    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_block(draw, x: int, y: int, text: str, size: int, width: int = 56) -> int:
    """Draw a wrapped text block and return the y just below it."""
    font = _font(size)
    line_h = size + max(4, size // 6)
    for line in textwrap.wrap(text, width=width):
        draw.text((x, y), line, fill="black", font=font)
        y += line_h
    return y


def render_image(case: CorpusCase, out_dir: Path = IMAGES_DIR) -> Path:
    """Render one case's label PNG from its ``label`` (printed) fields."""
    from PIL import Image, ImageDraw

    label: dict[str, Any] = case.label
    img = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(img)

    y = 48
    x = 48
    # Headline fields, largest first, in label reading order.
    y = _draw_block(draw, x, y, label["brand_name"], 44) + 16
    if label.get("class_type"):
        y = _draw_block(draw, x, y, label["class_type"], 28) + 14
    if label.get("vintage"):
        y = _draw_block(draw, x, y, f"Vintage {label['vintage']}", 24) + 8
    if label.get("alcohol_content_text"):
        y = _draw_block(draw, x, y, label["alcohol_content_text"], 30) + 8
    if label.get("net_contents"):
        y = _draw_block(draw, x, y, label["net_contents"], 28) + 8
    if label.get("country_of_origin"):
        y = _draw_block(draw, x, y, label["country_of_origin"], 22) + 8
    if label.get("name_and_address"):
        y = _draw_block(draw, x, y, label["name_and_address"], 20, width=60) + 8

    # Government warning anchored near the bottom (small print, as on real labels).
    warning = label.get("government_warning")
    if warning:
        _draw_block(draw, x, max(y + 24, HEIGHT - 220), warning, 17, width=58)

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / Path(case.image).name
    img.save(path)
    return path


def generate() -> None:
    """Render every image and rewrite the manifest."""
    manifest = build_manifest()
    for case in manifest.cases:
        path = render_image(case)
        print(f"rendered {path.relative_to(MANIFEST_PATH.parent)}")
    MANIFEST_PATH.write_text(manifest.to_json(), encoding="utf-8")
    print(f"wrote {MANIFEST_PATH.name} ({len(manifest.cases)} cases)")


if __name__ == "__main__":
    generate()
