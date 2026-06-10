# Backend — TTB Label Verification API

FastAPI service. See the [root README](../README.md) for the full picture.

## Develop

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env              # adjust DATABASE_URL / CORS_ORIGINS as needed
uvicorn app.main:app --reload     # http://localhost:8000/health
```

Configuration is read from the environment (and an optional `.env` file) via
pydantic-settings — see `app/config.py` and `.env.example`.

## Database & migrations

Postgres via SQLAlchemy 2.0 + Alembic. The Alembic environment reads
`DATABASE_URL` from the app settings, so migrations target the same database as
the app.

```bash
# Apply all migrations (creates the schema):
alembic upgrade head

# Autogenerate a migration after changing models in app/models/:
alembic revision --autogenerate -m "describe change"

# Verify the models and migrations are in sync (no drift):
alembic check
```

The driver is psycopg 3, so connection URLs use the `postgresql+psycopg://`
scheme.

## OCR

Text extraction uses [RapidOCR](https://github.com/RapidAI/RapidOCR) on
ONNXRuntime (PP-OCRv3 detection + recognition, plus an angle classifier). The
service lives in `app/ocr/`:

```python
from app.ocr import get_ocr_service

result = get_ocr_service().extract(image)   # path | bytes | numpy ndarray
result.full_text          # all lines, top-to-bottom
result.lines[0].text      # recognised text
result.lines[0].box       # axis-aligned BoundingBox (+ .polygon for rotation)
result.lines[0].confidence
```

Two deliberate constraints:

- **Models are pinned locally** in `app/ocr/models/*.onnx` and loaded by explicit
  path. The TTB network blocks outbound traffic, so nothing is downloaded at
  runtime.
- **The model is warmed at startup** (FastAPI lifespan) so the first real request
  doesn't pay the multi-second session-init cost. Set `OCR_WARMUP=false` to skip
  it during fast-iteration runs.

The OCR tests run the real models against `tests/fixtures/sample_label.png`
(regenerate with `python tests/fixtures/generate_sample_label.py`).

## Performance (the 5s budget)

A `< 5s` per-label result is a hard product constraint. `tests/perf/` benchmarks
the full **preprocess → OCR → extract** path over the corpus and gates p95
against the budget; today's headroom is ~30–50% on a CPU host. See
[`docs/perf.md`](../docs/perf.md) for methodology and tuning levers.

```bash
python -m tests.perf.report          # p50/p95 report (CLI)
pytest -m perf                       # the SLA gate (runs in the full suite too)
pytest -m "not perf"                 # skip it for fast iteration
```

Knobs: `OCR_MAX_SIDE` (upload resolution cap, default 1600), `OCR_REC_BATCH_NUM`
(default 8), and `PERF_BUDGET_MS` / `PERF_REPEATS` for the gate.

## Lint & test

```bash
ruff check .
ruff format --check .
pytest
```

Model tests run against an in-memory SQLite database (see `tests/conftest.py`),
so the suite needs no running Postgres.

## Layout

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py          # app factory + CORS + /health
│   ├── config.py        # pydantic-settings Settings
│   ├── db.py            # engine, session factory, declarative Base
│   ├── ocr/             # RapidOCR service + schemas + vendored ONNX models
│   └── models/          # ORM models
│       ├── application.py   # COLA / TTB 5100.31 (1513-0020) expected fields
│       ├── submission.py    # one label image: status, timing, result JSON
│       ├── batch.py         # Batch + BatchItem (bulk uploads)
│       ├── enums.py
│       └── types.py         # JSONB/JSON variant, timestamp mixin
├── alembic/             # migration environment + versions/
├── alembic.ini
├── tests/               # pytest suite (SQLite-backed model tests)
└── pyproject.toml       # deps + ruff/pytest config
```

## Data model

- **Application** — the expected label data an agent verifies against, mirroring
  TTB Form 5100.31 (OMB 1513-0020): brand name, class/type, alcohol content, net
  contents, bottler name/address, country of origin, plus wine-specific fields.
- **Submission** — one uploaded label image: storage ref, processing status and
  timing, and the verification `result` (JSONB on Postgres). Submissions are
  durable verification records.
- **Batch** / **BatchItem** — a bulk upload (peak-season importer dumps) and the
  ordered links to its submissions.

## Verification result schema

`app/verify` rolls the engine's individual checks into one verdict. The output
(`VerificationResult`) is the **stable JSON contract** stored in
`Submission.result` and rendered by the comparison UI / batch results:

```python
from app.verify import build_result, field_result_from_match, verify_warning_from_ocr

fields = [field_result_from_match(m) for m in field_matches]   # + extracted fields
warning = verify_warning_from_ocr(ocr_result)
result = build_result(fields, warning)     # overall verdict + summary + rationale
result.model_dump(mode="json")             # -> persist on the Submission
```

Shape:

- `overall` — `pass` / `warning` / `fail` (`OverallVerdict`). `warning` is the
  "needs review" middle state.
- `fields[]` — per field: `field` (logical key), `status`
  (`match` / `soft_warning` / `mismatch` / `not_checked`), `expected`, `found`,
  `score` ∈ [0,1], and a `span` + `box` locating the matched text for the UI.
- `government_warning` — the dedicated `GovernmentWarningResult` (its own
  `compliant` / `altered` / `missing` vocabulary), kept separate from the fields.
- `summary` — counts by field status; `rationale` — why the overall came out so;
  `schema_version` — bumped on incompatible shape changes.

**Aggregation rules** (`app/verify/aggregate.py`): any field `mismatch`, or a
warning that is `altered`/`missing` → **FAIL**; otherwise any `soft_warning` →
**WARNING**; otherwise **PASS**. `not_checked` fields (absent from the
application) never affect the verdict. These rules are pinned against the golden
corpus by `tests/test_corpus.py` and `tests/test_aggregate.py`, so the engine and
the labelled expectations cannot drift apart.
