"""HTTP API layer: routers and request/response schemas.

Domain logic lives in ``app.ocr`` / ``app.extract`` / ``app.match`` /
``app.verify``; this package only adapts it to HTTP (multipart upload in, JSON
verdict out) and persistence.
"""

from app.api.verify import router as verify_router

__all__ = ["verify_router"]
