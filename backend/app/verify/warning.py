"""Dedicated verifier for the mandatory Government Health Warning.

Unlike the fuzzy field matching used for brand/class-type, the warning is checked
against the canonical 27 CFR 16.21 statement on a near-exact basis. The verifier
catches the common evasions:

* **Missing** — no ``GOVERNMENT WARNING`` header anywhere in the OCR text.
* **Altered wording** — the statement deviates from the required text (a dropped
  sentence, a swapped clause) beyond what OCR noise explains.
* **Title-case header** — ``Government Warning`` instead of the required all-caps
  ``GOVERNMENT WARNING`` (Jenny's catch). The body may be word-perfect, so the
  casing of the header is inspected independently of the wording.

What it deliberately does *not* claim to verify: bold type and minimum font size
(27 CFR 16.22) cannot be recovered from OCR text and are surfaced as limitations.

Matching strategy:

1. Whitespace-normalise the text (OCR splits the warning across many lines).
2. Locate the ``GOVERNMENT WARNING`` header case-insensitively. Absent -> MISSING.
3. Inspect the located header's casing for the all-caps requirement.
4. Score the wording against the canonical statement at the word level, so minor
   OCR noise (a garbled character) passes while genuine tampering (a dropped
   sentence, a reworded clause) fails the threshold.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.extract.schemas import SourceSpan
from app.ocr.schemas import BoundingBox, OcrResult
from app.verify.schemas import (
    DEFAULT_SIMILARITY_THRESHOLD,
    GOVERNMENT_WARNING_TEXT,
    TEXT_ONLY_LIMITATIONS,
    GovernmentWarningResult,
    WarningVerdict,
)

# Locates the header regardless of casing or whitespace between the two words.
# ``\s*`` (not ``\s+``) because PP-OCRv4 frequently drops the space and runs the
# words together (``GOVERNMENTWARNING``); requiring a space there made a plainly
# present, all-caps warning read as MISSING on tightly-kerned labels.
_HEADER_RE = re.compile(r"government\s*warning", re.IGNORECASE)

# The canonical statement's closing phrase, used to bound the candidate region so
# trailing label text after the warning does not dilute the similarity score.
# ``\s*`` between the words because OCR routinely drops the space
# ("HEALTHPROBLEMS"); requiring one left the region unbounded and the trailing
# label text dragged otherwise-valid warnings below the threshold.
_TAIL_RE = re.compile(r"health\s*problems\s*\.?", re.IGNORECASE)

_CANONICAL_LC = GOVERNMENT_WARNING_TEXT.lower()


def _alnum(text: str) -> str:
    """Lowercase alphanumeric content only — drops punctuation *and* whitespace.

    Comparing on this makes the wording check insensitive to how the OCR engine
    spaces or splits words (some engines, e.g. PP-OCRv4, run adjacent words
    together: ``GOVERNMENTWARNING``), while still reflecting the actual letters.
    """
    return re.sub(r"[^a-z0-9]", "", text.lower())


_CANONICAL_ALNUM = _alnum(GOVERNMENT_WARNING_TEXT)


def _normalise_whitespace(text: str) -> str:
    """Collapse all runs of whitespace (incl. newlines) to single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def _bound_warning_region(region: str) -> str:
    """Trim ``region`` (header onward) to roughly just the warning statement.

    Bounds at the canonical closing phrase when present; otherwise falls back to
    a length window. This keeps any label text that follows the warning from
    dragging down the similarity score of an otherwise-valid statement.
    """
    tail = _TAIL_RE.search(region)
    if tail is not None:
        return region[: tail.end()]
    # No recognisable ending (truncated/altered): cap to a generous window.
    return region[: int(len(_CANONICAL_LC) * 1.1) + 5]


# The mandatory clauses of the 27 CFR 16.21 statement. Compliance requires every
# one to be present: a dropped or reworded clause (the real evasion) removes one,
# which a global character-similarity score can miss when the change is small
# relative to the whole statement. Matched OCR-tolerantly (alnum, fuzzy) so a
# clause garbled by a character or three still counts as present.
_REQUIRED_PHRASES = (
    "According to the Surgeon General",
    "women should not drink alcoholic beverages during pregnancy",
    "because of the risk of birth defects",
    "Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery",
    "may cause health problems",
)
_REQUIRED_ALNUM = tuple(_alnum(p) for p in _REQUIRED_PHRASES)

# Per-clause similarity at/above which a clause counts as present. Set between
# OCR noise on a real clause (~0.9+) and a reworded clause (the corpus reword
# scores ~0.4 against the original), so noise passes and tampering is caught.
_PHRASE_PRESENT_THRESHOLD = 0.78


