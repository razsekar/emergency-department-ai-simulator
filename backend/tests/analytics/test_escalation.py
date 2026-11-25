"""Deterministic GREEN/AMBER/RED assessment. Pure function: no database needed."""
import pytest

from app.modules.analytics import public as analytics

GREEN_BASE = {"patients_waiting": 10, "avg_wait_minutes": 20.0, "beds_available": 8,
              "doctors_on_duty": 6, "nurses_on_duty": 10, "pending_investigations": 5}


def m(**over):
    return {**GREEN_BASE, **over}


def level(**over):
    return analytics.assess_escalation(m(**over)).level


# The three built-in scenarios, with the values the real database produced in the Ollama demo run.
NORMAL = {"patients_waiting": 12, "avg_wait_minutes": 15.0, "beds_available": 8,
          "doctors_on_duty": 6, "nurses_on_duty": 10, "pending_investigations": 5}
SURGE = {"patients_waiting": 38, "avg_wait_minutes": 75.0, "beds_available": 1,
         "doctors_on_duty": 3, "nurses_on_duty": 4, "pending_investigations": 28}
RECOVERY = {"patients_waiting": 9, "avg_wait_minutes": 18.0, "beds_available": 10,
            "doctors_on_duty": 7, "nurses_on_duty": 12, "pending_investigations": 4}


def test_builtin_scenarios_are_green_red_green():
    assert analytics.assess_escalation(NORMAL).level == "GREEN"
    assert analytics.assess_escalation(SURGE).level == "RED"
    assert analytics.assess_escalation(RECOVERY).level == "GREEN"


def test_surge_has_every_indicator_red_and_normal_has_none():
    surge = analytics.assess_escalation(SURGE)
    assert surge.red_count == 6 and all(i.band == "RED" for i in surge.indicators)
    normal = analytics.assess_escalation(NORMAL)
    assert normal.red_count == 0 and normal.amber_or_worse_count == 0 and all(i.band == "GREEN" for i in normal.indicators)


@pytest.mark.parametrize("wait,band", [(0, "GREEN"), (30, "GREEN"), (30.5, "AMBER"), (31, "AMBER"), (60, "AMBER"), (60.5, "RED"), (61, "RED")])
def test_average_wait_bands(wait, band):
    a = analytics.assess_escalation(m(avg_wait_minutes=wait))
    assert {i.key: i.band for i in a.indicators}["avg_wait_minutes"] == band


@pytest.mark.parametrize("waiting,band", [(15, "GREEN"), (16, "AMBER"), (30, "AMBER"), (31, "RED")])
def test_patients_waiting_bands(waiting, band):
    a = analytics.assess_escalation(m(patients_waiting=waiting, doctors_on_duty=100, nurses_on_duty=100))
    assert {i.key: i.band for i in a.indicators}["patients_waiting"] == band


@pytest.mark.parametrize("beds,band", [(10, "GREEN"), (5, "GREEN"), (4, "AMBER"), (2, "AMBER"), (1, "RED"), (0, "RED")])
def test_available_bed_bands_lower_is_worse(beds, band):
    a = analytics.assess_escalation(m(beds_available=beds))
    assert {i.key: i.band for i in a.indicators}["beds_available"] == band


@pytest.mark.parametrize("pending,band", [(10, "GREEN"), (11, "AMBER"), (20, "AMBER"), (21, "RED")])
def test_pending_investigation_bands(pending, band):
    a = analytics.assess_escalation(m(pending_investigations=pending))
    assert {i.key: i.band for i in a.indicators}["pending_investigations"] == band


@pytest.mark.parametrize("waiting,doctors,band", [(9, 3, "GREEN"), (12, 3, "AMBER"), (18, 3, "AMBER"), (21, 3, "RED")])
def test_waiting_per_doctor_bands(waiting, doctors, band):
    a = analytics.assess_escalation(m(patients_waiting=waiting, doctors_on_duty=doctors))
    assert {i.key: i.band for i in a.indicators}["waiting_per_doctor"] == band


@pytest.mark.parametrize("waiting,nurses,band", [(8, 2, "GREEN"), (10, 2, "AMBER"), (16, 2, "AMBER"), (18, 2, "RED")])
def test_waiting_per_nurse_bands(waiting, nurses, band):
    a = analytics.assess_escalation(m(patients_waiting=waiting, nurses_on_duty=nurses))
    assert {i.key: i.band for i in a.indicators}["waiting_per_nurse"] == band


# -- the combination rule from the policy
def test_a_single_red_indicator_raises_the_level_to_amber():
    assert level(beds_available=1) == "AMBER"


def test_one_amber_indicator_alone_stays_green():
    assert level(avg_wait_minutes=45) == "GREEN"


def test_two_amber_indicators_make_amber():
    assert level(avg_wait_minutes=45, pending_investigations=15) == "AMBER"


def test_two_red_indicators_make_red():
    assert level(beds_available=0, pending_investigations=25) == "RED"


def test_one_red_and_one_amber_is_amber_not_red():
    assert level(beds_available=0, pending_investigations=15) == "AMBER"


# -- robustness
def test_zero_staff_with_patients_waiting_is_red_not_a_division_error():
    a = analytics.assess_escalation(m(doctors_on_duty=0, nurses_on_duty=0))
    bands = {i.key: i.band for i in a.indicators}
    assert bands["waiting_per_doctor"] == "RED" and bands["waiting_per_nurse"] == "RED"
    assert a.level == "RED"


def test_nobody_waiting_and_no_staff_is_not_penalised():
    a = analytics.assess_escalation(m(patients_waiting=0, avg_wait_minutes=None, doctors_on_duty=0, nurses_on_duty=0))
    assert {i.key: i.band for i in a.indicators}["waiting_per_doctor"] == "UNKNOWN"
    assert a.level == "GREEN"


def test_missing_metrics_are_unknown_and_excluded_from_counts():
    a = analytics.assess_escalation({"beds_available": 0})
    assert a.level == "AMBER"  # one RED indicator; the rest unknown
    assert sum(1 for i in a.indicators if i.band == "UNKNOWN") == 5


def test_result_is_serialisable_and_names_its_source():
    d = analytics.assess_escalation(SURGE).as_dict()
    assert d["level"] == "RED" and len(d["indicators"]) == 6
    assert "Escalation" in d["policy_reference"] and "at least two indicators" in d["rule"]
