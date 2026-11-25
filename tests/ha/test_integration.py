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
    status = hass.states.get(eid(hass, entry, "sensor", "portal_status"))
    assert status.state == "stale"
    assert status.attributes["consecutive_failures"] == 1
    assert status.attributes["last_failure"] is not None
    assert status.attributes["last_success"] is not None
    assert status.attributes["data_age_minutes"] >= 2 * 24 * 60
    # recovery resets the failure counter
    portal.fail_all = False
    coordinator._data.fetched = {
        k: v - timedelta(days=2) for k, v in coordinator._data.fetched.items()
    }
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    status = hass.states.get(eid(hass, entry, "sensor", "portal_status"))
    assert status.state == "ok"
    assert status.attributes["consecutive_failures"] == 0


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


async def test_new_cancellation_event(
    hass: HomeAssistant, entry: MockConfigEntry, portal: FakePortal
) -> None:
    from pytest_homeassistant_custom_component.common import async_capture_events

    today = dt_util.now().date()
    portal.substitutions = [make_sub(today, "1")]
    await setup(hass, entry)
    cancellations = async_capture_events(hass, "schulportal_hessen_new_cancellation")
    substitutions = async_capture_events(hass, "schulportal_hessen_new_substitution")
    assert not cancellations  # nothing fires on the first load

    portal.substitutions = [
        make_sub(today, "1"),  # already known
        make_sub(today, "2"),  # new cancellation
        make_sub(today, "4", kind="Vertretung"),  # new, but not a cancellation
        make_sub(today, "3", classes=("9C",)),  # other class
    ]
    coordinator = entry.runtime_data
    coordinator._data.fetched.pop("substitutions")
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert [e.data["lesson"] for e in cancellations] == ["2"]
    assert sorted(e.data["lesson"] for e in substitutions) == ["2", "4"]


async def test_room_teacher_and_homework_change_events(
    hass: HomeAssistant, entry: MockConfigEntry, portal: FakePortal
) -> None:
    from dataclasses import replace

    from pytest_homeassistant_custom_component.common import async_capture_events

    from custom_components.schulportal_hessen.parsers import Homework

    today = dt_util.now().date()
    base = replace(make_sub(today, "1", kind="Vertretung"), room="R1", substitute="XYZ")
    portal.substitutions = [base]
    portal.applets = ["Vertretungsplan", "Stundenplan", "Mein Unterricht"]
    portal.homework = [Homework("b-1", "Mathe", "Brüche", today, "S. 10")]
    await setup(hass, entry)
    rooms = async_capture_events(hass, "schulportal_hessen_room_changed")
    teachers = async_capture_events(hass, "schulportal_hessen_teacher_changed")
    homework = async_capture_events(hass, "schulportal_hessen_homework_changed")
    new_hw = async_capture_events(hass, "schulportal_hessen_new_homework")
    assert not (rooms or teachers or homework)

    portal.substitutions = [replace(base, room="R2", substitute="UVW")]
    portal.homework = [Homework("b-1", "Mathe", "Brüche", today, "S. 10 und 11")]
    coordinator = entry.runtime_data
    coordinator._data.fetched.pop("substitutions")
    coordinator._data.fetched.pop("homework")
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert [(e.data["old_room"], e.data["new_room"]) for e in rooms] == [("R1", "R2")]
    assert [(e.data["old_teacher"], e.data["new_teacher"]) for e in teachers] == [
        ("XYZ", "UVW")
    ]
    assert [e.data["new_text"] for e in homework] == ["S. 10 und 11"]
    assert not new_hw  # an edit is not a new homework entry

    history = hass.states.get(eid(hass, entry, "sensor", "change_history"))
    assert history.state == "3"
    assert {e["kind"] for e in history.attributes["entries"]} == {
        "room_changed", "teacher_changed", "homework_changed"
    }
    quality = hass.states.get(eid(hass, entry, "sensor", "data_quality"))
    assert quality.state == "ok"
    assert hass.states.get(eid(hass, entry, "sensor", "school_week")) is not None


async def test_next_lesson_skips_cancelled_and_school_start(
    hass: HomeAssistant, entry: MockConfigEntry, portal: FakePortal, freezer
) -> None:
    from datetime import UTC, date, datetime, time

    from custom_components.schulportal_hessen.parsers import Lesson

    # Monday 07:00 local time (hass default zone is US/Pacific)
    freezer.move_to(datetime(2026, 11, 9, 15, 0, tzinfo=UTC))
    portal.lessons = [
        Lesson(0, "1", time(8, 0), time(8, 45), "M", "ABC", "R1", ""),
        Lesson(0, "2", time(8, 50), time(9, 35), "D", "DEF", "R2", ""),
    ]
    portal.substitutions = [make_sub(date(2026, 11, 9), "1")]  # subject_old "M"
    await setup(hass, entry)

    next_lesson = hass.states.get(eid(hass, entry, "sensor", "next_lesson"))
    assert next_lesson.state == "Deutsch"
    assert [s["subject"] for s in next_lesson.attributes["skipped_cancelled"]] == ["Mathematik"]

    start = hass.states.get(eid(hass, entry, "sensor", "school_start"))
    assert start.state == "2026-11-09T16:50:00+00:00"  # 08:50 local

    end = hass.states.get(eid(hass, entry, "sensor", "school_end"))
    assert end.state == "2026-11-09T17:35:00+00:00"  # 09:35 local
    overview = hass.states.get(eid(hass, entry, "sensor", "school_day_overview"))
    assert overview.state == "1"
    assert overview.attributes["total_lessons"] == 2
    assert overview.attributes["cancelled_lessons"] == 1
    assert overview.attributes["first_lesson"] == "Deutsch"


