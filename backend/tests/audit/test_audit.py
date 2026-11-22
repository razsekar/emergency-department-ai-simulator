from sqlalchemy import text

from app.modules.audit.public import AuditEvent, record
from app.platform import db as platform_db
from app.platform.events import get_event_bus
from tests.identity.conftest import PASSWORDS, auth_headers, login


def _rows(engine, where="true"):
    with engine.connect() as c:
        return c.execute(text(
            f"SELECT actor, action, outcome, resource, detail FROM audit.audit_events WHERE {where} "
            "ORDER BY occurred_at")).all()


def test_failed_login_is_audited(client, ident_engine):
    login(client, "demo_admin", "wrong-password")
    rows = _rows(ident_engine, "action='auth.login'")
    assert len(rows) == 1
    actor, _, outcome, _, detail = rows[0]
    assert (actor, outcome, detail["reason"]) == ("demo_admin", "failure", "bad_password")


def test_unknown_user_login_audited_with_internal_reason(client, ident_engine):
    login(client, "ghost", "x")
    assert _rows(ident_engine, "actor='ghost'")[0][4]["reason"] == "unknown_user"


def test_successful_login_audited_without_secrets(client, ident_engine):
    login(client, "demo_presenter")
    rows = _rows(ident_engine, "action='auth.login' AND outcome='success'")
    assert [r[0] for r in rows] == ["demo_presenter"]
    assert PASSWORDS["demo_presenter"] not in str(rows)


def test_permission_denied_is_audited(client, ident_engine):
    client.get("/_perm/scenario-apply", headers=auth_headers(client, "demo_viewer"))
    rows = _rows(ident_engine, "action='authz.denied'")
    assert len(rows) == 1
    assert rows[0][0] == "demo_viewer" and rows[0][2] == "denied"
    assert rows[0][4]["missing_permissions"] == ["scenario:apply"]


def test_any_module_can_record_via_event_bus_and_public_record(db, ident_engine):
    get_event_bus().publish(AuditEvent(actor="sim", action="scenario.apply", resource="scenario/surge",
                                       detail={"data_version": 7}))
    record(AuditEvent(actor="sim", action="scenario.reset"))
    rows = _rows(ident_engine, "actor='sim'")
    assert [r[1] for r in rows] == ["scenario.apply", "scenario.reset"]
    assert rows[0][3] == "scenario/surge" and rows[0][4] == {"data_version": 7}


def test_secrets_in_detail_are_redacted(db, ident_engine):
    record(AuditEvent(actor="x", action="probe", detail={
        "password": "p1", "api_key": "k1", "nested": {"access_token": "t1", "ok": 1},
        "items": [{"Authorization": "Bearer abc"}], "tokens_used": 120}))
    detail = _rows(ident_engine, "actor='x'")[0][4]
    assert detail["password"] == detail["api_key"] == "[REDACTED]"
    assert detail["nested"] == {"access_token": "[REDACTED]", "ok": 1}
    assert detail["items"] == [{"Authorization": "[REDACTED]"}]
    assert detail["tokens_used"] == 120  # usage counters are not secrets


def test_invalid_event_rejected_at_creation():
    import pytest
    with pytest.raises(ValueError):
        AuditEvent(actor="a", action="b", outcome="maybe")


def test_audit_failure_never_breaks_caller(db, monkeypatch):
    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(platform_db, "unit_of_work", boom)
    record(AuditEvent(actor="a", action="b"))  # must not raise
    get_event_bus().publish(AuditEvent(actor="a", action="b"))


def test_audit_listing_is_admin_only(client):
    assert client.get("/api/audit/events").status_code == 401
    for user in ("demo_viewer", "demo_presenter"):
        assert client.get("/api/audit/events", headers=auth_headers(client, user)).status_code == 403
    assert client.get("/api/audit/events", headers=auth_headers(client, "demo_admin")).status_code == 200


def test_audit_listing_pagination_and_filters(client):
    for i in range(5):
        record(AuditEvent(actor="bulk", action=f"bulk.item{i}", outcome="failure" if i % 2 else "success"))
    admin = auth_headers(client, "demo_admin")
    page = client.get("/api/audit/events?actor=bulk&limit=2&offset=0", headers=admin).json()
    assert page["total"] == 5 and len(page["items"]) == 2 and page["limit"] == 2
    second = client.get("/api/audit/events?actor=bulk&limit=2&offset=2", headers=admin).json()
    assert {i["id"] for i in page["items"]}.isdisjoint({i["id"] for i in second["items"]})
    failures = client.get("/api/audit/events?actor=bulk&outcome=failure", headers=admin).json()
    assert failures["total"] == 2
    assert client.get("/api/audit/events?action=bulk.", headers=admin).json()["total"] == 5
    assert client.get("/api/audit/events?limit=1000", headers=admin).status_code == 422
    assert client.get("/api/audit/events?outcome=bogus", headers=admin).status_code == 422


def test_audit_listing_never_contains_passwords(client):
    login(client, "demo_admin", "wrong-password-123")
    body = client.get("/api/audit/events", headers=auth_headers(client, "demo_admin")).text
    assert "wrong-password-123" not in body and PASSWORDS["demo_admin"] not in body
