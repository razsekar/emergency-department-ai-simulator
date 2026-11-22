"""Audit use cases: recording (own transaction) and querying."""
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.modules.audit.domain.redaction import redact
from app.modules.audit.infrastructure.repository import AuditRepository
from app.platform import db as platform_db
from app.platform.audit_events import AuditEvent
from app.platform.db import get_session
from app.platform.events import get_event_bus

log = logging.getLogger("app.audit")
_registered = False


class AuditRecord(BaseModel):
    id: UUID
    occurred_at: datetime
    actor: str
    action: str
    resource: str | None
    outcome: str
    detail: dict[str, Any]


class AuditPage(BaseModel):
    items: list[AuditRecord]
    total: int
    limit: int
    offset: int


def record(event: AuditEvent) -> None:
    """Persist an audit event in its OWN transaction, so it survives a rolled-back request.

    Failures are logged, never raised: auditing must not take the request path down.
    """
    try:
        with platform_db.unit_of_work() as session:
            AuditRepository(session).add_event(
                occurred_at=event.occurred_at,
                actor=event.actor[:128],
                action=event.action[:128],
                resource=event.resource[:255] if event.resource else None,
                outcome=event.outcome,
                detail=redact(event.detail),
            )
    except Exception:
        log.exception("Failed to persist audit event action=%s actor=%s", event.action, event.actor)


def register_event_subscribers() -> None:
    """Idempotently subscribe `record` to AuditEvent on the in-process bus."""
    global _registered
    if not _registered:
        get_event_bus().subscribe(AuditEvent, record)
        _registered = True


class AuditQueryService:
    def __init__(self, session: Session) -> None:
        self._repo = AuditRepository(session)

    def list_events(
        self, *, limit: int, offset: int, action: str | None = None,
        actor: str | None = None, outcome: str | None = None,
    ) -> AuditPage:
        rows, total = self._repo.list_events(
            limit=limit, offset=offset, action=action, actor=actor, outcome=outcome
        )
        items = [
            AuditRecord(id=r.id, occurred_at=r.occurred_at, actor=r.actor, action=r.action,
                        resource=r.resource, outcome=r.outcome, detail=r.detail or {})
            for r in rows
        ]
        return AuditPage(items=items, total=total, limit=limit, offset=offset)


def get_audit_query_service(session: Session = Depends(get_session)) -> AuditQueryService:
    return AuditQueryService(session)
