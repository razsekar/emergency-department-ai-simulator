"""Automated DEMONSTRATION scoring of model answers. Pure functions, no I/O.

IMPORTANT: these are transparent regex heuristics for a classroom demonstration. They are NOT a formal benchmark:
they can miss correct numbers phrased unusually and cannot judge reasoning quality, and a high score does not mean
an answer is operationally sound. Each score documents exactly what it measured.

Scores are fractions in [0, 1], or None when the measure does not apply (for example no citations were made).

  accuracy              fraction of the KEY_METRICS whose stated value matches the true snapshot value. A metric is
                        "correct" when every number the answer states for it matches (floats within +/-0.5, integers
                        exactly), "wrong" when any stated number differs, and "not_mentioned" when no recognised
                        phrasing was found. Wrong numbers are listed explicitly. Policy limits ("31 to 60",
                        "more than 30", "15 or fewer", "<=30") and per-doctor/per-nurse ratios are not treated as
                        statements about current values, so a wrong value phrased as a limit is not detected.
  completeness          fraction of REQUIRED_ELEMENTS present (five labelled sections, at least one citation, and
                        the scenario name or data version stated).
  relevance             fraction of TOPIC_GROUPS addressed (waiting time, beds, staffing, investigations, policy,
                        recommendations), minus 0.25 if the answer strays into clinical advice terms (floor 0).
  citation_correctness  verified / total `[Source: <doc>, p.<n>]` citations, checked against what was actually
                        retrieved (None when the answer cites nothing).
  overall_demo_score    plain mean of the available scores above; for teaching discussion only.
"""
import re
from dataclasses import dataclass
from typing import Any

from app.modules.ai_orchestration.domain.citations import RetrievedRef, check_citations

SCORING_NOTE = (
    "Demonstration comparison, not a formal benchmark. Scores come from simple automated heuristics applied to "
    "identical, frozen scenario data and retrieved context; they check stated numbers, answer structure and citation "
    "validity, not reasoning quality."
)

FLOAT_TOLERANCE = 0.5

_NUM = r"(\d+(?:\.\d+)?)"
# Separator between a label and its number: spaces, ':', '=', '(', '~' or filler words. A digit must follow
# directly, so "waiting (data version 2)" never yields the version number.
_SEP = r"(?:\s|[:=(~]|\bis\b|\bwas\b|\bare\b|\bof\b|\bat\b|\babout\b|\bapproximately\b|\baround\b|\broughly\b)*"

# Quoted policy limits and band ranges are not claims about the current data; they are blanked before matching.
# The "[limit]" marker is not part of _SEP, so a label can never attach to a number across it.
_LIMIT = re.compile(
    rf"{_NUM}\s*(?:to|-|–)\s*{_NUM}"
    rf"|(?:\bup\s+to|\b(?:more|fewer|less|greater)\s+than|\babove|\bbelow|\bover|\bunder|\bat\s+(?:least|most)"
    rf"|<=|>=|≤|≥|<|(?<![-=])>)\s*{_NUM}"
    rf"|{_NUM}(?:\s*min(?:ute)?s?)?\s+or\s+(?:fewer|more|less)\b",
    re.IGNORECASE,
)

