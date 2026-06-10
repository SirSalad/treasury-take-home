"""Latency benchmark for the full verification pipeline.

What it measures
----------------
For each corpus label, the wall-clock time of the production hot path:

    preprocess (decode + resolution cap) → OCR → field extraction

OCR dominates this budget by two orders of magnitude; matching/aggregation that
follows extraction is sub-millisecond pure-Python and is left out so the number
tracks the part that can actually breach 5 seconds.

How it measures (best-of-N)
---------------------------
Each label is timed ``repeats`` times and the **minimum** is kept as that
label's latency. The minimum is the run least perturbed by the host — on shared
CI runners and this multi-tenant dev box, a noisy neighbour can triple a single
sample, so a raw worst-of-N gate would flake constantly while telling us nothing
about the pipeline. Best-of-N isolates the latency the pipeline *can* achieve on
the given hardware, which is what a regression gate should defend. The trade-off
(it does not capture contention-driven tail latency) is acceptable here: the SLA
question is "is the pipeline fast enough on a CPU", not "how loaded is the box".

The per-label minima are then summarised with nearest-rank percentiles. The
corpus is small (a handful of labels), so p95 is effectively the slowest label —
deliberately, since the SLA is a per-label promise.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from app.extract import extract_fields
from app.ocr import OcrService, get_ocr_service
from tests.corpus import CorpusCase, load_corpus

# Default 5s budget from the discovery interviews, and a default sample count
# that balances signal against the wall-clock cost of running real OCR in CI.
DEFAULT_BUDGET_MS = 5000.0
DEFAULT_REPEATS = 3


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile of ``values`` (``q`` in [0, 1]).

    Nearest-rank (rather than interpolation) suits the small corpus: it always
    returns an actually-observed latency, so "p95 = 2.4s" names a real label.
    """
    if not values:
        raise ValueError("percentile of empty sequence")
    ordered = sorted(values)
    if q <= 0:
        return ordered[0]
    if q >= 1:
        return ordered[-1]
    # Nearest-rank: smallest value with at least ceil(q*N) values <= it.
    rank = math.ceil(q * len(ordered))
    return ordered[rank - 1]


@dataclass
class CaseTiming:
    """Timing + sanity signal for one corpus label."""

    case_id: str
    best_ms: float
    samples: list[float]
    n_lines: int
    n_candidates: int

    @property
    def did_work(self) -> bool:
        """True if OCR actually recognised text — guards against timing a no-op.

        A pipeline that silently returns nothing would post superb latencies; the
        gate must reject that, so every label is required to have produced lines.
        """
        return self.n_lines > 0


@dataclass
class BenchmarkReport:
    """Aggregate latency report over the corpus."""

    budget_ms: float
    repeats: int
    timings: list[CaseTiming] = field(default_factory=list)

    @property
    def best_values(self) -> list[float]:
        return [t.best_ms for t in self.timings]

    @property
    def p50_ms(self) -> float:
        return percentile(self.best_values, 0.50)

    @property
    def p95_ms(self) -> float:
        return percentile(self.best_values, 0.95)

    @property
    def max_ms(self) -> float:
        return max(self.best_values)

    @property
    def headroom_pct(self) -> float:
        """How far p95 sits under budget, as a percentage of the budget."""
        return (self.budget_ms - self.p95_ms) / self.budget_ms * 100.0

    @property
    def all_did_work(self) -> bool:
        return all(t.did_work for t in self.timings)

    @property
    def passed(self) -> bool:
        return self.all_did_work and self.p95_ms < self.budget_ms

    def format(self) -> str:
        """Human-readable report for the CLI and CI logs."""
        lines = [
            f"Pipeline latency over {len(self.timings)} labels "
            f"(best of {self.repeats}, budget {self.budget_ms:.0f} ms)",
            "-" * 64,
            f"  {'label':<28} {'best ms':>9} {'lines':>6} {'fields':>7}",
        ]
        for t in sorted(self.timings, key=lambda x: x.best_ms, reverse=True):
            flag = "" if t.did_work else "  <-- NO TEXT"
            lines.append(
                f"  {t.case_id:<28} {t.best_ms:>9.0f} {t.n_lines:>6} {t.n_candidates:>7}{flag}"
            )
        lines += [
            "-" * 64,
            f"  p50 {self.p50_ms:>8.0f} ms   p95 {self.p95_ms:>8.0f} ms   "
            f"max {self.max_ms:>8.0f} ms",
            f"  headroom under budget: {self.headroom_pct:.0f}%   "
            f"verdict: {'PASS' if self.passed else 'FAIL'}",
        ]
        return "\n".join(lines)


def _time_pipeline(service: OcrService, image_bytes: bytes) -> tuple[float, int, int]:
    """Run preprocess+OCR+extract once; return (elapsed_ms, n_lines, n_fields).

    Takes raw bytes (the upload shape) so decoding is timed as production would
    pay it, and so each repeat is independent of any path/array caching.
    """
    start = time.perf_counter()
    ocr_result = service.extract(image_bytes)
    extraction = extract_fields(ocr_result)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return elapsed_ms, len(ocr_result.lines), len(extraction.candidates)


def benchmark_corpus(
    *,
    service: OcrService | None = None,
    cases: list[CorpusCase] | None = None,
    repeats: int = DEFAULT_REPEATS,
    budget_ms: float = DEFAULT_BUDGET_MS,
) -> BenchmarkReport:
    """Benchmark the pipeline over the corpus and return a :class:`BenchmarkReport`.

    The OCR engine is warmed once up front so first-call session-build cost (a
    one-time startup expense paid by the app's lifespan warmup) never lands in a
    measured sample.
    """
    service = service or get_ocr_service()
    cases = cases if cases is not None else load_corpus().cases

    # Warm the ONNX sessions outside the measured loop.
    service.warmup()

    # Read bytes once; we measure decode+OCR+extract, not disk I/O.
    payloads = {c.id: c.image_path().read_bytes() for c in cases}

    timings: list[CaseTiming] = []
    for case in cases:
        samples: list[float] = []
        n_lines = n_fields = 0
        for _ in range(max(1, repeats)):
            elapsed_ms, n_lines, n_fields = _time_pipeline(service, payloads[case.id])
            samples.append(elapsed_ms)
        timings.append(
            CaseTiming(
                case_id=case.id,
                best_ms=min(samples),
                samples=samples,
                n_lines=n_lines,
                n_candidates=n_fields,
            )
        )

    return BenchmarkReport(budget_ms=budget_ms, repeats=repeats, timings=timings)
