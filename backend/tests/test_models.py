"""Tests for the core ORM models and their relationships."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Application,
    Batch,
    BatchItem,
    BatchStatus,
    ProductSource,
    ProductType,
    Submission,
    SubmissionStatus,
)


def _make_application(**overrides: object) -> Application:
    defaults: dict[str, object] = {
        "source": ProductSource.DOMESTIC,
        "product_type": ProductType.DISTILLED_SPIRITS,
        "brand_name": "OLD TOM DISTILLERY",
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "alcohol_content_pct": 45.0,
        "alcohol_content_text": "45% Alc./Vol. (90 Proof)",
        "net_contents": "750 mL",
    }
    defaults.update(overrides)
    return Application(**defaults)


def test_application_persists_with_timestamps(db_session: Session) -> None:
    app = _make_application(serial_number="24-001")
    db_session.add(app)
    db_session.commit()

    fetched = db_session.scalar(select(Application).where(Application.id == app.id))
    assert fetched is not None
    assert fetched.brand_name == "OLD TOM DISTILLERY"
    assert fetched.source is ProductSource.DOMESTIC
    assert fetched.product_type is ProductType.DISTILLED_SPIRITS
    # Server-side defaults populate the audit columns.
    assert fetched.created_at is not None
    assert fetched.updated_at is not None


def test_submission_links_to_application_and_stores_result_json(db_session: Session) -> None:
    app = _make_application()
    submission = Submission(
        application=app,
        image_ref="/data/labels/old-tom.png",
        image_filename="old-tom.png",
        content_type="image/png",
        status=SubmissionStatus.COMPLETED,
        started_at=datetime(2026, 6, 10, 12, 0, tzinfo=UTC),
        completed_at=datetime(2026, 6, 10, 12, 0, 3, tzinfo=UTC),
        processing_ms=3000,
        result={
            "overall": "pass",
            "fields": {"brand_name": {"expected": "OLD TOM DISTILLERY", "match": True}},
        },
    )
    db_session.add(submission)
    db_session.commit()

    fetched = db_session.scalar(select(Submission).where(Submission.id == submission.id))
    assert fetched is not None
    assert fetched.application_id == app.id
    assert fetched.result["overall"] == "pass"
    assert fetched.result["fields"]["brand_name"]["match"] is True
    assert app.submissions == [fetched]


def test_submission_status_defaults_to_pending(db_session: Session) -> None:
    submission = Submission(image_ref="/data/labels/x.png")
    db_session.add(submission)
    db_session.commit()
    assert submission.status is SubmissionStatus.PENDING


def test_batch_orders_items_and_cascades(db_session: Session) -> None:
    batch = Batch(name="Acme Importers — peak season", status=BatchStatus.PENDING)
    for i in range(3):
        sub = Submission(image_ref=f"/data/labels/{i}.png")
        batch.items.append(BatchItem(submission=sub, position=i))
    db_session.add(batch)
    db_session.commit()

    fetched = db_session.scalar(select(Batch).where(Batch.id == batch.id))
    assert fetched is not None
    assert [item.position for item in fetched.items] == [0, 1, 2]

    submission_ids = [item.submission_id for item in fetched.items]

    # Deleting the batch cascades to its join rows but keeps the submissions,
    # which are durable verification records.
    db_session.delete(fetched)
    db_session.commit()
    assert db_session.scalar(select(BatchItem)) is None
    remaining = db_session.scalars(
        select(Submission).where(Submission.id.in_(submission_ids))
    ).all()
    assert len(remaining) == 3


def test_deleting_submission_removes_its_batch_item(db_session: Session) -> None:
    batch = Batch()
    submission = Submission(image_ref="/data/labels/x.png")
    batch.items.append(BatchItem(submission=submission, position=0))
    db_session.add(batch)
    db_session.commit()

    db_session.delete(submission)
    db_session.commit()
    assert db_session.scalar(select(BatchItem)) is None


def test_batch_position_must_be_unique(db_session: Session) -> None:
    batch = Batch()
    batch.items.append(BatchItem(submission=Submission(image_ref="/a.png"), position=0))
    batch.items.append(BatchItem(submission=Submission(image_ref="/b.png"), position=0))
    db_session.add(batch)
    with pytest.raises(IntegrityError):
        db_session.commit()
