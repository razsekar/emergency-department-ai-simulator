from datetime import datetime, timezone

import pytest

from tests.simdb import module_client
from app.modules.analytics import public as analytics
from app.modules.simulation import public as sim
from app.modules.simulation.application import service
from app.modules.simulation.application.generator import generate
from app.modules.simulation.domain.builtin import BUILTIN
from app.modules.simulation.domain.errors import ScenarioNotFoundError, ScenarioValidationError
from app.platform.db import unit_of_work

TARGETS = {
    "normal": dict(waiting=12, wait=15, pending=5, avail=8, doctors=6, nurses=10),
    "surge": dict(waiting=38, wait=75, pending=28, avail=1, doctors=3, nurses=4),
    "recovery": dict(waiting=9, wait=18, pending=4, avail=10, doctors=7, nurses=12),
}


def metrics():
    with unit_of_work() as s:
        return analytics.get_dashboard_metrics(s)


@pytest.mark.parametrize("key", list(TARGETS))
def test_builtin_scenarios_produce_target_conditions(clean_state, key):
    t = TARGETS[key]
    result = sim.apply_scenario(key)
    m = metrics()
    assert result.state.data_version == 1 and result.run.status == "applied"
    assert m.patients_waiting == t["waiting"]
    assert abs(m.avg_wait_minutes - t["wait"]) <= 0.1 * t["wait"]
    assert m.pending_investigations == t["pending"]
    assert m.beds.available == t["avail"]
    roles = {s.role: s.on_duty for s in m.staff}
    assert roles == {"doctor": t["doctors"], "nurse": t["nurses"]}
    assert m.patients_in_treatment == m.beds.occupied
    assert all(c["ok"] for c in result.run.validation)


def test_generation_is_deterministic_for_same_seed_and_reference_time():
    ref = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    a = generate(BUILTIN["surge"].params, ref)
    b = generate(BUILTIN["surge"].params, ref)
    assert a == b
    other = generate(BUILTIN["surge"].params.model_copy(update={"seed": 7}), ref)
    assert other != a


def test_synthetic_identifiers_only(clean_state):
    sim.apply_scenario("normal")
    from app.modules.patient_queue import public as queue

    with unit_of_work() as s:
        page = queue.get_queue(s, page_size=200)
    assert page.items and all(r.patient_ref.startswith("SIM-PAT-") for r in page.items)
    assert all(r.visit_ref.startswith("SIM-VIS-") for r in page.items)


def test_apply_increments_data_version_and_records_history(clean_state):
    assert sim.current_state().data_version == 0
    sim.apply_scenario("normal")
    sim.apply_scenario("surge")
    state = sim.current_state()
    assert state.data_version == 2 and state.scenario_key == "surge" and state.scenario_name == "Emergency Surge"
    hist = sim.get_history()
    assert [r.data_version for r in hist.items] == [2, 1]
    assert hist.items[0].parameters["waiting_patients"] == 38


def test_reset_restores_baseline_and_bumps_version(clean_state):
    sim.apply_scenario("surge")
    res = sim.reset_database()
    m = metrics()
    assert res.run.trigger == "reset" and res.state.scenario_key == "normal"
    assert res.state.data_version == 2
    assert m.patients_waiting == 12 and m.beds.available == 8


def test_failure_in_second_module_rolls_back_everything(clean_state, monkeypatch):
    sim.apply_scenario("normal")
    before = metrics()

    def boom(*_a, **_k):
        raise RuntimeError("simulated failure after resource data was replaced")

    monkeypatch.setattr(service.queue, "replace_dataset", boom)
    with pytest.raises(RuntimeError):
        sim.apply_scenario("surge")
    monkeypatch.undo()

    after = metrics()
    assert after.data_version == before.data_version == 1
    assert after.beds == before.beds and after.staff == before.staff  # resource module write rolled back
    assert after.patients_waiting == before.patients_waiting == 12
    failed = [r for r in sim.get_history().items if r.status == "failed"]
    assert len(failed) == 1 and failed[0].data_version is None


