#!/usr/bin/env sh
# Backend container entrypoint: apply DB migrations, then launch the API.
#
# Compose orders startup with `depends_on: db: condition: service_healthy`, so
# Postgres is reachable by the time we get here. `alembic upgrade head` is
# idempotent — re-running it on an up-to-date database is a no-op.
set -e

echo "[entrypoint] Applying database migrations..."
alembic upgrade head

# Optional demo data: SEED_DEMO=1 populates an EMPTY database with sample
# submissions (pass/warning/fail + recorded decisions) so the review queue
# demos with realistic content. A no-op whenever any submission exists.
if [ "${SEED_DEMO:-0}" = "1" ]; then
  echo "[entrypoint] SEED_DEMO=1 — seeding demo submissions (skips if data exists)..."
  python -m app.seed
fi

echo "[entrypoint] Starting API on :8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
