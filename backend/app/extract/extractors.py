"""Deterministic, regex-based extractors for regex-friendly label fields.

Each extractor scans a piece of text and yields zero or more :class:`RawMatch`
objects (value + matched substring + confidence + char span). The driver
functions :func:`extract_from_text` and :func:`extract_fields` wrap those into
:class:`~app.extract.schemas.FieldCandidate` objects, attaching OCR line/box
context.

Design notes:

* **Deterministic over learned.** These fields ("45% Alc./Vol.", "90 Proof",
  "750 mL", "Product of France", "Bottled by …") follow tight conventions, so
  hand-written rules are faster, explainable, and need no model. Fuzzier fields
  (brand, class/type) are handled elsewhere.
* **Confidence reflects rule specificity**, not a probability — a value seen
  with strong surrounding context (an explicit "Alc./Vol." anchor) scores higher
  than a bare token that merely *looks* like the field.
* Matching is case-insensitive and tolerant of the spacing/punctuation noise OCR
  introduces.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from app.extract.schemas import (
    ExtractionResult,
    FieldCandidate,
    FieldName,
    SourceSpan,
)
from app.ocr.schemas import BoundingBox, OcrResult


@dataclass(frozen=True)
class RawMatch:
    """A single rule hit within one text string (offsets local to that string)."""

    value: str
    text: str
    confidence: float
    start: int
    end: int


# --- ABV: "45% Alc./Vol.", "ALC. 45% BY VOL.", "Alcohol 45% by volume",
#         "40% Vol." (British/EU spirits omit "Alc."), "5.1% ABV" ---------------

# OCR digit confusion: a capital I, lowercase l, or pipe read where a 1 was
# printed ("I3% ALC/VOL" on a stylised typeface). Normalised only where the
# letter abuts a digit, and only inside the numeric extractors, so words are
# never touched. Replacements are one-for-one, keeping every match span valid
# against the original text.
_DIGIT_CONFUSION_RE = re.compile(r"(?:(?<![A-Za-z0-9])|(?<=\d))[Il|](?=\d)")


def _fix_digit_confusion(text: str) -> str:
    return _DIGIT_CONFUSION_RE.sub("1", text)


# Two shapes: a percentage that is immediately followed by an alcohol/volume
# anchor, or an alcohol anchor immediately followed by a percentage. Requiring an
# anchor keeps it from matching unrelated percentages and, crucially, the proof
# number. The percent-first shape also accepts a bare "Vol" anchor so EU-style
# "40% Vol." labels (no "Alc.") are recognised, the craft-beer "ABV", and the
# spelled-out "ALCOHOL BY VOLUME" even when OCR strips its spaces
# ("40%ALCOHOLBYVOLUME").
_ABV_RE = re.compile(
    r"""
    (?:
        (?P<pct_first>\d{1,2}(?:\.\d+)?)\s*%\s*            # "45% "
        (?:
            alc(?:ohol)?(?:[\s./]*by[\s./]*vol(?:ume)?)?    # Alc / Alcohol by Volume
          | vol(?:ume)?                                     # bare Vol (EU)
          | abv                                             # craft-beer ABV
        )\b
      |
        \b(?:alc(?:ohol)?\.?                               # "Alc." / "Alcohol"
        \s*(?:[./]?\s*vol(?:ume)?\.?|by\s+vol(?:ume)?)?    # optional "/Vol."
        |abv)                                              # or "ABV: 5.1%"
        [:\s.]*                                            # filler
        (?P<pct_second>\d{1,2}(?:\.\d+)?)\s*%              # "45%"
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _find_abv(text: str) -> Iterator[RawMatch]:
    text = _fix_digit_confusion(text)
    for m in _ABV_RE.finditer(text):
        pct = m.group("pct_first") or m.group("pct_second")
        # Higher confidence when an explicit "vol" anchor is present, not just
        # the bare word "alcohol".
        confidence = 0.97 if re.search(r"vol", m.group(0), re.IGNORECASE) else 0.9
        yield RawMatch(
            value=_num(pct),
            text=m.group(0),
            confidence=confidence,
            start=m.start(),
            end=m.end(),
        )


# --- Proof: "90 Proof", "Proof 90", "90° Proof" ------------------------------

_PROOF_RE = re.compile(
    r"""
    (?:
        (?P<num_first>\d{1,3}(?:\.\d+)?)\s*°?\s*proof\b   # "90 Proof"
      |
        \bproof\s*[:\s]\s*(?P<num_second>\d{1,3}(?:\.\d+)?)  # "Proof: 90"
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _find_proof(text: str) -> Iterator[RawMatch]:
    text = _fix_digit_confusion(text)
    for m in _PROOF_RE.finditer(text):
        num = m.group("num_first") or m.group("num_second")
        yield RawMatch(
            value=_num(num),
            text=m.group(0),
            confidence=0.95,
            start=m.start(),
            end=m.end(),
        )


# --- Net contents: "750 mL", "1.75 L", "12 FL OZ", "1 PINT" -------------------

# Canonical spellings keyed by every accepted surface form (lowercased, dots and
# spaces stripped). Strong volume units score higher than ambiguous ones.
_NET_UNITS: dict[str, tuple[str, float]] = {
    "ml": ("mL", 0.95),
    "milliliter": ("mL", 0.95),
    "milliliters": ("mL", 0.95),
    "millilitre": ("mL", 0.95),
    "millilitres": ("mL", 0.95),
    "cl": ("cL", 0.9),
    "centiliter": ("cL", 0.9),
    "centiliters": ("cL", 0.9),
    "l": ("L", 0.9),
    "liter": ("L", 0.9),
    "liters": ("L", 0.9),
    "litre": ("L", 0.9),
    "litres": ("L", 0.9),
    "floz": ("fl oz", 0.92),
    "fluidoz": ("fl oz", 0.92),
    "fluidounce": ("fl oz", 0.92),
    "fluidounces": ("fl oz", 0.92),
    "pint": ("pint", 0.8),
    "pints": ("pint", 0.8),
    "pt": ("pint", 0.7),
    "gal": ("gallon", 0.8),
    "gallon": ("gallon", 0.8),
    "gallons": ("gallon", 0.8),
}

_NET_RE = re.compile(
    r"""
    \b(?P<qty>\d+(?:[.,]\d+)?)\s*                          # "750", "1.75"
    (?P<unit>
        m\s*l | millilit(?:er|re)s? |
        c\s*l | centilit(?:er|re)s? |
        fl\.?\s*oz | fluid\s*(?:oz|ounces?) |
        lit(?:er|re)s? | l |
        pints? | pt | gal(?:lon)?s?
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _find_net_contents(text: str) -> Iterator[RawMatch]:
    text = _fix_digit_confusion(text)
    for m in _NET_RE.finditer(text):
        key = re.sub(r"[.\s]", "", m.group("unit")).lower()
        canonical, confidence = _NET_UNITS.get(key, (m.group("unit"), 0.6))
        qty = m.group("qty").replace(",", ".")
        yield RawMatch(
            value=f"{_num(qty)} {canonical}",
            text=m.group(0),
            confidence=confidence,
            start=m.start(),
            end=m.end(),
        )


# --- Country of origin -------------------------------------------------------

# An explicit "Country of Origin:" label is the strongest signal; the common
# marketing phrasings ("Product of …", "Distilled in …") are slightly weaker.
_COUNTRY_LABEL_RE = re.compile(
    r"\bcountry\s+of\s+origin\b\s*[:\-]?\s*(?P<country>[A-Za-z][A-Za-z.\-' ]{1,40})",
    re.IGNORECASE,
)
_COUNTRY_PHRASE_RE = re.compile(
    r"""
    \b(?:product|produce|distilled|brewed|made|bottled|vinted|produced|imported)
    \s+(?:of|in|from)\s+
    (?P<country>[A-Za-z][A-Za-z.\-' ]{1,40})
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _clean_country(raw: str) -> str:
    # Trim trailing filler/punctuation OCR or copy tends to append.
    cleaned = re.split(r"[.;,]| - ", raw, maxsplit=1)[0]
    return re.sub(r"\s+", " ", cleaned).strip(" -'")


def _find_country(text: str) -> Iterator[RawMatch]:
    seen: set[tuple[int, int]] = set()
    for m in _COUNTRY_LABEL_RE.finditer(text):
        country = _clean_country(m.group("country"))
        if country:
            seen.add((m.start(), m.end()))
            yield RawMatch(country, m.group(0).strip(), 0.92, m.start(), m.end())
    for m in _COUNTRY_PHRASE_RE.finditer(text):
        if (m.start(), m.end()) in seen:
            continue
        country = _clean_country(m.group("country"))
        if country:
            yield RawMatch(country, m.group(0).strip(), 0.8, m.start(), m.end())


# --- Bottler / producer address heuristics -----------------------------------

# The responsibility statement is signalled by a verb phrase ("Bottled by",
# "Distilled and bottled by", "Imported by"). We capture from that phrase to the
# end of the line as the address candidate — full parsing is left to the caller,
# hence the deliberately modest confidence.
_BOTTLER_RE = re.compile(
    r"""
    \b(?P<phrase>
        (?:distilled|produced|bottled|brewed|vinted|blended|made|imported|
           packed|manufactured|prepared)
        (?:\s+(?:and|&)\s+\w+)?            # "Distilled and bottled"
        \s+(?:by|for)\b
    )
    \s*(?P<rest>.*\S)?                     # remainder of the line (the address)
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _find_bottler(text: str) -> Iterator[RawMatch]:
    for m in _BOTTLER_RE.finditer(text):
        rest = (m.group("rest") or "").strip()
        # The signal phrase alone (no address text) is a weak hit.
        confidence = 0.65 if rest else 0.4
        value = re.sub(r"\s+", " ", m.group(0)).strip()
        yield RawMatch(
            value=value,
            text=m.group(0),
            confidence=confidence,
            start=m.start(),
            end=m.end(),
        )


def _num(raw: str) -> str:
    """Normalise a numeric string: drop trailing zeros/point ("45.0" -> "45")."""
    return f"{float(raw):g}"


# Registry: field -> finder. Iteration order is the declared field order.
_EXTRACTORS: dict[FieldName, Callable[[str], Iterator[RawMatch]]] = {
    FieldName.ABV: _find_abv,
    FieldName.PROOF: _find_proof,
    FieldName.NET_CONTENTS: _find_net_contents,
    FieldName.COUNTRY_OF_ORIGIN: _find_country,
    FieldName.BOTTLER_ADDRESS: _find_bottler,
}


def extract_from_text(text: str, *, line_index: int | None = None) -> list[FieldCandidate]:
    """Run every extractor over ``text`` and return field candidates.

    ``line_index`` is recorded on each candidate's :class:`SourceSpan` so callers
    that pass one OCR line at a time can trace a hit back to its line.
    """
    candidates: list[FieldCandidate] = []
    for field, finder in _EXTRACTORS.items():
        for match in finder(text):
            candidates.append(
                FieldCandidate(
                    field=field,
                    value=match.value,
                    text=match.text,
                    confidence=match.confidence,
                    span=SourceSpan(line_index=line_index, start=match.start, end=match.end),
                )
            )
    return candidates


def extract_fields(result: OcrResult) -> ExtractionResult:
    """Extract all label fields from an :class:`OcrResult`.

    Each OCR line is scanned independently so candidates carry their source line
    index and bounding box — the per-field statements this targets sit on their
    own lines, and per-line scanning keeps offsets meaningful for highlighting.

    Two assembly steps then use cross-line context only an :class:`OcrResult`
    has: unit-label adjacency (a big "50" detected separately from its small
    "ALC/VOL" caption — a common spirits layout) and a proof-derived ABV
    fallback (US proof is exactly twice ABV), so a label stating only "80
    PROOF" still yields a comparable alcohol content.
    """
    candidates: list[FieldCandidate] = []
    for i, line in enumerate(result.lines):
        for candidate in extract_from_text(line.text, line_index=i):
            candidate.box = line.box
            candidates.append(candidate)
    candidates.extend(_assemble_adjacent_units(result, candidates))
    candidates.extend(_derive_abv_from_proof(candidates))
    return ExtractionResult(candidates=candidates)


# --- Cross-line assembly ------------------------------------------------------

# A line that is *only* a unit caption ("ALC/VOL", "ALC. BY VOL.", "PROOF",
# "ABV"), its number detected as a separate line — stylised spirit labels print
# the number much larger than the caption, which splits the detection.
_UNIT_CAPTION_RES: dict[FieldName, re.Pattern[str]] = {
    FieldName.ABV: re.compile(
        r"^[\W_]*(?:alc(?:ohol)?[\W_]*(?:by[\W_]*)?vol(?:ume)?|abv)[\W_]*$", re.IGNORECASE
    ),
    FieldName.PROOF: re.compile(r"^[\W_]*proof[\W_]*$", re.IGNORECASE),
}

# A line that is only a number (allowing %/degree dressing), the caption's value.
_BARE_NUMBER_RE = re.compile(r"^[\W_]*(?P<num>\d{1,3}(?:\.\d+)?)[\W_]*$")

# Plausibility bounds — adjacency is a weaker signal than an inline statement,
# so an implausible value is dropped rather than surfaced.
_VALUE_BOUNDS = {FieldName.ABV: (1.0, 80.0), FieldName.PROOF: (2.0, 160.0)}

# How far (in caption heights) the number may sit from the caption's centre.
_ADJACENCY_MAX_GAP = 2.5


def _assemble_adjacent_units(
    result: OcrResult, existing: list[FieldCandidate]
) -> list[FieldCandidate]:
    """ABV/proof read from a bare number next to its unit caption.

    For each caption-only line, the nearest bare-number line within
    :data:`_ADJACENCY_MAX_GAP` caption heights becomes the value. Skipped for
    fields that already have an inline candidate — adjacency exists to recover
    layouts the inline regexes cannot see, not to outvote them.
    """
    found_fields = {c.field for c in existing}
    assembled: list[FieldCandidate] = []
    for field, caption_re in _UNIT_CAPTION_RES.items():
        if field in found_fields:
            continue
        for i, caption in enumerate(result.lines):
            if not caption_re.match(caption.text):
                continue
            nearest: tuple[float, int, str] | None = None
            # The number is usually printed much larger than its caption, so the
            # allowance scales with the caption's larger dimension.
            max_gap = _ADJACENCY_MAX_GAP * max(caption.box.height, caption.box.width / 4, 1.0)
            for j, line in enumerate(result.lines):
                if j == i:
                    continue
                m = _BARE_NUMBER_RE.match(line.text)
                if m is None:
                    continue
                lo, hi = _VALUE_BOUNDS[field]
                if not lo <= float(m.group("num")) <= hi:
                    continue
                distance = _box_gap(caption.box, line.box)
                if distance <= max_gap and (nearest is None or distance < nearest[0]):
                    nearest = (distance, j, m.group("num"))
            if nearest is not None:
                _, j, num = nearest
                line = result.lines[j]
                assembled.append(
                    FieldCandidate(
                        field=field,
                        value=_num(num),
                        text=f"{line.text.strip()} {caption.text.strip()}",
                        confidence=0.75,
                        span=SourceSpan(line_index=j, start=0, end=len(line.text)),
                        box=line.box,
                    )
                )
    return assembled


def _box_gap(a: BoundingBox, b: BoundingBox) -> float:
    """Shortest edge-to-edge distance between two boxes (0 when they touch)."""
    dx = max(a.x_min - b.x_max, b.x_min - a.x_max, 0.0)
    dy = max(a.y_min - b.y_max, b.y_min - a.y_max, 0.0)
    return (dx**2 + dy**2) ** 0.5


def _derive_abv_from_proof(candidates: list[FieldCandidate]) -> list[FieldCandidate]:
    """An ABV candidate derived from a proof statement, when ABV is absent.

    US proof is exactly twice the alcohol-by-volume percentage (27 CFR 5.65),
    so "80 PROOF" pins ABV at 40 even when the percentage statement itself was
    not recovered. Derived — not read — hence the discounted confidence.
    """
    if any(c.field is FieldName.ABV for c in candidates):
        return []
    derived: list[FieldCandidate] = []
    for c in candidates:
        if c.field is FieldName.PROOF:
            derived.append(
                FieldCandidate(
                    field=FieldName.ABV,
                    value=_num(str(float(c.value) / 2)),
                    text=c.text,
                    confidence=round(c.confidence * 0.85, 4),
                    span=c.span,
                    box=c.box,
                )
            )
    return derived
