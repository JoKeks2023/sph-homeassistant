"""Integration tests against a real Home Assistant test instance."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.schulportal_hessen import snapshot
from custom_components.schulportal_hessen.api import SphAuthError
from custom_components.schulportal_hessen.const import DOMAIN
from custom_components.schulportal_hessen.coordinator import store_key
from custom_components.schulportal_hessen.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.schulportal_hessen.parsers import Homework

from .conftest import FakePortal, make_sub


def eid(hass: HomeAssistant, entry: MockConfigEntry, platform: str, key: str) -> str:
    """Entity id of an entity by its unique key."""
    found = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{entry.entry_id}_{key}"
    )
    assert found, f"no {platform} entity for {key}"
    return found


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_sensors_and_cancellations(
    hass: HomeAssistant, entry: MockConfigEntry, portal: FakePortal
) -> None:
    today = dt_util.now().date()
    portal.substitutions = [
        make_sub(today, "2"),  # own class, first hours
        make_sub(today, "1", classes=("9C",)),  # other class
        make_sub(today, "4", kind="Vertretung"),  # not a cancellation
    ]
    await setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    assert hass.states.get(eid(hass, entry, "sensor", "substitutions")).state == "2"
    assert hass.states.get(eid(hass, entry, "sensor", "other_substitutions")).state == "1"
    assert hass.states.get(eid(hass, entry, "binary_sensor", "cancellation_today")).state == "on"
    assert hass.states.get(eid(hass, entry, "binary_sensor", "cancellation_first_hours")).state == "on"
    assert hass.states.get(eid(hass, entry, "binary_sensor", "cancellation_tomorrow")).state == "off"


async def test_first_hours_not_triggered_by_later_lesson(
    hass: HomeAssistant, entry: MockConfigEntry, portal: FakePortal
) -> None:
    portal.substitutions = [make_sub(dt_util.now().date(), "3")]
    await setup(hass, entry)
    assert hass.states.get(eid(hass, entry, "binary_sensor", "cancellation_today")).state == "on"
    assert hass.states.get(eid(hass, entry, "binary_sensor", "cancellation_first_hours")).state == "off"


async def test_options_flow_changes_first_hours(
    hass: HomeAssistant, entry: MockConfigEntry, portal: FakePortal
) -> None:
    portal.substitutions = [make_sub(dt_util.now().date(), "3")]
    await setup(hass, entry)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"first_hours": 3}
    )
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert entry.options["first_hours"] == 3
    assert hass.states.get(eid(hass, entry, "binary_sensor", "cancellation_first_hours")).state == "on"


async def test_total_failure_keeps_last_data(
    hass: HomeAssistant, entry: MockConfigEntry, portal: FakePortal
) -> None:
    portal.substitutions = [make_sub(dt_util.now().date(), "1")]
    await setup(hass, entry)
    coordinator = entry.runtime_data
    sensor = eid(hass, entry, "sensor", "substitutions")
    assert hass.states.get(sensor).state == "1"

    portal.fail_all = True
    coordinator._data.fetched = {
        k: v - timedelta(days=2) for k, v in coordinator._data.fetched.items()
    }
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(sensor)
    assert state.state == "1"
    assert state.attributes["stale"] is True


async def test_failure_before_any_data_retries_setup(
    hass: HomeAssistant, entry: MockConfigEntry, portal: FakePortal
) -> None:
    portal.fail_all = True
    await setup(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unloaded_category_is_unavailable_not_zero(
    hass: HomeAssistant, entry: MockConfigEntry, portal: FakePortal
) -> None:
    portal.applets = ["Vertretungsplan", "Mein Unterricht"]
    portal.fail_homework = True
    await setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(eid(hass, entry, "sensor", "homework")).state == "unavailable"
    assert hass.states.get(eid(hass, entry, "sensor", "substitutions")).state == "0"


async def test_restart_recovery_from_snapshot(
    hass: HomeAssistant, entry: MockConfigEntry, portal: FakePortal, hass_storage
) -> None:
    old = dt_util.utcnow() - timedelta(days=2)
    hass_storage[store_key(entry.entry_id)] = {
        "version": 1,
        "minor_version": 1,
        "key": store_key(entry.entry_id),
        "data": snapshot.dump(
            applets=["Vertretungsplan"],
            own_class="10A",
            substitutions=[make_sub(dt_util.now().date(), "1")],
            lessons=[],
            homework=[],
            fetched={"applets": old, "substitutions": old},
        ),
    }
    portal.fail_all = True  # portal is down while HA starts
    await setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    state = hass.states.get(eid(hass, entry, "sensor", "substitutions"))
    assert state.state == "1"
    assert state.attributes["stale"] is True


async def test_diagnostics_are_redacted(
    hass: HomeAssistant, entry: MockConfigEntry, portal: FakePortal
) -> None:
    portal.substitutions = [make_sub(dt_util.now().date(), "1", teacher="GEHEIMLEHRER")]
    portal.homework = [Homework("u1", "Mathe", "Thema", None, "GEHEIMTEXT")]
    portal.applets = ["Vertretungsplan", "Stundenplan", "Mein Unterricht"]
    await setup(hass, entry)
    text = repr(await async_get_config_entry_diagnostics(hass, entry))
    for secret in ("geheim", "max.muster", "1234", "Testschule", "GEHEIMLEHRER", "GEHEIMTEXT", "10A"):
        assert secret not in text, secret


async def test_config_flow_creates_entry(hass: HomeAssistant) -> None:
    schools = [{"id": "1234", "name": "Testschule", "city": "Teststadt"}]
    fake = AsyncMock()
    with (
        patch("custom_components.schulportal_hessen.config_flow.search_schools", AsyncMock(return_value=schools)),
        patch("custom_components.schulportal_hessen.config_flow.SphClient", return_value=fake),
        patch("custom_components.schulportal_hessen.async_setup_entry", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        assert result["step_id"] == "user"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"query": "Test"})
        assert result["step_id"] == "school"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"school": "1234"})
        assert result["step_id"] == "credentials"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "max.muster", "password": "x"}
        )
    assert result["type"] == "create_entry"
    assert result["data"]["school_id"] == "1234"


async def test_config_flow_invalid_auth(hass: HomeAssistant) -> None:
    schools = [{"id": "1234", "name": "Testschule", "city": "Teststadt"}]
    fake = AsyncMock()
    fake.login.side_effect = SphAuthError
    with (
        patch("custom_components.schulportal_hessen.config_flow.search_schools", AsyncMock(return_value=schools)),
        patch("custom_components.schulportal_hessen.config_flow.SphClient", return_value=fake),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"query": "Test"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"school": "1234"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "max.muster", "password": "falsch"}
        )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}