METRIC_PATTERNS: dict[str, list[str]] = {
    "patients_waiting": [
        rf"{_NUM}\s+(?:patients?|visits?|people)?\s*(?:are\s+|were\s+)?(?:currently\s+)?waiting\b(?!\s+(?:patients?\s+)?per\b)",
        rf"patients?\s+waiting{_SEP}{_NUM}",
        rf"waiting\s+(?:patients?|queue|count|room){_SEP}{_NUM}",
    ],
    "avg_wait_minutes": [
        rf"(?:average|avg\.?|mean)\s+(?:waiting|wait)(?:\s+time)?{_SEP}{_NUM}",
        rf"{_NUM}\s*(?:min(?:ute)?s?)\s+(?:average|avg|mean)\s+wait",
    ],
    "max_wait_minutes": [
        rf"(?:max(?:imum)?|longest)\s+(?:current\s+)?(?:waiting\s+time|wait\s+time|waiting|wait){_SEP}{_NUM}",
    ],
    "beds_available": [
        rf"{_NUM}\s+(?:of\s+\d+\s+)?beds?\s+(?:is\s+|are\s+)?(?:currently\s+)?(?:available|free|open|unoccupied)",
        rf"{_NUM}\s+(?:available|free|open)\s+beds?",
        rf"(?:available|free|open)\s+beds?{_SEP}{_NUM}",
        rf"beds?\s+available{_SEP}{_NUM}",
    ],
    "beds_total": [
        rf"{_NUM}\s+(?:total\s+)?beds?\s+(?:in\s+total|total)",
        rf"total\s+(?:of\s+)?(?:beds?|bed\s+capacity){_SEP}{_NUM}",
        rf"(?:out\s+of|of)\s+{_NUM}\s+(?:total\s+)?beds?",
    ],
    "doctors_on_duty": [
        rf"{_NUM}\s+doctors?\s+(?:are\s+)?on\s+duty",
        rf"(?<!per\s)doctors?\s+on\s+duty{_SEP}{_NUM}",
    ],
    "nurses_on_duty": [
        rf"{_NUM}\s+nurses?\s+(?:are\s+)?on\s+duty",
        rf"(?<!per\s)nurses?\s+on\s+duty{_SEP}{_NUM}",
    ],
    "pending_investigations": [
        rf"{_NUM}\s+(?:pending\s+)?investigations?(?:\s+requests?)?(?:\s+(?:are|were)\s+)?\s*pending",
        rf"{_NUM}\s+pending\s+investigations?",
        rf"pending\s+investigations?(?:\s+requests?)?{_SEP}{_NUM}",
    ],
}
KEY_METRICS = tuple(METRIC_PATTERNS)
_COMPILED = {k: [re.compile(p, re.IGNORECASE) for p in v] for k, v in METRIC_PATTERNS.items()}

SECTION_PATTERNS: dict[str, str] = {
    "current_situation": r"current\s+situation|situation\s*\(from\s+data\)",
    "bottlenecks_shortages": r"bottlenecks?|shortages?",
    "waiting_time_issues": r"waiting[\s-]time",
    "relevant_policy": r"relevant\s+policy|retrieved\s+policy|policy",
    "recommended_actions": r"recommended\s+(?:administrative\s+)?actions?|recommendations?",
}
REQUIRED_ELEMENTS = (*SECTION_PATTERNS, "citation_present", "scenario_or_version_stated")

TOPIC_GROUPS: dict[str, str] = {
    "waiting_time": r"wait(?:ing)?",
    "beds": r"\bbeds?\b|bed\s+capacity",
    "staffing": r"\bdoctors?\b|\bnurses?\b|\bstaff(?:ing)?\b",
    "investigations": r"investigations?",
    "policy": r"polic(?:y|ies)|procedure|protocol|guideline|\bsop\b",
    "recommendations": r"recommend|suggest|action|escalat",
}
OUT_OF_SCOPE = re.compile(r"\bdiagnos\w*|\bprescrib\w*|\bdosage\b|\bdose\b|treatment\s+plan|\bmedicat\w*", re.IGNORECASE)


@dataclass(frozen=True)
class ScoreInputs:
    answer: str | None
    metrics: dict[str, Any]  # the true snapshot metrics
    retrieved: list[RetrievedRef]  # unflagged chunks that were actually retrieved
    scenario_name: str | None
    data_version: int | None


def _matches(claimed: float, truth: Any) -> bool:
    if isinstance(truth, float):  # also covers 75.0-style values: tolerate rounding or a dropped decimal
        return abs(claimed - truth) <= FLOAT_TOLERANCE
    return claimed == truth


