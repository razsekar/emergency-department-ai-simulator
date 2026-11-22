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
