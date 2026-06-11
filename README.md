# TTB Label Verification

AI-powered alcohol-label verification prototype for the TTB Compliance Division.
An agent enters the application data (the COLA/TTB Form 5100.31 "1513-0020"
fields), uploads the label artwork, and the app extracts the label's text and
compares it against the application — flagging matches, warnings, and mismatches,
with special handling for the mandatory Government Health Warning.

The product constraints come straight from the discovery interviews: **< 5s**
results, an interface **"my 73-year-old mother could figure out"**, and **no
outbound network calls** (everything runs locally, because the agency firewall
blocks outbound ML endpoints).

## Live demo

**🔗 https://sculpture-confident-provided-acting.trycloudflare.com**

Open the URL: the **Review Queue** (stat cards over recent submissions) is the
home screen. Click **New Verification**, fill in the application fields, and
upload a label image (samples live in
[`backend/tests/corpus/images/`](backend/tests/corpus/images/)) to get a
field-by-field verdict. **Batch upload** runs the same pipeline over a CSV
manifest + image set.

The full Docker Compose stack (Postgres + FastAPI + nginx-served frontend) runs
on a VPS; the public HTTPS URL is a Cloudflare tunnel terminating at the
frontend, which proxies `/api/*` to the backend. See
[Deployment](#deployment) for how it's wired. The tunnel uses a free
quick-tunnel hostname, so the URL changes if the tunnel is restarted — the value
above is current as of deploy.

## Stack

| Layer    | Choice                                          | Why |
| -------- | ----------------------------------------------- | --- |
| Backend  | FastAPI (Python 3.11+)                           | Fast to build, typed, async-friendly |
| Frontend | Vite + React + TypeScript                        | Modern DX; USWDS-themed for a 50+ user base |
| OCR      | RapidOCR on ONNXRuntime, models vendored locally | On-device inference; no cloud calls |
| DB       | Postgres                                         | Submission/application persistence + audit trail |
| Runtime  | Docker Compose                                   | One command to bring up DB + API + frontend |

## Repository layout

```
.
├── backend/      # FastAPI service (app/, tests/), pyproject.toml
│   ├── app/
│   │   ├── ocr/        # RapidOCR service, preprocessing, vendored ONNX models
│   │   ├── extract/    # deterministic regex extractors (ABV, net contents, …)
│   │   ├── match/      # fuzzy three-state brand/class-type matcher
│   │   ├── verify/     # verification engine, aggregation, Government Warning check
│   │   ├── batch/      # CSV-manifest batch ingestion (library; not yet an endpoint)
│   │   ├── api/        # POST /api/verify endpoint + request/response schemas
│   │   └── models/     # SQLAlchemy ORM (Application, Submission)
│   └── tests/          # unit + golden corpus + perf SLA harness
├── frontend/     # Vite + React + TS app
│   └── src/
│       ├── pages/         # QueuePage (review queue), ReviewPage, VerifyPage, BatchPage
│       ├── components/    # application form, 3-pane comparison view, layout
│       └── lib/           # API client, validation, types
├── docker/       # Dockerfiles + docker-compose
├── docs/         # perf.md (the 5s budget); approach notes
└── README.md
```

## Setup

### Prerequisites

- Python 3.11+
- Node 20+ and pnpm (or npm)
- Docker + Docker Compose (for the full local stack)

The OCR models are vendored in `backend/app/ocr/models/` and committed to the
repo — there is **nothing to download** and the service makes no outbound calls.

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # optional; defaults already match docker-compose / local dev
```

### Frontend

```bash
cd frontend
pnpm install      # or: npm install
```

## Run

### Everything (Docker Compose) — recommended

```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up --build
```

This brings up three services and waits for each to become healthy:

| Service    | Image / build              | URL                    | Notes |
| ---------- | -------------------------- | ---------------------- | ----- |
| `frontend` | nginx serving the SPA      | http://localhost:8080  | Proxies `/api/*` to the backend |
| `backend`  | FastAPI + RapidOCR         | http://localhost:8000  | `/health` probe; OCR models baked in |
| `db`       | `postgres:16-alpine`       | internal only (`db:5432`) | Volume `pgdata`; db `labelverify`; not published to the host |

The base file (`docker-compose.yml`) publishes **no host ports** so it deploys
unchanged behind a reverse-proxy PaaS (Dokploy, Coolify, …): route the domain
to service `frontend`, container port `80`, and set `CORS_ORIGINS` to the
public URL. The `docker-compose.dev.yml` overlay adds the localhost publishes
above (override with `FRONTEND_PORT`/`BACKEND_PORT`).

Set **`SEED_DEMO=1`** to populate an *empty* database with sample submissions
on boot (passes, flags, fails, and a couple of recorded decisions), so the
review queue demos with realistic content. It never touches a database that
already has submissions. Same thing by hand: `python -m app.seed`.

Open **http://localhost:8080** to use the app. The frontend talks to the API
same-origin through nginx, so there are no CORS or outbound calls. On boot the
backend applies Alembic migrations and warms the OCR model (hence the ~40s
`start_period` on its health check); the frontend waits for the backend to be
healthy before it starts.

Useful variants:

```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up --build -d   # detached
docker compose -f docker/docker-compose.yml logs -f backend # follow API logs
docker compose -f docker/docker-compose.yml down            # stop
docker compose -f docker/docker-compose.yml down -v         # stop + drop the DB volume
```

### Backend (dev)

```bash
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload
# health check: curl http://localhost:8000/health
# interactive API docs: http://localhost:8000/docs
```

A Postgres reachable at `DATABASE_URL` is required (default points at the
docker-compose db). The first request after startup warms the OCR model unless
`OCR_WARMUP=false`.

### Frontend (dev)

```bash
cd frontend
pnpm dev          # or: npm run dev   → http://localhost:5173
```

The dev server proxies `/api/*` to `http://localhost:8000`, so run the backend
alongside it.

## Deployment

The [live demo](#live-demo) runs the **same Docker Compose stack** above on a
small VPS, fronted by a Cloudflare tunnel for public HTTPS — no code changes
between local and prod.

```
reviewer ──HTTPS──▶ Cloudflare edge ──tunnel──▶ cloudflared ──▶ :8080 frontend ──/api/*──▶ :8000 backend ──▶ :5432 db
```

- **Stack** — `docker compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up -d`
  (the dev overlay publishes `:8080`, which the tunnel points at; a
  reverse-proxy PaaS like Dokploy needs only the base file). Each service
  carries `restart: unless-stopped`, so the stack survives a host reboot.
- **Public URL** — a [`cloudflared`](https://github.com/cloudflare/cloudflared)
  quick tunnel exposes the frontend (`:8080`) over HTTPS. It runs as a systemd
  service (`cloudflared-ttb.service`, `Restart=on-failure`,
  `WantedBy=multi-user.target`) pointing at `http://localhost:8080`, so it comes
  back after a crash or reboot:

  ```bash
  cloudflared tunnel --no-autoupdate --url http://localhost:8080
  ```

  The tunnel terminates TLS at Cloudflare's edge and forwards plain HTTP to the
  frontend; the frontend serves the SPA and proxies `/api/*` to the backend, so
  the browser only ever talks same-origin HTTPS.
- **Why a tunnel** — it needs no inbound firewall rule, no certificate
  management, and no DNS setup, which keeps the prototype deploy to a single
  command. The trade-off is the quick-tunnel hostname is ephemeral: restarting
  the tunnel mints a new `*.trycloudflare.com` URL. A production deploy would use
  a named Cloudflare tunnel (or a reverse proxy + Let's Encrypt) bound to a
  stable domain.

## Lint & test

```bash
# Backend
cd backend && source .venv/bin/activate
ruff check . && ruff format --check . && pytest        # add -m "not perf" to skip the latency gate

# Frontend
cd frontend
pnpm lint && pnpm format:check && pnpm typecheck && pnpm test
```

### OCR robustness eval (out-of-distribution)

The product targets **pre-market COLA review**, whose input is the manufacturer's
clean, head-on **label artwork**. That representative correctness is measured by
the **synthetic golden corpus** (`tests/corpus`, run by the unit suite) — clean,
generated labels that mirror a COLA submission.

This separate **eval** is the opposite on purpose: ~18 real **photos of real
labels** spanning clean front-of-label shots (Jack Daniel's, Jameson, Smirnoff,
Corona, Gallo, 7 Deadly Zins, Tito's, Sam Adams…) through wildly colorful RTDs
(Four Loko, BuzzBallz) to deliberately bad captures (a tilted Maker's Mark, a far
shelf) — none of which would be filed with the TTB. It is a **robustness /
graceful-degradation** check (not a COLA-accuracy number): it confirms that on
out-of-distribution inputs the pipeline still fuzzy-matches brands, reads
regulated fields where legible, and flags unreadable photos for retake rather than
producing a confident wrong verdict.

```bash
cd backend && pytest -m eval -s        # slow (real OCR over ~18 labels); runs offline
```

Cases live in `tests/eval/manifest.json` (ground truth + expected quality/verdict).
The photos are committed under `tests/eval/images/` so it runs offline and
deterministically — see `tests/eval/images/ATTRIBUTION.md` for each image's source
and licence (`commons_file` is only used to re-fetch if a local image is missing).
The eval is deselected from the default suite and CI. It
prints a per-case scorecard, e.g.:

```
ok    jack_daniels_eu_spirit  [spirit]  q=ok  brand=soft_warning abv=match
ok    buzzballz_chaos         [chaos]   q=ok  brand=soft_warning abv=mismatch
ok    makers_mark_bad_photo   [bad]     q=low  (flagged for retake)
```

### Real COLA artwork eval (in-distribution)

The third measurement closes the loop: **30 real approved COLAs (2025–2026)
scraped from the TTB Public COLA Registry** — 10 each wine/spirits/malt — with
the actual label artwork filed with each application and the filed form fields
as ground truth. This is exactly the input the product is built for, as it
exists in the wild: handwritten keg collars, rotated can wraps, a genuine 3%
lager. Expectations are monotone (equal-or-better passes, regressions fail), so
the set honestly encodes today's measured gaps — most notably that the
Government Warning on can wraps/keg collars usually runs 90° to the artwork and
is missed by OCR (found on only 10/30 real labels, vs. brand verified on
29/30 and ABV read on 23/30). See `backend/tests/eval_cola/README.md` for
methodology and traceability (every case carries its public TTB ID).

```bash
cd backend && pytest -m eval tests/eval_cola -s
```

## Continuous integration & quality gates

Every push to `main` and every pull request runs `.github/workflows/ci.yml`. A PR
is blocked unless all gates pass:

| Gate | Frontend | Backend |
| --- | --- | --- |
| Type safety | `tsc` (strict) | `mypy` |
| Lint | `eslint` | `ruff check` |
| Format | `prettier --check` | `ruff format --check` |
| Tests | `vitest` | `pytest` |
| Accessibility | **WCAG 2.1 AA via `axe-core`** (`src/a11y.test.tsx`) | — |
| Build | `vite build` | — |

The accessibility suite renders the Home, Verify, Batch, and result/comparison
screens and fails CI on any WCAG 2.0/2.1 **A or AA** violation — so the federal
accessibility bar is enforced automatically, not by hand.

### Software Bill of Materials (SBOM)

CI also generates a **CycloneDX SBOM** for each ecosystem (frontend npm/pnpm and
backend Python) via [Anchore Syft](https://github.com/anchore/sbom-action) and
uploads them as build artifacts (`sbom-frontend.cdx.json`, `sbom-backend.cdx.json`)
for supply-chain inventory and vulnerability scanning.

## Approach

### The verification pipeline

A single label is verified along the hot path **preprocess → OCR → extract →
verify**:

1. **Preprocess** (`app/ocr/preprocess.py`) — decode the upload and cap its
   longest side at 1600px. OCR cost scales with pixel area, so bounding the
   working resolution is what keeps a 4000px phone photo inside the latency
   budget; small labels are left untouched (only ever downscaled, using
   `INTER_AREA` to preserve small-text legibility).
2. **OCR** (`app/ocr/service.py`) — RapidOCR (detection + angle classification +
   recognition) on ONNXRuntime, CPU-only. The angle classifier is enabled so
   labels photographed sideways/upside-down still read. Models are vendored and
   loaded by path; the engine is warmed at startup so the first real request
   isn't slow.
3. **Field comparison** (`app/verify/engine.py`) — each field the application
   supplies is routed to the comparison strategy that fits it (below). Fields the
   application omits are not emitted, so the result mirrors the COLA that was
   filed.
4. **Aggregate** (`app/verify/aggregate.py`) — per-field results plus the
   Government Warning verdict roll up to one headline verdict.

Everything after OCR is pure-Python and sub-millisecond; OCR dominates the budget.

### Three comparison strategies, by field type

- **Numeric — alcohol content.** ABV is compared *numerically*, not as a string.
  A regex extractor (`app/extract/extractors.py`) recovers the percentage from
  the label ("45% Alc./Vol.", "ALC. 45% BY VOL.", anchored so it never matches
  the proof number), and it is compared to the application value within a 0.05%
  tolerance. A fuzzy string compare cannot tell "45%" from "40%" — a
  one-character, high-similarity difference that is nonetheless the most common
  and most consequential data-entry error.
- **Fuzzy free-text — brand name & class/type** (`app/match/matcher.py`). These
  can't be pinned with a regex, so the expected value is looked for *somewhere*
  in the OCR text and graded into three states with a blended character/token
  similarity ratio:
  - **MATCH** — present (ignoring whitespace/quote noise).
  - **SOFT_WARNING** — present but the *surface form* differs only in case or
    punctuation, **or** a near miss worth a human glance. This is Dave's
    "STONE'S THROW" vs "Stone's Throw" case: obviously the same brand, but worth
    flagging rather than silently passing. The engine prefers to grade the brand
    against the line that *is* the brand banner, so an all-caps header is caught
    even when the brand is spelled correctly elsewhere (e.g. in the address).
  - **MISMATCH** — a genuinely different value.
- **Other free-text** — net contents, name/address, country of origin, vintage
  use the same fuzzy-presence grader (these are printed verbatim, so presence
  matching is simple and robust to OCR noise).

### The Government Health Warning (special path)

The warning (`app/verify/warning.py`) gets its own near-exact verifier against
the canonical 27 CFR 16.21 statement, because Jenny told us it has to be
*exact*. It catches the common evasions:

- **MISSING** — no `GOVERNMENT WARNING` header anywhere in the text.
- **Altered wording** — the statement deviates from the required text (a dropped
  sentence, a reworded clause) beyond what OCR noise explains. Scored at the
  *word* level so a single garbled character passes but several missing words
  fail.
- **Title-case header** — `Government Warning` instead of the required all-caps
  `GOVERNMENT WARNING` (Jenny's catch). Header casing is judged independently of
  the wording, so a word-perfect body with a lowercased header still fails.

### Overall verdict (worst-of)

The headline verdict is the worst outcome implied by the parts:

- **FAIL** — any field is a MISMATCH, **or** the warning is ALTERED/MISSING. A
  mandatory-warning fault fails the label outright.
- **WARNING** — no hard fault, but at least one SOFT_WARNING. Plausibly fine,
  needs a human look.
- **PASS** — every checked field matches and the warning is compliant.

This policy is pinned by a golden-corpus test so the engine and the labelled
fixtures cannot drift apart.

### Performance — the 5s budget

The discovery interviews made < 5s a hard product constraint (the prior vendor's
30–40s pilot got abandoned). A perf harness (`backend/tests/perf/`) times
preprocess + OCR + extract over the labelled corpus and gates p95 against the
budget in CI. On a 6-core dev host the corpus runs ~2.4s p50, leaving roughly
30–50% headroom. The main lever is the resolution cap; recognition cost scales
with the number of detected text regions, so text-dense wine labels are the
slowest. Full detail in [`docs/perf.md`](docs/perf.md).

### Error handling

An undecodable upload, an empty file, or a decodable image with no recognisable
text is reported as a clean `4xx` (and recorded as a `FAILED` submission for the
audit trail) rather than a 500 or a misleading all-mismatch verdict. Uploads are
size-capped (20 MB) to bound memory.

## Assumptions & trade-offs

### Scope

- **Standalone prototype** — no COLA integration (out of scope per the IT
  interview); this is a proof-of-concept that could inform future procurement.
- **Single-label verification is the core flow** and is wired end-to-end:
  verify → review screen (annotated label, checklist, Government Warning diff)
  → recorded reviewer decision, with every submission landing in the **review
  queue** and every action in an append-only **audit trail** (`/api/audit`).
  **Batch upload** runs client-side over the same `POST /api/verify` pipeline
  (sample CSV, in-browser manifest editing, per-row triage); the backend batch
  ingestion library (`app/batch/`) exists and is tested but is not yet exposed
  as a server-side endpoint — given the time box, one verified pipeline beats
  two divergent ones.
- **No real authn/PII handling** — per the IT interview, nothing sensitive is
  stored for the exercise. Uploaded images are written to a local directory and
  referenced from the DB; a production deployment would use an object store and
  retention policy.

### Known limitations

- **Bold / font-size are not verified.** Jenny noted the `GOVERNMENT WARNING`
  header must be all-caps *and bold*, and 27 CFR 16.22 sets minimum font sizes.
  OCR recovers *text*, not typography — bold weight and absolute font size in
  points cannot be recovered from recognised text. The verifier checks presence,
  wording, and the all-caps requirement, and **explicitly surfaces bold/font-size
  as out-of-scope limitations** on the warning result rather than silently
  passing them. A future pass could measure glyph stroke-width and box height
  from the detector's bounding boxes to approximate these.
- **OCR edge cases.** RapidOCR is robust to moderate skew (the angle classifier
  handles 90°/180° rotations) and noise, but severe glare, very low resolution,
  heavy stylised/script typefaces, or text overlaid on busy artwork can drop or
  garble lines. The fuzzy thresholds are tuned to absorb ordinary OCR noise; a
  badly degraded image that yields no text is reported as unreadable (so an agent
  re-requests a better photo) rather than silently failing the label. Image
  enhancement (deglare, contrast normalisation) beyond the resolution cap was out
  of scope.
- **Fuzzy thresholds are heuristic.** The MATCH/SOFT_WARNING/MISMATCH cutoffs are
  similarity ratios tuned against the corpus, not learned probabilities. They are
  deliberately conservative — borderline cases become a SOFT_WARNING (a human
  glance) rather than a silent pass or a hard fail.
- **Latency is measured best-of-N** on a CPU host, which captures the latency the
  pipeline *can* achieve, not contention-driven tail latency under production
  load — that's a capacity question, not a pipeline question.

Further design notes live in [`docs/`](docs/).
