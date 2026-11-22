"""Canonical permission and role definitions (reference data; also seeded by migration 0400)."""
from enum import StrEnum


class Permission(StrEnum):
    DASHBOARD_READ = "dashboard:read"
    QUEUE_READ = "queue:read"
    RESOURCES_READ = "resources:read"
    SCENARIO_READ = "scenario:read"
    SCENARIO_APPLY = "scenario:apply"
    SCENARIO_RESET = "scenario:reset"
    KNOWLEDGE_READ = "knowledge:read"
    KNOWLEDGE_UPLOAD = "knowledge:upload"
    AI_CHAT = "ai:chat"
    AGENT_RUN = "agent:run"
    MODELS_READ = "models:read"
    MODELS_CONFIGURE = "models:configure"
    COMPARISON_RUN = "comparison:run"
    AUDIT_READ = "audit:read"


_VIEWER = frozenset({
    Permission.DASHBOARD_READ, Permission.QUEUE_READ, Permission.RESOURCES_READ,
    Permission.SCENARIO_READ, Permission.KNOWLEDGE_READ, Permission.MODELS_READ,
})
_PRESENTER = _VIEWER | frozenset({
    Permission.SCENARIO_APPLY, Permission.SCENARIO_RESET, Permission.KNOWLEDGE_UPLOAD,
    Permission.AI_CHAT, Permission.AGENT_RUN, Permission.COMPARISON_RUN,
})
_ADMIN = frozenset(Permission)

ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "viewer": _VIEWER,
    "presenter": _PRESENTER,
    "admin": _ADMIN,
}

DEMO_USERS: dict[str, tuple[str, str]] = {
    # username: (role, display name)
    "demo_admin": ("admin", "Demo Administrator"),
    "demo_presenter": ("presenter", "Demo Presenter"),
    "demo_viewer": ("viewer", "Demo Viewer"),
}
