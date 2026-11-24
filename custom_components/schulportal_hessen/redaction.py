"""Build redacted diagnostics (no Home Assistant dependencies)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

REDACTED = "**REDACTED**"

# Everything that identifies the account, school or person.
SENSITIVE_KEYS = frozenset(
    {"username", "password", "school_id", "school_name", "query", "school"}
)


def redact(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy with sensitive keys replaced (non-recursive is enough here)."""
    return {k: (REDACTED if k in SENSITIVE_KEYS else v) for k, v in data.items()}


def summarize(
    *,
    entry_data: Mapping[str, Any],
    options: Mapping[str, Any],
    applets: list[str],
    own_class: str | None,
    counts: Mapping[str, int],
    fetched: Mapping[str, str],
    last_update_success: bool,
) -> dict[str, Any]:
    """Diagnostics payload: structure and counts only, never portal content."""
    return {
        "entry": redact(entry_data),
        "options": dict(options),
        "applets": list(applets),
        "own_class_known": own_class is not None,
        "counts": dict(counts),
        "last_fetched": dict(fetched),
        "last_update_success": last_update_success,
    }
