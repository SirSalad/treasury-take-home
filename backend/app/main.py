"""FastAPI application entrypoint.

This is an intentionally minimal skeleton: it exposes a health check so the
scaffold's lint/test gates run green. Domain routes (verification, batch, etc.)
are added by their respective issues.
"""

from fastapi import FastAPI

from app import __version__

app = FastAPI(
    title="TTB Label Verification API",
    version=__version__,
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness/readiness probe used by Docker Compose and the frontend."""
    return {"status": "ok", "version": __version__}
