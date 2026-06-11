"""HTTP API layer: routers and request/response schemas.

Domain logic lives in ``app.ocr`` / ``app.extract`` / ``app.match`` /
``app.verify``; this package only adapts it to HTTP (multipart upload in, JSON
verdict out) and persistence.
"""

from app.api.audit import router as audit_router
from app.api.submissions import router as submissions_router
from app.api.verify import router as verify_router

__all__ = ["audit_router", "submissions_router", "verify_router"]
