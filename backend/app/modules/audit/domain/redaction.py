"""Strip secrets from audit details before they are stored."""
import re
from typing import Any

_SENSITIVE_SUBSTRING = re.compile(r"(password|passwd|secret|authorization|api[_-]?key|credential)", re.I)
_SENSITIVE_EXACT = frozenset({"token", "access_token", "refresh_token", "id_token", "jwt", "bearer"})
REDACTED = "[REDACTED]"


def _sensitive(key: str) -> bool:
    return key.lower() in _SENSITIVE_EXACT or bool(_SENSITIVE_SUBSTRING.search(key))


def redact(value: Any) -> Any:
    """Return a JSON-safe copy with sensitive keys masked (recursively)."""
    if isinstance(value, dict):
        return {str(k): REDACTED if _sensitive(str(k)) else redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [redact(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
