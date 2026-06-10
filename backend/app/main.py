"""FastAPI application entrypoint.

Wires up configuration (pydantic-settings), CORS, OCR model warmup, and the
health check. Domain routes (verification, batch, etc.) are added by their
respective issues.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import verify_router
from app.config import get_settings
from app.ocr import get_ocr_service

logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Warm the OCR model at startup so the first request isn't slow.

    Building the ONNX sessions and running the first inference costs a few
    seconds; doing it here (rather than on the first upload) keeps real requests
    inside the latency budget. Warmup failures are logged but non-fatal so the
    service still starts and serves ``/health``.
    """
    if settings.ocr_warmup:
        try:
            get_ocr_service().warmup()
        except Exception:  # pragma: no cover - defensive: never block startup
            logger.exception("OCR warmup failed; first request may be slow")
    yield


app = FastAPI(
    title="TTB Label Verification API",
    version=__version__,
    lifespan=lifespan,
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


app.include_router(verify_router)
