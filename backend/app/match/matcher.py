"""Fuzzy matching of expected brand / class-type against recognised label text.

Brand name and class/type are free text, so they can't be pinned with the tight
regexes used for ABV or net contents. Instead we look for the expected value
*somewhere* in the OCR output and grade how well it matches:

1. **Normalise** both sides — fold smart quotes, case-fold, drop punctuation and
   collapse whitespace — so cosmetic noise doesn't sink an otherwise clean hit.
2. **Scan** the label text for the best-matching token window (the expected value
   may sit on its own line or be split across lines by the detector), scoring
   each window with a blend of character- and token-level similarity.
3. **Grade** the best score into three states. A high score where the *surface*
   forms differ only in case or punctuation is deliberately demoted to a soft
   warning — ``STONE'S THROW`` vs ``Stone's Throw`` is "obviously the same
   brand" yet the casing difference is worth a human glance, not a silent pass.

The thresholds are similarity ratios, not probabilities; they're tuned so that
OCR-grade noise stays inside ``MATCH``/``SOFT_WARNING`` while a genuinely
different value falls through to ``MISMATCH``.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.match.schemas import FieldMatch, FuzzyFieldName, MatchStatus
from app.ocr.schemas import OcrResult

# Similarity at/above which the expected value is considered present; between
# LOW and HIGH it's a near miss worth flagging; below LOW it's a mismatch.
HIGH_THRESHOLD = 0.85
LOW_THRESHOLD = 0.60

# Curly quotes / primes that OCR and copy-paste introduce, folded to ASCII so
# "Stone’s" and "Stone's" compare equal.
_SMART_QUOTES = str.maketrans(
    {
        "‘": "'",  # left single quote
        "’": "'",  # right single quote / apostrophe
        "ʼ": "'",  # modifier letter apostrophe
        "′": "'",  # prime
        "“": '"',  # left double quote
        "”": '"',  # right double quote
        "″": '"',  # double prime
        "´": "'",  # acute accent (OCR mis-read of apostrophe)
        "`": "'",
    }
)


def _fold_quotes(text: str) -> str:
    return text.translate(_SMART_QUOTES)


def _light_normalise(text: str) -> str:
    """Fold quotes and collapse whitespace, *preserving* case and punctuation.

    Used to tell an exact hit from a cosmetic (case/punctuation-only) one: if the
    aggressively-normalised forms match but these don't, the difference is purely
    surface and the result is demoted to a soft warning.
    """
    return re.sub(r"\s+", " ", _fold_quotes(text)).strip()


def _normalise(text: str) -> str:
    """Aggressive normalisation for similarity scoring.

    Folds quotes, case-folds, replaces every non-alphanumeric run with a single
    space and trims — so only the words (and digits) survive.
    """
    folded = _fold_quotes(text).casefold()
    return re.sub(r"[^0-9a-z]+", " ", folded).strip()


def _similarity(a: str, b: str) -> float:
    """Blended char/token similarity of two already-normalised strings.

    Combines a plain character-ratio (catches typos / OCR substitutions) with a
    token-sorted ratio (robust to word-order differences), taking the stronger of
    the two.
    """
    if not a or not b:
        return 0.0
    char_ratio = SequenceMatcher(None, a, b).ratio()
    a_sorted = " ".join(sorted(a.split()))
    b_sorted = " ".join(sorted(b.split()))
    token_ratio = SequenceMatcher(None, a_sorted, b_sorted).ratio()
    return max(char_ratio, token_ratio)


def _best_window(expected: str, tokens: list[str]) -> tuple[float, str]:
    """Best similarity of ``expected`` to any token window of the OCR text.

    Slides windows whose length brackets the expected token count (``n-1`` …
    ``n+1``) across ``tokens`` (original surface forms), returning the highest
    score and the raw text of the window that produced it.
    """
    norm_expected = _normalise(expected)
    light_expected = _light_normalise(expected)
    n = max(1, len(norm_expected.split()))
    if not tokens:
        return 0.0, ""

    best_score = 0.0
    best_raw = ""
    best_exact = False

    def consider(raw: str) -> None:
        nonlocal best_score, best_raw, best_exact
        score = _similarity(norm_expected, _normalise(raw))
        exact = _light_normalise(raw) == light_expected
        # Higher score wins; on a tie prefer a window that matches the expected
        # surface form exactly, so a correctly-printed occurrence elsewhere isn't
        # masked by a louder cosmetic variant.
        if score > best_score or (score == best_score and exact and not best_exact):
            best_score, best_raw, best_exact = score, raw, exact

    for size in range(max(1, n - 1), n + 2):
        if size > len(tokens):
            # Whole text is shorter than this window; score it once and stop
            # widening further.
            consider(" ".join(tokens))
            break
        for i in range(len(tokens) - size + 1):
            consider(" ".join(tokens[i : i + size]))
    return best_score, best_raw


def match_field(field: FuzzyFieldName, expected: str, text: str) -> FieldMatch:
    """Fuzzy-match an expected free-text value against recognised label text.

    ``expected`` is the application value; ``text`` is the OCR output (any
    newline-joined block). Returns a graded :class:`FieldMatch`.
    """
    expected = (expected or "").strip()
    tokens = re.findall(r"\S+", text)
    score, matched_raw = _best_window(expected, tokens)

    if not expected:
        return FieldMatch(
            field=field,
            status=MatchStatus.MISMATCH,
            expected=expected,
            matched_text=matched_raw,
            score=score,
            reason="no expected value to verify against",
        )

    if score < LOW_THRESHOLD:
        status = MatchStatus.MISMATCH
        reason = f"best match scored {score:.2f}, below {LOW_THRESHOLD:.2f}"
    elif score < HIGH_THRESHOLD:
        status = MatchStatus.SOFT_WARNING
        reason = f"near match ({score:.2f}); review for OCR noise or wording drift"
    elif _light_normalise(expected) == _light_normalise(matched_raw):
        status = MatchStatus.MATCH
        reason = "exact match (ignoring whitespace)"
    else:
        # Same words, but the surface forms differ only in case or punctuation.
        status = MatchStatus.SOFT_WARNING
        reason = "case/punctuation-only difference"

    return FieldMatch(
        field=field,
        status=status,
        expected=expected,
        matched_text=matched_raw,
        score=score,
        reason=reason,
    )


def match_from_ocr(field: FuzzyFieldName, expected: str, result: OcrResult) -> FieldMatch:
    """Convenience wrapper: match against the full text of an :class:`OcrResult`."""
    return match_field(field, expected, result.full_text)
