"""Label verification endpoint.

``POST /api/verify`` accepts a filing's label image set (repeated ``images``
multipart parts — front, back, neck — or a single ``image`` for older clients)
plus the expected COLA fields, runs the production hot path — preprocess ->
OCR -> extract -> verify, merged per field across the set — persists a
:class:`app.models.submission.Submission` (and the
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

from app.api.audit import record_event
from app.api.schemas import (
    ApplicationInput,
    TimingInfo,
    VerificationImageInfo,
    VerificationResponse,
)
from app.config import Settings, get_settings
from app.db import get_db
from app.models.application import Application
from app.models.enums import ProductSource, ProductType, SubmissionStatus
from app.models.submission import Submission
from app.models.submission_image import SubmissionImage
from app.ocr import OcrService, get_ocr_service
from app.ocr.preprocess import decode_image
from app.ocr.quality import assess_image_quality
from app.verify import verify_label_images

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


# Upper bound on label images per verification: a COLA's attachments rarely
# exceed front/back/neck/strip; the cap bounds worst-case OCR cost.
MAX_IMAGES = 6


@router.post("/verify", response_model=VerificationResponse)
def verify(
    application: Annotated[ApplicationInput, Depends(_application_input)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    ocr: Annotated[OcrService, Depends(get_ocr_service)],
    image: Annotated[
        UploadFile | None, File(description="A single label image (older clients).")
    ] = None,
    images: Annotated[
        list[UploadFile] | None,
        File(description="The filing's label images in order (front, back, …)."),
    ] = None,
) -> VerificationResponse:
    """Verify a filing's label image set against its expected application data.

    Accepts the full set of label images a COLA carries (repeated ``images``
    parts) — the mandatory content is split across them (warning on the back,
    ABV on the front) — or a single ``image`` for older clients. Fields merge
    on best verdict across the set; the result records which image each
    verdict came from.
    """
    uploads = ([image] if image is not None else []) + list(images or [])
    if not uploads:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No label image was uploaded."
        )
    if len(uploads) > MAX_IMAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"At most {MAX_IMAGES} label images per verification.",
        )

    datas: list[bytes] = []
    for position, upload in enumerate(uploads):
        data = upload.file.read()
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image {position + 1} is an empty upload.",
            )
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"Image {position + 1} exceeds the "
                    f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit."
                ),
            )
        # Validate decodability before doing anything expensive, so a bad
        # upload is a clean 422 rather than an OCR-time crash.
        try:
            decode_image(data)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Image {position + 1} is not a readable image file.",
            ) from exc
        datas.append(data)

    image_refs = [
        _store_upload(settings.upload_dir, upload.filename, data)
        for upload, data in zip(uploads, datas, strict=True)
    ]
    app_row = _persist_application(db, application)

    started = datetime.now(UTC)
    start = time.perf_counter()
    # The adaptive pipeline per image (one OCR pass for clean labels, with
    # conditional rotation/zoom rescue passes), merged on best verdict per
    # field across the filing's label set.
    result, reads = verify_label_images(application, datas, ocr=ocr)

    if all(not read.lines for read in reads):
        # Decodable but no text recovered anywhere: treat as unreadable rather
        # than silently returning an all-mismatch verdict on blank images.
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        _persist_submission(
            db,
            app_row,
            uploads=uploads,
            image_refs=image_refs,
            status=SubmissionStatus.FAILED,
            started_at=started,
            processing_ms=elapsed_ms,
            error="No text could be recognised in the uploaded image(s).",
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No text could be recognised in the uploaded image(s).",
        )

    elapsed_ms = int((time.perf_counter() - start) * 1000)

    submission = _persist_submission(
        db,
        app_row,
        uploads=uploads,
        image_refs=image_refs,
        status=SubmissionStatus.COMPLETED,
        started_at=started,
        processing_ms=elapsed_ms,
        result=result.model_dump(mode="json"),
    )

    qualities = [assess_image_quality(read) for read in reads]
    # Retake guidance keys off the least readable image: a blurry back label
    # warrants a retake even when the front read fine.
    worst = min(qualities, key=lambda q: (q.level != "low", q.mean_confidence))
    return VerificationResponse(
        submission_id=submission.id,
        application_id=app_row.id,
        status=submission.status,
        image_filename=uploads[0].filename,
        images=[
            VerificationImageInfo(index=i, filename=upload.filename, quality=quality)
            for i, (upload, quality) in enumerate(zip(uploads, qualities, strict=True))
        ],
        timing=TimingInfo(total_ms=elapsed_ms, ocr_ms=int(sum(read.elapsed_ms for read in reads))),
        result=result,
        image_quality=worst,
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
    uploads: list[UploadFile],
    image_refs: list[str],
    status: SubmissionStatus,
    started_at: datetime,
    processing_ms: int,
    result: dict | None = None,
    error: str | None = None,
) -> Submission:
    """Insert and commit the submission record for this verification.

    The submission's legacy image columns mirror the first image; the full
    label set is stored as ordered :class:`SubmissionImage` rows, which is what
    the result's ``image_index`` values refer to.
    """
    submission = Submission(
        application=application,
        image_ref=image_refs[0],
        image_filename=uploads[0].filename,
        content_type=uploads[0].content_type,
        status=status,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        processing_ms=processing_ms,
        result=result,
        error=error,
        images=[
            SubmissionImage(
                position=position,
                image_ref=ref,
                image_filename=upload.filename,
                content_type=upload.content_type,
            )
            for position, (upload, ref) in enumerate(zip(uploads, image_refs, strict=True))
        ],
    )
    db.add(submission)
    db.flush()  # assign the submission id so the audit row can reference it
    record_event(
        db,
        f"verification.{status.value.lower()}",
        submission_id=submission.id,
        detail={
            "brand_name": application.brand_name,
            "image_filename": uploads[0].filename,
            "image_count": len(uploads),
            "processing_ms": processing_ms,
            "overall": (result or {}).get("overall"),
            "error": error,
        },
    )
    db.commit()
    db.refresh(submission)
    return submission
