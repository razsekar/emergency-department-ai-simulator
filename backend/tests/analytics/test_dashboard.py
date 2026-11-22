from datetime import timedelta

from sqlalchemy import create_engine, text

from tests.simdb import module_client
from app.modules.analytics import public as analytics
from app.modules.simulation import public as sim
from app.platform.db import unit_of_work


def metrics():
    with unit_of_work() as s:
        return analytics.get_dashboard_metrics(s)


def test_empty_database_reports_zero_version_and_no_data(clean_state):
    m = metrics()
    assert m.data_version == 0 and m.scenario_key is None
    assert m.total_visits == m.patients_waiting == m.beds.total == m.pending_investigations == 0
    assert m.avg_wait_minutes == 0.0


def test_dashboard_values_match_independent_sql_over_raw_records(clean_state):
    sim.apply_scenario("surge")
    m = metrics()
    eng = create_engine(clean_state)
    with eng.connect() as c:
        one = lambda q: c.execute(text(q)).scalar_one()  # noqa: E731
        assert m.total_visits == one("select count(*) from patient_queue.patient_visits")
        assert m.patients_waiting == one("select count(*) from patient_queue.patient_visits where status='waiting'")
        assert m.patients_in_treatment == one(
            "select count(*) from patient_queue.patient_visits where status='in_treatment'")
        assert m.completed_discharges == one(
            "select count(*) from patient_queue.patient_visits where status='discharged'")
        assert m.critical_patients == one(
            "select count(*) from patient_queue.patient_visits where triage_category='critical' "
            "and status<>'discharged'")
        assert m.beds.total == one("select count(*) from resource_management.beds")
        assert m.beds.occupied == one("select count(*) from resource_management.beds where status='occupied'")
        assert m.pending_investigations == one(
            "select count(*) from patient_queue.investigation_requests where status='pending'")
        avg = one(
            "select avg(extract(epoch from (r.reference_time - v.arrival_at))/60.0) "
            "from patient_queue.patient_visits v, patient_queue.dataset_clock r where v.status='waiting'")
        assert abs(m.avg_wait_minutes - float(avg)) < 0.01
    eng.dispose()
    assert sum(b.count for b in m.waiting_time_distribution) == m.patients_waiting
    assert sum(w.waiting for w in m.department_workload) == m.patients_waiting
    assert sum(w.in_treatment for w in m.department_workload) == m.patients_in_treatment
    assert sum(w.pending_investigations for w in m.department_workload) == m.pending_investigations
    assert sum(a.count for a in m.arrivals_over_time) <= m.total_visits


def test_arrivals_over_time_cover_requested_window(clean_state):
    sim.apply_scenario("normal")
    m = metrics()
    assert len(m.arrivals_over_time) == 8  # 240 min / 30 min buckets
    assert m.arrivals_over_time[1].bucket_start - m.arrivals_over_time[0].bucket_start == timedelta(minutes=30)


def test_baseline_surge_recovery_changes_version_and_metrics(clean_state):
    """Critical acceptance (data half): changing the scenario changes the records AND the metrics."""
    sim.apply_scenario("normal")
    base = metrics()
    sim.apply_scenario("surge")
    surge = metrics()
    sim.apply_scenario("recovery")
    rec = metrics()

    assert (base.data_version, surge.data_version, rec.data_version) == (1, 2, 3)
    assert (base.scenario_key, surge.scenario_key, rec.scenario_key) == ("normal", "surge", "recovery")

    assert surge.patients_waiting > base.patients_waiting > rec.patients_waiting
    assert surge.avg_wait_minutes > rec.avg_wait_minutes > base.avg_wait_minutes
    assert surge.beds.available < base.beds.available < rec.beds.available
    assert surge.pending_investigations > base.pending_investigations > rec.pending_investigations
    assert surge.total_visits != base.total_visits
    assert surge.resource_utilization.doctors_pct > base.resource_utilization.doctors_pct
    # a different number of patient records proves data (not a frontend variable) changed
    assert len({base.total_visits, surge.total_visits, rec.total_visits}) >= 2


def test_dashboard_has_no_stale_values_after_reapplying_same_scenario(clean_state):
    sim.apply_scenario("surge")
    first = metrics()
    sim.apply_scenario("surge")
    second = metrics()
    assert second.data_version == first.data_version + 1


def test_api_dashboard_metrics_and_resource_utilization(clean_state):
    client = module_client()
    client.post("/api/scenarios/apply", json={"scenario_key": "surge"})
    body = client.get("/api/dashboard/metrics").json()
    assert body["data_version"] == 1 and body["patients_waiting"] == 38 and body["beds"]["available"] == 1
    util = client.get("/api/dashboard/resource-utilization").json()
    assert util["beds_pct"] == 93.8 and {f["code"] for f in util["facilities"]} == {"LAB", "XRAY", "CT", "US"}
    assert sum(f["pending_requests"] for f in util["facilities"]) == 28
    assert client.get("/api/dashboard/metrics", params={"bucket_minutes": 1}).status_code == 422
