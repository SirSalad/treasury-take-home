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
