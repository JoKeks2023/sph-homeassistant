"""Schulportal Hessen integration (read-only)."""

from __future__ import annotations

from pathlib import Path

import aiohttp

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.storage import Store

from .api import SphClient
from .const import CONF_SCHOOL_ID, DOMAIN
from .coordinator import SphCoordinator, store_key

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.CALENDAR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

CARD_URL = "/schulportal_hessen/schulportal-hessen-card.js"
CARD_PATH = Path(__file__).parent / "www" / "schulportal-hessen-card.js"
CARD_VERSION = "0.1.0"

type SphConfigEntry = ConfigEntry[SphCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the Lovelace card shipped with the integration."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_PATH), cache_headers=False)]
    )
    add_extra_js_url(hass, f"{CARD_URL}?v={CARD_VERSION}")
    return True


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
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: SphConfigEntry) -> None:
    """Reload so changed options take effect."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SphConfigEntry) -> bool:
    """Unload a config entry and end the portal session."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.client.logout()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: SphConfigEntry) -> None:
    """Delete the cached snapshot when the integration is removed."""
    await Store(hass, 1, store_key(entry.entry_id)).async_remove()
