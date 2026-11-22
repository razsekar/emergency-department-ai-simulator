"""Demonstration workflow: baseline -> surge -> recovery with the identical question and changing data."""
from types import SimpleNamespace

import pytest

from app.modules.ai_orchestration import public as orchestration
from app.modules.ai_orchestration.application import demo_contracts as d
from app.modules.ai_orchestration.application import demo_service
from app.modules.ai_orchestration.application.demo_service import DemoService, DemoVerificationError
from app.modules.ai_orchestration.application.service import AgentService, get_run, list_runs
from app.modules.ai_orchestration.domain import demo_diff
from app.modules.model_providers.public import ProviderCallError, ProviderNotConfiguredError
from app.modules.simulation import public as simulation
from tests.agentdb import ScriptedLlm, all_text, reply, tool_messages

FOUR_FACTS = [("calculate_waiting_metrics", {}), ("get_bed_availability", {}),
              ("get_staff_availability", {}), ("get_pending_investigations", {})]
POLICY = ("retrieve_hospital_protocol", {"topics": ["waiting_time", "bed_capacity", "escalation"]})


def grounded(request):
    n: dict = {}
    for payload in tool_messages(request):
        n.update({k: v for k, v in payload.items() if isinstance(v, (int, float))})
    return reply(f"{n['waiting_patients']} patients waiting, {n['available_beds']} beds available "
                 f"(data version {n['data_version']}). [Source: Hospital Escalation Procedures, p.2]")


def script():
    return [reply(tool_calls=FOUR_FACTS), reply(tool_calls=[POLICY]), grounded]


def step(scenario: str, llm: ScriptedLlm | None = None, service_cls=AgentService, **kw):
    llm = llm or ScriptedLlm(script())
    req = d.DemoStepRequest(scenario=scenario, provider="ollama", model="fake", **kw)
    return DemoService(service_cls(llm)).step(req, actor="tester"), llm


def session():
    return orchestration.demo_session()


# ------------------------------------------------------------------ the critical acceptance workflow
def test_baseline_surge_recovery_same_question_different_data(demo_state):
    results, llms = [], []
    for scenario in ("normal", "surge", "recovery"):
        res, llm = step(scenario)
        results.append(res)
        llms.append(llm)
    runs = [r.run for r in results]

    # Run 1/2/3, strictly increasing data versions, each traced to its own scenario
    assert [r.run_label for r in runs] == ["Run 1", "Run 2", "Run 3"]
    assert [r.scenario_key for r in runs] == ["normal", "surge", "recovery"]
    assert runs[0].data_version < runs[1].data_version < runs[2].data_version
    assert len({r.session_id for r in runs}) == 1

    # the underlying records really changed: 12 / 38 / 9 waiting, 5 / 28 / 4 pending
    assert [r.metrics["patients_waiting"] for r in runs] == [12, 38, 9]
    assert [r.metrics["pending_investigations"] for r in runs] == [5, 28, 4]
    assert all(r.patient_record_count == r.metrics["total_visits"] > 0 for r in runs)
    assert runs[1].metrics["avg_wait_minutes"] > runs[0].metrics["avg_wait_minutes"] * 3

    # verification block proves it before the question was asked
    for r in runs:
        v = r.verification
        assert v.data_version_changed and v.data_version_after > v.data_version_before
        assert v.metrics_changed and v.changed_metrics and v.question_identical and v.analysis_data_version_matches
    assert runs[0].verification.compared_to == "state_before_step"
    assert runs[1].verification.compared_to == "previous_run"
    assert {c.metric: (c.before, c.after) for c in runs[1].verification.changed_metrics}["patients_waiting"] == (12, 38)

    # identical question, byte for byte, every time (and the model really received it)
    assert {r.question for r in runs} == {orchestration.FIXED_DEMO_QUESTION}
    assert len({r.question_sha256 for r in runs}) == 1
    for llm in llms:
        assert orchestration.FIXED_DEMO_QUESTION in all_text(llm.requests[0])

    # each model prompt contained THAT scenario's metrics, and the answers differ accordingly
    for llm, waiting in zip(llms, (12, 38, 9)):
        assert any(p.get("waiting_patients") == waiting for p in tool_messages(llm.requests[1]))
    assert "12 patients waiting" in runs[0].final_answer and "38 patients waiting" in runs[1].final_answer
    assert "9 patients waiting" in runs[2].final_answer
    assert len({r.final_answer for r in runs}) == 3

    # every run keeps tools, policies, provider/model, latency and tokens, and links to its agent run
    for r in runs:
        assert [t["tool_name"] for t in r.tools_executed] == [n for n, _ in FOUR_FACTS] + ["retrieve_hospital_protocol"]
        assert {p["document_name"] for p in r.retrieved_policies} == {
            "Hospital Escalation Procedures", "Resource Management Guidelines"}
        assert (r.provider, r.model) == ("ollama", "fake") and r.latency_ms >= 0 and r.usage.total_tokens == 450
        assert get_run(r.analysis_run_id).data_version == r.data_version

    # session view: saved runs + metric comparison derived from the data
    view = session()
    assert view.run_count == 3 and [r.run_label for r in view.runs] == ["Run 1", "Run 2", "Run 3"]
    assert view.question == orchestration.FIXED_DEMO_QUESTION
    rows = {r.metric: r for r in view.metric_comparison}
    assert rows["patients_waiting"].values == [12, 38, 9] and rows["patients_waiting"].differs
    assert rows["patients_waiting"].deltas_vs_previous == [None, 26, -29]
    assert results[-1].metric_comparison == view.metric_comparison and results[-1].run_count == 3


