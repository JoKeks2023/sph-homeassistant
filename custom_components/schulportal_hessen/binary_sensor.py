"""Cancellation (Entfall) binary sensors for Schulportal Hessen."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import SphConfigEntry
from .cancellations import cancellations_on, first_hours_cancelled
from .const import APPLET_SUBSTITUTIONS, CONF_FIRST_HOURS, DEFAULT_FIRST_HOURS
from .coordinator import SphData
from .entity import SphEntity
from .subjects import full_subject

SCAN_INTERVAL = timedelta(minutes=1)


@dataclass(frozen=True, kw_only=True)
class SphBinarySensorDescription(BinarySensorEntityDescription):
    """Description of a cancellation sensor."""

    day_offset: int
    first_hours_only: bool = False


BINARY_SENSORS: tuple[SphBinarySensorDescription, ...] = (
    SphBinarySensorDescription(key="cancellation_today", day_offset=0),
    SphBinarySensorDescription(
        key="cancellation_first_hours", day_offset=0, first_hours_only=True
    ),
    SphBinarySensorDescription(key="cancellation_tomorrow", day_offset=1),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: SphConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the sensors if the account has the substitution plan."""
    coordinator = entry.runtime_data
    if not coordinator.data.has_applet(APPLET_SUBSTITUTIONS):
        return
    async_add_entities(SphCancellationSensor(coordinator, d) for d in BINARY_SENSORS)


class SphCancellationSensor(SphEntity, BinarySensorEntity):
    """On if a lesson of the own class is cancelled on the given day."""

    entity_description: SphBinarySensorDescription
    # The day rolls over with the clock, so re-evaluate from cached data.
    _attr_should_poll = True

    def __init__(self, coordinator, description: SphBinarySensorDescription) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_update(self) -> None:
        """Re-evaluate from cached data; never hits the portal."""

    @property
    def available(self) -> bool:
        """Unavailable until substitutions were loaded once (not "no cancellation")."""
        return super().available and self.coordinator.data.has_fetched("substitutions")

    @property
    def _first_hours(self) -> int:
        return int(
            self.coordinator.config_entry.options.get(
                CONF_FIRST_HOURS, DEFAULT_FIRST_HOURS
            )
        )

    def _day(self) -> date:
        return dt_util.now().date() + timedelta(days=self.entity_description.day_offset)

    def _rows(self):
        data: SphData = self.coordinator.data
        return cancellations_on(data.my_substitutions(), self._day())

    @property
    def is_on(self) -> bool:
        """Return True if a relevant lesson is cancelled."""
        rows = self._rows()
        if self.entity_description.first_hours_only:
            return first_hours_cancelled(rows, self._first_hours)
        return bool(rows)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the cancelled lessons of the day."""
        attrs: dict[str, Any] = {
            "date": self._day().isoformat(),
            "stale": self.coordinator.data.stale,
            "entries": [
                {**s.as_dict(), "subject_full": full_subject(s.subject_old or s.subject)}
                for s in self._rows()
            ][:25],
        }
        if self.entity_description.first_hours_only:
            attrs["first_hours"] = self._first_hours
        return attrs
