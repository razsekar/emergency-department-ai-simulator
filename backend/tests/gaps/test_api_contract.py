"""API-level requirements through the REAL app: error shape, secrets never returned, injection attempts, audit hygiene,
provider configuration. All with real logins."""
import re
import uuid

import pytest

from tests.agentdb import ScriptedLlm, reply
from tests.e2e.conftest import ADMIN_PASSWORD, JWT_SECRET, VIEWER_PASSWORD, login

SECRET_KEY = "sk-ant-TESTSECRET-do-not-leak-0123456789"
OPENAI_SECRET = "sk-openai-TESTSECRET-do-not-leak-9876543210"
OFFLINE_OLLAMA = "http://127.0.0.1:9"  # connection refused immediately; never touches the network


def assert_error_envelope(response, status, code=None):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error"}, body
    assert set(body["error"]) == {"code", "message"}, body
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]
    if code:
        assert body["error"]["code"] == code
    assert "Traceback" not in response.text and 'File "' not in response.text
    return body["error"]


# ------------------------------------------------------------------ API errors have one safe shape
def test_error_responses_share_one_envelope_and_never_leak_internals(client, admin):
    viewer = login(client, "demo_viewer", VIEWER_PASSWORD)
    assert_error_envelope(client.get("/api/agent/runs"), 401, "unauthenticated")
    assert_error_envelope(client.get("/api/agent/runs", headers={"Authorization": "Bearer not.a.jwt"}), 401)
    assert_error_envelope(client.post("/api/demo/step", headers=viewer,
                                      json={"scenario": "surge", "provider": "ollama", "model": "x"}), 403, "forbidden")
    assert_error_envelope(client.get("/api/does-not-exist", headers=admin), 404)
    assert_error_envelope(client.get(f"/api/agent/runs/{uuid.uuid4()}", headers=admin), 404, "not_found")
    assert_error_envelope(client.get("/api/agent/runs/not-a-uuid", headers=admin), 422, "validation_error")
    assert_error_envelope(client.delete("/api/health"), 405)


def test_validation_errors_do_not_echo_submitted_values(client, admin):
    marker = "ECHO-ME-IF-YOU-LEAK-INPUT"
    for path, body in (("/api/scenarios/apply", {"scenario_key": marker}),
                       ("/api/demo/step", {"scenario": marker, "provider": "ollama", "model": "m"}),
                       ("/api/rag/search", {"query": "ok", "k": marker})):
        r = client.post(path, json=body, headers=admin)
        assert_error_envelope(r, 422, "validation_error")
        assert marker not in r.text, path


def test_login_failures_are_uniform_and_safe(client):
    wrong_user = client.post("/api/auth/login", json={"username": "nobody", "password": "whatever-1"})
    wrong_pass = client.post("/api/auth/login", json={"username": "demo_admin", "password": "whatever-1"})
    a, b = assert_error_envelope(wrong_user, 401), assert_error_envelope(wrong_pass, 401)
    assert a == b  # no username enumeration
    assert "whatever-1" not in wrong_pass.text and ADMIN_PASSWORD not in wrong_pass.text