def test_saved_runs_and_metrics_are_never_reused(demo_state):
    first, llm1 = step("normal")
    second, llm2 = step("normal")  # same scenario twice: new version, new LLM call, new tool run, new row
    a, b = first.run, second.run
    assert a.id != b.id and a.analysis_run_id != b.analysis_run_id
    assert b.data_version == a.data_version + 1 and b.run_label == "Run 2"
    assert len(llm1.requests) == 3 and len(llm2.requests) == 3  # the model was asked again each time
    assert b.verification.compared_to == "previous_run" and b.verification.metrics_changed is False
    assert "already loaded" in b.verification.note
    assert f"data version {b.data_version}" in b.final_answer  # answer built from the NEW version's tool output
    assert list_runs(run_type="demo").total == 2


def test_metric_comparison_is_derived_from_data():
    rows = {r["metric"]: r for r in demo_diff.metric_comparison([{"a": 1, "b": 2.5, "c": "x"}, {"a": 4, "b": 2.5, "c": "y"}])}
    assert rows["a"]["differs"] and rows["a"]["deltas_vs_previous"] == [None, 3]
    assert not rows["b"]["differs"] and rows["c"]["differs"] and rows["c"]["deltas_vs_previous"] == [None, None]
    assert demo_diff.changed_metrics({"a": 1, "b": 2}, {"a": 1, "b": 3, "c": 1}) == [
        {"metric": "b", "before": 2, "after": 3}, {"metric": "c", "before": None, "after": 1}]
    assert demo_diff.metric_comparison([]) == []


# ------------------------------------------------------------------ failure handling: nothing partial is saved
def test_agent_failure_saves_no_run_and_keeps_earlier_runs(demo_state):
    step("normal")
    with pytest.raises(ProviderCallError):
        step("surge", ScriptedLlm([ProviderCallError("upstream boom")], repeat_last=True))
    view = session()
    assert view.run_count == 1 and view.runs[0].run_label == "Run 1"  # no partial Run 2
    # the next successful step becomes Run 2 (no gap, no duplicate)
    res, _ = step("surge")
    assert res.run.run_label == "Run 2" and res.run_count == 2


def test_apply_failure_leaves_data_and_runs_untouched(demo_state, monkeypatch):
    step("normal")
    version = simulation.current_state().data_version

    def boom(key, *a, **k):
        raise RuntimeError("apply exploded")

    monkeypatch.setattr(demo_service.simulation, "apply_scenario", boom)
    llm = ScriptedLlm(script())
    with pytest.raises(RuntimeError):
        step("surge", llm)
    assert llm.requests == []  # the question was never asked
    assert simulation.current_state().data_version == version and session().run_count == 1


def test_unchanged_data_version_stops_before_the_question(demo_state, monkeypatch):
    step("normal")
    current = simulation.current_state()
    monkeypatch.setattr(demo_service.simulation, "apply_scenario",
                        lambda key, *a, **k: SimpleNamespace(state=current))  # pretends to apply; version unchanged
    llm = ScriptedLlm(script())
    with pytest.raises(DemoVerificationError, match="did not change"):
        step("surge", llm)
    assert llm.requests == [] and session().run_count == 1


def test_not_configured_provider_fails_before_any_data_changes(demo_state):
    step("normal")
    version = simulation.current_state().data_version
    with pytest.raises(ProviderNotConfiguredError):
        step("surge", ScriptedLlm([], configured=False))
    assert simulation.current_state().data_version == version and session().run_count == 1


def test_a_run_that_did_not_use_the_fixed_question_is_rejected(demo_state):
    class Tampering(AgentService):
        def demo_run(self, **kw):  # a buggy/hostile agent layer asking something else
            return self.run(question="Something else entirely?", run_type="demo", **kw)

    with pytest.raises(DemoVerificationError, match="fixed question"):
        step("normal", service_cls=Tampering)
    assert session().run_count == 0


# ------------------------------------------------------------------ reset and replay
def test_reset_clears_runs_reloads_baseline_and_allows_replay(demo_state):
    for scenario in ("normal", "surge", "recovery"):
        step(scenario)
    old_session = session().session_id
    version_before = simulation.current_state().data_version

    out = DemoService(AgentService(ScriptedLlm([]))).reset(actor="tester")
    assert out.cleared_runs == 3 and out.baseline_scenario == "Normal Operations"
    assert out.data_version == version_before + 1
    state = simulation.current_state()
    assert state.scenario_key == "normal" and state.data_version == out.data_version
    empty = session()
    assert empty.run_count == 0 and empty.session_id is None and empty.metric_comparison == []

    # replay: a fresh session starting again at Run 1
    res, _ = step("surge")
    assert res.run.run_label == "Run 1" and res.run.session_id != old_session
    assert res.run.metrics["patients_waiting"] == 38 and res.run.data_version > out.data_version


def test_unknown_scenario_is_rejected_by_validation():
    with pytest.raises(ValueError):
        d.DemoStepRequest(scenario="custom", provider="ollama", model="fake")
