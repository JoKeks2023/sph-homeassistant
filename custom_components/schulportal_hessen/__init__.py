"""Schulportal Hessen integration (read-only)."""

from __future__ import annotations

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import SphClient
from .const import CONF_SCHOOL_ID
from .coordinator import SphCoordinator

PLATFORMS = [Platform.SENSOR, Platform.CALENDAR]

type SphConfigEntry = ConfigEntry[SphCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SphConfigEntry) -> bool:
    """Set up Schulportal Hessen from a config entry."""
    # Own session with its own cookie jar: the portal session lives in cookies.
    session = async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar())
    client = SphClient(
        session,
        entry.data[CONF_SCHOOL_ID],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    coordinator = SphCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SphConfigEntry) -> bool:
    """Unload a config entry and end the portal session."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.client.logout()
    return unloaded
