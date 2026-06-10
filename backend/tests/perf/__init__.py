"""Performance harness for the verification pipeline.

Measures end-to-end *preprocess → OCR → extract* latency over the labelled test
corpus and reports p50/p95 against the 5-second budget from the discovery
interviews. Public surface::

    from tests.perf import benchmark_corpus

    report = benchmark_corpus()
    print(report.format())
    assert report.passed

See :mod:`tests.perf.harness` for the methodology (notably best-of-N sampling,
which keeps the measurement — and the CI gate — robust to the transient CPU
contention of shared runners).
"""

from .harness import (
    BenchmarkReport,
    CaseTiming,
    benchmark_corpus,
    percentile,
)

__all__ = [
    "BenchmarkReport",
    "CaseTiming",
    "benchmark_corpus",
    "percentile",
]
