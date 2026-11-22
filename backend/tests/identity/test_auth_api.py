from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import text

from app.modules.identity.infrastructure.settings import IdentitySettings
from app.modules.identity.infrastructure.tokens import issue_token
from tests.identity.conftest import JWT_SECRET, PASSWORDS, auth_headers, login


def test_login_success_returns_token_and_user(client):
    r = login(client, "demo_presenter")
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 3600
    assert body["user"]["username"] == "demo_presenter"
    assert body["user"]["roles"] == ["presenter"]
    assert "scenario:apply" in body["user"]["permissions"]
    assert "audit:read" not in body["user"]["permissions"]


def test_login_failures_are_indistinguishable(client):
    bad_pw = login(client, "demo_admin", "wrong-password")
    unknown = login(client, "no_such_user", "whatever")
    assert bad_pw.status_code == unknown.status_code == 401
    assert bad_pw.json() == unknown.json()
    assert bad_pw.json()["error"]["message"] == "Invalid username or password"


def test_inactive_user_cannot_login(client, ident_engine):
    with ident_engine.begin() as c:
        c.execute(text("UPDATE identity.users SET is_active = false WHERE username = 'demo_viewer'"))
    assert login(client, "demo_viewer").status_code == 401


def test_login_validation_errors(client):
    assert client.post("/api/auth/login", json={"username": "", "password": "x"}).status_code == 422
    assert client.post("/api/auth/login", json={}).status_code == 422


def test_me_with_valid_token(client):
    r = client.get("/api/auth/me", headers=auth_headers(client, "demo_viewer"))
    assert r.status_code == 200 and r.json()["username"] == "demo_viewer"


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Basic abc"}).status_code == 401


def test_tampered_and_foreign_tokens_rejected(client):
    token = login(client, "demo_admin").json()["access_token"]
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered}"}).status_code == 401
    foreign = jwt.encode({"sub": "x", "iss": "ed-simulator", "exp": datetime.now(timezone.utc)
                          + timedelta(hours=1)}, "another-secret-" + "y" * 40, algorithm="HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {foreign}"}).status_code == 401
    unsigned = jwt.encode({"sub": "x", "iss": "ed-simulator"}, key=None, algorithm="none")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {unsigned}"}).status_code == 401


def test_expired_token_rejected(client, ident_engine):
    with ident_engine.connect() as c:
        uid = c.execute(text("SELECT id FROM identity.users WHERE username='demo_admin'")).scalar_one()
    past = datetime.now(timezone.utc) - timedelta(hours=3)
    token, _ = issue_token(str(uid), "demo_admin", IdentitySettings(), now=past)
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_token_for_deactivated_user_rejected(client, ident_engine):
    headers = auth_headers(client, "demo_presenter")
    with ident_engine.begin() as c:
        c.execute(text("UPDATE identity.users SET is_active=false WHERE username='demo_presenter'"))
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_role_change_takes_effect_without_new_token(client, ident_engine):
    headers = auth_headers(client, "demo_presenter")
    assert client.get("/_perm/scenario-apply", headers=headers).status_code == 200
    with ident_engine.begin() as c:
        c.execute(text("DELETE FROM identity.user_roles WHERE user_id = "
                       "(SELECT id FROM identity.users WHERE username='demo_presenter')"))
    assert client.get("/_perm/scenario-apply", headers=headers).status_code == 403


def test_unconfigured_secret_fails_closed_with_safe_message(client, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "too-short")
    r = login(client, "demo_admin")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "auth_not_configured"
    assert "too-short" not in r.text


def test_secrets_never_returned(client):
    for resp in (login(client, "demo_admin"),
                 client.get("/api/auth/me", headers=auth_headers(client, "demo_admin"))):
        text_ = resp.text
        assert "password" not in text_.lower()
        assert "scrypt$" not in text_
        assert PASSWORDS["demo_admin"] not in text_
        assert JWT_SECRET not in text_
