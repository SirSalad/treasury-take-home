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

For the complementary question — what the *tail* does under concurrent
contention — see :mod:`tests.perf.loadtest`::

    from tests.perf import benchmark_load

    report = benchmark_load()
    print(report.format())  # p50/p95/p99 + throughput across a concurrency sweep
"""

from .harness import (
    BenchmarkReport,
    CaseTiming,
    benchmark_corpus,
    percentile,
)
from .loadtest import (
    LoadReport,
    LoadResult,
    benchmark_load,
)

__all__ = [
    "BenchmarkReport",
    "CaseTiming",
    "LoadReport",
    "LoadResult",
    "benchmark_corpus",
    "benchmark_load",
    "percentile",
]
