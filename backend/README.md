# Backend — TTB Label Verification API

FastAPI service. See the [root README](../README.md) for the full picture.

## Develop

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

uvicorn app.main:app --reload     # http://localhost:8000/health
```

## Lint & test

```bash
ruff check .
ruff format --check .
pytest
```

## Layout

```
backend/
├── app/            # application package (FastAPI app, routes, services)
│   ├── __init__.py
│   └── main.py     # app factory + /health
├── tests/          # pytest suite
└── pyproject.toml  # deps + ruff/pytest config
```
