"""Data coordinator for Schulportal Hessen."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from icalendar import Calendar

from .api import SphAuthError, SphClient, SphConnectionError, SphError
from .const import (
    APPLET_CALENDAR,
    APPLET_HOMEWORK,
    APPLET_SUBSTITUTIONS,
    APPLET_TIMETABLE,
    DOMAIN,
    EVENT_NEW_HOMEWORK,
    EVENT_NEW_SUBSTITUTION,
    TTL_APPLETS,
    TTL_CALENDAR,
    TTL_HOMEWORK,
    TTL_SUBSTITUTIONS,
    TTL_TIMETABLE,
    UPDATE_INTERVAL,
)
from .parsers import Homework, Lesson, Substitution

if TYPE_CHECKING:
    from . import SphConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass
class SphData:
    """Everything fetched from the portal. Missing categories stay empty."""

    applets: list[str] = field(default_factory=list)
    substitutions: list[Substitution] = field(default_factory=list)
    lessons: list[Lesson] = field(default_factory=list)
    own_class: str | None = None
    homework: list[Homework] = field(default_factory=list)
    calendars: dict[int, Calendar] = field(default_factory=dict)
    fetched: dict[str, datetime] = field(default_factory=dict)

    def has_applet(self, key: str) -> bool:
        """Return True if the portal lists a module containing ``key``."""
        return any(key in name.casefold() for name in self.applets)

    def my_substitutions(self) -> list[Substitution]:
        """Substitutions for the account's own class (all if class unknown)."""
        if not self.own_class:
            return self.substitutions
        mine = self.own_class.casefold()
        return [
            s for s in self.substitutions if any(c.casefold() == mine for c in s.classes)
        ]

    def other_substitutions(self) -> list[Substitution]:
        """Substitutions of all other classes (empty if own class is unknown)."""
        if not self.own_class:
            return []
        mine = {id(s) for s in self.my_substitutions()}
        return [s for s in self.substitutions if id(s) not in mine]


class SphCoordinator(DataUpdateCoordinator[SphData]):
    """Fetch data with a separate time-to-live per category."""

    config_entry: SphConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: SphClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self._data = SphData()
        self._first = True

    def _due(self, key: str, ttl: timedelta) -> bool:
        last = self._data.fetched.get(key)
        return last is None or dt_util.utcnow() - last >= ttl

    def _mark(self, key: str) -> None:
        self._data.fetched[key] = dt_util.utcnow()

    async def _async_update_data(self) -> SphData:
        data = self._data
        failures = 0
        attempted = 0
        old_homework = {h.uid for h in data.homework}
        old_subs = {s.uid for s in data.substitutions}

        async def run(key: str, ttl: timedelta, coro_factory) -> None:
            nonlocal failures, attempted
            if not self._due(key, ttl):
                return
            attempted += 1
            try:
                await coro_factory()
            except SphAuthError as err:
                raise ConfigEntryAuthFailed("Login to Schulportal Hessen failed") from err
            except SphError as err:
                failures += 1
                _LOGGER.warning("Could not update %s: %s", key, type(err).__name__)
            else:
                self._mark(key)

        async def applets() -> None:
            data.applets = await self.client.get_applets()

        async def substitutions() -> None:
            data.substitutions = await self.client.get_substitutions()

        async def timetable() -> None:
            data.own_class, data.lessons = await self.client.get_timetable()

        async def homework() -> None:
            data.homework = await self.client.get_homework()

        async def calendar() -> None:
            today = dt_util.now().date()
            years = {today.year}
            if today.month >= 10:
                years.add(today.year + 1)
            for year in sorted(years):
                ics = await self.client.get_calendar_ics(year)
                data.calendars[year] = await self.hass.async_add_executor_job(
                    Calendar.from_ical, ics
                )

        try:
            await run("applets", TTL_APPLETS, applets)
            if data.applets:
                if data.has_applet(APPLET_SUBSTITUTIONS):
                    await run("substitutions", TTL_SUBSTITUTIONS, substitutions)
                if data.has_applet(APPLET_TIMETABLE):
                    await run("timetable", TTL_TIMETABLE, timetable)
                if data.has_applet(APPLET_HOMEWORK):
                    await run("homework", TTL_HOMEWORK, homework)
                if data.has_applet(APPLET_CALENDAR):
                    await run("calendar", TTL_CALENDAR, calendar)
        except SphConnectionError as err:  # pragma: no cover - defensive
            raise UpdateFailed("Schulportal Hessen not reachable") from err

        if attempted and failures == attempted:
            raise UpdateFailed("Schulportal Hessen could not be read")

        if not self._first:
            for item in data.homework:
                if item.uid not in old_homework:
                    self.hass.bus.async_fire(EVENT_NEW_HOMEWORK, item.as_dict())
            for sub in data.my_substitutions():
                if sub.uid not in old_subs:
                    self.hass.bus.async_fire(EVENT_NEW_SUBSTITUTION, sub.as_dict())
        self._first = False
        return data
