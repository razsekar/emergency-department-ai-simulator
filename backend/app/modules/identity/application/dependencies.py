"""FastAPI dependencies that enforce authentication and RBAC server-side."""
from collections.abc import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.modules.identity.application.contracts import CurrentUser
from app.modules.identity.application.service import AuthService
from app.modules.identity.domain.errors import AuthenticationError, PermissionDeniedError
from app.platform.audit_events import AuditEvent
from app.platform.db import get_session
from app.platform.events import get_event_bus

_bearer = HTTPBearer(auto_error=False, description="Token from POST /api/auth/login")


def get_auth_service(session: Session = Depends(get_session)) -> AuthService:
    return AuthService(session)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    service: AuthService = Depends(get_auth_service),
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Authentication required")
    return service.authenticate_token(credentials.credentials)


def require_permission(*codes: str) -> Callable[..., CurrentUser]:
    """Dependency factory: `Depends(require_permission("scenario:apply"))`. All codes are required."""
    required = tuple(str(c) for c in codes)

    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        missing = [c for c in required if not user.has_permission(c)]
        if missing:
            get_event_bus().publish(
                AuditEvent(actor=user.username, action="authz.denied", outcome="denied",
                           detail={"missing_permissions": missing})
            )
            raise PermissionDeniedError("Insufficient permissions")
        return user

    return dependency
