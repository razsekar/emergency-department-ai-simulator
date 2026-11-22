"""CRITICAL ACCEPTANCE TEST (master prompt section 13), end to end over HTTP on the real `app.main`:

  load baseline -> fetch metrics -> record data_version -> load surge -> fetch metrics -> version changed and
  metrics changed -> run the SAME question -> agent retrieved the NEW metrics -> the LLM prompt and the generated
  answer are based on the new data -> recovery likewise.

Real login, real routers, real database (all migrations), real tools. The LLM is a scripted fake: this proves the
SYSTEM feeds fresh data to the model and carries its answer back, not the quality of any real model's prose.
"""
import pytest

from app.modules.ai_orchestration.domain.prompts import FIXED_DEMO_QUESTION
from tests.agentdb import ScriptedLlm, all_text, reply, tool_messages
from tests.comparison.test_comparison_service import PerModelLlm, good_answer
from tests.e2e.conftest import PRESENTER_PASSWORD, VIEWER_PASSWORD, login

FACTS = [("calculate_waiting_metrics", {}), ("get_bed_availability", {}),
         ("get_staff_availability", {}), ("get_pending_investigations", {})]
POLICY = ("retrieve_hospital_protocol", {"topics": ["waiting_time", "bed_capacity", "escalation"]})
EXPECTED = {"normal": (12, 5), "surge": (38, 28), "recovery": (9, 4)}  # (waiting, pending investigations)


def grounded(request):
    """A fake model that can only quote numbers present in the tool results it was shown."""
    n: dict = {}
    for payload in tool_messages(request):
        n.update({k: v for k, v in payload.items() if isinstance(v, (int, float))})
    return reply(f"{n['waiting_patients']} patients waiting; {n['available_beds']} beds available; "
                 f"data version {n['data_version']}. [Source: Hospital Escalation Procedures, p.2]")


def script():
    return [reply(tool_calls=FACTS), reply(tool_calls=[POLICY]), grounded]


def apply(client, admin, key):
    r = client.post("/api/scenarios/apply", json={"scenario_key": key}, headers=admin)
    assert r.status_code == 200, r.text
    return r.json()


def metrics(client, admin):
    r = client.get("/api/dashboard/metrics", headers=admin)
    assert r.status_code == 200, r.text
    return r.json()


def test_baseline_surge_recovery_over_http(client, admin, llm_holder):
    seen = {}
    for key in ("normal", "surge", "recovery"):
        before = client.get("/api/scenarios/current", headers=admin).json()["data_version"]
        applied = apply(client, admin, key)
        m = metrics(client, admin)
        waiting, pending = EXPECTED[key]

        # (2-3, 4-7) the data version moved and the calculated metrics changed
        assert applied["state"]["data_version"] == before + 1 == m["data_version"]
        assert (m["patients_waiting"], m["pending_investigations"]) == (waiting, pending)
        if seen:
            previous = list(seen.values())[-1]["metrics"]
            assert m["data_version"] > previous["data_version"]
            assert (m["patients_waiting"], m["avg_wait_minutes"]) != (previous["patients_waiting"], previous["avg_wait_minutes"])

        # (8) the same fixed question through the real agent endpoint
        llm = llm_holder.use(ScriptedLlm(script()))
        r = client.post("/api/agent/demo-run", json={"provider": "ollama", "model": "fake"}, headers=admin)
        assert r.status_code == 200, r.text
        run = r.json()

        # (9) the agent retrieved the NEW metrics: same data_version, same numbers as the dashboard
        assert run["question"] == FIXED_DEMO_QUESTION
        assert run["data_version"] == m["data_version"] and run["scenario_key"] == key
        assert run["data_version_consistent"] is True and run["status"] == "completed"
        assert run["snapshot_metrics"]["patients_waiting"] == m["patients_waiting"] == waiting
        assert run["snapshot_metrics"]["pending_investigations"] == pending
        waits = next(t for t in run["tools_executed"] if t["tool_name"] == "calculate_waiting_metrics")
        assert waits["output"]["waiting_patients"] == waiting and waits["output"]["data_version"] == m["data_version"]

        # (10) the generated answer is based on the new data: the model was SHOWN them, and its reply carries them
        assert FIXED_DEMO_QUESTION in all_text(llm.requests[0])
        final_prompt = tool_messages(llm.requests[-1])
        assert any(p.get("waiting_patients") == waiting for p in final_prompt)
        assert f"{waiting} patients waiting" in run["answer"] and f"data version {m['data_version']}" in run["answer"]
        seen[key] = {"metrics": m, "answer": run["answer"]}

    assert len({v["answer"] for v in seen.values()}) == 3  # same question, three different grounded answers
    # no answer cached across versions: three runs, three distinct traces in the history
    runs = client.get("/api/agent/runs", headers=admin).json()
    assert runs["total"] == 3 and len({i["data_version"] for i in runs["items"]}) == 3


