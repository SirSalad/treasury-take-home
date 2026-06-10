#!/usr/bin/env sh
# Backend container entrypoint: apply DB migrations, then launch the API.
#
# Compose orders startup with `depends_on: db: condition: service_healthy`, so
# Postgres is reachable by the time we get here. `alembic upgrade head` is
# idempotent — re-running it on an up-to-date database is a no-op.
set -e

echo "[entrypoint] Applying database migrations..."
alembic upgrade head

echo "[entrypoint] Starting API on :8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
