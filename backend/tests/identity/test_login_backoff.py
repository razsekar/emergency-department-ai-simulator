"""Login back-off over HTTP (defaults: 5 failures, then 15 s doubling up to 300 s)."""
import pytest

from app.platform.ratelimit import get_login_backoff
from tests.identity.conftest import PASSWORDS, auth_headers, login


class Clock:
    now = 5000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture()
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(get_login_backoff(), "_clock", c)
    return c


def _fail(client, username="demo_viewer", times=5):
    for _ in range(times):
        assert login(client, username, "wrong-password").status_code == 401


def test_five_failures_lock_the_user_even_for_the_correct_password(client, clock):
    _fail(client)
    r = login(client, "demo_viewer")  # correct password, but locked out
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"
    assert int(r.headers["Retry-After"]) == 15
    assert "password" not in r.text.lower().replace("sign-in", "")  # no hint about which part was wrong


def test_lock_expires_and_a_correct_password_then_works(client, clock):
    _fail(client)
    assert login(client, "demo_viewer").status_code == 429
    clock.now += 15
    assert login(client, "demo_viewer").status_code == 200


def test_repeated_lockouts_back_off_exponentially(client, clock):
    _fail(client)
    clock.now += 15
    assert login(client, "demo_viewer", "wrong-password").status_code == 401  # 6th failure: 30 s lock
    r = login(client, "demo_viewer")
    assert r.status_code == 429 and int(r.headers["Retry-After"]) == 30


def test_four_failures_then_success_does_not_lock_and_resets_the_counter(client, clock):
    _fail(client, times=4)
    assert login(client, "demo_viewer").status_code == 200
    _fail(client, times=4)  # counter restarted, so 4 more failures still do not lock
    assert login(client, "demo_viewer").status_code == 200


def test_other_users_are_not_locked_out(client, clock):
    _fail(client, "demo_viewer")
    assert login(client, "demo_viewer").status_code == 429
    assert login(client, "demo_presenter").status_code == 200
    assert login(client, "demo_admin").status_code == 200


def test_unknown_usernames_are_throttled_too(client, clock):
    """Back-off applies to usernames that do not exist, so it cannot be used to probe for valid ones."""
    for _ in range(5):
        assert login(client, "no_such_user", "x").status_code == 401
    assert login(client, "no_such_user", "x").status_code == 429


def test_lockout_is_audited_and_visible_to_admin(client, clock):
    _fail(client)
    events = client.get("/api/audit/events", params={"action": "auth.lockout"},
                        headers=auth_headers(client, "demo_admin")).json()
    items = events["items"]
    assert len(items) == 1
    assert items[0]["actor"] == "demo_viewer" and items[0]["outcome"] == "denied"
    assert items[0]["detail"]["lockout_seconds"] == 15
    assert PASSWORDS["demo_viewer"] not in str(events)
