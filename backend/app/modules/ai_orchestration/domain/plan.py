"""Deterministic tool plan for models without tool calling (clearly labelled 'fallback' mode).

The plan is data-driven: which policy topics to search is derived from the metrics the earlier tools returned.
These are search heuristics for retrieving documents, not clinical or operational judgements.
"""
from typing import Any

PLAN_HEAD: list[tuple[str, dict[str, Any]]] = [
    ("calculate_waiting_metrics", {}),
    ("get_bed_availability", {}),
    ("get_staff_availability", {}),
    ("get_pending_investigations", {"limit": 5}),
]


def policy_topics(outputs: dict[str, dict[str, Any] | None]) -> list[str]:
    """Pick policy topics from observed tool outputs (missing outputs simply drop their topic)."""
    waiting = outputs.get("calculate_waiting_metrics") or {}
    beds = outputs.get("get_bed_availability") or {}
    pending = outputs.get("get_pending_investigations") or {}

    topics: list[str] = []
    if waiting.get("waiting_patients", 0) > 0:
        topics.append("waiting_time")
    topics.append("bed_capacity")
    topics.append("staffing")
    if pending.get("pending_count", 0) > 0:
        topics.append("pending_investigations")
    if waiting.get("waiting_patients", 0) > 0 or beds.get("available_beds", 1) == 0:
        topics.append("escalation")
    if beds.get("available_beds", 99) <= 2:
        topics.append("discharge")
    return list(dict.fromkeys(topics))
