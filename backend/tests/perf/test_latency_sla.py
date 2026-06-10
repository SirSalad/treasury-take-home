"""The 5-second SLA gate: assert pipeline p95 stays under budget.

Runs real OCR over the whole corpus, so it is marked ``perf`` and is the
slowest test in the suite. It still runs by default (CI is meant to catch
latency regressions); deselect it for fast local iteration with
``pytest -m "not perf"``.

Both the budget and the sample count are env-overridable so a constrained CI
runner can relax them without code changes:

* ``PERF_BUDGET_MS``  — latency budget in ms (default 5000).
* ``PERF_REPEATS``    — best-of-N sample count (default 3).
"""

from __future__ import annotations

import os

import pytest

from tests.perf import benchmark_corpus
from tests.perf.harness import DEFAULT_BUDGET_MS, DEFAULT_REPEATS

pytestmark = pytest.mark.perf


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


@pytest.fixture(scope="module")
def report():
    """One benchmark run shared by the assertions below (OCR is expensive)."""
    return benchmark_corpus(
        repeats=_env_int("PERF_REPEATS", DEFAULT_REPEATS),
        budget_ms=_env_float("PERF_BUDGET_MS", DEFAULT_BUDGET_MS),
    )


def test_pipeline_actually_recognised_text(report) -> None:
    """Guard: every label must produce OCR lines, or the timing is meaningless."""
    empty = [t.case_id for t in report.timings if not t.did_work]
    assert not empty, f"OCR produced no text for {empty}; latency numbers are bogus"


def test_p95_latency_under_budget(report) -> None:
    """The headline SLA: p95 of per-label best latency is under the budget."""
    # Always surface the distribution so CI logs document p50/p95 even on pass.
    print("\n" + report.format())
    assert report.p95_ms < report.budget_ms, (
        f"p95 {report.p95_ms:.0f} ms exceeds budget {report.budget_ms:.0f} ms\n" + report.format()
    )
