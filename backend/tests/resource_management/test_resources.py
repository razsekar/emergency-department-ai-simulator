
from tests.simdb import module_client
from app.modules.patient_queue import public as queue
from app.modules.resource_management import public as resources
from app.modules.simulation import public as sim
from app.platform.db import unit_of_work


def test_bed_availability_surge_vs_recovery(clean_state):
    sim.apply_scenario("surge")
    with unit_of_work() as s:
        b = resources.get_bed_availability(s)
    assert (b.total_beds, b.occupied_beds, b.available_beds, b.utilization_pct) == (16, 15, 1, 93.8)
    assert sum(d.total_beds for d in b.by_department) == 16
    assert sum(d.available_beds for d in b.by_department) == 1

    sim.apply_scenario("recovery")
    with unit_of_work() as s:
        b = resources.get_bed_availability(s)
        one = resources.get_bed_availability(s, department_code="ACUTE")
    assert (b.occupied_beds, b.available_beds) == (6, 10)
    assert [d.department_code for d in one.by_department] == ["ACUTE"]


def test_staff_availability_by_role_and_department(clean_state):
    sim.apply_scenario("surge")
    with unit_of_work() as s:
        all_staff = resources.get_staff_availability(s)
        doctors = resources.get_staff_availability(s, role="doctor")
    assert (all_staff.on_duty, all_staff.available) == (7, 0)  # 3 doctors + 4 nurses, all busy in a surge
    assert {t.role: t.on_duty for t in all_staff.totals_by_role} == {"doctor": 3, "nurse": 4}
    assert doctors.on_duty == 3 and all(g.role == "doctor" for g in doctors.groups)

    sim.apply_scenario("recovery")
    with unit_of_work() as s:
        rec = resources.get_staff_availability(s)
    assert rec.on_duty == 19 and rec.available > 0


def test_department_capacity_and_facilities(clean_state):
    sim.apply_scenario("normal")
    with unit_of_work() as s:
        deps = resources.get_department_capacity(s)
        fac = resources.list_facilities(s)
    assert {d.department_code for d in deps} == {"ACUTE", "RESUS", "MINOR", "PEDS"}
    assert sum(d.bed_capacity for d in deps) == 18 and sum(d.occupied_beds for d in deps) == 10
    assert sum(d.doctors_on_duty for d in deps) == 6 and sum(d.nurses_on_duty for d in deps) == 10
    assert {f.code for f in fac} == {"LAB", "XRAY", "CT", "US"}


def test_bed_and_staff_pagination(clean_state):
    sim.apply_scenario("normal")
    with unit_of_work() as s:
        p1 = resources.list_beds(s, page=1, page_size=10)
        p2 = resources.list_beds(s, page=2, page_size=10)
        occupied = resources.list_beds(s, status="occupied")
        nurses = resources.list_staff(s, role="nurse")
    assert p1.total == 18 and len(p1.items) == 10 and len(p2.items) == 8
    assert not {b.ref for b in p1.items} & {b.ref for b in p2.items}
    assert occupied.total == 10 and nurses.total == 10


def test_occupied_beds_match_patient_bed_references(clean_state):
    """Cross-module consistency: every occupied bed has exactly one in-treatment visit."""
    sim.apply_scenario("surge")
    with unit_of_work() as s:
        occupied = {b.ref for b in resources.list_beds(s, status="occupied", page_size=200).items}
        treated = queue.get_queue(s, queue.QueueFilter(status="in_treatment"), page_size=200)
    assert {r.bed_ref for r in treated.items} == occupied and len(treated.items) == len(occupied)


def test_empty_resources_are_safe(clean_state):
    with unit_of_work() as s:
        b = resources.get_bed_availability(s)
        st = resources.get_staff_availability(s)
    assert b.total_beds == 0 and b.utilization_pct == 0.0 and st.on_duty == 0


def test_api_resources(clean_state):
    c = module_client()
    c.post("/api/scenarios/apply", json={"scenario_key": "surge"})
    assert c.get("/api/resources/beds/availability").json()["available_beds"] == 1
    assert c.get("/api/resources/staff/availability", params={"role": "doctor"}).json()["on_duty"] == 3
    assert len(c.get("/api/resources/departments").json()) == 4
    assert len(c.get("/api/resources/facilities").json()) == 4
    page = c.get("/api/resources/beds", params={"status": "occupied", "page_size": 5}).json()
    assert page["total"] == 15 and len(page["items"]) == 5
    assert c.get("/api/resources/staff", params={"role": "surgeon"}).status_code == 422
    assert c.get("/api/resources/beds", params={"page_size": 0}).status_code == 422
