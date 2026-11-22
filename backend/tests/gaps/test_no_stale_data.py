"""'Do not reuse stale metrics / do not cache across versions' over HTTP, plus agent tool behaviour through the real app.

The strongest staleness probe: edit a row DIRECTLY in the database (no scenario apply, so data_version does not move)
and check every read path (dashboard, queue, tool results, agent snapshot) sees the change immediately. A cache keyed
on data_version, or any cached answer, would fail these tests.
"""
from sqlalchemy import text

from tests.agentdb import ScriptedLlm, reply, tool_messages
from tests.e2e.test_acceptance_http import FACTS, POLICY, apply, grounded, metrics, script


def waiting_count(client, admin):
    return client.get("/api/patient-queue/waiting-metrics", headers=admin).json()["waiting_patients"]


def test_direct_record_edit_is_visible_everywhere_without_a_version_bump(client, admin, engine, llm_holder):
    apply(client, admin, "normal")
    version = client.get("/api/scenarios/current", headers=admin).json()["data_version"]
    assert metrics(client, admin)["patients_waiting"] == 12 and waiting_count(client, admin) == 12

    with engine.begin() as c:  # one waiting patient starts treatment
        updated = c.execute(text(
            "UPDATE patient_queue.patient_visits SET status='in_treatment', treatment_started_at=now() "
            "WHERE id = (SELECT id FROM patient_queue.patient_visits WHERE status='waiting' LIMIT 1)")).rowcount
    assert updated == 1

    assert client.get("/api/scenarios/current", headers=admin).json()["data_version"] == version  # not bumped
    m = metrics(client, admin)
    assert m["patients_waiting"] == 11 and m["patients_in_treatment"] >= 1
    assert waiting_count(client, admin) == 11
    queue = client.get("/api/patient-queue", params={"status": "waiting", "page_size": 200}, headers=admin).json()
    assert queue["total"] == 11

    llm = llm_holder.use(ScriptedLlm(script()))
    run = client.post("/api/agent/demo-run", json={"provider": "ollama", "model": "fake"}, headers=admin).json()
    assert run["snapshot_metrics"]["patients_waiting"] == 11
    waits = next(t for t in run["tools_executed"] if t["tool_name"] == "calculate_waiting_metrics")
    assert waits["output"]["waiting_patients"] == 11
    assert "11 patients waiting" in run["answer"]
    assert any(p.get("waiting_patients") == 11 for p in tool_messages(llm.requests[-1]))


def test_two_identical_runs_on_unchanged_data_are_two_real_executions(client, admin, llm_holder):
    """No answer cache: the same question on the same data still calls the model and the tools again."""
    apply(client, admin, "surge")
    first = llm_holder.use(ScriptedLlm(script()))
    a = client.post("/api/agent/demo-run", json={"provider": "ollama", "model": "fake"}, headers=admin).json()
    second = llm_holder.use(ScriptedLlm(script()))
    b = client.post("/api/agent/demo-run", json={"provider": "ollama", "model": "fake"}, headers=admin).json()
    assert a["id"] != b["id"] and a["data_version"] == b["data_version"]
    assert len(first.requests) == len(second.requests) == 3  # the model was asked again, every time
    assert client.get("/api/agent/runs", headers=admin).json()["total"] == 2


def test_failed_apply_never_bumps_version_or_changes_metrics(client, admin):
    apply(client, admin, "normal")
    before = (client.get("/api/scenarios/current", headers=admin).json()["data_version"], metrics(client, admin))
    for bad in ({"scenario_key": "normal", "overrides": {"beds_available": -5}},
                {"scenario_key": "normal", "overrides": {"waiting_patients": 99999}},
                {"scenario_key": "normal", "overrides": {"not_a_parameter": 1}}):
        assert client.post("/api/scenarios/apply", json=bad, headers=admin).status_code == 422
    after = (client.get("/api/scenarios/current", headers=admin).json()["data_version"], metrics(client, admin))
    assert before == after


