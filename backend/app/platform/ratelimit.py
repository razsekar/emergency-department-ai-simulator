"""Small in-process rate limiting and login back-off (shared kernel; no business logic).

State lives in this process's memory, which matches the single-process deployment (see DEPLOYMENT.md).
Behind a reverse proxy every request shares the proxy's address, so the client key combines the
peer address with a hash of the Authorization header: different signed-in users get separate
buckets. X-Forwarded-For is deliberately NOT trusted (clients can forge it).
"""
import hashlib
import math
import threading
import time
from collections import deque
from collections.abc import Callable

from fastapi import Request

from app.platform.audit_events import AuditEvent
from app.platform.config import get_settings
from app.platform.errors import AppError
from app.platform.events import get_event_bus


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, message: str, retry_after: float) -> None:
        super().__init__(message)
        self.retry_after = max(1, math.ceil(retry_after))
        self.headers = {"Retry-After": str(self.retry_after)}


class SlidingWindowLimiter:
    """At most `limit` hits per `window` seconds for each (bucket, key)."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._rejected_at: dict[tuple[str, str], float] = {}

    def hit(self, bucket: str, key: str, limit: int, window: float) -> tuple[float, bool]:
        """Record a hit. Returns (retry_after_seconds, first_rejection); retry_after is 0 when allowed."""
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault((bucket, key), deque())
            while hits and now - hits[0] >= window:
                hits.popleft()
            if len(hits) < limit:
                hits.append(now)
                return 0.0, False
            last = self._rejected_at.get((bucket, key))
            first = last is None or now - last >= window
            if first:
                self._rejected_at[(bucket, key)] = now
            return window - (now - hits[0]), first

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
            self._rejected_at.clear()


class LoginBackoff:
    """Exponential lock-out after repeated login failures for one (client, username) key."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._state: dict[str, list[float]] = {}  # key -> [failures, last_failure_at, locked_until]

    def check(self, key: str) -> None:
        """Raise RateLimitedError while the key is locked out. Does not extend the lock-out."""
        now = self._clock()
        with self._lock:
            state = self._state.get(key)
            if state and state[2] > now:
                raise RateLimitedError("Too many failed sign-in attempts. Try again later.", state[2] - now)

    def failed(self, key: str) -> float:
        """Record a failure. Returns the new lock-out in seconds (0 if none was started)."""
        s = get_settings()
        now = self._clock()
        with self._lock:
            state = self._state.get(key)
            if state is None or now - state[1] > s.login_failure_window_seconds:
                state = [0.0, now, 0.0]
            state[0] += 1
            state[1] = now
            lockout = 0.0
            if state[0] >= s.login_max_failures:
                lockout = min(s.login_lockout_base_seconds * 2 ** (state[0] - s.login_max_failures),
                              s.login_lockout_max_seconds)
                state[2] = now + lockout
            self._state[key] = state
            return lockout

    def succeeded(self, key: str) -> None:
        with self._lock:
            self._state.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._state.clear()


_limiter = SlidingWindowLimiter()
_login_backoff = LoginBackoff()


def get_login_backoff() -> LoginBackoff:
    return _login_backoff


def reset_rate_limits() -> None:
    """Clear all limiter state (used by tests and by an operator restart-free reset)."""
    _limiter.reset()
    _login_backoff.reset()


def client_key(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    auth = request.headers.get("authorization")
    token = hashlib.sha256(auth.encode()).hexdigest()[:16] if auth else "anon"
    return f"{peer}:{token}"


_LIMIT_SETTINGS = {
    "agent": "rate_limit_agent_per_minute",
    "chat": "rate_limit_chat_per_minute",
    "upload": "rate_limit_upload_per_minute",
}


def rate_limit(bucket: str) -> Callable[[Request], None]:
    """FastAPI dependency factory: `dependencies=[Depends(rate_limit("agent"))]`.

    The limit is read from settings on every call, so configuration changes apply without
    rebuilding the router. Rejections return 429 with Retry-After in the standard error shape and
    publish one audit event per client per window (so a flood cannot flood the audit log).
    """
    setting = _LIMIT_SETTINGS[bucket]

    def dependency(request: Request) -> None:
        s = get_settings()
        limit = getattr(s, setting)
        if not s.rate_limit_enabled or limit <= 0:
            return
        key = client_key(request)
        retry_after, first = _limiter.hit(bucket, key, limit, 60.0)
        if retry_after > 0:
            if first:
                get_event_bus().publish(AuditEvent(
                    actor=f"client:{key}", action="ratelimit.exceeded", outcome="denied",
                    resource=request.url.path, detail={"bucket": bucket, "limit_per_minute": limit},
                ))
            raise RateLimitedError(
                f"Rate limit reached for this action ({limit} per minute). Please wait and retry.", retry_after
            )

    return dependency
