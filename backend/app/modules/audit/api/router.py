"""Admin-only audit log listing."""
from fastapi import APIRouter, Depends, Query

from app.modules.audit.application.service import (
    AuditPage, AuditQueryService, get_audit_query_service, register_event_subscribers,
)
from app.modules.identity.public import CurrentUser, Permission, require_permission

router = APIRouter(prefix="/api/audit", tags=["audit"])

# Importing this router (done by the app's module auto-discovery) activates audit recording.
register_event_subscribers()


@router.get("/events", response_model=AuditPage)
def list_events(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None, max_length=128, description="Action prefix, e.g. 'auth.'"),
    actor: str | None = Query(None, max_length=128),
    outcome: str | None = Query(None, pattern="^(success|failure|denied)$"),
    _user: CurrentUser = Depends(require_permission(Permission.AUDIT_READ)),
    service: AuditQueryService = Depends(get_audit_query_service),
) -> AuditPage:
    return service.list_events(limit=limit, offset=offset, action=action, actor=actor, outcome=outcome)
