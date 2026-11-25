"""Demonstration scoring heuristics (pure functions, no database)."""
import pytest

from app.modules.ai_orchestration.domain.citations import RetrievedRef
from app.modules.ai_orchestration.domain.comparison_scoring import (
    KEY_METRICS,
    SCORING_NOTE,
    ScoreInputs,
    score_accuracy,
    score_answer,
    score_citations,
    score_completeness,
    score_relevance,
)

METRICS = {
    "patients_waiting": 38, "avg_wait_minutes": 75.0, "max_wait_minutes": 121.0, "beds_available": 1,
    "beds_total": 18, "doctors_on_duty": 3, "nurses_on_duty": 4, "pending_investigations": 28,
}

FULL = (
    "Current situation (from data): Emergency Surge, data version 2. 38 patients waiting; average wait 75.0 min; "
    "maximum wait 121.0 minutes. 1 of 18 beds available. 3 doctors on duty and 4 nurses on duty. "
    "28 pending investigations.\n"
    "Bottlenecks and shortages: beds and staffing.\n"
    "Waiting-time issues: long waits.\n"
    "Relevant policy (retrieved): escalate [Source: Hospital Escalation Procedures, p.2]\n"
    "Recommended administrative actions: consider opening surge capacity per the escalation procedure."
)


def test_all_key_metrics_correct_when_every_number_matches():
    acc = score_accuracy(FULL, METRICS)
    assert acc["score"] == 1.0 and acc["correct"] == len(KEY_METRICS) and acc["wrong"] == 0
    assert acc["wrong_numbers"] == {}


def test_wrong_numbers_are_flagged_per_metric():
    text = FULL.replace("38 patients waiting", "99 patients waiting").replace("1 of 18 beds available", "6 beds available")
    acc = score_accuracy(text, METRICS)
    assert acc["wrong"] == 2
    assert acc["wrong_numbers"] == {"patients_waiting": [99.0], "beds_available": [6.0]}
    assert acc["per_metric"]["patients_waiting"]["status"] == "wrong"
    assert acc["per_metric"]["avg_wait_minutes"]["status"] == "correct"
    assert acc["score"] == pytest.approx((len(KEY_METRICS) - 2 - 1) / len(KEY_METRICS), abs=0.01)  # beds_total lost too


def test_unmentioned_metrics_are_not_counted_as_wrong():
    acc = score_accuracy("The department is busy. 38 patients waiting.", METRICS)
    assert acc["correct"] == 1 and acc["wrong"] == 0 and acc["not_mentioned"] == len(KEY_METRICS) - 1
    assert acc["score"] == pytest.approx(1 / len(KEY_METRICS), abs=0.01)


def test_data_version_is_never_mistaken_for_a_metric_value():
    acc = score_accuracy("Patients waiting (data version 2). Pending investigations (data version 2).", METRICS)
    assert acc["wrong"] == 0 and acc["correct"] == 0


def test_floats_tolerate_rounding_but_integers_must_match_exactly():
    assert score_accuracy("average wait 75 min", METRICS)["per_metric"]["avg_wait_minutes"]["status"] == "correct"
    assert score_accuracy("average wait of about 75.4 minutes", METRICS)["per_metric"]["avg_wait_minutes"]["status"] == "correct"
    assert score_accuracy("average wait 80 min", METRICS)["per_metric"]["avg_wait_minutes"]["status"] == "wrong"
    assert score_accuracy("39 patients waiting", METRICS)["per_metric"]["patients_waiting"]["status"] == "wrong"


@pytest.mark.parametrize("phrase,metric", [
    ("There are 38 patients currently waiting", "patients_waiting"),
    ("Patients waiting: 38", "patients_waiting"),
    ("The average waiting time is 75 minutes", "avg_wait_minutes"),
    ("Available beds: 1", "beds_available"),
    ("Only 1 bed is available", "beds_available"),
    ("Doctors on duty: 3", "doctors_on_duty"),
    ("4 nurses are on duty", "nurses_on_duty"),
    ("Pending investigations: 28", "pending_investigations"),
    ("the longest wait is 121 minutes", "max_wait_minutes"),
    ("a total of 18 beds", "beds_total"),
])
def test_common_phrasings_are_recognised(phrase, metric):
    assert score_accuracy(phrase, METRICS)["per_metric"][metric]["status"] == "correct"


