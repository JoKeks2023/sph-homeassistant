"""Config flow for Schulportal Hessen."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import SphAuthError, SphClient, SphError, search_schools
from .const import (
    CONF_FIRST_HOURS,
    CONF_QUERY,
    CONF_SCHOOL,
    CONF_SCHOOL_ID,
    CONF_SCHOOL_NAME,
    DEFAULT_FIRST_HOURS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
MAX_RESULTS = 100


class SphConfigFlow(ConfigFlow, domain=DOMAIN):
    """Search school -> pick school -> enter credentials."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return SphOptionsFlow()

    def __init__(self) -> None:
        """Initialise the flow."""
        self._schools: dict[str, dict[str, str]] = {}
        self._school_id = ""
        self._school_name = ""

    async def _check_login(self, school_id: str, username: str, password: str) -> str | None:
        """Try to log in. Returns an error key or None."""
        session = async_create_clientsession(self.hass, cookie_jar=aiohttp.CookieJar())
        client = SphClient(session, school_id, username, password)
        try:
            await client.login()
        except SphAuthError:
            return "invalid_auth"
        except SphError:
            return "cannot_connect"
        except Exception as err:  # noqa: BLE001
            # Type only: tracebacks/messages may contain URLs or request details.
            _LOGGER.error("Unexpected error during login check: %s", type(err).__name__)
            return "unknown"
        else:
            await client.logout()
            return None
        finally:
            await session.close()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a school search term."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                found = await search_schools(
                    async_get_clientsession(self.hass), user_input[CONF_QUERY], MAX_RESULTS
                )
            except SphError:
                errors["base"] = "cannot_connect"
            else:
                if not found:
                    errors["base"] = "no_schools_found"
                elif len(found) > MAX_RESULTS:
                    errors["base"] = "too_many_results"
                else:
                    self._schools = {school["id"]: school for school in found}
                    return await self.async_step_school()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_QUERY): str}),
            errors=errors,
        )

    async def async_step_school(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the school from the search results."""
        if user_input is not None:
            school = self._schools[user_input[CONF_SCHOOL]]
            self._school_id = school["id"]
            self._school_name = f"{school['name']}, {school['city']}"
            return await self.async_step_credentials()
        options = [
            SelectOptionDict(
                value=school["id"],
                label=f"{school['name']}, {school['city']} ({school['id']})",
            )
            for school in self._schools.values()
        ]
        return self.async_show_form(
            step_id="school",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCHOOL): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
                    )
                }
            ),
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the portal credentials and validate them."""
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            error = await self._check_login(
                self._school_id, username, user_input[CONF_PASSWORD]
            )
            if error is None:
                await self.async_set_unique_id(f"{self._school_id}_{username.casefold()}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{self._school_name} ({username})",
                    data={
                        CONF_SCHOOL_ID: self._school_id,
                        CONF_SCHOOL_NAME: self._school_name,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="credentials",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            description_placeholders={"school": self._school_name},
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start re-authentication after the portal rejected the login."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new password."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            error = await self._check_login(
                entry.data[CONF_SCHOOL_ID],
                entry.data[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            if error is None:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            description_placeholders={"school": entry.data[CONF_SCHOOL_NAME]},
            errors=errors,
        )


class SphOptionsFlow(OptionsFlow):
    """Options: how many first periods count for the "first hours" sensor."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options form."""
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_FIRST_HOURS: int(user_input[CONF_FIRST_HOURS])}
            )
        current = self.config_entry.options.get(CONF_FIRST_HOURS, DEFAULT_FIRST_HOURS)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_FIRST_HOURS, default=current): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=10, step=1, mode=NumberSelectorMode.BOX
                        )
                    )
                }
            ),
        )
