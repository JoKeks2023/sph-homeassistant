"""Fixtures for the Home Assistant based tests (run in CI only)."""

from __future__ import annotations

from collections.abc import Generator
from datetime import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.schulportal_hessen.api import SphError
from custom_components.schulportal_hessen.const import (
    CONF_SCHOOL_ID,
    CONF_SCHOOL_NAME,
    DOMAIN,
)
from custom_components.schulportal_hessen.parsers import Lesson, Substitution


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations):
    """Allow loading custom_components in every test."""


@pytest.fixture(autouse=True)
def _no_http_frontend(hass) -> Generator[None]:
    """Treat the http/frontend dependencies as set up.

    The integration only registers its Lovelace card with them; starting the
    real frontend is neither needed nor possible in the test environment.
    """
    hass.config.components.update({"http", "frontend"})
    hass.http = MagicMock(async_register_static_paths=AsyncMock())
    with patch("custom_components.schulportal_hessen.add_extra_js_url"):
        yield


def make_sub(day, lesson, kind="Entfall", classes=("10A",), teacher="ABC") -> Substitution:
    """Build a substitution row."""
    return Substitution(
        day=day, lesson=lesson, classes=classes, substitute="", teacher=teacher,
        kind=kind, subject="", subject_old="M", room="", note="",
    )


class FakePortal:
    """Configurable stand-in for the portal; one instance per test."""

    def __init__(self) -> None:
        self.applets = ["Vertretungsplan", "Stundenplan"]
        self.substitutions: list[Substitution] = []
        self.lessons = [
            Lesson(0, "1", time(8, 0), time(8, 45), "M", "ABC", "R1", "Mathe")
        ]
        self.own_class: str | None = "10A"
        self.homework: list = []
        self.fail_all = False
        self.fail_homework = False


class FakeClient:
    """Replacement for SphClient reading from a FakePortal."""

    portal: FakePortal

    def __init__(self, *args, **kwargs) -> None:
        pass

    def _check(self) -> None:
        if self.portal.fail_all:
            raise SphError("portal down")

    async def login(self) -> None:
        self._check()

    async def logout(self) -> None:
        return None

    async def get_applets(self) -> list[str]:
        self._check()
        return list(self.portal.applets)

    async def get_substitutions(self):
        self._check()
        return list(self.portal.substitutions)

    async def get_timetable(self):
        self._check()
        return self.portal.own_class, list(self.portal.lessons)

    async def get_homework(self):
        self._check()
        if self.portal.fail_homework:
            raise SphError("homework failed")
        return list(self.portal.homework)

    async def get_calendar_ics(self, year: int) -> str:
        self._check()
        return "BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n"


@pytest.fixture
def portal() -> Generator[FakePortal]:
    """Patch the client used by the integration and yield the fake portal."""
    fake = FakePortal()
    FakeClient.portal = fake
    with patch("custom_components.schulportal_hessen.SphClient", FakeClient):
        yield fake


@pytest.fixture
def entry() -> MockConfigEntry:
    """A config entry for the fake account."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234_max.muster",
        data={
            CONF_SCHOOL_ID: "1234",
            CONF_SCHOOL_NAME: "Testschule, Teststadt",
            "username": "max.muster",
            "password": "geheim",
        },
    )
