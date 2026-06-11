"""Audit-trail endpoint and the helper that writes audit events.

``record_event`` is called inside the same transaction as the action it
records, so the event and the state change commit (or roll back) together.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.audit import AuditEvent

router = APIRouter(prefix="/api/audit", tags=["audit"])


def record_event(
    db: Session,
    action: str,
    *,
    submission_id: int | None = None,
    detail: dict[str, Any] | None = None,
    actor: str = "reviewer",
) -> None:
    """Stage one audit row; committed with the caller's transaction."""
    db.add(AuditEvent(action=action, actor=actor, submission_id=submission_id, detail=detail))


class AuditEventRow(BaseModel):
    """One audit-log entry as returned by the API."""

    id: int
    created_at: datetime | None
    action: str
    actor: str
    submission_id: int | None
    detail: dict[str, Any] | None


@router.get("", response_model=list[AuditEventRow])
def list_events(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    submission_id: Annotated[int | None, Query()] = None,
) -> list[AuditEventRow]:
    """Newest-first audit trail, optionally scoped to one submission."""
    stmt = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
    if submission_id is not None:
        stmt = stmt.where(AuditEvent.submission_id == submission_id)
    return [
        AuditEventRow(
            id=e.id,
            created_at=e.created_at,
            action=e.action,
            actor=e.actor,
            submission_id=e.submission_id,
            detail=e.detail,
        )
        for e in db.scalars(stmt)
    ]
