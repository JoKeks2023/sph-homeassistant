"""Sensors for Schulportal Hessen."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import SphConfigEntry
from .const import (
    APPLET_HOMEWORK,
    APPLET_SUBSTITUTIONS,
    APPLET_TIMETABLE,
    MAX_ATTRIBUTE_ITEMS,
)
from .coordinator import SphData
from .entity import SphEntity
from .subjects import full_subject
from .timetable import next_lesson

SCAN_INTERVAL = timedelta(minutes=1)


@dataclass(frozen=True, kw_only=True)
class SphSensorDescription(SensorEntityDescription):
    """Sensor description with the portal module it depends on."""

    applet: str
    value_fn: Callable[[SphData], Any]
    attrs_fn: Callable[[SphData], dict[str, Any]]


def _next_lesson(data: SphData):
    return next_lesson(data.lessons, dt_util.now(), dt_util.DEFAULT_TIME_ZONE)


def _next_lesson_value(data: SphData) -> str | None:
    found = _next_lesson(data)
    return full_subject(found[0].subject) if found else None


def _next_lesson_attrs(data: SphData) -> dict[str, Any]:
    found = _next_lesson(data)
    if not found:
        return {}
    lesson, start, end = found
    return {
        "subject_short": lesson.subject,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "teacher": lesson.teacher,
        "room": lesson.room,
        "period": lesson.period,
        "class": data.own_class,
    }


SENSORS: tuple[SphSensorDescription, ...] = (
    SphSensorDescription(
        key="next_lesson",
        applet=APPLET_TIMETABLE,
        value_fn=_next_lesson_value,
        attrs_fn=_next_lesson_attrs,
    ),
    SphSensorDescription(
        key="substitutions",
        applet=APPLET_SUBSTITUTIONS,
        value_fn=lambda data: len(data.my_substitutions()),
        attrs_fn=lambda data: {
            "class": data.own_class,
            "entries": [s.as_dict() for s in data.my_substitutions()][:MAX_ATTRIBUTE_ITEMS],
        },
        native_unit_of_measurement="entries",
    ),
    SphSensorDescription(
        key="other_substitutions",
        applet=APPLET_SUBSTITUTIONS,
        value_fn=lambda data: len(data.other_substitutions()),
        attrs_fn=lambda data: {
            "entries": [s.as_dict() for s in data.other_substitutions()][
                :MAX_ATTRIBUTE_ITEMS
            ],
        },
        native_unit_of_measurement="entries",
    ),
    SphSensorDescription(
        key="homework",
        applet=APPLET_HOMEWORK,
        value_fn=lambda data: len(data.homework),
        attrs_fn=lambda data: {
            "entries": [h.as_dict() for h in data.homework][:MAX_ATTRIBUTE_ITEMS],
            "note": "lesson_date is the date of the lesson, not a due date",
        },
        native_unit_of_measurement="entries",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: SphConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create sensors for modules enabled for the account."""
    coordinator = entry.runtime_data
    async_add_entities(
        SphSensor(coordinator, description)
        for description in SENSORS
        if coordinator.data.has_applet(description.applet)
    )


class SphSensor(SphEntity, SensorEntity):
    """Sensor reading from the coordinator data."""

    entity_description: SphSensorDescription
    # next_lesson changes with the clock, so recompute the state every minute
    # from cached data (no portal request is made).
    _attr_should_poll = True

    def __init__(self, coordinator, description: SphSensorDescription) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_update(self) -> None:
        """Recompute state from cached data; never hits the portal."""

    @property
    def native_value(self) -> Any:
        """Return the state."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return attributes (no credentials or tokens)."""
        return self.entity_description.attrs_fn(self.coordinator.data)
