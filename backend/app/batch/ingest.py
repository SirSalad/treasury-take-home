"""Pair a parsed manifest against an uploaded image set and persist the batch.

The pairing key is the image filename. Three failure modes are reported rather
than guessed at, because each needs the agent to fix the *upload*, not the data:

* **Missing file** — a valid row names an image that was not uploaded.
* **Extra file** — an uploaded image that no row references.
* **Duplicate reference** — two rows naming the same image (ambiguous pairing);
  both rows are rejected so the agent dedups rather than us picking one.

Valid, unambiguously paired rows become a :class:`app.models.batch.Batch` of
``PENDING`` submissions (each with its expected :class:`app.models.application.Application`),
ordered by manifest position — ready for the processing queue.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping

from sqlalchemy.orm import Session

from app.batch.manifest import ParsedRow, parse_manifest
from app.batch.schemas import BatchIngestResult, RowError
from app.models import (
    Application,
    Batch,
    BatchItem,
    BatchStatus,
    Submission,
    SubmissionStatus,
)


def ingest_batch(
    db: Session,
    *,
    manifest_csv: str | bytes,
    image_refs: Mapping[str, str],
    content_types: Mapping[str, str | None] | None = None,
    name: str | None = None,
) -> BatchIngestResult:
    """Pair ``manifest_csv`` rows against ``image_refs`` and persist a batch.

    ``image_refs`` maps each uploaded image's filename to its stored reference
    (path/key) — its keys are the available image set. ``content_types`` is an
    optional parallel map of filename -> MIME type. A :class:`Batch` is committed
    when at least one row pairs cleanly; otherwise nothing is persisted. Either
    way the returned :class:`BatchIngestResult` accounts for every row and file.

    Raises :class:`app.batch.manifest.ManifestError` if the manifest is
    structurally malformed (see :func:`app.batch.manifest.parse_manifest`).
    """
    rows = parse_manifest(manifest_csv)
    content_types = content_types or {}
    available = set(image_refs)

    # Filenames named by more than one row: pairing would be ambiguous.
    referenced = [row.image_filename for row in rows if row.image_filename]
    duplicates = {name_ for name_, count in Counter(referenced).items() if count > 1}

    row_errors: list[RowError] = []
    paired: list[ParsedRow] = []
    missing_files: list[str] = []

    for row in rows:
        errors = list(row.errors)
        filename = row.image_filename
        if filename:
            if filename in duplicates:
                errors.append(f"Image '{filename}' is referenced by more than one row.")
            elif filename not in available:
                errors.append(f"Image '{filename}' was not included in the upload.")
                missing_files.append(filename)

        if errors:
            row_errors.append(
                RowError(row_number=row.row_number, image_filename=filename, messages=errors)
            )
        else:
            paired.append(row)

    extra_files = sorted(available - set(referenced))

    batch_id = _persist_batch(db, paired, image_refs, content_types, name) if paired else None

    return BatchIngestResult(
        batch_id=batch_id,
        total_rows=len(rows),
        paired=len(paired),
        row_errors=row_errors,
        missing_files=sorted(set(missing_files)),
        extra_files=extra_files,
    )


def _persist_batch(
    db: Session,
    paired: list[ParsedRow],
    image_refs: Mapping[str, str],
    content_types: Mapping[str, str | None],
    name: str | None,
) -> int:
    """Persist a PENDING batch with one item per paired row; return its id."""
    batch = Batch(name=name, status=BatchStatus.PENDING)
    for position, row in enumerate(paired):
        # paired rows always have a validated application and a present filename.
        assert row.application is not None and row.image_filename is not None
        submission = Submission(
            application=Application(**row.application.model_dump()),
            image_ref=image_refs[row.image_filename],
            image_filename=row.image_filename,
            content_type=content_types.get(row.image_filename),
            status=SubmissionStatus.PENDING,
        )
        batch.items.append(BatchItem(submission=submission, position=position))

    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch.id
