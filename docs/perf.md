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
a question about whether the pipeline is fast enough on a CPU.

Both knobs are environment-overridable so a constrained runner can adjust
without code changes:

| Variable          | Default | Meaning                          |
| ----------------- | ------- | -------------------------------- |
| `PERF_BUDGET_MS`  | `5000`  | latency budget (ms)              |
| `PERF_REPEATS`    | `3`     | best-of-N sample count per label |

## Headroom today

On a 6-core CPU dev host, best-of-N over the corpus:

| Metric | Latency  |
| ------ | -------- |
| p50    | ~2.4 s   |
| p95    | ~2.5–3.7 s (rises under host load) |
| budget | 5.0 s    |

That is roughly **30–50% headroom** under the budget, the wider figure on a
quiet box. The slowest labels are the text-dense ones (the wine label has ~13
recognised lines); recognition cost scales with the number of detected text
regions, not just image size.

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
