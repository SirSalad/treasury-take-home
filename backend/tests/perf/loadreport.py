"""CLI: print the under-load tail-latency report.

    python -m tests.perf.loadreport                       # default sweep
    python -m tests.perf.loadreport --waves 12            # more samples per level
    python -m tests.perf.loadreport --concurrency 1,8,16,24
    python -m tests.perf.loadreport --budget-ms 4000

Drives real concurrent OCR load across a concurrency sweep and reports
p50/p95/p99/max latency and throughput per level. Exits non-zero if any level's
p99 breaches the budget, so it doubles as a manual capacity gate.
"""

from __future__ import annotations

import argparse
import sys

from tests.perf.harness import DEFAULT_BUDGET_MS
from tests.perf.loadtest import DEFAULT_CONCURRENCY, DEFAULT_WAVES, benchmark_load


def _parse_concurrency(raw: str) -> tuple[int, ...]:
    return tuple(int(p) for p in raw.split(",") if p.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TTB pipeline concurrency load benchmark")
    parser.add_argument(
        "--concurrency",
        type=_parse_concurrency,
        default=DEFAULT_CONCURRENCY,
        help="comma-separated concurrency levels (default {})".format(
            ",".join(map(str, DEFAULT_CONCURRENCY))
        ),
    )
    parser.add_argument(
        "--waves",
        type=int,
        default=DEFAULT_WAVES,
        help=f"waves of `concurrency` requests per level (default {DEFAULT_WAVES})",
    )
    parser.add_argument(
        "--budget-ms",
        type=float,
        default=DEFAULT_BUDGET_MS,
        help=f"latency budget in ms (default {DEFAULT_BUDGET_MS:.0f})",
    )
    args = parser.parse_args(argv)

    report = benchmark_load(
        concurrency_levels=args.concurrency,
        waves=args.waves,
        budget_ms=args.budget_ms,
    )
    print(report.format())
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
