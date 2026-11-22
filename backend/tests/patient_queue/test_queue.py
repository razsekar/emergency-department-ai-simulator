import re

import pytest
from sqlalchemy import create_engine, text

from tests.simdb import module_client
from app.modules.patient_queue import public as queue
from app.modules.simulation import public as sim
from app.platform.db import unit_of_work


@pytest.fixture()
def surge(clean_state):
    sim.apply_scenario("surge")
    return clean_state


def q(**kw):
    page = kw.pop("page", 1)
    size = kw.pop("page_size", 200)
    with unit_of_work() as s:
        return queue.get_queue(s, queue.QueueFilter(**kw), page, size)


def test_queue_retrieval_and_status_filter(surge):
    waiting = q(status="waiting")
    assert waiting.total == 38 and all(r.status == "waiting" for r in waiting.items)
    assert all(re.fullmatch(r"SIM-PAT-\d{3,}", r.patient_ref) for r in waiting.items)
    assert q(status="in_treatment").total == 15
    assert q().total == 100


def test_filters_match_raw_sql_counts(surge):
    eng = create_engine(surge)
    with eng.connect() as c:
        dept = c.execute(text("select count(*) from patient_queue.patient_visits where department_code='ACUTE'")).scalar_one()
        crit = c.execute(text("select count(*) from patient_queue.patient_visits where triage_category='critical'")).scalar_one()
        pend = c.execute(text(
            "select count(distinct visit_id) from patient_queue.investigation_requests where status='pending'")).scalar_one()
    eng.dispose()
    assert q(department_code="ACUTE").total == dept
    assert q(triage_category="critical").total == crit
    assert q(investigation_status="pending").total == pend


def test_waiting_duration_and_arrival_time_filters(surge):
    slow = q(status="waiting", min_wait_minutes=75)
    assert slow.total > 0 and all(r.waiting_minutes >= 75 for r in slow.items)
    fast = q(status="waiting", max_wait_minutes=60)
    assert all(r.waiting_minutes <= 60 for r in fast.items)
    mid = q(status="waiting", min_wait_minutes=60, max_wait_minutes=75)
    assert all(60 <= r.waiting_minutes <= 75 for r in mid.items)
    assert slow.total + mid.total + fast.total >= 38  # the three bands cover every waiting patient
    recent = q(arrived_within_minutes=60)
    assert 0 < recent.total < 100 and all(r.waiting_minutes >= 0 for r in recent.items)


def test_pagination(surge):
    p1 = q(status="waiting", page=1, page_size=10)
    p4 = q(status="waiting", page=4, page_size=10)
    assert len(p1.items) == 10 and p1.total == 38 and len(p4.items) == 8
    refs = {r.visit_ref for pg in (1, 2, 3, 4) for r in q(status="waiting", page=pg, page_size=10).items}
    assert len(refs) == 38


def test_waiting_metrics_distribution_and_filters(surge):
    with unit_of_work() as s:
        m = queue.get_waiting_metrics(s)
        acute = queue.get_waiting_metrics(s, department_code="ACUTE")
        window = queue.get_waiting_metrics(s, window_minutes=60)
    assert m.waiting_patients == 38 and abs(m.avg_wait_minutes - 75) <= 7.5
    assert m.max_wait_minutes >= m.avg_wait_minutes > 0
    assert sum(b.count for b in m.distribution) == 38
    assert 0 < acute.waiting_patients < 38
    assert window.waiting_patients < 38  # only those who arrived within the last hour


def test_pending_investigation_delays(surge):
    with unit_of_work() as s:
        p = queue.get_pending_investigations(s, limit=5)
    assert p.pending_count == 28 and len(p.items) == 5
    assert abs(p.avg_age_minutes - 60) <= 9
    assert p.items[0].age_minutes >= p.items[-1].age_minutes
    assert all(i.delay_minutes == max(0.0, round(i.age_minutes - i.expected_minutes, 1)) for i in p.items)
    assert sum(f.pending for f in p.by_facility) == 28


def test_empty_queue_is_safe(clean_state):
    assert q().total == 0
    with unit_of_work() as s:
        assert queue.get_waiting_metrics(s).waiting_patients == 0
        assert queue.get_pending_investigations(s).pending_count == 0


def test_dataset_rejects_investigation_for_unknown_visit(clean_state):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    spec = queue.DatasetSpec(
        reference_time=now, visits=[],
        investigations=[queue.InvestigationSpec(visit_ref="SIM-VIS-9999", facility_code="LAB",
                                                investigation_type="LAB", status="pending", requested_at=now,
                                                expected_minutes=30)],
    )
    with pytest.raises(ValueError):
        with unit_of_work() as s:
            queue.replace_dataset(s, spec)


def test_api_queue_filters_and_validation(surge):
    c = module_client()
    body = c.get("/api/patient-queue", params={"status": "waiting", "department": "ACUTE", "page_size": 5}).json()
    assert body["page_size"] == 5 and len(body["items"]) <= 5 and body["total"] > 0
    assert all(i["department_code"] == "ACUTE" and i["status"] == "waiting" for i in body["items"])
    assert c.get("/api/patient-queue", params={"status": "bogus"}).status_code == 422
    assert c.get("/api/patient-queue", params={"page_size": 1000}).status_code == 422
    assert c.get("/api/patient-queue/waiting-metrics").json()["waiting_patients"] == 38
    assert c.get("/api/patient-queue/pending-investigations").json()["pending_count"] == 28
