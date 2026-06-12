# Performance: the 5-second budget

The discovery interviews pinned a hard product constraint: an agent uploads a
label and gets results in **under 5 seconds**. This note documents how that
budget is measured, what the headroom is today, and the levers available if a
future change eats into it.

## What dominates the budget

The verification hot path is:

```
preprocess (decode + resolution cap)  →  OCR  →  field extraction  →  match + aggregate
```

OCR is the entire story. Detection + angle classification + recognition on CPU
runs in low single-digit seconds; everything downstream (regex extraction, fuzzy
matching, the warning check, aggregation) is pure-Python and sub-millisecond. So
the harness measures **preprocess + OCR + extract** and treats match/aggregate
as free — they are, relative to a 5s budget.

## The harness

`tests/perf/` measures the pipeline over the labelled corpus
(`tests/corpus/`, 6 representative labels spanning the verdict space).

- **`tests/perf/harness.py`** — `benchmark_corpus()` returns a
  `BenchmarkReport` with per-label timings and p50/p95/max.
- **`tests/perf/test_latency_sla.py`** — the CI gate (marked `perf`): asserts
  p95 < budget and that every label actually produced OCR text (so a silently
  broken pipeline can't "pass" by doing nothing).
- **`tests/perf/report.py`** — a CLI for humans.

```bash
# Full report (best of 3 samples per label, 5000 ms budget):
python -m tests.perf.report

# Tighter budget / more samples:
python -m tests.perf.report --budget-ms 4000 --repeats 5

# Run the gate as part of the suite (it runs by default):
pytest -m perf
# Skip it for fast local iteration:
pytest -m "not perf"
```

### Best-of-N sampling (why the gate doesn't flake)

Each label is timed `repeats` times and the **minimum** is kept. CI runners and
shared dev hosts are multi-tenant: a noisy neighbour can triple a single sample
without the pipeline changing at all. A raw worst-case gate would flake
constantly and teach us nothing. Best-of-N isolates the latency the pipeline
*can* achieve on the given CPU — which is exactly what a latency **regression**
gate should defend. The trade-off is that it does not capture
contention-driven tail latency; that's an infrastructure/capacity question, not
a question about whether the pipeline is fast enough on a CPU. That capacity
question is no longer left open — it is measured directly in
[Under concurrent load](#under-concurrent-load-tail-latency--capacity) below.

Both knobs are environment-overridable so a constrained runner can adjust
without code changes:

| Variable          | Default | Meaning                          |
| ----------------- | ------- | -------------------------------- |
| `PERF_BUDGET_MS`  | `5000`  | latency budget (ms)              |
| `PERF_REPEATS`    | `3`     | best-of-N sample count per label |

## Headroom today

The deployment moved from a 4-vCPU **shared** VPS to a **dedicated** 12-vCPU /
31 GB host. Best-of-N over the corpus (best of 5), measured on the dedicated
host:

| Metric | Latency  |
| ------ | -------- |
| p50    | ~0.9 s   |
| p95    | ~1.0 s   |
| budget | 5.0 s    |

That is roughly **80% headroom** under the budget — about 2.5× faster than the
old 6-core shared box (which ran ~2.4 s p50, ~30–50% headroom). The slowest
labels are still the text-dense ones (the wine label has ~13 recognised lines);
recognition cost scales with the number of detected text regions, not just image
size.

These are *best-of-N* (uncontended) figures: the latency one request sees when
it has the box to itself. What happens when several land at once is a separate
question, measured next.

## Under concurrent load: tail latency & capacity

Best-of-N answers "is the pipeline fast enough on a CPU?". It deliberately says
nothing about what the **tail** does when N requests arrive together and fight
over the cores — the capacity question the caveat above used to defer. On the
dedicated host we now drive that directly.

### The harness

`tests/perf/loadtest.py` drives a sweep of concurrency levels, each firing waves
of concurrent requests through the production hot path against the shared, warmed
`OcrService` — the same singleton the FastAPI app hands every request (the verify
endpoint is a *sync* def, so Starlette already serves concurrent requests from a
worker thread pool over that one engine; the harness reproduces that, it doesn't
invent a new model). Unlike the best-of-N gate it keeps **every** sample and
reports the full distribution plus throughput.

- **`tests/perf/loadtest.py`** — `benchmark_load()` returns a `LoadReport` with
  per-level p50/p95/p99/max and throughput.
- **`tests/perf/test_load_latency.py`** — a `perf`-marked gate. It asserts the
  tail holds under budget only at the *supported* concurrency (see below) and
  reports the rest; gating a property the single process was never built to hold
  would be dishonest. Deselected in CI alongside the other `perf`/`e2e` markers.
- **`tests/perf/loadreport.py`** — a CLI for humans:
  `python -m tests.perf.loadreport`.

```bash
# Full sweep (concurrency 1..16, real OCR under load):
python -m tests.perf.loadreport
# Custom sweep / more samples:
python -m tests.perf.loadreport --concurrency 1,8,16,24 --waves 12
```

### What we measured (dedicated 12-vCPU host)

| Concurrency | p50    | p95    | p99    | Throughput |
| ----------- | ------ | ------ | ------ | ---------- |
| 1           | ~0.9 s | ~1.0 s | ~1.0 s | ~1.2 req/s |
| 2           | ~1.9 s | ~2.3 s | ~2.3 s | ~1.0 req/s |
| 4           | ~3.9 s | ~4.5 s | ~4.6 s | ~1.0 req/s |
| 8           | ~8.7 s | ~10 s  | ~10 s  | ~0.9 req/s |
| 12          | ~12 s  | ~15 s  | ~15 s  | ~1.0 req/s |
| 16          | ~17 s  | ~20 s  | ~21 s  | ~1.0 req/s |

Two things are clear, and they are the honest answer to the deferred question:

1. **Tail latency grows ~linearly with in-flight count, and throughput is flat
   at ~1 req/s** regardless of concurrency. The pipeline does **not** scale
   across concurrent requests on a single process: ONNXRuntime already uses
   *every* core for intra-op parallelism within one inference, so a single OCR
   call saturates the box. Adding a second concurrent request buys no extra
   cores — the two time-share, each takes ~2× as long, and aggregate throughput
   stays put. This is a capacity ceiling, not a pipeline regression.

2. **The 5 s budget holds the tail up to ~4 concurrent in-flight requests per
   process** (p99 ~4.6 s at concurrency 4) and **breaches by 8** (p99 ~10 s). So
   a single process comfortably serves the SLA at low concurrency; sustained
   concurrent load past ~4 in-flight is where the budget breaks.

### What this means for capacity

The unit of capacity is **~1 verification/second per process**, holding the 5 s
tail to ~4 concurrent in-flight. To serve more, scale the thing that is actually
the bottleneck — **CPU cores per request** — by going *wider*, not by making one
request faster:

- **Horizontal scaling.** Run multiple app processes/replicas (uvicorn workers
  or containers), each with a slice of the cores, behind a load balancer.
  Aggregate throughput scales with the number of processes until the 12 cores are
  divided up.
- **Trade per-request latency for throughput.** Cap ONNXRuntime intra-op threads
  per request (e.g. `OMP_NUM_THREADS`, or session `intra_op_num_threads`) so each
  request uses fewer cores and more requests run on disjoint cores at once. This
  raises a *single* request's latency but lets concurrent requests scale —
  worthwhile if the workload is bursty/parallel rather than latency-critical
  single shots. (See the thread-settings lever in
  [Tuning levers](#tuning-levers-used-and-available).)

The knobs are environment-overridable so a constrained host can shrink the sweep:

| Variable            | Default       | Meaning                                   |
| ------------------- | ------------- | ----------------------------------------- |
| `PERF_BUDGET_MS`    | `5000`        | latency budget (ms)                       |
| `LOAD_CONCURRENCY`  | `1,2`         | gated concurrency levels (test)           |
| `LOAD_WAVES`        | `4`           | waves of `concurrency` requests per level |

## Tuning levers (used and available)

Applied:

- **Resolution cap (`OCR_MAX_SIDE`, default 1600px).** OCR cost scales with
  pixel area. Uploads are downscaled so their longest side is ≤ the cap before
  detection (`app/ocr/preprocess.py`), bounding worst-case latency on
  multi-megapixel phone photos. The synthetic corpus is ~900px, so the cap is a
  no-op there — it protects the real-world tail. The detector is also set to
  `limit_type="max"`, which stops RapidOCR from *upscaling* small labels (its
  default pads the short side up to 736px).
- **Recognition batching (`OCR_REC_BATCH_NUM`, default 8).** Text-dense labels
  recognise their crops in fewer batched passes (RapidOCR defaults to groups of
  6).
- **Startup warmup.** The ONNX sessions are built and exercised once at app
  startup (FastAPI lifespan) and once before the benchmark loop, so the
  multi-second first-call cost never lands on a real request or a measured
  sample.

Available if the budget tightens:

- **Lower `OCR_MAX_SIDE`** (e.g. 1024). Faster, but small print is the risk —
  the mandatory Government Health Warning is the smallest text on the label and
  must stay legible. Going below ~700px on the corpus starts dropping the
  warning, so this lever has a floor.
- **Drop the angle classifier** for pipelines where labels are always upright.
  Measured *slower* here (and it costs rotated-text robustness), so it stays on.
- **Model choice.** RapidOCR ships heavier/lighter PP-OCR variants; an
  English-only recogniser would trim the recognition head. Out of scope for now
  (models are vendored and the current pair already clears the budget), but it's
  the next lever if CPU gets slower or the budget gets stricter.
- **Thread settings.** ONNXRuntime already uses all physical cores for intra-op
  parallelism by default; on a busier host, pinning `OMP_NUM_THREADS` can trade
  per-request latency against cross-request throughput.
