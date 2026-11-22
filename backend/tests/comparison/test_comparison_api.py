"""HTTP layer: RBAC, validation, error mapping, audit events, history; and registration in the real app."""
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.agent_tools.application import handlers
from app.modules.ai_orchestration.api.comparison_router import router as comparison_router
from app.modules.ai_orchestration.application.comparison_service import ComparisonService
from app.modules.ai_orchestration.application.comparison_wiring import get_comparison_service
from app.modules.ai_orchestration.application.snapshot import take_snapshot
from app.modules.ai_orchestration.domain.prompts import FIXED_DEMO_QUESTION
from app.modules.identity.application.contracts import CurrentUser
from app.modules.identity.public import Permission, get_current_user
from app.modules.model_providers.public import ProviderCallError
from app.modules.simulation import public as simulation
from app.platform.audit_events import AuditEvent
from app.platform.errors import install_error_handlers
from app.platform.events import get_event_bus
from tests.agentdb import make_fake_search, policy_chunk, reply
from tests.comparison.test_comparison_service import CITE, PerModelLlm, good_answer

BODY = {"selections": [{"provider": "ollama", "model": "a"}, {"provider": "openai", "model": "b"}]}


def user(perms=(Permission.COMPARISON_RUN,), name="presenter1") -> CurrentUser:
    return CurrentUser(id=uuid.uuid4(), username=name, display_name=name, roles=("t",),
                       permissions=frozenset(str(p) for p in perms))


def grounded(_request):
    snap = take_snapshot()
    return reply(good_answer(snap.metrics, snap.scenario_name or "", snap.data_version))


@pytest.fixture()
def make_client(comparison_state, monkeypatch):
    simulation.apply_scenario("normal")
    monkeypatch.setattr(handlers.rag, "search", make_fake_search([policy_chunk()]))

    def _make(llm: PerModelLlm, who: CurrentUser | None = None) -> TestClient:
        app = FastAPI()
        install_error_handlers(app)
        app.include_router(comparison_router)
        app.dependency_overrides[get_current_user] = lambda: who or user()
        app.dependency_overrides[get_comparison_service] = lambda: ComparisonService(llm)
        return TestClient(app, raise_server_exceptions=False)

    return _make


@pytest.fixture()
def audit_events():
    seen: list[AuditEvent] = []
    bus = get_event_bus()
    bus.subscribe(AuditEvent, seen.append)
    yield seen
    bus._handlers[AuditEvent].remove(seen.append)


def test_run_returns_shared_context_results_scores_and_the_benchmark_disclaimer(make_client):
    r = make_client(PerModelLlm({"a": grounded, "b": grounded})).post("/api/comparison/run", json=BODY)
    assert r.status_code == 200
    body = r.json()
    assert body["label"] == "Demonstration comparison, not a formal benchmark."
    assert "not a formal benchmark" in body["scoring_note"].lower()
    assert body["question"] == FIXED_DEMO_QUESTION  # defaulted when omitted
    assert body["status"] == "completed" and body["identical_context_verified"] is True
    ctx = body["shared_context"]
    assert ctx["data_version"] == 1 and ctx["snapshot_metrics"]["patients_waiting"] == 12
    assert len(ctx["context_sha256"]) == 64 and ctx["tools_executed"][0]["tool_name"] == "calculate_waiting_metrics"
    assert [(x["provider"], x["model"]) for x in body["results"]] == [("ollama", "a"), ("openai", "b")]
    first = body["results"][0]
    assert first["scores"]["accuracy"]["score"] == 1.0 and first["usage"]["total_tokens"] == 150
    assert first["context_sha256"] == ctx["context_sha256"] and first["latency_ms"] >= 0
    assert "estimated_cost_usd" in first and "tool_calling_supported" in first


def test_custom_question_is_used(make_client):
    llm = PerModelLlm({"a": grounded, "b": grounded})
    r = make_client(llm).post("/api/comparison/run", json={**BODY, "question": "What about beds?"})
    assert r.json()["question"] == "What about beds?"
    assert "What about beds?" in llm.requests[0].messages[1].content


def test_unconfigured_and_failing_models_are_reported_in_the_response(make_client):
    llm = PerModelLlm({"a": grounded, "b": ProviderCallError("Provider timed out."), "c": grounded},
                      unconfigured=("c",))
    body = {"selections": [{"provider": "ollama", "model": "a"}, {"provider": "openai", "model": "b"},
                           {"provider": "gemini", "model": "c"}]}
    r = make_client(llm).post("/api/comparison/run", json=body)
    assert r.status_code == 200
    out = r.json()
    assert out["status"] == "partial"
    assert [x["status"] for x in out["results"]] == ["completed", "failed", "not_configured"]
    assert out["results"][1]["error"] == "Provider timed out."
    assert "GEMINI_API_KEY" in out["results"][2]["error"]


