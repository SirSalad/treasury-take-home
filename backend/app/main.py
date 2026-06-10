"""FastAPI application entrypoint.

Wires up configuration (pydantic-settings), CORS, and the health check. Domain
routes (verification, batch, etc.) are added by their respective issues.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="TTB Label Verification API",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness/readiness probe used by Docker Compose and the frontend."""
    return {"status": "ok", "version": __version__}