def test_generated_data_not_matching_scenario_is_rejected_and_rolled_back(clean_state, monkeypatch):
    sim.apply_scenario("normal")
    real = service.generate

    def faulty(params, ref):
        resource, queue = real(params, ref)
        doctors = [x for x in resource.staff if x.role == "doctor"]
        trimmed = resource.model_copy(update={"staff": [x for x in resource.staff if x != doctors[0]]})
        return trimmed, queue

    monkeypatch.setattr(service, "generate", faulty)
    with pytest.raises(ScenarioValidationError, match="doctors_on_duty"):
        sim.apply_scenario("surge")
    monkeypatch.undo()
    m = metrics()
    assert m.data_version == 1 and m.patients_waiting == 12


def test_manual_overrides_create_custom_scenario(clean_state):
    res = sim.apply_scenario(
        "surge",
        sim.ScenarioOverrides(beds_available=3, waiting_patients=20, pending_investigations=5, doctors_on_duty=5),
    )
    m = metrics()
    assert res.run.scenario_key == "custom" and res.run.trigger == "manual"
    assert res.run.scenario_name == "Custom (based on Emergency Surge)"
    assert m.patients_waiting == 20 and m.beds.available == 3 and m.pending_investigations == 5
    assert {s.role: s.on_duty for s in m.staff}["doctor"] == 5


def test_invalid_overrides_rejected_without_touching_data(clean_state):
    sim.apply_scenario("normal")
    for bad in (
        sim.ScenarioOverrides(window_minutes=60, avg_wait_minutes=60),  # window cannot hold the waits
        sim.ScenarioOverrides(pending_investigations=100),  # more pending than active patients
        sim.ScenarioOverrides(department_workload={"NOPE": 1.0}),  # unknown department
    ):
        with pytest.raises(ScenarioValidationError):
            sim.apply_scenario("normal", bad)
    assert sim.current_state().data_version == 1
    assert metrics().patients_waiting == 12


def test_unknown_scenario(clean_state):
    with pytest.raises(ScenarioNotFoundError):
        sim.apply_scenario("nope")


def test_randomize_produces_valid_custom_scenario(clean_state):
    res = sim.randomize_scenario(seed=42)
    m = metrics()
    assert res.run.trigger == "randomize" and res.run.scenario_key == "custom"
    assert m.patients_waiting == res.run.parameters["waiting_patients"]
    assert all(c["ok"] for c in res.run.validation)


# ---------------------------------------------------------------- API
def test_api_apply_current_history_reset(clean_state):
    client = module_client()
    assert [s["key"] for s in client.get("/api/scenarios").json()] == ["normal", "surge", "recovery"]
    r = client.post("/api/scenarios/apply", json={"scenario_key": "surge"})
    assert r.status_code == 200 and r.json()["state"]["data_version"] == 1
    cur = client.get("/api/scenarios/current").json()
    assert cur["scenario_name"] == "Emergency Surge"
    assert client.get("/api/scenarios").json()[1]["is_current"] is True
    client.post("/api/scenarios/reset")
    hist = client.get("/api/scenarios/history", params={"limit": 1}).json()
    assert hist["total"] == 2 and len(hist["items"]) == 1 and hist["items"][0]["trigger"] == "reset"


def test_api_errors_are_consistent(clean_state):
    client = module_client()
    assert client.post("/api/scenarios/apply", json={"scenario_key": "bogus"}).status_code == 422
    bad = client.post(
        "/api/scenarios/apply",
        json={"scenario_key": "normal", "overrides": {"window_minutes": 60, "avg_wait_minutes": 60}},
    )
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "scenario_validation_failed"
    assert client.post("/api/scenarios/apply", json={"scenario_key": "normal",
                                                     "overrides": {"beds_available": -1}}).status_code == 422
    assert client.get("/api/scenarios/history", params={"limit": 0}).status_code == 422
    assert client.get("/api/scenarios/current").json()["data_version"] == 0  # nothing was applied


def test_api_randomize(clean_state):
    r = module_client().post("/api/scenarios/randomize")
    assert r.status_code == 200 and r.json()["run"]["trigger"] == "randomize"


@pytest.mark.parametrize("seed", range(25))
def test_randomize_is_robust_across_seeds(clean_state, seed):
    res = sim.randomize_scenario(seed=seed)
    assert res.run.status == "applied" and all(c["ok"] for c in res.run.validation)
