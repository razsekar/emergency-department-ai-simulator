"""Shared audit event contract (shared kernel).

Any module may publish an `AuditEvent` on the in-process event bus
(`app.platform.events.get_event_bus().publish(...)`). The audit module subscribes and persists it.
Living here (not in a module) keeps producers decoupled from the audit module, so there is no
dependency cycle between identity and audit.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

OUTCOMES = frozenset({"success", "failure", "denied"})


@dataclass(frozen=True)
class AuditEvent:
    actor: str
    action: str
    outcome: str = "success"
    resource: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"outcome must be one of {sorted(OUTCOMES)}")
        if not self.actor or not self.action:
            raise ValueError("actor and action are required")
