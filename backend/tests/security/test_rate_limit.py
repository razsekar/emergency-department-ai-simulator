"""Rate limiter and login back-off: unit behaviour with a fake clock, and the 429 contract over HTTP."""
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.platform import ratelimit
from app.platform.audit_events import AuditEvent
from app.platform.config import get_settings
from app.platform.errors import install_error_handlers
from app.platform.events import get_event_bus
from app.platform.ratelimit import LoginBackoff, RateLimitedError, SlidingWindowLimiter, rate_limit


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture()
def settings_env(monkeypatch):
    """Set environment overrides and rebuild cached settings, restoring them afterwards."""

    def apply(**env: str) -> None:
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()

    yield apply
    monkeypatch.undo()
    get_settings.cache_clear()


# --- SlidingWindowLimiter ---------------------------------------------------------------------------

def test_limiter_allows_up_to_limit_then_rejects_with_retry_after():
    clock = Clock()
    lim = SlidingWindowLimiter(clock)
    assert [lim.hit("agent", "k", 3, 60)[0] for _ in range(3)] == [0.0, 0.0, 0.0]
    retry, first = lim.hit("agent", "k", 3, 60)
    assert retry == 60 and first is True
    clock.now += 20
    retry, first = lim.hit("agent", "k", 3, 60)
    assert retry == pytest.approx(40) and first is False  # only the first rejection per window is "first"


def test_limiter_window_slides_and_recovers():
    clock = Clock()
    lim = SlidingWindowLimiter(clock)
    for _ in range(2):
        lim.hit("b", "k", 2, 60)
    assert lim.hit("b", "k", 2, 60)[0] > 0
    clock.now += 60
    assert lim.hit("b", "k", 2, 60) == (0.0, False)


def test_limiter_buckets_and_keys_are_independent():
    lim = SlidingWindowLimiter(Clock())
    lim.hit("agent", "alice", 1, 60)
    assert lim.hit("agent", "alice", 1, 60)[0] > 0
    assert lim.hit("agent", "bob", 1, 60)[0] == 0
    assert lim.hit("chat", "alice", 1, 60)[0] == 0


def test_limiter_reset_clears_everything():
    lim = SlidingWindowLimiter(Clock())
    lim.hit("b", "k", 1, 60)
    assert lim.hit("b", "k", 1, 60)[0] > 0
    lim.reset()
    assert lim.hit("b", "k", 1, 60)[0] == 0


# --- LoginBackoff ----------------------------------------------------------------------------------

@pytest.fixture()
def backoff_settings(settings_env):
    settings_env(LOGIN_MAX_FAILURES="3", LOGIN_LOCKOUT_BASE_SECONDS="10", LOGIN_LOCKOUT_MAX_SECONDS="35",
                 LOGIN_FAILURE_WINDOW_SECONDS="100")


def test_backoff_locks_after_max_failures_and_doubles_up_to_the_cap(backoff_settings):
    clock = Clock()
    bo = LoginBackoff(clock)
    assert [bo.failed("k") for _ in range(2)] == [0, 0]
    bo.check("k")  # not locked yet
    assert bo.failed("k") == 10  # 3rd failure: base
    with pytest.raises(RateLimitedError) as exc:
        bo.check("k")
    assert exc.value.retry_after == 10 and exc.value.headers == {"Retry-After": "10"}
    clock.now += 10
    bo.check("k")  # lock expired
    assert bo.failed("k") == 20  # 4th: doubled
    clock.now += 20
    assert bo.failed("k") == 35  # 5th: 40 capped at 35
    clock.now += 35
    assert bo.failed("k") == 35


def test_backoff_check_does_not_extend_the_lock(backoff_settings):
    clock = Clock()
    bo = LoginBackoff(clock)
    for _ in range(3):
        bo.failed("k")
    for _ in range(5):
        with pytest.raises(RateLimitedError):
            bo.check("k")
    clock.now += 10
    bo.check("k")  # checks while locked did not push the expiry out


