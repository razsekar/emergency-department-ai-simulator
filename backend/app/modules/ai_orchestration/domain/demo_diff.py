"""Pure logic for the demonstration: which metrics differ between data states (derived, never hardcoded text)."""
import hashlib
from typing import Any


def question_sha256(question: str) -> str:
    return hashlib.sha256(question.encode("utf-8")).hexdigest()


def changed_metrics(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    """Metrics whose value differs between two snapshots (union of keys; a missing key counts as None)."""
    out = []
    for key in sorted(set(before) | set(after)):
        b, a = before.get(key), after.get(key)
        if b != a:
            out.append({"metric": key, "before": b, "after": a})
    return out


def _delta(prev: Any, cur: Any) -> float | None:
    if isinstance(prev, bool) or isinstance(cur, bool):
        return None
    if isinstance(prev, (int, float)) and isinstance(cur, (int, float)):
        return round(cur - prev, 2)
    return None


def metric_comparison(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per metric: its value in each run, whether it differs across runs, and change vs the previous run."""
    keys: list[str] = []
    for snap in snapshots:
        for key in snap:
            if key not in keys:
                keys.append(key)
    rows = []
    for key in keys:
        values = [snap.get(key) for snap in snapshots]
        deltas = [None] + [_delta(values[i - 1], values[i]) for i in range(1, len(values))]
        rows.append({
            "metric": key,
            "values": values,
            "differs": len({repr(v) for v in values}) > 1,
            "deltas_vs_previous": deltas,
        })
    return rows
