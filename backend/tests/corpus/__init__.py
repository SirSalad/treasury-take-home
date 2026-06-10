"""Labelled test-label corpus for the verification engine.

Public surface for tests::

    from tests.corpus import load_corpus

    for case in load_corpus().cases:
        ...  # case.application, case.label, case.golden, case.image_path()

The committed artifacts are ``manifest.json`` plus the PNGs under ``images/``.
Regenerate them with ``python -m tests.corpus.generate`` after editing
:mod:`tests.corpus.cases`.
"""

from .schema import (
    CorpusCase,
    FieldVerdict,
    Golden,
    Manifest,
    OverallVerdict,
    WarningVerdict,
    load_manifest,
)


def load_corpus() -> Manifest:
    """Load the committed corpus manifest from disk."""
    return load_manifest()


__all__ = [
    "CorpusCase",
    "FieldVerdict",
    "Golden",
    "Manifest",
    "OverallVerdict",
    "WarningVerdict",
    "load_corpus",
    "load_manifest",
]