def test_completeness_lists_missing_elements():
    full = score_completeness(FULL, "Emergency Surge", 2)
    assert full["score"] == 1.0 and full["missing"] == []
    bare = score_completeness("Things are busy.", "Emergency Surge", 2)
    assert bare["score"] == 0.0 and "citation_present" in bare["missing"]
    # scenario name OR data version satisfies the "stated" check
    assert score_completeness("data version 2", "Emergency Surge", 2)["present"]["scenario_or_version_stated"]
    assert score_completeness("Emergency Surge", "Emergency Surge", 2)["present"]["scenario_or_version_stated"]
    assert not score_completeness("data version 3", "Emergency Surge", 2)["present"]["scenario_or_version_stated"]


def test_relevance_rewards_topics_and_penalises_clinical_advice():
    assert score_relevance(FULL)["score"] == 1.0
    advice = score_relevance(FULL + " We recommend a treatment plan and a diagnosis for the patients.")
    assert advice["score"] == 0.75 and "diagnosis" in advice["out_of_scope_terms"]
    assert score_relevance("Hello.")["score"] == 0.0


def test_citation_correctness_checks_against_retrieved_refs():
    refs = [RetrievedRef("Hospital Escalation Procedures", 2)]
    ok = score_citations("[Source: Hospital Escalation Procedures, p.2]", refs)
    assert ok["score"] == 1.0 and not ok["no_citations"]
    mixed = score_citations("[Source: Hospital Escalation Procedures, p.2] [Source: Invented Handbook, p.9]", refs)
    assert mixed["score"] == 0.5 and mixed["check"]["unverified"][0]["document"] == "Invented Handbook"
    wrong_page = score_citations("[Source: Hospital Escalation Procedures, p.7]", refs)
    assert wrong_page["score"] == 0.0
    none = score_citations("No citations here.", refs)
    assert none["score"] is None and none["no_citations"]


def test_overall_score_is_the_mean_of_available_scores_and_carries_the_disclaimer():
    inputs = ScoreInputs(answer=FULL, metrics=METRICS, retrieved=[RetrievedRef("Hospital Escalation Procedures", 2)],
                         scenario_name="Emergency Surge", data_version=2)
    result = score_answer(inputs)
    assert result["overall_demo_score"] == 1.0
    assert "not a formal benchmark" in result["note"].lower() and result["note"] == SCORING_NOTE
    no_cites = score_answer(ScoreInputs(answer="38 patients waiting.", metrics=METRICS, retrieved=[],
                                        scenario_name=None, data_version=None))
    assert no_cites["citation_correctness"]["score"] is None  # excluded from the mean, not counted as zero
    assert no_cites["overall_demo_score"] is not None


# ---- false positives seen in a real Ollama comparison (2026-11-25): correct answers were scored 0% ----
RECOVERY = {
    "patients_waiting": 9, "avg_wait_minutes": 18.0, "max_wait_minutes": 29.2, "beds_available": 10,
    "beds_total": 16, "doctors_on_duty": 7, "nurses_on_duty": 12, "pending_investigations": 4,
}


@pytest.mark.parametrize("line", [
    "Waiting patients per doctor on duty: 1.3 ratio",
    "Waiting patients per nurse on duty: 0.8 ratio",
    "high waiting patients per doctor on duty ratio (1.3) and waiting patients per nurse on duty ratio (0.8)",
    "There are 1.3 waiting patients per doctor on duty.",
])
def test_staffing_ratios_are_not_read_as_head_counts_or_queue_length(line):
    assert score_accuracy(line, RECOVERY)["wrong_numbers"] == {}


