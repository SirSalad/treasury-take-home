"""Schemas for fuzzy matching expected label fields against OCR text.

The deterministic extractors (:mod:`app.extract`) cover tightly-formatted fields
(ABV, proof, net contents, …). The two *free-text* fields an agent verifies —
brand name and class/type designation — don't follow a fixed grammar, so they're
compared against the recognised label text by fuzzy string matching instead.

A comparison yields one of three states, mirroring the verdict vocabulary the
verification engine uses:

* ``MATCH`` — the expected value is present, identical modulo whitespace.
* ``SOFT_WARNING`` — present and clearly the same value, but differing in a
  human-equivalent way (case-only or punctuation-only, e.g. ``STONE'S THROW`` vs
  ``Stone's Throw``), *or* a near miss that warrants a human glance.
* ``MISMATCH`` — not found, or too different to be the same value.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, Field


class FuzzyFieldName(enum.StrEnum):
    """Free-text label fields compared by fuzzy matching.

    Values match the corresponding :class:`app.models.application.Application`
    columns (and the corpus golden field keys) so downstream aggregation can key
    on them directly.
    """

    BRAND_NAME = "brand_name"
    CLASS_TYPE = "class_type"


class MatchStatus(enum.StrEnum):
    """Three-state outcome of a fuzzy field comparison.

    String values align with ``tests.corpus.schema.FieldVerdict`` so the
    verification engine can map a :class:`FieldMatch` straight onto a per-field
    verdict.
    """

    MATCH = "match"
    SOFT_WARNING = "soft_warning"
    MISMATCH = "mismatch"


class FieldMatch(BaseModel):
    """Result of fuzzy-matching one expected value against the OCR text."""

    field: FuzzyFieldName
    status: MatchStatus
    # The expected value (from the application), verbatim.
    expected: str
    # The best-matching span recovered from the OCR text (empty if nothing
    # plausible was found).
    matched_text: str
    # Similarity of the best span to the expected value, in [0, 1].
    score: float = Field(ge=0.0, le=1.0)
    # Human-readable explanation of why this status was assigned.
    reason: str = ""