def _phrase_present(needle: str, haystack: str) -> bool:
    """Whether ``needle`` (alnum) appears in ``haystack`` (alnum), OCR-tolerantly.

    Exact containment first; otherwise the best same-length window is scored, so a
    clause with a few character slips still matches while a dropped or reworded
    clause (absent or substantially different) does not.
    """
    if not needle or needle in haystack:
        return True
    n = len(needle)
    if len(haystack) < n:
        return SequenceMatcher(None, needle, haystack).ratio() >= _PHRASE_PRESENT_THRESHOLD
    best = 0.0
    step = max(1, n // 8)
    for i in range(0, len(haystack) - n + 1, step):
        ratio = SequenceMatcher(None, needle, haystack[i : i + n]).ratio()
        if ratio > best:
            best = ratio
            if best >= _PHRASE_PRESENT_THRESHOLD:
                return True
    return best >= _PHRASE_PRESENT_THRESHOLD


def _missing_required_phrases(region: str) -> list[str]:
    """The mandatory clauses not found in ``region`` (OCR-tolerant)."""
    region_alnum = _alnum(region)
    return [
        phrase
        for phrase, alnum in zip(_REQUIRED_PHRASES, _REQUIRED_ALNUM, strict=True)
        if not _phrase_present(alnum, region_alnum)
    ]


def _wording_similarity(region: str) -> float:
    """Similarity of ``region`` to the canonical statement, in ``[0, 1]``.

    Scored on alphanumeric characters (whitespace and punctuation removed), so
    it is robust to OCR spacing/word-splitting differences while still
    penalising real alterations — a dropped or reworded sentence changes many
    characters, whereas an incidental single-character OCR slip barely moves the
    ratio. Case-insensitive, since header casing is judged separately. The
    canonical statement appearing verbatim (even amid trailing label text)
    scores 1.0.
    """
    region_alnum = _alnum(region)
    if _CANONICAL_ALNUM and _CANONICAL_ALNUM in region_alnum:
        return 1.0
    # autojunk=False: the canonical string is >200 chars, where SequenceMatcher's
    # "popular character" heuristic would otherwise distort the ratio.
    return SequenceMatcher(None, _CANONICAL_ALNUM, region_alnum, autojunk=False).ratio()


def verify_government_warning(
    text: str,
    *,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> GovernmentWarningResult:
    """Verify the Government Health Warning in a piece of OCR text.

    ``text`` is typically :attr:`app.ocr.schemas.OcrResult.full_text`; use
    :func:`verify_warning_from_ocr` to also attach the source line/box.
    """
    limitations = list(TEXT_ONLY_LIMITATIONS)
    normalised = _normalise_whitespace(text)

    header = _HEADER_RE.search(normalised)
    if header is None:
        return GovernmentWarningResult(
            verdict=WarningVerdict.MISSING,
            found_text=None,
            header_all_caps=None,
            similarity=0.0,
            issues=["No Government Warning found on the label."],
            limitations=limitations,
        )

    header_text = normalised[header.start() : header.end()]
    # The required header is all caps; a title-case header (Jenny's catch) fails.
    header_all_caps = header_text.isupper()

    region = _bound_warning_region(normalised[header.start() :])
    similarity = _wording_similarity(region)
    missing_phrases = _missing_required_phrases(region)

    issues: list[str] = []
    if not header_all_caps:
        issues.append(
            f"Header is not in all caps; 'GOVERNMENT WARNING' is required, found {header_text!r}."
        )
    if missing_phrases:
        # A required clause is gone — the real evasion. (When OCR merely failed to
        # read part of the statement the effect is the same: the tool will not
        # claim compliance on wording it could not recover.)
        issues.append(
            "Required clause(s) missing or altered: "
            + "; ".join(f"{p!r}" for p in missing_phrases)
            + "."
        )
    elif similarity < similarity_threshold:
        # Every clause is present but the statement is broadly garbled.
        issues.append(
            "Warning wording does not match the required statement "
            f"(similarity {similarity:.2f} < {similarity_threshold:.2f})."
        )

    verdict = WarningVerdict.COMPLIANT if not issues else WarningVerdict.ALTERED
    return GovernmentWarningResult(
        verdict=verdict,
        found_text=region,
        header_all_caps=header_all_caps,
        similarity=similarity,
        issues=issues,
        limitations=limitations,
        span=SourceSpan(line_index=None, start=header.start(), end=header.end()),
    )


def verify_warning_from_ocr(
    result: OcrResult,
    *,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> GovernmentWarningResult:
    """Verify the warning over an :class:`OcrResult`, attaching the source box.

    The verdict is computed on the joined full text (the warning routinely spans
    several OCR lines). For traceability the header's source line index and
    bounding box are attached when the header can be tied to a single line; if
    the header is split across lines, the line that opens it is used.
    """
    outcome = verify_government_warning(result.full_text, similarity_threshold=similarity_threshold)
    if outcome.verdict is WarningVerdict.MISSING:
        return outcome

    line_index, box, span = _locate_header_line(result)
    if line_index is not None:
        outcome.span = span
        outcome.box = box
    return outcome


def _locate_header_line(
    result: OcrResult,
) -> tuple[int | None, BoundingBox | None, SourceSpan | None]:
    """Find the OCR line that carries (or opens) the warning header."""
    for i, line in enumerate(result.lines):
        m = _HEADER_RE.search(line.text)
        if m is not None:
            return i, line.box, SourceSpan(line_index=i, start=m.start(), end=m.end())
    # Header split across lines: fall back to the line containing "government".
    for i, line in enumerate(result.lines):
        m = re.search(r"government", line.text, re.IGNORECASE)
        if m is not None:
            return i, line.box, SourceSpan(line_index=i, start=m.start(), end=m.end())
    return None, None, None