@pytest.mark.parametrize("line", [
    "AMBER (Elevated load): average waiting time 31 to 60 minutes; 16 to 30 patients waiting; 2 to 4 available "
    "beds; 4 to 6 waiting patients per doctor; 11 to 20\npending investigation requests.",
    "RED (Surge): average waiting time above 60 minutes; more than 30 patients waiting; 1 or fewer available beds; "
    "more than 6 waiting patients per doctor; more than 20 pending investigation requests.",
    "GREEN: average waiting time 30 minutes or less; 15 or fewer patients\nwaiting; 5 or more available beds; "
    "3 or fewer waiting patients per doctor on duty; 10 or fewer pending investigation requests.",
    "Up to 10 pending requests: normal operation. Average waiting time within the GREEN threshold of 30 minutes or less.",
    "Average waiting time: GREEN <=30; AMBER 31-60; RED >60. Patients waiting: GREEN <=15; AMBER 16-30; RED >30.",
    "Available beds (bands: GREEN >=5; AMBER 2–4; RED <=1)",
    "The surge observation area (up to 4 additional beds available) may be opened.",
])
def test_quoted_policy_thresholds_are_not_claims_about_current_data(line):
    assert score_accuracy(line, RECOVERY)["wrong_numbers"] == {}


def test_real_data_section_with_band_annotations_is_scored_on_the_data_values_only():
    text = (
        "- Average waiting time: 18 min -> GREEN (bands: GREEN <=30; AMBER 31-60; RED >60)\n"
        "- Patients waiting: 9 patients -> GREEN (bands: GREEN <=15; AMBER 16-30; RED >30)\n"
        "- Available beds: 10 beds -> GREEN (bands: GREEN >=5; AMBER 2-4; RED <=1)\n"
        "- Waiting patients per doctor on duty: 1.3 ratio\n"
        "- Pending investigation requests: 4 requests\n"
    )
    acc = score_accuracy(text, RECOVERY)
    assert acc["wrong_numbers"] == {} and acc["correct"] == 4


@pytest.mark.parametrize(("line", "metric", "value"), [
    ("Average waiting time: 30 min -> GREEN (bands: GREEN <=30)", "avg_wait_minutes", 30.0),
    ("Patients waiting: 30 patients", "patients_waiting", 30.0),
    ("Doctors on duty: 3", "doctors_on_duty", 3.0),
    ("2 nurses on duty", "nurses_on_duty", 2.0),
    ("There are 20 pending investigations.", "pending_investigations", 20.0),
    ("Beds available: 4 (up to 4 more may be opened)", "beds_available", 4.0),
])
def test_wrong_current_values_are_still_flagged(line, metric, value):
    assert score_accuracy(line, RECOVERY)["wrong_numbers"] == {metric: [value]}


# ---- real cloud-model comparison: bold numbers were invisible (0%) and per-area counts were "wrong" ----
@pytest.mark.parametrize("text", [
    "**9** patients waiting. **10** beds available. **4** pending investigations.",
    "Patients waiting: **9**. Beds available: __10__. Pending investigations: `4`.",
    "**Patients waiting:** 9. **Beds available:** 10. **Pending investigations:** 4.",
])
def test_markdown_emphasis_does_not_hide_numbers(text):
    acc = score_accuracy(text, RECOVERY)
    assert acc["correct"] == 3 and acc["wrong_numbers"] == {}


@pytest.mark.parametrize("line", [
    "By department: Pediatric Emergency has 1 doctor on duty, who is busy, and Resuscitation has 1 nurse on duty.",
    "Acute Care 4 available beds, Minor Injuries 2 available beds.",
    "- **Pediatric Emergency:** 1 doctor on duty, 2 beds available",
    "Resuscitation: nurses on duty 1.",
    "Minor Injuries has 3 pending investigations.",
])
def test_counts_for_one_department_area_are_not_department_totals(line):
    acc = score_accuracy(line, RECOVERY)
    assert acc["wrong_numbers"] == {} and acc["correct"] == 0


@pytest.mark.parametrize("line", [
    "The emergency department has 3 doctors on duty.",
    "Acute Care is the busiest area. There are 3 doctors on duty.",
    "Minor Injuries has the highest occupancy; 3 doctors on duty overall.",
    "Resuscitation is quiet.\nDoctors on duty: 3",
    "**3** doctors on duty.",
])
def test_wrong_department_totals_are_still_flagged_near_area_names(line):
    assert score_accuracy(line, RECOVERY)["wrong_numbers"] == {"doctors_on_duty": [3.0]}


def test_every_simulated_department_area_is_known_to_the_scorer():
    from app.modules.ai_orchestration.domain.comparison_scoring import AREA_NAMES
    from app.modules.simulation.application.generator import DEPARTMENT_NAMES

    assert {n.lower() for n in DEPARTMENT_NAMES.values()} == set(AREA_NAMES)
