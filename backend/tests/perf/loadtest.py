"""Concurrency load benchmark: contention-driven tail latency under load.

Why this exists
---------------
The best-of-N harness in :mod:`tests.perf.harness` answers "is the pipeline fast
enough on a CPU?" by keeping the *least*-perturbed sample, deliberately
discarding contention. That left one question unmeasured — the one the Known
Limitations caveat deferred: when *N requests land at once* and fight over the
same cores, what does the **tail** latency look like? On a shared 4-vCPU VPS
that was a capacity question we couldn't answer honestly; on the dedicated
12-vCPU host we can drive real concurrent load and measure it.

How it measures
---------------
Unlike the best-of-N harness, this keeps **every** sample. For each concurrency
level it fires a fixed number of waves of requests through a thread pool, each
request running the production hot path (preprocess → OCR → extract) against the
shared, warmed :class:`~app.ocr.OcrService` — the same singleton the FastAPI app
hands every request. The verify endpoint is a *sync* def, so Starlette already
runs concurrent requests in a worker thread pool over that one service; driving
threads here reproduces production's contention model rather than inventing a
new one. ONNXRuntime releases the GIL during inference, so concurrent threads
genuinely contend for CPU cores — which is the whole point.

Each level reports the full distribution (p50/p95/p99/max) **and** throughput
(requests/second), so the report shows both how the tail degrades and how much
work the box clears as concurrency climbs past the core count.

Sample sizes
------------
Requests per level scale with the concurrency (``concurrency * waves``), so the
high-concurrency levels — exactly where tail resolution matters — get the most
samples. Percentiles are nearest-rank (reused from the best-of-N harness for
consistency): at low concurrency the sample count is small, so p99 there
coincides with the worst observed run. ``max_ms`` is always reported alongside
so that coincidence is transparent rather than hidden.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from app.ocr import OcrService, get_ocr_service
from tests.corpus import CorpusCase, load_corpus
from tests.perf.harness import DEFAULT_BUDGET_MS, _time_pipeline, percentile

# Concurrency levels swept by default: 1 (uncontended baseline) up to and past
# the dedicated host's 12-core capacity, so the report shows where — if anywhere
# — the tail starts to degrade under oversubscription.
DEFAULT_CONCURRENCY: tuple[int, ...] = (1, 2, 4, 8, 12, 16)

# Number of full waves of `concurrency` requests fired at each level. Requests
# per level = concurrency * waves, so high-concurrency levels (where the tail
# matters) accumulate the most samples while the whole sweep stays to a sane
# wall-clock cost (each request runs real OCR).
DEFAULT_WAVES = 8

# Concurrency the single process is expected to hold the budget at. OCR is
# CPU-bound and ONNXRuntime already uses every core for intra-op parallelism, so
# a single inference saturates the box; concurrent requests time-share rather
# than scale, and the tail grows ~linearly with in-flight count. Measurement on
# the dedicated 12-vCPU host shows the 5s p99 budget holds comfortably to ~2
# in-flight and is at the edge by ~4; we gate the conservative figure and report
# the full envelope (where the budget actually breaks) for capacity planning.
DEFAULT_SUPPORTED_CONCURRENCY = 2


@dataclass
class LoadResult:
    """Latency distribution + throughput at one concurrency level."""

    concurrency: int
    latencies_ms: list[float]
    wall_s: float
    budget_ms: float
    n_lines_min: int

    @property
    def n_requests(self) -> int:
        return len(self.latencies_ms)

    @property
    def p50_ms(self) -> float:
        return percentile(self.latencies_ms, 0.50)

    @property
    def p95_ms(self) -> float:
        return percentile(self.latencies_ms, 0.95)

    @property
    def p99_ms(self) -> float:
        return percentile(self.latencies_ms, 0.99)

    @property
    def max_ms(self) -> float:
        return max(self.latencies_ms)

    @property
    def mean_ms(self) -> float:
        return sum(self.latencies_ms) / len(self.latencies_ms)

    @property
    def throughput_rps(self) -> float:
        """Completed requests per wall-clock second at this level."""
        return self.n_requests / self.wall_s if self.wall_s > 0 else 0.0

    @property
    def did_work(self) -> bool:
        """Guard: every request must have produced OCR lines (no timed no-ops)."""
        return self.n_lines_min > 0

    @property
    def under_budget(self) -> bool:
        """Whether this level's tail (p99) stayed under the latency budget."""
        return self.p99_ms < self.budget_ms


