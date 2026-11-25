"""Sensors for Schulportal Hessen."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
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
from .timetable import (
    next_lesson_skipping_cancelled,
    next_school_start,
    relevant_day_summary,
    week_plan,
    week_summary,
)

SCAN_INTERVAL = timedelta(minutes=1)


@dataclass(frozen=True, kw_only=True)
class SphSensorDescription(SensorEntityDescription):
    """Sensor description with the portal module it depends on."""

    applet: str | None
    fetch_key: str | None
    value_fn: Callable[[SphData], Any]
    attrs_fn: Callable[[SphData], dict[str, Any]]


def _next_lesson(data: SphData):
    found, _skipped = next_lesson_skipping_cancelled(
        data.lessons, dt_util.now(), dt_util.DEFAULT_TIME_ZONE, data.my_substitutions()
    )
    return found


def _next_lesson_value(data: SphData) -> str | None:
    found = _next_lesson(data)
    return full_subject(found[0].subject) if found else None


def _next_lesson_attrs(data: SphData) -> dict[str, Any]:
    found, skipped = next_lesson_skipping_cancelled(
        data.lessons, dt_util.now(), dt_util.DEFAULT_TIME_ZONE, data.my_substitutions()
    )
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
        # Cancelled lessons skipped on the way to this one.
        "skipped_cancelled": [
            {"subject": full_subject(item.subject), "start": at.isoformat()}
            for item, at in skipped
        ][:MAX_ATTRIBUTE_ITEMS],
    }


def _school_start(data: SphData):
    return next_school_start(
        data.lessons, dt_util.now(), dt_util.DEFAULT_TIME_ZONE, data.my_substitutions()
    )


def _school_start_attrs(data: SphData) -> dict[str, Any]:
    found = _school_start(data)
    if not found:
        return {}
    lesson, _start = found
    return {
        "first_lesson": full_subject(lesson.subject),
        "period": lesson.period,
        "room": lesson.room,
    }


def _day(data: SphData):
    return relevant_day_summary(
        data.lessons, dt_util.now(), dt_util.DEFAULT_TIME_ZONE, data.my_substitutions()
    )


def _school_end(data: SphData):
    summary = _day(data)
    return summary.last[1] if summary and summary.last else None


def _day_overview_value(data: SphData) -> int | None:
    summary = _day(data)
    return summary.total - summary.cancelled if summary else None


def _day_overview_attrs(data: SphData) -> dict[str, Any]:
    summary = _day(data)
    if not summary:
        return {}
    return {
        "date": summary.day.isoformat(),
        "first_lesson": full_subject(summary.first[0].subject) if summary.first else None,
        "last_lesson": full_subject(summary.last[0].subject) if summary.last else None,
        "school_start": summary.first[1].isoformat() if summary.first else None,
        "school_end": summary.last[1].isoformat() if summary.last else None,
        "total_lessons": summary.total,
        "cancelled_lessons": summary.cancelled,
        "substitutions": summary.substitutions,
        "free_periods": len(summary.free_periods),
        "free_period_windows": [
            {"start": a.isoformat(), "end": b.isoformat()} for a, b in summary.free_periods
        ][:MAX_ATTRIBUTE_ITEMS],
    }


def _portal_status_attrs(data: SphData) -> dict[str, Any]:
    age = data.data_age(dt_util.utcnow())
    return {
        "last_success": data.last_success.isoformat() if data.last_success else None,
        "last_failure": data.last_failure.isoformat() if data.last_failure else None,
        "consecutive_failures": data.consecutive_failures,
        "data_age_minutes": int(age.total_seconds() // 60) if age is not None else None,
    }


def _week(data: SphData):
    return week_summary(
        data.lessons, dt_util.now(), dt_util.DEFAULT_TIME_ZONE, data.my_substitutions()
    )


def _week_attrs(data: SphData) -> dict[str, Any]:
    week = _week(data)
    monday, plan = week_plan(
        data.lessons, dt_util.now(), dt_util.DEFAULT_TIME_ZONE, data.my_substitutions()
    )
    return {
        "calendar_week": week.calendar_week,
        "today_is_school_day": week.today_is_school_day,
        "next_school_day": week.next_school_day.isoformat() if week.next_school_day else None,
        "days_until_next_school_day": week.days_until_next,
        "note": "school holidays are not taken into account",
        "plan_week_start": monday.isoformat(),
        # Whole week for the Lovelace card (a few KB; no extra portal request).
        "plan": plan,
    }


def _history_attrs(data: SphData) -> dict[str, Any]:
    # Newest first; limited so the attributes stay small.
    return {"entries": list(reversed(data.history))[:10]}


SENSORS: tuple[SphSensorDescription, ...] = (
    SphSensorDescription(
        key="next_lesson",
        fetch_key="timetable",
        applet=APPLET_TIMETABLE,
        value_fn=_next_lesson_value,
        attrs_fn=_next_lesson_attrs,
    ),
    SphSensorDescription(
        key="school_start",
        fetch_key="timetable",
        applet=APPLET_TIMETABLE,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: (found[1] if (found := _school_start(data)) else None),
        attrs_fn=_school_start_attrs,
    ),
    SphSensorDescription(
        key="portal_status",
        fetch_key=None,
        applet=None,
        device_class=SensorDeviceClass.ENUM,
        options=["ok", "stale", "no_data"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status(),
        attrs_fn=_portal_status_attrs,
    ),
    SphSensorDescription(
        key="school_week",
        fetch_key="timetable",
        applet=APPLET_TIMETABLE,
        value_fn=lambda data: _week(data).remaining_days,
        attrs_fn=_week_attrs,
        native_unit_of_measurement="days",
    ),
    SphSensorDescription(
        key="data_quality",
        fetch_key=None,
        applet=None,
        device_class=SensorDeviceClass.ENUM,
        options=["ok", "warning"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: "warning" if data.quality_issues() else "ok",
        attrs_fn=lambda data: {"issues": data.quality_issues()},
    ),
    SphSensorDescription(
        key="change_history",
        fetch_key=None,
        applet=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: len(data.history),
        attrs_fn=_history_attrs,
        native_unit_of_measurement="entries",
    ),
    SphSensorDescription(
        key="school_end",
        fetch_key="timetable",
        applet=APPLET_TIMETABLE,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_school_end,
        attrs_fn=lambda data: {},
    ),
    SphSensorDescription(
        key="school_day_overview",
        fetch_key="timetable",
        applet=APPLET_TIMETABLE,
        value_fn=_day_overview_value,
        attrs_fn=_day_overview_attrs,
        native_unit_of_measurement="lessons",
    ),
    SphSensorDescription(
        key="substitutions",
        fetch_key="substitutions",
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
        fetch_key="substitutions",
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
        fetch_key="homework",
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
        if description.applet is None or coordinator.data.has_applet(description.applet)
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
    def available(self) -> bool:
        """Unavailable until the category was loaded once (not "0 entries")."""
        key = self.entity_description.fetch_key
        return super().available and (key is None or self.coordinator.data.has_fetched(key))

    @property
    def native_value(self) -> Any:
        """Return the state."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return attributes (no credentials or tokens).

        ``sph`` identifies the sensor kind so the Lovelace card can find it.
        """
        return {
            "sph": self.entity_description.key,
            # Opaque id of the config entry: lets the card tell accounts apart.
            "account": self.coordinator.config_entry.entry_id,
            "account_name": self.coordinator.config_entry.title,
            "stale": self.coordinator.data.stale,
            **self.entity_description.attrs_fn(self.coordinator.data),
        }