def _claims(answer: str, metric: str) -> list[float]:
    found: list[float] = []
    for pattern in _COMPILED[metric]:
        found += [float(m.group(1)) for m in pattern.finditer(answer)]
    return found


def score_accuracy(answer: str | None, metrics: dict[str, Any]) -> dict[str, Any]:
    text = _LIMIT.sub(" [limit] ", answer or "")
    per_metric: dict[str, dict[str, Any]] = {}
    correct = 0
    for metric in KEY_METRICS:
        truth = metrics.get(metric)
        claims = _claims(text, metric)
        if truth is None:
            status, wrong = "not_applicable", []
        elif not claims:
            status, wrong = "not_mentioned", []
        else:
            wrong = sorted({c for c in claims if not _matches(c, truth)})
            status = "wrong" if wrong else "correct"
        correct += status == "correct"
        per_metric[metric] = {"true_value": truth, "claimed": sorted(set(claims)), "status": status,
                              "wrong_numbers": wrong}
    applicable = sum(1 for m in per_metric.values() if m["status"] != "not_applicable")
    return {
        "score": round(correct / applicable, 3) if applicable else None,
        "correct": correct,
        "wrong": sum(m["status"] == "wrong" for m in per_metric.values()),
        "not_mentioned": sum(m["status"] == "not_mentioned" for m in per_metric.values()),
        "wrong_numbers": {k: v["wrong_numbers"] for k, v in per_metric.items() if v["status"] == "wrong"},
        "per_metric": per_metric,
    }


def score_completeness(answer: str | None, scenario_name: str | None, data_version: int | None) -> dict[str, Any]:
    text = answer or ""
    present: dict[str, bool] = {k: bool(re.search(p, text, re.IGNORECASE)) for k, p in SECTION_PATTERNS.items()}
    present["citation_present"] = bool(re.search(r"\[Source:", text, re.IGNORECASE))
    stated_name = bool(scenario_name) and scenario_name.lower() in text.lower()
    stated_version = data_version is not None and bool(
        re.search(rf"(?:data\s+)?version\s*[:#]?\s*{data_version}\b", text, re.IGNORECASE)
    )
    present["scenario_or_version_stated"] = stated_name or stated_version
    return {
        "score": round(sum(present.values()) / len(REQUIRED_ELEMENTS), 3),
        "present": present,
        "missing": [k for k, v in present.items() if not v],
    }


def score_relevance(answer: str | None) -> dict[str, Any]:
    text = answer or ""
    covered = {k: bool(re.search(p, text, re.IGNORECASE)) for k, p in TOPIC_GROUPS.items()}
    flags = sorted({m.group(0).lower() for m in OUT_OF_SCOPE.finditer(text)})
    base = sum(covered.values()) / len(TOPIC_GROUPS)
    score = max(0.0, base - (0.25 if flags else 0.0))
    return {"score": round(score, 3), "topics_covered": covered, "out_of_scope_terms": flags}


def score_citations(answer: str | None, retrieved: list[RetrievedRef]) -> dict[str, Any]:
    check = check_citations(answer, retrieved)
    total = len(check["citations"])
    score = None if total == 0 else round(check["verified_count"] / total, 3)
    return {"score": score, "check": check, "no_citations": total == 0}


def score_answer(inputs: ScoreInputs) -> dict[str, Any]:
    accuracy = score_accuracy(inputs.answer, inputs.metrics)
    completeness = score_completeness(inputs.answer, inputs.scenario_name, inputs.data_version)
    relevance = score_relevance(inputs.answer)
    citations = score_citations(inputs.answer, inputs.retrieved)
    available = [s for s in (accuracy["score"], completeness["score"], relevance["score"], citations["score"])
                 if s is not None]
    return {
        "accuracy": accuracy,
        "completeness": completeness,
        "relevance": relevance,
        "citation_correctness": citations,
        "overall_demo_score": round(sum(available) / len(available), 3) if available else None,
        "note": SCORING_NOTE,
    }
