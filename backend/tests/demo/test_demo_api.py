"""HTTP layer: RBAC, validation, error mapping and audit events for the demonstration endpoints."""
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.ai_orchestration import public as orchestration
from app.modules.ai_orchestration.api.demo_router import demo_router
from app.modules.ai_orchestration.application.demo_service import DemoService
from app.modules.ai_orchestration.application.demo_wiring import get_demo_service
from app.modules.ai_orchestration.application.service import AgentService
from app.modules.identity.application.contracts import CurrentUser
from app.modules.identity.public import Permission, get_current_user
from app.platform.audit_events import AuditEvent
from app.platform.errors import install_error_handlers
from app.platform.events import get_event_bus
from tests.agentdb import ScriptedLlm, reply
from tests.demo.test_demo_flow import script

PRESENTER = (Permission.AGENT_RUN, Permission.SCENARIO_APPLY, Permission.SCENARIO_RESET)
BODY = {"scenario": "normal", "provider": "ollama", "model": "fake"}


def user(name="presenter1", perms=PRESENTER) -> CurrentUser:
    return CurrentUser(id=uuid.uuid4(), username=name, display_name=name, roles=("t",),
                       permissions=frozenset(str(p) for p in perms))


@pytest.fixture()
def make_client(demo_state):
    def _make(llm: ScriptedLlm | None = None, who: CurrentUser | None = None) -> TestClient:
        app = FastAPI()
        install_error_handlers(app)
        app.include_router(demo_router)
        app.dependency_overrides[get_current_user] = lambda: who or user()
        app.dependency_overrides[get_demo_service] = lambda: DemoService(AgentService(llm or ScriptedLlm(script())))
        return TestClient(app, raise_server_exceptions=False)

    return _make


@pytest.fixture()
def audit_events():
    seen: list[AuditEvent] = []
    bus = get_event_bus()
    bus.subscribe(AuditEvent, seen.append)
    yield seen
    bus._handlers[AuditEvent].remove(seen.append)


def test_full_workflow_over_http(make_client):
    client = make_client()
    assert client.get("/api/demo/question").json() == {"question": orchestration.FIXED_DEMO_QUESTION}
    assert client.get("/api/demo/session").json()["run_count"] == 0

    waiting = []
    for scenario in ("normal", "surge", "recovery"):
        r = client.post("/api/demo/step", json={**BODY, "scenario": scenario, "question": "ignored override"})
        assert r.status_code == 200, r.text
        run = r.json()["run"]
        assert run["question"] == orchestration.FIXED_DEMO_QUESTION  # a client cannot change the question
        assert run["verification"]["data_version_changed"] is True
        waiting.append(run["metrics"]["patients_waiting"])
    assert waiting == [12, 38, 9]

    body = client.get("/api/demo/session").json()
    assert body["run_count"] == 3 and [r["run_label"] for r in body["runs"]] == ["Run 1", "Run 2", "Run 3"]
    for key in ("scenario_name", "data_version", "patient_record_count", "metrics", "tools_executed",
                "retrieved_policies", "final_answer", "provider", "model", "latency_ms", "usage"):
        assert all(key in run for run in body["runs"]), key
    row = next(m for m in body["metric_comparison"] if m["metric"] == "patients_waiting")
    assert row["values"] == [12, 38, 9] and row["differs"] is True

    reset = client.post("/api/demo/session/reset")
    assert reset.status_code == 200 and reset.json()["cleared_runs"] == 3
    assert client.get("/api/demo/session").json()["run_count"] == 0


def test_rbac_is_enforced_server_side(make_client):
    viewer = make_client(who=user("viewer1", perms=(Permission.DASHBOARD_READ, Permission.SCENARIO_READ)))
    for method, path, kw in (("get", "/api/demo/question", {}), ("post", "/api/demo/step", {"json": BODY}),
                             ("get", "/api/demo/session", {}), ("post", "/api/demo/session/reset", {})):
        assert getattr(viewer, method)(path, **kw).status_code == 403, path
    # agent permission alone cannot change the data; reset needs its own permission
    no_apply = make_client(who=user(perms=(Permission.AGENT_RUN,)))
    assert no_apply.post("/api/demo/step", json=BODY).status_code == 403
    assert no_apply.get("/api/demo/session").status_code == 200
    assert no_apply.post("/api/demo/session/reset").status_code == 403


def test_request_validation(make_client):
    client = make_client()
    for bad in ({**BODY, "scenario": "custom"}, {**BODY, "scenario": "chaos"}, {**BODY, "provider": "mystery"},
                {**BODY, "temperature": 9}, {**BODY, "model": ""}, {"scenario": "normal"}):
        assert client.post("/api/demo/step", json=bad).status_code == 422


def test_error_mapping_is_safe(make_client):
    r = make_client(ScriptedLlm([], configured=False)).post("/api/demo/step", json=BODY)
    assert r.status_code in (409, 422) and "FAKE_API_KEY" in r.json()["error"]["message"]
    assert "Traceback" not in r.text
    # nothing was saved or applied
    assert make_client().get("/api/demo/session").json()["run_count"] == 0


def test_audit_events_are_published(make_client, audit_events):
    client = make_client(who=user("presenter_x"))
    client.post("/api/demo/step", json=BODY)
    client.post("/api/demo/session/reset")
    actions = [(e.action, e.outcome, e.actor) for e in audit_events if e.action.startswith("demo.")]
    assert ("demo.step", "success", "presenter_x") in actions and ("demo.reset", "success", "presenter_x") in actions
    step_event = next(e for e in audit_events if e.action == "demo.step")
    assert step_event.detail["scenario"] == "normal" and step_event.detail["run"] == "Run 1"


def test_failed_step_is_audited_as_failure(make_client, audit_events):
    from app.modules.model_providers.public import ProviderCallError

    r = make_client(ScriptedLlm([ProviderCallError("boom")], repeat_last=True)).post("/api/demo/step", json=BODY)
    assert r.status_code >= 400
    assert any(e.action == "demo.step" and e.outcome == "failure" for e in audit_events)
    assert reply  # imported fixture helper kept for clarity