# ------------------------------------------------------------------ agent tool execution over HTTP
def test_invalid_tool_arguments_are_rejected_logged_and_do_not_stop_the_run(client, admin, engine, llm_holder):
    apply(client, admin, "normal")
    llm_holder.use(ScriptedLlm([
        reply(tool_calls=[("get_patient_queue", {"status": "not-a-status", "limit": -1})]),
        reply(tool_calls=[("calculate_waiting_metrics", {}), ("get_bed_availability", {})]),
        grounded,
    ]))
    r = client.post("/api/agent/run", headers=admin, json={
        "question": "How long are patients waiting?", "provider": "ollama", "model": "fake"})
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["status"] == "completed"
    bad, good = run["tools_executed"][0], run["tools_executed"][1]
    assert bad["tool_name"] == "get_patient_queue" and bad["status"] != "ok" and bad["error"]
    assert good["tool_name"] == "calculate_waiting_metrics" and good["status"] == "ok"
    assert "12 patients waiting" in run["answer"]
    # every interaction, including the rejected one, is in the execution log with its run id
    with engine.connect() as c:
        rows = c.execute(text("SELECT tool_name, status FROM agent_tools.agent_execution_logs "
                              "WHERE run_id = :r ORDER BY sequence"), {"r": run["id"]}).all()
    assert [r[0] for r in rows] == ["get_patient_queue", "calculate_waiting_metrics", "get_bed_availability"]
    assert rows[0][1] != "ok" and rows[1][1] == "ok"


def test_tool_loop_is_bounded_even_if_the_model_never_stops(client, admin, engine, llm_holder):
    apply(client, admin, "normal")
    llm_holder.use(ScriptedLlm([reply(tool_calls=[("get_bed_availability", {})])], repeat_last=True))
    r = client.post("/api/agent/run", headers=admin, json={
        "question": "Keep calling tools forever", "provider": "ollama", "model": "fake"})
    assert r.status_code != 500, r.text  # a runaway model must end in a handled outcome, not a crash
    with engine.connect() as c:
        ok = c.execute(text("SELECT count(*) FROM agent_tools.agent_execution_logs WHERE status='ok'")).scalar_one()
    assert ok <= 5  # the master prompt's cap on tool interactions per request


def test_five_tools_run_on_live_data_and_the_sixth_is_refused(client, admin, engine, llm_holder):
    apply(client, admin, "surge")
    llm_holder.use(ScriptedLlm([
        reply(tool_calls=FACTS + [("get_patient_queue", {"status": "waiting", "limit": 5})]),  # five interactions
        reply(tool_calls=[POLICY]),                                                           # the sixth
        grounded,
    ]))
    run = client.post("/api/agent/demo-run", json={"provider": "ollama", "model": "fake"}, headers=admin).json()
    tools = run["tools_executed"]
    assert [t["tool_name"] for t in tools] == [n for n, _ in FACTS] + ["get_patient_queue", "retrieve_hospital_protocol"]
    assert [t["status"] for t in tools] == ["ok"] * 5 + ["refused"]
    assert "at most 5 tool interactions" in tools[5]["error"] and not tools[5]["output"]
    by = {t["tool_name"]: t["output"] for t in tools[:5]}
    assert by["calculate_waiting_metrics"]["waiting_patients"] == 38
    assert by["get_bed_availability"]["available_beds"] == 1
    assert by["get_pending_investigations"]["pending_count"] == 28
    assert by["get_patient_queue"]["data_version"] == by["calculate_waiting_metrics"]["data_version"]
    with engine.connect() as c:  # the refused call is audited in the execution log too, never executed
        statuses = [r[0] for r in c.execute(text(
            "SELECT status FROM agent_tools.agent_execution_logs WHERE run_id=:r ORDER BY sequence"), {"r": run["id"]})]
    assert statuses == ["ok"] * 5 + ["refused"]