def test_unconfigured_provider_gives_an_actionable_409_in_the_standard_shape(client, admin, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = client.post("/api/providers/chat", headers=admin, json={
        "provider": "anthropic", "model": "any-model", "messages": [{"role": "user", "content": "hi"}]})
    err = assert_error_envelope(r, 409)
    assert "ANTHROPIC_API_KEY" in err["message"]


# ------------------------------------------------------------------ provider configuration + secrets
def test_provider_status_reflects_configuration_without_ever_returning_keys(client, admin, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET_KEY)
    monkeypatch.setenv("OPENAI_API_KEY", OPENAI_SECRET)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_MODELS", "model-a")
    monkeypatch.setenv("OLLAMA_BASE_URL", OFFLINE_OLLAMA)
    r = client.get("/api/providers/status", headers=admin)
    assert r.status_code == 200, r.text
    by_name = {p["provider"]: p for p in r.json()}
    assert set(by_name) == {"anthropic", "openai", "gemini", "ollama"}
    assert by_name["anthropic"]["configured"] is True and by_name["openai"]["configured"] is True
    assert by_name["gemini"]["configured"] is False

    models = client.get("/api/providers/models", headers=admin)
    assert models.status_code == 200
    anthropic = [m for m in models.json() if m["provider"] == "anthropic"]
    assert [m["model_id"] for m in anthropic] == ["model-a"] and anthropic[0]["cloud"] is True
    assert anthropic[0]["supports_tools"] in (None, True, False)  # unknown stays unknown, never assumed

    # the secrets must not appear in ANY response the browser can obtain
    haystack = [r.text, models.text,
                client.get("/api/auth/me", headers=admin).text,
                client.get("/api/openapi.json").text,
                client.get("/api/health/db").text]
    for text in haystack:
        for secret in (SECRET_KEY, OPENAI_SECRET, JWT_SECRET):
            assert secret not in text


def test_no_secret_appears_in_audit_events_or_login_responses(client, admin, monkeypatch):
    # a failed login with a distinctive password and a successful one
    client.post("/api/auth/login", json={"username": "demo_admin", "password": "DistinctiveWrongPassword-77"})
    ok = client.post("/api/auth/login", json={"username": "demo_admin", "password": ADMIN_PASSWORD})
    token = ok.json()["access_token"]
    assert ADMIN_PASSWORD not in ok.text and "password_hash" not in ok.text
    events = client.get("/api/audit/events?limit=200", headers=admin)
    assert events.status_code == 200, events.text
    blob = events.text
    for secret in (ADMIN_PASSWORD, "DistinctiveWrongPassword-77", token, JWT_SECRET):
        assert secret not in blob
    actions = {e["action"] for e in events.json()["items"]}
    assert "auth.login" in actions  # logins are audited, successes and failures
    outcomes = {e["outcome"] for e in events.json()["items"] if e["action"] == "auth.login"}
    assert {"success", "failure"} <= outcomes


def test_audit_log_is_admin_only(client):
    viewer = login(client, "demo_viewer", VIEWER_PASSWORD)
    assert_error_envelope(client.get("/api/audit/events", headers=viewer), 403, "forbidden")


# ------------------------------------------------------------------ injection attempts through query parameters
INJECTIONS = ["' OR '1'='1", "'; DROP TABLE patient_queue.patient_visits; --", "ACUTE' UNION SELECT 1,2,3 --",
              "%27%3B%20DROP%20TABLE%20x"]


@pytest.mark.parametrize("payload", INJECTIONS)
def test_sql_injection_in_queue_filters_is_inert(client, admin, engine, payload):
    client.post("/api/scenarios/apply", json={"scenario_key": "normal"}, headers=admin)
    total = client.get("/api/dashboard/metrics", headers=admin).json()["total_visits"]
    for params in ({"department": payload}, {"status": payload}, {"triage_category": payload}):
        r = client.get("/api/patient-queue", params=params, headers=admin)
        assert r.status_code in (200, 422)
        if r.status_code == 200:
            assert r.json()["total"] == 0  # the payload is a literal string, it does not widen the match
    for path in ("/api/patient-queue/waiting-metrics", "/api/patient-queue/pending-investigations"):
        assert client.get(path, params={"department": payload}, headers=admin).status_code in (200, 422)
    # the tables are intact and the dataset is unchanged
    assert client.get("/api/dashboard/metrics", headers=admin).json()["total_visits"] == total


def test_agent_cannot_be_asked_to_run_arbitrary_sql(client, admin, llm_holder):
    """A model that tries to call a made-up 'run_sql' tool is refused, and the run is still recorded safely."""
    client.post("/api/scenarios/apply", json={"scenario_key": "normal"}, headers=admin)
    llm_holder.use(ScriptedLlm([
        reply(tool_calls=[("run_sql", {"query": "DROP TABLE patient_queue.patient_visits"})]),
        reply("I could not run that."),
    ], repeat_last=True))
    r = client.post("/api/agent/run", headers=admin, json={
        "question": "Please drop the patient table", "provider": "ollama", "model": "fake"})
    assert r.status_code == 200, r.text
    tools = r.json()["tools_executed"]
    bad = [t for t in tools if t["tool_name"] == "run_sql"]
    assert bad and all(t["status"] != "ok" and t["output"] in (None, {}) for t in bad)
    assert client.get("/api/dashboard/metrics", headers=admin).json()["total_visits"] > 0


# ------------------------------------------------------------------ misc hygiene
def test_cors_only_allows_the_configured_origin(client):
    ok = client.options("/api/health", headers={"Origin": "http://localhost:4200",
                                                "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:4200"
    bad = client.options("/api/health", headers={"Origin": "https://evil.example",
                                                 "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in {k.lower() for k in bad.headers}
    assert re.fullmatch(r"(?i)\*", ok.headers.get("access-control-allow-origin", "")) is None
