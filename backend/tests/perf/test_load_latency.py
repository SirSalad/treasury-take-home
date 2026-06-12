"""Under-load tail-latency gate: p99 stays under budget across a concurrency sweep.

This is the load counterpart to the best-of-N SLA gate in
``test_latency_sla.py``. Where that gate keeps the *least*-perturbed sample to
defend the latency the pipeline *can* achieve, this one keeps **every** sample
under genuine concurrent contention and asserts the **tail** (p99) holds up —
the contention-driven question the Known Limitations caveat used to defer.

Real OCR under concurrent load, so it is marked ``perf`` (the slowest family in
the suite) and is deselected in CI alongside the other perf/e2e gates
(``pytest -m "not perf and not e2e and not eval"``). Run it explicitly with
``pytest -m perf`` or via the CLI: ``python -m tests.perf.loadreport``.

OCR is CPU-bound and ONNXRuntime already saturates every core for a single
inference, so concurrent requests time-share rather than scale and the tail
grows ~linearly with in-flight count. The single process therefore holds the 5s
budget only up to a small *supported concurrency* (see
``DEFAULT_SUPPORTED_CONCURRENCY``); beyond that the answer is horizontal scaling,
not a faster pipeline. This gate accordingly asserts the tail only at the
*gated* (supported) levels and merely reports the rest — gating a property the
single process was never built to hold would be dishonest.

Both the sweep and the budget are env-overridable so a constrained host can
relax them without code changes:

* ``PERF_BUDGET_MS``   — latency budget in ms (default 5000).
* ``LOAD_CONCURRENCY`` — comma-separated levels (default ``1,2``).
* ``LOAD_WAVES``       — waves of ``concurrency`` requests per level (default 4).

The defaults here are deliberately lighter than the harness/CLI defaults so a
manual ``pytest -m perf`` stays quick; the CLI report
(``python -m tests.perf.loadreport``) sweeps the fuller envelope for docs.
"""

from __future__ import annotations

import os

import pytest

from tests.perf.harness import DEFAULT_BUDGET_MS
from tests.perf.loadtest import benchmark_load

pytestmark = pytest.mark.perf

# Lighter than DEFAULT_CONCURRENCY / DEFAULT_WAVES so `pytest -m perf` is quick:
# just the gated (supported) levels. The CLI report sweeps the fuller envelope.
_TEST_CONCURRENCY = (1, 2)
_TEST_WAVES = 4


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


def _env_concurrency(name: str, default: tuple[int, ...]) -> tuple[int, ...]:
    raw = os.environ.get(name)
    if not raw:
        return default
    return tuple(int(p) for p in raw.split(",") if p.strip())


@pytest.fixture(scope="module")
def report():
    """One load sweep shared by the assertions below (real OCR is expensive)."""
    return benchmark_load(
        concurrency_levels=_env_concurrency("LOAD_CONCURRENCY", _TEST_CONCURRENCY),
        waves=_env_int("LOAD_WAVES", _TEST_WAVES),
        budget_ms=_env_float("PERF_BUDGET_MS", DEFAULT_BUDGET_MS),
    )


def test_every_level_recognised_text(report) -> None:
    """Guard: every concurrency level must produce OCR lines, or timings are bogus."""
    empty = [r.concurrency for r in report.results if not r.did_work]
    assert not empty, f"OCR produced no text at concurrency {empty}; numbers are bogus"


def test_tail_latency_under_budget_within_supported_envelope(report) -> None:
    """The headline: p99 holds under budget at every *gated* (supported) level."""
    # Always surface the distribution so CI logs document the load envelope.
    print("\n" + report.format())
    breaches = [
        (r.concurrency, round(r.p99_ms)) for r in report.gated_results if not r.under_budget
    ]
    assert not breaches, (
        f"p99 breached the {report.budget_ms:.0f} ms budget within the supported "
        f"envelope (concurrency <= {report.supported_concurrency}) at {breaches}\n"
        + report.format()
    )
