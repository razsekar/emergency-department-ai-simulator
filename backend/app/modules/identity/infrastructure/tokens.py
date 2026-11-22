"""Signed bearer tokens (HS256 JWT via PyJWT)."""
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.modules.identity.domain.errors import AuthenticationError
from app.modules.identity.infrastructure.settings import IdentitySettings

ISSUER = "ed-simulator"
ALGORITHM = "HS256"


def issue_token(
    user_id: str, username: str, settings: IdentitySettings, now: datetime | None = None
) -> tuple[str, int]:
    """Return (token, expires_in_seconds). Claims carry identity only; permissions come from the DB."""
    secret = settings.require_signing_secret()
    issued = now or datetime.now(timezone.utc)
    ttl = timedelta(minutes=settings.jwt_ttl_minutes)
    claims = {"sub": user_id, "username": username, "iss": ISSUER, "iat": issued, "exp": issued + ttl}
    return jwt.encode(claims, secret, algorithm=ALGORITHM), int(ttl.total_seconds())


def decode_token(token: str, settings: IdentitySettings) -> dict[str, Any]:
    secret = settings.require_signing_secret()
    try:
        return jwt.decode(
            token, secret, algorithms=[ALGORITHM], issuer=ISSUER,
            options={"require": ["exp", "sub", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid or expired token") from exc
