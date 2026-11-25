"""The verified briefing given to the model alongside the question.

It carries facts the application computed itself, so the model does not have to work them out (a small
local model got the operating level wrong in the first real Ollama demo): the scenario name, the data
version, and the GREEN/AMBER/RED level with the indicator table. Built fresh for every run from the live
snapshot; nothing here is cached.
"""
from app.modules.analytics import public as analytics
from app.modules.ai_orchestration.application.snapshot import Snapshot


def assess(snapshot: Snapshot) -> analytics.EscalationAssessment:
    return analytics.assess_escalation(snapshot.metrics)


def _fmt(value) -> str:
    if value is None:
        return "n/a"
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def build_briefing(snapshot: Snapshot, assessment: analytics.EscalationAssessment) -> str:
    lines = [
        "VERIFIED BRIEFING (computed by the application from live data a moment ago; do not recompute or contradict it)",
        f"Scenario: {snapshot.scenario_name or 'unknown'}",
        f"Data version: {snapshot.data_version}",
        f"Operating level: {assessment.level}",
        f"Rule applied: {assessment.rule}",
        f"Source of the bands: {assessment.policy_reference} (fictional demonstration policy)",
        "Indicators (value, band, and the policy bands):",
    ]
    for i in assessment.indicators:
        note = f" [{i.note}]" if i.note else ""
        lines.append(f"- {i.label}: {_fmt(i.value)} {i.unit} -> {i.band} (bands: {i.bands_text}){note}")
    lines.append(
        f"Summary: {assessment.red_count} indicator(s) RED, {assessment.amber_or_worse_count} AMBER or worse, "
        f"out of {len(assessment.indicators)}."
    )
    return "\n".join(lines)
