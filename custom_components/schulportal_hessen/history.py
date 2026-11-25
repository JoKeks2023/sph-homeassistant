"""Bounded local change history (no Home Assistant dependencies)."""

from __future__ import annotations

from typing import Any

MAX_HISTORY = 50
MAX_TEXT = 200


def _shorten(value: Any) -> Any:
    if isinstance(value, str) and len(value) > MAX_TEXT:
        return value[: MAX_TEXT - 1] + "…"
    return value


def record(
    history: list[dict[str, Any]], kind: str, data: dict[str, Any], at: str
) -> list[dict[str, Any]]:
    """Return ``history`` with a new entry appended, limited to MAX_HISTORY (oldest dropped)."""
    entry = {"at": at, "kind": kind, "data": {k: _shorten(v) for k, v in data.items()}}
    return [*history, entry][-MAX_HISTORY:]


def sanitize(raw: Any) -> list[dict[str, Any]]:
    """Validate stored history; anything malformed is dropped instead of raising."""
    if not isinstance(raw, list):
        return []
    result = [
        item
        for item in raw
        if isinstance(item, dict)
        and isinstance(item.get("at"), str)
        and isinstance(item.get("kind"), str)
        and isinstance(item.get("data"), dict)
    ]
    return result[-MAX_HISTORY:]
