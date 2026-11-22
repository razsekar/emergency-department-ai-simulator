"""Authentication use cases."""
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.identity.application.contracts import CurrentUser, LoginResult
from app.modules.identity.domain.errors import AuthenticationError
from app.modules.identity.domain.passwords import DUMMY_HASH, verify_password
from app.modules.identity.infrastructure.repository import IdentityRepository
from app.modules.identity.infrastructure.settings import IdentitySettings
from app.modules.identity.infrastructure.tokens import decode_token, issue_token
from app.platform.audit_events import AuditEvent
from app.platform.events import get_event_bus


class AuthService:
    def __init__(self, session: Session) -> None:
        self._repo = IdentityRepository(session)

    def login(self, username: str, password: str) -> LoginResult:
        settings = IdentitySettings()
        settings.require_signing_secret()  # fail closed if auth isn't configured
        user = self._repo.find_user_by_username(username.strip())
        # Always run one password verification so timing doesn't reveal whether a username exists.
        password_ok = verify_password(password, user.password_hash if user else DUMMY_HASH)
        if user is None or not password_ok or not user.is_active:
            reason = "unknown_user" if user is None else "inactive" if not user.is_active else "bad_password"
            get_event_bus().publish(
                AuditEvent(actor=username.strip()[:64] or "anonymous", action="auth.login",
                           outcome="failure", detail={"reason": reason})
            )
            raise AuthenticationError("Invalid username or password")
        current = self._build_current_user(user.id)
        token, expires_in = issue_token(str(user.id), user.username, settings)
        get_event_bus().publish(AuditEvent(actor=user.username, action="auth.login", outcome="success"))
        return LoginResult(access_token=token, expires_in=expires_in, user=current)

    def authenticate_token(self, token: str) -> CurrentUser:
        claims = decode_token(token, IdentitySettings())
        try:
            user_id = UUID(str(claims["sub"]))
        except ValueError as exc:
            raise AuthenticationError("Invalid or expired token") from exc
        row = self._repo.get_user(user_id)
        if row is None or not row.is_active:
            raise AuthenticationError("Invalid or expired token")
        return self._build_current_user(user_id)

    def _build_current_user(self, user_id: UUID) -> CurrentUser:
        row = self._repo.get_user(user_id)
        assert row is not None
        return CurrentUser(
            id=row.id,
            username=row.username,
            display_name=row.display_name,
            roles=tuple(self._repo.role_names(user_id)),
            permissions=frozenset(self._repo.permission_codes(user_id)),
        )
