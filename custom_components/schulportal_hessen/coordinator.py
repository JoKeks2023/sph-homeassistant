"""Data coordinator for Schulportal Hessen."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from icalendar import Calendar

from . import snapshot
from .api import SphAuthError, SphClient, SphConnectionError, SphError
from .cancellations import is_cancellation
from .const import (
    APPLET_CALENDAR,
    APPLET_HOMEWORK,
    APPLET_SUBSTITUTIONS,
    APPLET_TIMETABLE,
    DOMAIN,
    EMPTY_TIMETABLE_THRESHOLD,
    EVENT_NEW_CANCELLATION,
    EVENT_NEW_HOMEWORK,
    EVENT_NEW_SUBSTITUTION,
    ISSUE_TRACKER_URL,
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
    # True while the portal could not be reached and old data is being served.
    stale: bool = False
    # Technical status (never contains credentials or response content).
    last_success: datetime | None = None
    last_failure: datetime | None = None
    consecutive_failures: int = 0

    def status(self) -> str:
        """Return "ok", "stale" (old data served) or "no_data"."""
        if self.stale:
            return "stale"
        return "ok" if self.fetched else "no_data"

    def data_age(self, now: datetime) -> timedelta | None:
        """Age of the most recently fetched category, None if nothing was fetched."""
        return now - max(self.fetched.values()) if self.fetched else None

    def has_fetched(self, key: str) -> bool:
        """Return True if category ``key`` was loaded at least once.

        Distinguishes "portal returned nothing" (empty list) from "never loaded"
        (unknown), so sensors do not report 0 before any data exists.
        """
        return key in self.fetched

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


def store_key(entry_id: str) -> str:
    """Storage key of the cached snapshot of one config entry."""
    return f"{DOMAIN}_{entry_id}"


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
        self._empty_timetables = 0
        self._store: Store[dict] = Store(hass, 1, store_key(entry.entry_id))

    async def _async_setup(self) -> None:
        """Restore the last snapshot so a restart works while the portal is down.

        Calendars are not restored (they are refetched); the fetch timestamps of
        the other categories are, so fresh data is not requested again.
        """
        try:
            raw = await self._store.async_load()
        except Exception:  # noqa: BLE001 - corrupt storage must not block setup
            _LOGGER.warning("Could not read stored data, starting empty")
            return
        restored = snapshot.load(raw) if raw else None
        if restored is None:
            return
        data = self._data
        data.applets = restored["applets"]
        data.own_class = restored["own_class"]
        data.substitutions = restored["substitutions"]
        data.lessons = restored["lessons"]
        data.homework = restored["homework"]
        data.fetched = restored["fetched"]

    def _timetable_issue_id(self) -> str:
        return f"timetable_structure_{self.config_entry.entry_id}"

    def _check_timetable_structure(self, has_lessons: bool) -> None:
        """Raise/clear a repair issue when the timetable keeps coming back empty."""
        if has_lessons:
            self._empty_timetables = 0
            ir.async_delete_issue(self.hass, DOMAIN, self._timetable_issue_id())
            return
        self._empty_timetables += 1
        if self._empty_timetables >= EMPTY_TIMETABLE_THRESHOLD:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                self._timetable_issue_id(),
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="timetable_structure",
                learn_more_url=ISSUE_TRACKER_URL,
            )

    def _save(self) -> None:
        data = self._data
        self._store.async_delay_save(
            lambda: snapshot.dump(
                applets=data.applets,
                own_class=data.own_class,
                substitutions=data.substitutions,
                lessons=data.lessons,
                homework=data.homework,
                fetched={k: v for k, v in data.fetched.items() if k != "calendar"},
            ),
            30,
        )

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
            self._check_timetable_structure(bool(data.lessons))

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
            data.last_failure = dt_util.utcnow()
            data.consecutive_failures += 1
            if not data.fetched:
                raise UpdateFailed("Schulportal Hessen could not be read")
            # Keep serving the last known data instead of going unavailable.
            data.stale = True
            return data
        data.stale = False
        if attempted:
            data.last_success = dt_util.utcnow()
            data.consecutive_failures = 0
            self._save()

        if not self._first:
            for item in data.homework:
                if item.uid not in old_homework:
                    self.hass.bus.async_fire(EVENT_NEW_HOMEWORK, item.as_dict())
            for sub in data.my_substitutions():
                if sub.uid not in old_subs:
                    self.hass.bus.async_fire(EVENT_NEW_SUBSTITUTION, sub.as_dict())
                    if is_cancellation(sub):
                        self.hass.bus.async_fire(EVENT_NEW_CANCELLATION, sub.as_dict())
        self._first = False
        return data
