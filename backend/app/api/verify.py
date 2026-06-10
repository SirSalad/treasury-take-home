"""Single-label verification endpoint.

``POST /api/verify`` accepts a label image plus the expected COLA fields
(multipart form), runs the production hot path — preprocess -> OCR -> extract ->
verify — persists a :class:`app.models.submission.Submission` (and the
:class:`app.models.application.Application` it was checked against), and returns
the verdict contract with timing.

Robustness is a first-class concern: an undecodable upload or an image with no
recognisable text is reported as a clean ``422`` (and recorded as a ``FAILED``
submission for the audit trail) rather than a 500.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.schemas import ApplicationInput, TimingInfo, VerificationResponse
from app.config import Settings, get_settings
from app.db import get_db
from app.models.application import Application
from app.models.enums import ProductSource, ProductType, SubmissionStatus
from app.models.submission import Submission
from app.ocr import OcrService, get_ocr_service
from app.ocr.preprocess import decode_image
from app.ocr.quality import assess_image_quality
from app.verify import verify_label

router = APIRouter(prefix="/api", tags=["verification"])

# Cap upload size so a hostile or fat-fingered request can't exhaust memory. The
# corpus images are well under a megabyte; phone photos rarely top ~15 MB.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def _application_input(
    brand_name: Annotated[str, Form(min_length=1)],
    source: Annotated[ProductSource, Form()] = ProductSource.DOMESTIC,
    product_type: Annotated[ProductType, Form()] = ProductType.DISTILLED_SPIRITS,
    class_type: Annotated[str | None, Form()] = None,
    alcohol_content_pct: Annotated[float | None, Form()] = None,
    alcohol_content_text: Annotated[str | None, Form()] = None,
    net_contents: Annotated[str | None, Form()] = None,
    name_and_address: Annotated[str | None, Form()] = None,
    country_of_origin: Annotated[str | None, Form()] = None,
    vintage: Annotated[str | None, Form()] = None,
    serial_number: Annotated[str | None, Form()] = None,
    fanciful_name: Annotated[str | None, Form()] = None,
    appellation: Annotated[str | None, Form()] = None,
) -> ApplicationInput:
    """Bind the COLA form fields into a validated :class:`ApplicationInput`."""
    try:
        return ApplicationInput(
            brand_name=brand_name,
            source=source,
            product_type=product_type,
            class_type=class_type,
            alcohol_content_pct=alcohol_content_pct,
            alcohol_content_text=alcohol_content_text,
            net_contents=net_contents,
            name_and_address=name_and_address,
            country_of_origin=country_of_origin,
            vintage=vintage,
            serial_number=serial_number,
            fanciful_name=fanciful_name,
            appellation=appellation,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()
        ) from exc


@router.post("/verify", response_model=VerificationResponse)
def verify(
    image: Annotated[UploadFile, File(description="The label image to verify.")],
    application: Annotated[ApplicationInput, Depends(_application_input)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    ocr: Annotated[OcrService, Depends(get_ocr_service)],
) -> VerificationResponse:
    """Verify one label image against its expected application data."""
    data = image.file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty image upload.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )

    # Validate the image is decodable before doing anything expensive, so a bad
    # upload is a clean 422 rather than an OCR-time crash.
    try:
        decode_image(data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is not a readable image.",
        ) from exc

    image_ref = _store_upload(settings.upload_dir, image.filename, data)
    app_row = _persist_application(db, application)

    started = datetime.now(UTC)
    start = time.perf_counter()
    ocr_result = ocr.extract(data)

    if not ocr_result.lines:
        # Decodable but no text recovered: treat as unreadable rather than
        # silently returning an all-mismatch verdict on a blank/garbled image.
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        _persist_submission(
            db,
            app_row,
            image=image,
            image_ref=image_ref,
            status=SubmissionStatus.FAILED,
            started_at=started,
            processing_ms=elapsed_ms,
            error="No text could be recognised in the image.",
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No text could be recognised in the image.",
        )

    result = verify_label(application, ocr_result)
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    submission = _persist_submission(
        db,
        app_row,
        image=image,
        image_ref=image_ref,
        status=SubmissionStatus.COMPLETED,
        started_at=started,
        processing_ms=elapsed_ms,
        result=result.model_dump(mode="json"),
    )

    return VerificationResponse(
        submission_id=submission.id,
        application_id=app_row.id,
        status=submission.status,
        image_filename=image.filename,
        timing=TimingInfo(total_ms=elapsed_ms, ocr_ms=int(ocr_result.elapsed_ms)),
        result=result,
        image_quality=assess_image_quality(ocr_result),
    )


def _store_upload(upload_dir: str, filename: str | None, data: bytes) -> str:
    """Persist the upload bytes under ``upload_dir`` and return its path.

    Names files with a random id (keeping any original extension) so concurrent
    uploads of the same filename never collide.
    """
    directory = Path(upload_dir)
    directory.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix if filename else ""
    path = directory / f"{uuid.uuid4().hex}{suffix}"
    path.write_bytes(data)
    return str(path)


def _persist_application(db: Session, application: ApplicationInput) -> Application:
    """Insert the expected-application row the submission is checked against."""
    row = Application(**application.model_dump())
    db.add(row)
    db.flush()  # assign the PK without ending the transaction
    return row


def _persist_submission(
    db: Session,
    application: Application,
    *,
    image: UploadFile,
    image_ref: str,
    status: SubmissionStatus,
    started_at: datetime,
    processing_ms: int,
    result: dict | None = None,
    error: str | None = None,
) -> Submission:
    """Insert and commit the submission record for this verification."""
    submission = Submission(
        application=application,
        image_ref=image_ref,
        image_filename=image.filename,
        content_type=image.content_type,
        status=status,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        processing_ms=processing_ms,
        result=result,
        error=error,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission
