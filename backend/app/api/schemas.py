"""Request/response schemas for the verification API."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import ProductSource, ProductType, SubmissionStatus
from app.ocr.quality import ImageQuality
from app.verify.schemas import VerificationResult


class ApplicationInput(BaseModel):
    """The expected COLA (TTB 5100.31 / 1513-0020) fields submitted for a check.

    Mirrors the verifiable subset of :class:`app.models.application.Application`.
    Only ``brand_name`` is required; the rest are verified when supplied. Carries
    enough identity (``source``, ``product_type``) to persist the application
    alongside the submission. Satisfies the engine's ``ExpectedFields`` protocol.
    """

    brand_name: str = Field(min_length=1)
    source: ProductSource = ProductSource.DOMESTIC
    product_type: ProductType = ProductType.DISTILLED_SPIRITS

    class_type: str | None = None
    alcohol_content_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    alcohol_content_text: str | None = None
    net_contents: str | None = None
    name_and_address: str | None = None
    country_of_origin: str | None = None
    vintage: str | None = None

    # Optional identification carried through to the persisted application.
    serial_number: str | None = None
    fanciful_name: str | None = None
    appellation: str | None = None


class TimingInfo(BaseModel):
    """Where the wall-clock time went, so agents can see the 5s budget holding."""

    total_ms: int
    ocr_ms: int


class VerificationImageInfo(BaseModel):
    """One image of the verified filing, with its readability grade."""

    index: int
    filename: str | None
    quality: ImageQuality


class VerificationResponse(BaseModel):
    """The API response for one verification (a filing's full label set).

    ``image_filename`` mirrors the first image for older clients; ``images``
    lists every uploaded label with its per-image readability. The result's
    fields carry ``image_index`` into this list.
    """

    submission_id: int
    application_id: int | None
    status: SubmissionStatus
    image_filename: str | None
    images: list[VerificationImageInfo]
    timing: TimingInfo
    result: VerificationResult
    # Worst readability across the uploaded images — retake guidance: a blurry
    # back label warrants a retake even when the front read fine.
    image_quality: ImageQuality
