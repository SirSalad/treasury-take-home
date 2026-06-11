"""Export the FastAPI-generated OpenAPI spec to a stable, committed file.

The backend's pydantic models are the source of truth for the wire contract;
this dumps ``app.openapi()`` as deterministic JSON (sorted keys, 2-space
indent) into ``backend/openapi.json``. The frontend generates its TypeScript
API types from that file (``pnpm gen:api`` -> ``src/lib/api.gen.ts``), and CI
fails when either artefact is stale — so the client types can never silently
drift from the backend.

Usage (from ``backend/``)::

    python scripts/export_openapi.py            # write openapi.json
    python scripts/export_openapi.py --check    # exit 1 when out of date
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.main import app

SPEC_PATH = Path(__file__).resolve().parent.parent / "openapi.json"


def render() -> str:
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    spec = render()
    if "--check" in sys.argv[1:]:
        current = SPEC_PATH.read_text() if SPEC_PATH.exists() else ""
        if current != spec:
            print(
                f"{SPEC_PATH.name} is out of date with the FastAPI app. "
                "Regenerate with: python scripts/export_openapi.py "
                "(then `pnpm gen:api` in frontend/)",
                file=sys.stderr,
            )
            return 1
        print(f"{SPEC_PATH.name} is up to date.")
        return 0
    SPEC_PATH.write_text(spec)
    print(f"wrote {SPEC_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
