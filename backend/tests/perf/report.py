"""CLI: print the pipeline latency report.

    python -m tests.perf.report                  # default: best of 3, 5000 ms
    python -m tests.perf.report --repeats 5
    python -m tests.perf.report --budget-ms 4000

Exits non-zero if p95 breaches the budget, so it doubles as a manual gate.
"""

from __future__ import annotations

import argparse
import sys

from tests.perf import benchmark_corpus
from tests.perf.harness import DEFAULT_BUDGET_MS, DEFAULT_REPEATS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TTB pipeline latency benchmark")
    parser.add_argument(
        "--repeats",
        type=int,
        default=DEFAULT_REPEATS,
        help=f"best-of-N samples per label (default {DEFAULT_REPEATS})",
    )
    parser.add_argument(
        "--budget-ms",
        type=float,
        default=DEFAULT_BUDGET_MS,
        help=f"latency budget in ms (default {DEFAULT_BUDGET_MS:.0f})",
    )
    args = parser.parse_args(argv)

    report = benchmark_corpus(repeats=args.repeats, budget_ms=args.budget_ms)
    print(report.format())
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
