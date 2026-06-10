# TTB Label Verification

AI-powered alcohol-label verification prototype for the TTB Compliance Division.
An agent enters the application data (the COLA/TTB Form 5100.31 "1513-0020"
fields), uploads the label artwork, and the app extracts the label's text and
compares it against the application — flagging matches, warnings, and mismatches,
with special handling for the mandatory Government Health Warning.

> **Status:** scaffold. This README is a skeleton; sections are filled in as
> features land.

## Stack

| Layer    | Choice                                          | Why |
| -------- | ----------------------------------------------- | --- |
| Backend  | FastAPI (Python 3.11+)                           | Fast to build, typed, async-friendly |
| Frontend | Vite + React + TypeScript                        | Modern DX; USWDS theming for a 50+ user base |
| OCR      | Local, on-device (no cloud calls)                | Agency firewall blocks outbound ML endpoints |
| DB       | Postgres                                         | Batch/queue persistence |
| Runtime  | Docker Compose                                   | One command to bring up DB + API + frontend |

Design constraints come straight from the discovery interviews: **< 5s** results,
an interface **"my 73-year-old mother could figure out"**, and **no outbound
network calls** (everything runs locally).

## Repository layout

```
.
├── backend/      # FastAPI service (app/, tests/), pyproject.toml
├── frontend/     # Vite + React + TS app
├── docker/       # Dockerfiles + docker-compose
├── docs/         # Approach, decisions, assumptions
├── README.md
└── .pre-commit-config.yaml
```

## Setup

### Prerequisites

- Python 3.11+
- Node 20+ and pnpm (or npm)
- Docker + Docker Compose (for the full local stack)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### Frontend

```bash
cd frontend
pnpm install      # or: npm install
```

## Run

### Everything (Docker Compose)

```bash
docker compose -f docker/docker-compose.yml up --build
```

This will bring up Postgres, the API, and the frontend with a passing health
check. _(Compose lands with the Docker issue; until then, run the two services
manually below.)_

### Backend (dev)

```bash
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload
# health check: curl http://localhost:8000/health
```

### Frontend (dev)

```bash
cd frontend
pnpm dev          # or: npm run dev
```

## Lint & test

```bash
# Backend
cd backend && source .venv/bin/activate
ruff check . && ruff format --check . && pytest

# Frontend
cd frontend
pnpm lint && pnpm format:check && pnpm typecheck && pnpm test
```

## Approach

_To be documented as the verification engine and OCR pipeline land. Covers:
field extraction strategy, fuzzy matching rules (e.g. "STONE'S THROW" vs
"Stone's Throw"), the exact Government Warning check, and the 5s performance
budget._

## Assumptions & trade-offs

- **Standalone prototype** — no COLA integration; not storing PII or sensitive
  documents.
- **Local-only inference** — no cloud OCR/LLM APIs, per the agency firewall.
- **Scope** — single-label verification is the core flow; bulk upload and
  image-quality robustness are layered on as time allows.
- _Further trade-offs documented in `docs/` as decisions are made._