def test_data_edit_between_two_identical_questions_changes_what_the_model_sees(client, admin, llm_holder):
    apply(client, admin, "normal")
    first = llm_holder.use(ScriptedLlm(script()))
    a = client.post("/api/agent/demo-run", json={"provider": "ollama", "model": "fake"}, headers=admin).json()
    # manual parameter edit through the API (a changed record set, same scenario family)
    r = client.post("/api/scenarios/apply", json={"scenario_key": "normal", "overrides": {"beds_available": 2}},
                    headers=admin)
    assert r.status_code == 200, r.text
    second = llm_holder.use(ScriptedLlm(script()))
    b = client.post("/api/agent/demo-run", json={"provider": "ollama", "model": "fake"}, headers=admin).json()
    assert b["data_version"] == a["data_version"] + 1
    assert b["snapshot_metrics"] != a["snapshot_metrics"]
    assert tool_messages(first.requests[-1]) != tool_messages(second.requests[-1])


def test_full_demo_mode_sequence_over_http(client, admin, llm_holder):
    q = client.get("/api/demo/question", headers=admin).json()["question"]
    assert q == FIXED_DEMO_QUESTION
    waiting = []
    versions = []
    for key in ("normal", "surge", "recovery"):
        llm_holder.use(ScriptedLlm(script()))
        r = client.post("/api/demo/step", json={"scenario": key, "provider": "ollama", "model": "fake"},
                        headers=admin)
        assert r.status_code == 200, r.text
        run = r.json()["run"]
        v = run["verification"]
        assert v["data_version_changed"] and v["metrics_changed"] and v["question_identical"]
        assert run["question"] == FIXED_DEMO_QUESTION
        waiting.append(run["metrics"]["patients_waiting"])
        versions.append(run["data_version"])
    assert waiting == [12, 38, 9] and versions == sorted(set(versions))

    session = client.get("/api/demo/session", headers=admin).json()
    assert [r["run_label"] for r in session["runs"]] == ["Run 1", "Run 2", "Run 3"]
    assert len({r["final_answer"] for r in session["runs"]}) == 3
    row = next(m for m in session["metric_comparison"] if m["metric"] == "patients_waiting")
    assert row["values"] == [12, 38, 9] and row["differs"]

    # reset and replay
    reset = client.post("/api/demo/session/reset", headers=admin)
    assert reset.status_code == 200 and reset.json()["cleared_runs"] == 3
    assert client.get("/api/demo/session", headers=admin).json()["run_count"] == 0
    assert client.get("/api/scenarios/current", headers=admin).json()["scenario_key"] == "normal"


def test_demo_step_refuses_a_viewer_even_with_a_valid_login(client):
    viewer = login(client, "demo_viewer", VIEWER_PASSWORD)
    r = client.post("/api/demo/step", json={"scenario": "surge", "provider": "ollama", "model": "fake"},
                    headers=viewer)
    assert r.status_code == 403
    assert client.get("/api/scenarios/current", headers=viewer).status_code in (200, 403)
    # the failed attempt must not have changed the data
    admin = login(client, "demo_admin", "e2e-admin-password-1")
    assert client.get("/api/scenarios/current", headers=admin).json()["data_version"] == 0


def test_presenter_can_run_the_demo(client):
    presenter = login(client, "demo_presenter", PRESENTER_PASSWORD)
    r = client.post("/api/demo/step", json={"scenario": "normal", "provider": "ollama", "model": "fake"},
                    headers=presenter)
    # no scripted LLM was installed here; the point is authorisation, not a 403
    assert r.status_code != 403


def test_model_comparison_over_http_shares_identical_context(client, admin, llm_holder):
    apply(client, admin, "surge")

    def answer(request):
        m = metrics(client, admin)
        names = m["scenario_name"]
        snap = {
            "patients_waiting": m["patients_waiting"], "avg_wait_minutes": m["avg_wait_minutes"],
            "max_wait_minutes": m["max_wait_minutes"], "beds_available": m["beds"]["available"],
            "beds_total": m["beds"]["total"], "pending_investigations": m["pending_investigations"],
            "doctors_on_duty": next(s["on_duty"] for s in m["staff"] if s["role"] == "doctor"),
            "nurses_on_duty": next(s["on_duty"] for s in m["staff"] if s["role"] == "nurse"),
        }
        return reply(good_answer(snap, names, m["data_version"]))

    llm_holder.use(PerModelLlm({"a": answer, "b": answer}))
    r = client.post("/api/comparison/run", headers=admin, json={"selections": [
        {"provider": "ollama", "model": "a"}, {"provider": "openai", "model": "b"}]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "not a formal benchmark" in body["label"].lower()
    assert body["identical_context_verified"] is True and body["data_version_consistent"] is True
    ctx = body["shared_context"]
    assert ctx["snapshot_metrics"]["patients_waiting"] == 38
    assert {x["context_sha256"] for x in body["results"]} == {ctx["context_sha256"]}
    assert ctx["data_version"] == client.get("/api/scenarios/current", headers=admin).json()["data_version"]
    assert [x["status"] for x in body["results"]] == ["completed", "completed"]
    # both models were given byte-identical prompts
    llm = llm_holder.llm
    assert len(llm.requests) == 2 and all_text(llm.requests[0]) == all_text(llm.requests[1])


@pytest.mark.parametrize("path", ["/api/agent/runs", "/api/demo/session", "/api/comparison/runs", "/api/audit/events",
                                  "/api/providers/status"])
def test_protected_endpoints_reject_anonymous_requests(client, path):
    assert client.get(path).status_code == 401