def test_backoff_success_clears_counter_and_keys_are_independent(backoff_settings):
    bo = LoginBackoff(Clock())
    bo.failed("a")
    bo.failed("a")
    bo.succeeded("a")
    assert bo.failed("a") == 0  # counting restarted
    for _ in range(3):
        bo.failed("b")
    bo.check("a")  # b's lock does not affect a
    with pytest.raises(RateLimitedError):
        bo.check("b")


def test_backoff_failures_outside_the_window_do_not_accumulate(backoff_settings):
    clock = Clock()
    bo = LoginBackoff(clock)
    bo.failed("k")
    bo.failed("k")
    clock.now += 101
    assert bo.failed("k") == 0  # window expired, counting restarted at 1


# --- rate_limit dependency over HTTP -----------------------------------------------------------------

def _app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)
    app.add_api_route("/agent", lambda: {"ok": True}, methods=["POST"], dependencies=[Depends(rate_limit("agent"))])
    app.add_api_route("/chat", lambda: {"ok": True}, methods=["POST"], dependencies=[Depends(rate_limit("chat"))])
    app.add_api_route("/upload", lambda: {"ok": True}, methods=["POST"], dependencies=[Depends(rate_limit("upload"))])
    return app


def test_http_429_uses_the_standard_error_shape_and_retry_after(settings_env):
    settings_env(RATE_LIMIT_AGENT_PER_MINUTE="2")
    client = TestClient(_app())
    assert client.post("/agent").status_code == 200
    assert client.post("/agent").status_code == 200
    r = client.post("/agent")
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"
    assert "2 per minute" in r.json()["error"]["message"]
    assert 1 <= int(r.headers["Retry-After"]) <= 60
    assert client.post("/chat").status_code == 200  # other buckets are unaffected


def test_http_limit_resets_after_reset_and_per_signed_in_user(settings_env):
    settings_env(RATE_LIMIT_UPLOAD_PER_MINUTE="1")
    client = TestClient(_app())
    alice, bob = {"Authorization": "Bearer alice-token"}, {"Authorization": "Bearer bob-token"}
    assert client.post("/upload", headers=alice).status_code == 200
    assert client.post("/upload", headers=alice).status_code == 429
    assert client.post("/upload", headers=bob).status_code == 200  # same address, different user
    ratelimit.reset_rate_limits()
    assert client.post("/upload", headers=alice).status_code == 200


def test_http_limits_can_be_disabled(settings_env):
    settings_env(RATE_LIMIT_AGENT_PER_MINUTE="1", RATE_LIMIT_CHAT_PER_MINUTE="0")
    client = TestClient(_app())
    assert all(client.post("/chat").status_code == 200 for _ in range(10))  # 0 disables a bucket
    settings_env(RATE_LIMIT_ENABLED="false")
    assert all(client.post("/agent").status_code == 200 for _ in range(10))  # master switch


def test_default_limits_do_not_block_a_live_demo(settings_env):
    """A presenter clicking through the demo (3 steps, a few retries, chat) stays far below the defaults."""
    settings_env()
    client = TestClient(_app())
    assert all(client.post("/agent").status_code == 200 for _ in range(30))
    assert client.post("/agent").status_code == 429  # but a runaway loop is still stopped


def test_rejections_publish_one_audit_event_per_window(settings_env):
    settings_env(RATE_LIMIT_AGENT_PER_MINUTE="1")
    got: list[AuditEvent] = []
    handlers = get_event_bus()._handlers[AuditEvent]
    handlers.append(got.append)
    try:
        client = TestClient(_app())
        client.post("/agent")
        for _ in range(5):
            assert client.post("/agent").status_code == 429
    finally:
        handlers.remove(got.append)
    events = [e for e in got if e.action == "ratelimit.exceeded"]
    assert len(events) == 1
    assert events[0].outcome == "denied" and events[0].resource == "/agent"
    assert events[0].detail == {"bucket": "agent", "limit_per_minute": 1}