def test_no_usable_models_returns_409_with_a_safe_actionable_message(make_client):
    r = make_client(PerModelLlm({}, unconfigured=("a", "b"))).post("/api/comparison/run", json=BODY)
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "no_model_available" and "OLLAMA_API_KEY" in err["message"]


@pytest.mark.parametrize("payload", [
    {"selections": [{"provider": "ollama", "model": "a"}]},  # a comparison needs at least two models
    {"selections": [{"provider": "ollama", "model": "a"}, {"provider": "ollama", "model": "a"}]},  # duplicates
    {"selections": [{"provider": "ollama", "model": "a"}, {"provider": "mystery", "model": "b"}]},
    {"selections": [{"provider": "ollama", "model": "a"}, {"provider": "openai", "model": ""}]},
    {"selections": [{"provider": "ollama", "model": "a", "temperature": 3}, {"provider": "openai", "model": "b"}]},
    {**BODY, "question": "x"},
    {"selections": [{"provider": "ollama", "model": f"m{i}"} for i in range(7)]},  # more than the maximum
    {},
])
def test_invalid_requests_are_rejected_before_any_work(make_client, payload):
    llm = PerModelLlm({"a": grounded, "b": grounded})
    r = make_client(llm).post("/api/comparison/run", json=payload)
    assert r.status_code == 422 and llm.requests == []


def test_rbac_viewer_cannot_run_or_read_history(make_client):
    viewer = user(perms=(Permission.DASHBOARD_READ, Permission.MODELS_READ), name="viewer1")
    client = make_client(PerModelLlm({"a": grounded, "b": grounded}), who=viewer)
    assert client.post("/api/comparison/run", json=BODY).status_code == 403
    assert client.get("/api/comparison/runs").status_code == 403
    assert client.get(f"/api/comparison/runs/{uuid.uuid4()}").status_code == 403


def test_history_list_detail_filter_and_404(make_client):
    client = make_client(PerModelLlm({"a": grounded, "b": grounded}))
    first = client.post("/api/comparison/run", json=BODY).json()
    simulation.apply_scenario("surge")
    second = client.post("/api/comparison/run", json=BODY).json()

    page = client.get("/api/comparison/runs").json()
    assert page["total"] == 2 and [i["id"] for i in page["items"]] == [second["id"], first["id"]]
    assert page["items"][0]["models"] == ["ollama/a", "openai/b"] and page["items"][0]["data_version"] == 2
    assert client.get("/api/comparison/runs?data_version=1").json()["total"] == 1
    assert client.get("/api/comparison/runs?limit=0").status_code == 422

    detail = client.get(f"/api/comparison/runs/{first['id']}").json()
    assert detail["shared_context"]["snapshot_metrics"]["patients_waiting"] == 12
    assert second["shared_context"]["snapshot_metrics"]["patients_waiting"] == 38
    assert detail["results"][0]["answer"] == first["results"][0]["answer"]
    assert client.get(f"/api/comparison/runs/{uuid.uuid4()}").status_code == 404
    assert client.get("/api/comparison/runs/not-a-uuid").status_code == 422


def test_runs_publish_an_audit_event(make_client, audit_events):
    make_client(PerModelLlm({"a": grounded, "b": grounded})).post("/api/comparison/run", json=BODY)
    event = next(e for e in audit_events if e.action == "comparison.run")
    assert event.actor == "presenter1" and event.outcome == "success"
    assert event.detail["models"] == ["ollama/a", "openai/b"] and event.detail["data_version"] == 1


def test_no_secrets_or_prompts_with_credentials_in_responses(make_client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-should-never-appear")
    r = make_client(PerModelLlm({"a": grounded, "b": grounded})).post("/api/comparison/run", json=BODY)
    assert "sk-test-should-never-appear" not in r.text


def test_routes_are_registered_in_the_real_app_and_require_a_token():
    from app.main import create_app

    app = create_app()
    paths = app.openapi()["paths"]
    assert "/api/comparison/run" in paths and "/api/comparison/runs" in paths
    assert "/api/comparison/runs/{comparison_id}" in paths
    client = TestClient(app, raise_server_exceptions=False)
    assert client.post("/api/comparison/run", json=BODY).status_code == 401
    assert client.get("/api/comparison/runs").status_code == 401