@dataclass
class LoadReport:
    """Aggregate load report across the concurrency sweep.

    ``supported_concurrency`` is the in-flight count the single process is
    expected to hold the budget at. Levels at or below it are *gated* (their tail
    must stay under budget); higher levels are *reported* — they map out the
    capacity envelope (where the budget breaks and you must scale out) rather
    than gating a property the single process was never expected to hold.
    """

    budget_ms: float
    waves: int
    supported_concurrency: int = DEFAULT_SUPPORTED_CONCURRENCY
    results: list[LoadResult] = field(default_factory=list)

    @property
    def all_did_work(self) -> bool:
        return all(r.did_work for r in self.results)

    @property
    def gated_results(self) -> list[LoadResult]:
        """Levels at or below the supported concurrency (the hard gate)."""
        return [r for r in self.results if r.concurrency <= self.supported_concurrency]

    @property
    def budget_breaks_at(self) -> int | None:
        """Lowest concurrency whose p99 breaches the budget, if any."""
        for r in self.results:
            if not r.under_budget:
                return r.concurrency
        return None

    @property
    def passed(self) -> bool:
        """All levels did work and every *gated* level held its tail under budget."""
        return (
            bool(self.results)
            and self.all_did_work
            and all(r.under_budget for r in self.gated_results)
        )

    @property
    def peak_throughput(self) -> LoadResult:
        """The level that cleared the most requests per second."""
        return max(self.results, key=lambda r: r.throughput_rps)

    @property
    def worst_p99_ms(self) -> float:
        return max(r.p99_ms for r in self.results)

    def format(self) -> str:
        """Human-readable report for the CLI and CI logs."""
        lines = [
            f"Concurrency load, {self.waves}-wave sweep (real OCR, budget {self.budget_ms:.0f} ms)",
            "-" * 72,
            f"  {'conc':>4} {'reqs':>5} {'p50':>7} {'p95':>7} {'p99':>7} {'max':>7} {'rps':>6}",
        ]
        for r in self.results:
            if not r.did_work:
                flag = "  <-- NO TEXT"
            elif not r.under_budget:
                flag = "  <-- over budget"
            else:
                flag = ""
            lines.append(
                f"  {r.concurrency:>4} {r.n_requests:>5} {r.p50_ms:>7.0f} "
                f"{r.p95_ms:>7.0f} {r.p99_ms:>7.0f} {r.max_ms:>7.0f} "
                f"{r.throughput_rps:>6.1f}{flag}"
            )
        peak = self.peak_throughput
        breaks_at = self.budget_breaks_at
        envelope = (
            f"holds the {self.budget_ms:.0f} ms p99 budget through every level swept"
            if breaks_at is None
            else f"p99 first breaches the {self.budget_ms:.0f} ms budget at concurrency {breaks_at}"
        )
        lines += [
            "-" * 72,
            f"  peak throughput {peak.throughput_rps:.1f} req/s at concurrency "
            f"{peak.concurrency}   capacity envelope: {envelope}",
            f"  verdict: {'PASS' if self.passed else 'FAIL'} "
            f"(gated levels: concurrency <= {self.supported_concurrency})",
        ]
        return "\n".join(lines)


def _run_level(
    service: OcrService,
    payloads: list[bytes],
    concurrency: int,
    n_requests: int,
    budget_ms: float,
) -> LoadResult:
    """Fire ``n_requests`` through a ``concurrency``-wide pool; keep every sample.

    Each task runs the full preprocess→OCR→extract hot path against the shared
    service (round-robining the corpus payloads), exactly as a concurrent batch
    of verify requests would. Wall span is measured across the whole drain, so
    throughput reflects what the box actually cleared under that contention.
    """

    def _task(idx: int) -> tuple[float, int]:
        elapsed_ms, n_lines, _ = _time_pipeline(service, payloads[idx % len(payloads)])
        return elapsed_ms, n_lines

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(_task, range(n_requests)))
    wall_s = time.perf_counter() - start

    latencies = [r[0] for r in results]
    n_lines_min = min(r[1] for r in results)
    return LoadResult(
        concurrency=concurrency,
        latencies_ms=latencies,
        wall_s=wall_s,
        budget_ms=budget_ms,
        n_lines_min=n_lines_min,
    )


def benchmark_load(
    *,
    service: OcrService | None = None,
    cases: list[CorpusCase] | None = None,
    concurrency_levels: tuple[int, ...] = DEFAULT_CONCURRENCY,
    waves: int = DEFAULT_WAVES,
    budget_ms: float = DEFAULT_BUDGET_MS,
    supported_concurrency: int = DEFAULT_SUPPORTED_CONCURRENCY,
) -> LoadReport:
    """Sweep concurrency levels and return a :class:`LoadReport`.

    The OCR engine is warmed once up front (mirroring the best-of-N harness and
    the app's startup warmup) so one-time ONNX session-build cost never lands in
    a measured request. Payloads are read once; we measure decode+OCR+extract
    under contention, not disk I/O.
    """
    service = service or get_ocr_service()
    cases = cases if cases is not None else load_corpus().cases

    service.warmup()
    payloads = [c.image_path().read_bytes() for c in cases]

    results: list[LoadResult] = []
    for concurrency in concurrency_levels:
        n_requests = max(1, concurrency * max(1, waves))
        results.append(_run_level(service, payloads, concurrency, n_requests, budget_ms))

    return LoadReport(
        budget_ms=budget_ms,
        waves=max(1, waves),
        supported_concurrency=supported_concurrency,
        results=results,
    )
