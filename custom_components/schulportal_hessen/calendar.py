"""Calendar entities: school events (iCal export) and the weekly timetable."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import recurring_ical_events

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import SphConfigEntry
from .const import APPLET_CALENDAR, APPLET_TIMETABLE
from .coordinator import SphCoordinator
from .entity import SphEntity
from .subjects import full_subject
from .timetable import lessons_between, next_lesson


async def async_setup_entry(
    hass: HomeAssistant, entry: SphConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create calendars for modules enabled for the account."""
    coordinator = entry.runtime_data
    entities: list[CalendarEntity] = []
    if coordinator.data.has_applet(APPLET_CALENDAR):
        entities.append(SphSchoolCalendar(coordinator))
    if coordinator.data.has_applet(APPLET_TIMETABLE):
        entities.append(SphTimetableCalendar(coordinator))
    async_add_entities(entities)


def _localize(value: date | datetime) -> date | datetime:
    """Give floating datetimes the local time zone; keep dates as they are."""
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return value


class SphSchoolCalendar(SphEntity, CalendarEntity):
    """School events from the portal's iCal export."""

    def __init__(self, coordinator: SphCoordinator) -> None:
        """Initialise the calendar."""
        super().__init__(coordinator, "school_calendar")

    def _events_between(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        seen: set[tuple[str, str]] = set()
        events: list[CalendarEvent] = []
        for calendar in self.coordinator.data.calendars.values():
            for component in recurring_ical_events.of(calendar).between(start, end):
                dtstart = component.get("DTSTART")
                if dtstart is None:
                    continue
                begin = _localize(dtstart.dt)
                finish_prop = component.get("DTEND")
                finish = _localize(finish_prop.dt) if finish_prop else begin
                if isinstance(begin, datetime) != isinstance(finish, datetime):
                    finish = begin
                if finish == begin and not isinstance(begin, datetime):
                    finish = begin + timedelta(days=1)
                uid = str(component.get("UID", ""))
                key = (uid, str(begin))
                if key in seen:
                    continue
                seen.add(key)
                events.append(
                    CalendarEvent(
                        start=begin,
                        end=finish,
                        summary=str(component.get("SUMMARY", "")),
                        description=str(component.get("DESCRIPTION", "")) or None,
                        location=str(component.get("LOCATION", "")) or None,
                        uid=uid or None,
                    )
                )
        events.sort(key=lambda e: (e.start_datetime_local, e.summary))
        return events

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next event within 60 days."""
        now = dt_util.now()
        upcoming = [
            e
            for e in self._events_between(now, now + timedelta(days=60))
            if e.end_datetime_local > now
        ]
        return upcoming[0] if upcoming else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return events in a date range."""
        return await hass.async_add_executor_job(
            self._events_between, start_date, end_date
        )


class SphTimetableCalendar(SphEntity, CalendarEntity):
    """The regular weekly timetable expanded into calendar events.

    Substitutions are NOT merged in; see the substitutions sensor.
    """

    def __init__(self, coordinator: SphCoordinator) -> None:
        """Initialise the calendar."""
        super().__init__(coordinator, "timetable")

    @staticmethod
    def _to_event(lesson: Any, start: datetime, end: datetime) -> CalendarEvent:
        details = ", ".join(part for part in (lesson.teacher, lesson.room) if part)
        return CalendarEvent(
            start=start,
            end=end,
            summary=full_subject(lesson.subject),
            description=details or None,
            location=lesson.room or None,
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next lesson."""
        found = next_lesson(
            self.coordinator.data.lessons, dt_util.now(), dt_util.DEFAULT_TIME_ZONE
        )
        return self._to_event(*found) if found else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return lessons in a date range."""
        return [
            self._to_event(lesson, start, end)
            for lesson, start, end in lessons_between(
                self.coordinator.data.lessons,
                start_date,
                end_date,
                dt_util.DEFAULT_TIME_ZONE,
            )
        ]
