"""Diagnostics for Schulportal Hessen (redacted)."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import SphConfigEntry
from .redaction import summarize


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SphConfigEntry
) -> dict[str, Any]:
    """Return diagnostics without credentials, names, teachers or lesson content."""
    coordinator = entry.runtime_data
    data = coordinator.data
    return summarize(
        entry_data=entry.data,
        options=entry.options,
        applets=data.applets,
        own_class=data.own_class,
        counts={
            "substitutions": len(data.substitutions),
            "my_substitutions": len(data.my_substitutions()),
            "lessons": len(data.lessons),
            "homework": len(data.homework),
            "calendar_years": len(data.calendars),
        },
        fetched={k: v.isoformat() for k, v in data.fetched.items()},
        last_update_success=coordinator.last_update_success,
    )
