"""Tests for batch ingestion: manifest+images pairing and persistence."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.batch import ingest_batch
from app.batch.manifest import ManifestError
from app.models import Application, Batch, BatchItem, BatchStatus, Submission, SubmissionStatus

HEADER = "image_filename,brand_name,alcohol_content_pct"


def _refs(*filenames: str) -> dict[str, str]:
    """Map each filename to a stand-in stored reference."""
    return {name: f"/uploads/{name}" for name in filenames}


def test_clean_manifest_persists_pending_batch(db_session: Session) -> None:
    csv = f"{HEADER}\na.png,Alpha,40\nb.png,Beta,12\n"
    result = ingest_batch(
        db_session,
        manifest_csv=csv,
        image_refs=_refs("a.png", "b.png"),
        name="Acme Importers",
    )

    assert result.ok
    assert result.total_rows == 2
    assert result.paired == 2
    assert result.row_errors == []
    assert result.missing_files == []
    assert result.extra_files == []
    assert result.batch_id is not None

    batch = db_session.scalar(select(Batch).where(Batch.id == result.batch_id))
    assert batch is not None
    assert batch.name == "Acme Importers"
    assert batch.status is BatchStatus.PENDING

    # Items are ordered by manifest position and each is a PENDING submission.
    assert [item.position for item in batch.items] == [0, 1]
    submissions = [item.submission for item in batch.items]
    assert [s.image_filename for s in submissions] == ["a.png", "b.png"]
    assert [s.image_ref for s in submissions] == ["/uploads/a.png", "/uploads/b.png"]
    assert all(s.status is SubmissionStatus.PENDING for s in submissions)
    assert all(s.result is None for s in submissions)

    # Each submission carries its expected application from the manifest.
    assert submissions[0].application is not None
    assert submissions[0].application.brand_name == "Alpha"
    assert float(submissions[1].application.alcohol_content_pct) == 12.0


def test_content_types_are_recorded_when_supplied(db_session: Session) -> None:
    csv = f"{HEADER}\na.png,Alpha,40\n"
    result = ingest_batch(
        db_session,
        manifest_csv=csv,
        image_refs=_refs("a.png"),
        content_types={"a.png": "image/png"},
    )
    batch = db_session.scalar(select(Batch).where(Batch.id == result.batch_id))
    assert batch is not None
    assert batch.items[0].submission.content_type == "image/png"


def test_missing_file_is_reported_and_row_not_paired(db_session: Session) -> None:
    csv = f"{HEADER}\na.png,Alpha,40\nb.png,Beta,12\n"
    # Only a.png was uploaded; b.png is referenced but missing.
    result = ingest_batch(db_session, manifest_csv=csv, image_refs=_refs("a.png"))

    assert not result.ok
    assert result.paired == 1
    assert result.missing_files == ["b.png"]
    assert len(result.row_errors) == 1
    err = result.row_errors[0]
    assert err.row_number == 2
    assert err.image_filename == "b.png"
    assert any("not included" in m for m in err.messages)

    # Batch persisted with only the paired row.
    batch = db_session.scalar(select(Batch).where(Batch.id == result.batch_id))
    assert batch is not None
    assert [item.submission.image_filename for item in batch.items] == ["a.png"]


def test_extra_uploaded_file_is_reported(db_session: Session) -> None:
    csv = f"{HEADER}\na.png,Alpha,40\n"
    # b.png and c.png uploaded but never referenced.
    result = ingest_batch(db_session, manifest_csv=csv, image_refs=_refs("a.png", "c.png", "b.png"))

    assert not result.ok  # extra files make it not fully clean
    assert result.paired == 1
    assert result.extra_files == ["b.png", "c.png"]  # sorted
    assert result.row_errors == []
    assert result.batch_id is not None  # still persisted; manifest is source of truth


def test_duplicate_filename_references_reject_both_rows(db_session: Session) -> None:
    csv = f"{HEADER}\ndup.png,Alpha,40\ndup.png,Beta,12\n"
    result = ingest_batch(db_session, manifest_csv=csv, image_refs=_refs("dup.png"))

    assert result.paired == 0
    assert result.batch_id is None  # nothing valid to persist
    assert len(result.row_errors) == 2
    assert all("more than one row" in m for err in result.row_errors for m in err.messages)
    # dup.png was referenced, so it is not reported as an extra file.
    assert result.extra_files == []


def test_bad_row_is_skipped_but_good_rows_still_persist(db_session: Session) -> None:
    csv = f"{HEADER}\na.png,Alpha,40\nb.png,,12\nc.png,Gamma,200\n"
    result = ingest_batch(db_session, manifest_csv=csv, image_refs=_refs("a.png", "b.png", "c.png"))

    assert result.total_rows == 3
    assert result.paired == 1  # only row 1 is clean
    assert {err.row_number for err in result.row_errors} == {2, 3}

    batch = db_session.scalar(select(Batch).where(Batch.id == result.batch_id))
    assert batch is not None
    assert [item.submission.image_filename for item in batch.items] == ["a.png"]


def test_no_valid_rows_persists_nothing(db_session: Session) -> None:
    csv = f"{HEADER}\nmissing.png,Alpha,40\n"
    result = ingest_batch(db_session, manifest_csv=csv, image_refs={})

    assert result.paired == 0
    assert result.batch_id is None
    assert result.missing_files == ["missing.png"]
    # No batch / item / application / submission rows were written.
    assert db_session.scalar(select(Batch)) is None
    assert db_session.scalar(select(BatchItem)) is None
    assert db_session.scalar(select(Submission)) is None
    assert db_session.scalar(select(Application)) is None


def test_malformed_manifest_raises(db_session: Session) -> None:
    with pytest.raises(ManifestError):
        ingest_batch(db_session, manifest_csv="not_the_right_columns\nx\n", image_refs={})
