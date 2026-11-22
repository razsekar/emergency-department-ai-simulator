"""Public interface of the audit module. Other modules may import ONLY this file.

Emit audit records either by calling `record(AuditEvent(...))` or, preferably, by publishing an
`AuditEvent` on the event bus (`app.platform.events.get_event_bus().publish(...)`).
"""
from app.modules.audit.application.service import record, register_event_subscribers
from app.platform.audit_events import AuditEvent

__all__ = ["AuditEvent", "record", "register_event_subscribers"]
