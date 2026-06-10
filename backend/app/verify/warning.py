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

# Locates the header regardless of casing or the run of whitespace OCR may insert
# between the two words (including a line break that normalisation collapses).
_HEADER_RE = re.compile(r"government\s+warning", re.IGNORECASE)

# The canonical statement's closing phrase, used to bound the candidate region so
# trailing label text after the warning does not dilute the similarity score.
_WARNING_TAIL = "health problems"

_CANONICAL_LC = GOVERNMENT_WARNING_TEXT.lower()


def _tokens(text: str) -> list[str]:
    """Lowercase word/number tokens (drops punctuation and casing)."""
    return re.findall(r"[a-z0-9]+", text.lower())


_CANONICAL_TOKENS = _tokens(GOVERNMENT_WARNING_TEXT)


def _contains_subsequence(needle: list[str], haystack: list[str]) -> bool:
    """Whether ``needle`` appears as a contiguous run within ``haystack``."""
    if not needle or len(needle) > len(haystack):
        return False
    first = needle[0]
    for i in range(len(haystack) - len(needle) + 1):
        if haystack[i] == first and haystack[i : i + len(needle)] == needle:
            return True
    return False


def _normalise_whitespace(text: str) -> str:
    """Collapse all runs of whitespace (incl. newlines) to single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def _bound_warning_region(region: str) -> str:
    """Trim ``region`` (header onward) to roughly just the warning statement.

    Bounds at the canonical closing phrase when present; otherwise falls back to
    a length window. This keeps any label text that follows the warning from
    dragging down the similarity score of an otherwise-valid statement.
    """
    tail_idx = region.lower().find(_WARNING_TAIL)
    if tail_idx != -1:
        end = tail_idx + len(_WARNING_TAIL)
        # Include a trailing period if the warning ends with one.
        if region[end : end + 1] == ".":
            end += 1
        return region[:end]
    # No recognisable ending (truncated/altered): cap to a generous window.
    return region[: int(len(_CANONICAL_LC) * 1.1) + 5]


def _wording_similarity(region: str) -> float:
    """Similarity of ``region`` to the canonical statement, in ``[0, 1]``.

    Scored at the **word** level, not the character level: each token counts
    equally regardless of length, so the score reflects *how many words differ*
    rather than how many characters. This separates the common evasions (a
    dropped sentence, a reworded clause — several words gone) from incidental OCR
    noise (a single garbled character within one word). Case-insensitive, since
    header casing is judged separately. The canonical statement appearing
    verbatim (even with trailing label text) scores 1.0.
    """
    region_tokens = _tokens(region)
    if _contains_subsequence(_CANONICAL_TOKENS, region_tokens):
        return 1.0
    return SequenceMatcher(None, _CANONICAL_TOKENS, region_tokens).ratio()


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

    issues: list[str] = []
    if not header_all_caps:
        issues.append(
            f"Header is not in all caps; 'GOVERNMENT WARNING' is required, found {header_text!r}."
        )
    if similarity < similarity_threshold:
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