async def test_timetable_calendar_merges_substitutions(
    hass: HomeAssistant, entry: MockConfigEntry, portal: FakePortal, freezer
) -> None:
    from datetime import UTC, date, datetime, time

    from custom_components.schulportal_hessen.parsers import Lesson, Substitution

    freezer.move_to(datetime(2026, 11, 9, 15, 0, tzinfo=UTC))  # Monday 07:00 local
    portal.lessons = [
        Lesson(0, "1", time(8, 0), time(8, 45), "M", "ABC", "R1", ""),
        Lesson(0, "2", time(8, 50), time(9, 35), "D", "DEF", "R2", ""),
        Lesson(0, "3", time(9, 50), time(10, 35), "E", "GHI", "R3", ""),
    ]
    monday = date(2026, 11, 9)
    portal.substitutions = [
        make_sub(monday, "1"),  # M cancelled
        Substitution(
            day=monday, lesson="2", classes=("10A",), substitute="XYZ", teacher="DEF",
            kind="Vertretung", subject="D", subject_old="", room="R7", note="Aufgaben",
        ),
    ]
    await setup(hass, entry)

    result = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": eid(hass, entry, "calendar", "timetable"),
            "start_date_time": "2026-11-09T00:00:00-08:00",
            "end_date_time": "2026-11-09T23:59:00-08:00",
        },
        blocking=True,
        return_response=True,
    )
    events = result[eid(hass, entry, "calendar", "timetable")]["events"]
    summaries = [e["summary"] for e in events]
    assert summaries == ["Entfall: Mathematik", "Vertretung: Deutsch", "Englisch"]
    assert "XYZ" in events[1]["description"] and events[1]["location"] == "R7"


async def test_repair_issue_for_empty_timetable(
    hass: HomeAssistant, entry: MockConfigEntry, portal: FakePortal
) -> None:
    from datetime import time

    from homeassistant.helpers import issue_registry as ir

    from custom_components.schulportal_hessen.parsers import Lesson

    issue_id = f"timetable_structure_{entry.entry_id}"
    registry = ir.async_get(hass)

    async def refresh() -> None:
        coordinator = entry.runtime_data
        coordinator._data.fetched.pop("timetable", None)
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    portal.lessons = []
    await setup(hass, entry)  # first empty fetch
    assert registry.async_get_issue(DOMAIN, issue_id) is None  # one is not enough
    await refresh()  # second empty fetch
    assert registry.async_get_issue(DOMAIN, issue_id) is not None

    portal.lessons = [Lesson(0, "1", time(8, 0), time(8, 45), "M", "ABC", "R1", "")]
    await refresh()
    assert registry.async_get_issue(DOMAIN, issue_id) is None


async def test_two_accounts_are_distinguishable(
    hass: HomeAssistant, entry: MockConfigEntry, portal: FakePortal
) -> None:
    second = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234_anna.muster",
        data={**entry.data, "username": "anna.muster"},
    )
    await setup(hass, entry)
    await setup(hass, second)
    assert second.state is ConfigEntryState.LOADED

    one = hass.states.get(eid(hass, entry, "sensor", "substitutions"))
    two = hass.states.get(eid(hass, second, "sensor", "substitutions"))
    assert one.entity_id != two.entity_id
    assert one.attributes["account"] == entry.entry_id
    assert two.attributes["account"] == second.entry_id
    assert one.attributes["account"] != two.attributes["account"]


async def test_new_entry_title_contains_username(hass: HomeAssistant) -> None:
    schools = [{"id": "1234", "name": "Testschule", "city": "Teststadt"}]
    with (
        patch("custom_components.schulportal_hessen.config_flow.search_schools", AsyncMock(return_value=schools)),
        patch("custom_components.schulportal_hessen.config_flow.SphClient", return_value=AsyncMock()),
        patch("custom_components.schulportal_hessen.async_setup_entry", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"query": "Test"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"school": "1234"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "anna.muster", "password": "x"}
        )
    assert result["title"] == "Testschule, Teststadt (anna.muster)"


async def test_history_survives_restart(
    hass: HomeAssistant, entry: MockConfigEntry, portal: FakePortal, hass_storage
) -> None:
    from custom_components.schulportal_hessen.coordinator import history_store_key

    saved = [{"at": "2026-11-09T07:00:00+00:00", "kind": "room_changed",
              "data": {"old_room": "R1", "new_room": "R2"}}]
    hass_storage[history_store_key(entry.entry_id)] = {
        "version": 1, "minor_version": 1, "key": history_store_key(entry.entry_id),
        "data": {"entries": saved + ["junk"]},
    }
    await setup(hass, entry)
    state = hass.states.get(eid(hass, entry, "sensor", "change_history"))
    assert state.state == "1"
    assert state.attributes["entries"][0]["data"]["new_room"] == "R2"


async def test_data_quality_flags_empty_timetable(
    hass: HomeAssistant, entry: MockConfigEntry, portal: FakePortal
) -> None:
    portal.lessons = []
    await setup(hass, entry)
    state = hass.states.get(eid(hass, entry, "sensor", "data_quality"))
    assert state.state == "warning"
    assert "timetable_empty" in state.attributes["issues"]
