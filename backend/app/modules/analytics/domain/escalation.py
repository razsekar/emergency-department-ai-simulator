"""Operating-level assessment (GREEN / AMBER / RED) from live operational metrics. Pure: no I/O.

The bands below MIRROR the fictional demonstration policy "Hospital Escalation Procedures" (DGH-ESC-004)
and "Resource Management Guidelines" in sample_docs/. They are NOT read from uploaded documents at run
time: if someone uploads a different escalation policy, this code does not follow it. The retrieved policy
text stays the citable source; this function exists so the level is computed deterministically instead of
being left to a language model to work out. It is an administrative indicator for a simulation, not a
clinical triage tool.

Rule (policy section 2): "The department level is the highest level at which at least two indicators are
met. A single RED indicator raises the department level to at least AMBER." Implemented as:
  RED   if at least two indicators are RED
  AMBER if at least two indicators are AMBER or worse, or at least one is RED
  GREEN otherwise
"""
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

GREEN, AMBER, RED = "GREEN", "AMBER", "RED"
POLICY_REF = "Hospital Escalation Procedures (DGH-ESC-004), section 2; Resource Management Guidelines, section 2"
RULE_TEXT = (
    "The department level is the highest level at which at least two indicators are met; "
    "a single RED indicator raises the level to at least AMBER."
)


@dataclass(frozen=True)
class IndicatorResult:
    key: str
    label: str
    value: float | None
    unit: str
    band: str  # GREEN | AMBER | RED | UNKNOWN
    bands_text: str
    note: str | None = None


@dataclass(frozen=True)
class EscalationAssessment:
    level: str
    red_count: int
    amber_or_worse_count: int
    indicators: tuple[IndicatorResult, ...]
    rule: str = RULE_TEXT
    policy_reference: str = POLICY_REF

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "red_indicators": self.red_count,
            "amber_or_worse_indicators": self.amber_or_worse_count,
            "rule": self.rule,
            "policy_reference": self.policy_reference,
            "indicators": [
                {"key": i.key, "label": i.label, "value": i.value, "unit": i.unit, "band": i.band,
                 "bands": i.bands_text, "note": i.note}
                for i in self.indicators
            ],
        }


def _high_is_bad(value: float, green_max: float, amber_max: float) -> str:
    return GREEN if value <= green_max else AMBER if value <= amber_max else RED


def _low_is_bad(value: float, green_min: float, amber_min: float) -> str:
    return GREEN if value >= green_min else AMBER if value >= amber_min else RED


def _num(metrics: Mapping[str, Any], key: str) -> float | None:
    v = metrics.get(key)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _ratio(waiting: float | None, on_duty: float | None) -> tuple[float | None, str | None, bool]:
    """(ratio, note, defined). Zero staff on duty is treated as the worst band, never as a division error."""
    if waiting is None or on_duty is None:
        return None, "metric missing", False
    if on_duty <= 0:
        return None, "no staff on duty", True if waiting > 0 else False
    return round(waiting / on_duty, 2), None, True


def assess_escalation(metrics: Mapping[str, Any]) -> EscalationAssessment:
    waiting = _num(metrics, "patients_waiting")
    avg_wait = _num(metrics, "avg_wait_minutes")
    if avg_wait is None and waiting == 0:
        avg_wait = 0.0  # nobody waiting: no average to speak of
    beds = _num(metrics, "beds_available")
    pending = _num(metrics, "pending_investigations")
    per_doctor, doctor_note, doctor_defined = _ratio(waiting, _num(metrics, "doctors_on_duty"))
    per_nurse, nurse_note, nurse_defined = _ratio(waiting, _num(metrics, "nurses_on_duty"))

    def band(value: float | None, fn, *args) -> str:
        return "UNKNOWN" if value is None else fn(value, *args)

    def ratio_band(value: float | None, defined: bool, *args) -> str:
        if value is None:
            return RED if defined else "UNKNOWN"  # patients waiting and nobody on duty
        return _high_is_bad(value, *args)

    rows = (
        IndicatorResult("avg_wait_minutes", "Average waiting time", avg_wait, "min",
                        band(avg_wait, _high_is_bad, 30, 60), "GREEN <=30; AMBER 31-60; RED >60"),
        IndicatorResult("patients_waiting", "Patients waiting", waiting, "patients",
                        band(waiting, _high_is_bad, 15, 30), "GREEN <=15; AMBER 16-30; RED >30"),
        IndicatorResult("beds_available", "Available beds", beds, "beds",
                        band(beds, _low_is_bad, 5, 2), "GREEN >=5; AMBER 2-4; RED <=1"),
        IndicatorResult("waiting_per_doctor", "Waiting patients per doctor on duty", per_doctor, "ratio",
                        ratio_band(per_doctor, doctor_defined, 3, 6), "GREEN <=3; AMBER 4-6; RED >6", doctor_note),
        IndicatorResult("waiting_per_nurse", "Waiting patients per nurse on duty", per_nurse, "ratio",
                        ratio_band(per_nurse, nurse_defined, 4, 8), "GREEN <=4; AMBER 5-8; RED >8", nurse_note),
        IndicatorResult("pending_investigations", "Pending investigation requests", pending, "requests",
                        band(pending, _high_is_bad, 10, 20), "GREEN <=10; AMBER 11-20; RED >20"),
    )
    red = sum(1 for r in rows if r.band == RED)
    amber_or_worse = sum(1 for r in rows if r.band in (AMBER, RED))
    level = RED if red >= 2 else AMBER if (amber_or_worse >= 2 or red >= 1) else GREEN
    return EscalationAssessment(level, red, amber_or_worse, rows)
