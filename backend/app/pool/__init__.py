"""The canonical data pool — single source of truth for demo seeding and evals.

One committed artifact (``pool.json`` + a deduped ``images/`` dir, packaged under
``app/`` so the container seed ships with it) holds every label record exactly
once. Each record carries the filed ``application``, its ``images`` (front first),
``provenance``/licence, ``use_cases`` tags, and optional per-use-case annotation
blocks (``cola_golden``, ``ocr_expect``, ``corpus_golden``) plus a demo
``decision``.

Every consumer is a *filtered view* over this pool rather than its own copy of the
data:

* the demo seeder (:mod:`app.seed`) seeds **all** records (59 submissions);
* the real-COLA golden eval reads ``use_case == 'cola_golden'`` (30);
* the OOD OCR robustness eval reads ``ocr_stress`` (18);
* the synthetic golden corpus view is ``corpus_golden`` (10).

The ``corpus_golden`` records are authored upstream by ``tests/corpus/cases.py``
(which renders the synthetic images); ``tests/test_pool.py`` keeps the pool in
sync and asserts the per-use-case counts.
"""

from __future__ import annotations

import json
from importlib import resources
from importlib.resources.abc import Traversable

# Use-case tags. A record belongs to a view iff the tag is in its ``use_cases``.
COLA_GOLDEN = "cola_golden"
OCR_STRESS = "ocr_stress"
CORPUS_GOLDEN = "corpus_golden"
BASE_SEED = "base_seed"


def pool_images() -> Traversable:
    """The single deduped image directory backing every record."""
    return resources.files("app.pool") / "images"


def load_pool() -> list[dict]:
    """All pool records, in canonical (committed) order."""
    text = (resources.files("app.pool") / "pool.json").read_text()
    return list(json.loads(text)["records"])


def records_for(use_case: str) -> list[dict]:
    """The records a given view sees, in pool order."""
    return [r for r in load_pool() if use_case in r["use_cases"]]


def record_images(record: dict) -> list[str]:
    """A record's image filenames, front first (relative to :func:`pool_images`)."""
    return list(record["images"])


__all__ = [
    "BASE_SEED",
    "COLA_GOLDEN",
    "CORPUS_GOLDEN",
    "OCR_STRESS",
    "load_pool",
    "pool_images",
    "record_images",
    "records_for",
]
