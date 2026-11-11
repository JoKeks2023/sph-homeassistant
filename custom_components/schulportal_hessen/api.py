"""Read-only client for Schulportal Hessen (Lanis).

Login flow (observed on the live portal, cross-checked against the MIT
licensed liblanis-for-python): POST credentials to login.schulportal.hessen.de,
follow connect.schulportal.hessen.de by hand and read the ``sid`` cookie.

Only GET/HEAD requests are used after login. Credentials, cookies and URLs with
query tokens are never logged.
"""

from __future__ import annotations

import asyncio
import json
import logging
import unicodedata
from typing import Any

import aiohttp
from yarl import URL

from .parsers import (
    Homework,
    Lesson,
    Substitution,
    parse_applet_names,
    parse_homework,
    parse_substitutions,
    parse_timetable,
)

_LOGGER = logging.getLogger(__name__)

START = "https://start.schulportal.hessen.de/"
LOGIN = "https://login.schulportal.hessen.de/"
CONNECT = "https://connect.schulportal.hessen.de/"
SCHOOLS = "https://startcache.schulportal.hessen.de/exporteur.php"
TIMEOUT = aiohttp.ClientTimeout(total=25)
USER_AGENT = "HomeAssistant-SchulportalHessen (read-only integration)"


class SphError(Exception):
    """Base error."""


class SphAuthError(SphError):
    """Login failed (wrong credentials or school)."""


class SphConnectionError(SphError):
    """Portal unreachable or timed out."""


class SphModuleError(SphError):
    """A portal module could not be loaded (not enabled or markup changed)."""


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.replace("-", " "))
    return "".join(c for c in value if not unicodedata.combining(c)).casefold().strip()


async def search_schools(
    session: aiohttp.ClientSession, query: str, limit: int = 100
) -> list[dict[str, str]]:
    """Search the public school list by name, city or school number."""
    try:
        async with session.get(SCHOOLS, params={"a": "schoollist"}, timeout=TIMEOUT) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError) as err:
        raise SphConnectionError from err

    needle = _norm(query)
    results: list[dict[str, str]] = []
    for municipality in data:
        for school in municipality.get("Schulen", []):
            haystack = " ".join(
                _norm(str(school.get(key, ""))) for key in ("Name", "Ort", "Id")
            ) + " " + _norm(str(municipality.get("Name", "")))
            if needle in haystack:
                results.append(
                    {
                        "id": str(school["Id"]),
                        "name": str(school.get("Name", "")),
                        "city": str(school.get("Ort", "")),
                    }
                )
                if len(results) > limit:
                    return results
    return results


class SphClient:
    """Session-keeping read-only client."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        school_id: str,
        username: str,
        password: str,
    ) -> None:
        self._session = session
        self._school_id = school_id
        self._username = username
        self._password = password
        self._logged_in = False
        self._lock = asyncio.Lock()

    async def login(self) -> None:
        """Create a new portal session."""
        self._session.cookie_jar.clear()
        headers = {"User-Agent": USER_AGENT}
        try:
            async with self._session.post(
                LOGIN,
                params={"i": self._school_id},
                data={
                    "user": f"{self._school_id}.{self._username}",
                    "user2": self._username,
                    "password": self._password,
                },
                headers=headers,
                allow_redirects=False,
                timeout=TIMEOUT,
            ):
                pass
            async with self._session.head(
                CONNECT, headers=headers, allow_redirects=False, timeout=TIMEOUT
            ) as resp:
                target = resp.headers.get("Location")
            if not target:
                raise SphAuthError("no redirect after login")
            async with self._session.head(
                URL(CONNECT).join(URL(target)),
                headers=headers,
                allow_redirects=False,
                timeout=TIMEOUT,
            ):
                pass
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SphConnectionError from err

        if "sid" not in self._session.cookie_jar.filter_cookies(URL(START)):
            raise SphAuthError("no session cookie")
        self._logged_in = True
        _LOGGER.debug("Logged in to Schulportal Hessen")

    async def logout(self) -> None:
        """End the portal session (best effort)."""
        if not self._logged_in:
            return
        try:
            async with self._session.get(
                START + "index.php",
                params={"logout": "all"},
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
            ):
                pass
        except (aiohttp.ClientError, TimeoutError):
            pass
        self._logged_in = False

    async def _get_text(self, path: str, params: dict[str, str] | None = None) -> str:
        async with self._lock:
            for _attempt in (1, 2):
                if not self._logged_in:
                    await self.login()
                try:
                    async with self._session.get(
                        START + path,
                        params=params,
                        headers={"User-Agent": USER_AGENT},
                        timeout=TIMEOUT,
                    ) as resp:
                        text = await resp.text()
                        expired = resp.url.path.endswith("forward.php") or (
                            "forward.js" in text
                        )
                except (aiohttp.ClientError, TimeoutError) as err:
                    raise SphConnectionError from err
                if resp.status >= 500:
                    raise SphConnectionError(f"portal error {resp.status}")
                if not expired:
                    return text
                # Session ended (or module not enabled): log in once more.
                self._logged_in = False
        raise SphModuleError(f"{path} not available")

    async def get_applets(self) -> list[str]:
        """Return names of the portal modules enabled for this account."""
        text = await self._get_text("startseite.php", {"a": "ajax", "f": "apps"})
        try:
            payload: dict[str, Any] = json.loads(text)
        except ValueError as err:
            raise SphModuleError("applet list unreadable") from err
        return parse_applet_names(payload)

    async def get_substitutions(self) -> list[Substitution]:
        """Fetch the substitution plan."""
        return parse_substitutions(await self._get_text("vertretungsplan.php"))

    async def get_timetable(self) -> tuple[str | None, list[Lesson]]:
        """Fetch the personal timetable. Returns (own class, lessons)."""
        return parse_timetable(await self._get_text("stundenplan.php"))

    async def get_homework(self) -> list[Homework]:
        """Fetch current homework from the course list."""
        return parse_homework(await self._get_text("meinunterricht.php"))

    async def get_calendar_ics(self, year: int) -> str:
        """Fetch the iCal export of a calendar year."""
        text = await self._get_text(
            "kalender.php", {"a": "export", "export": "ical", "year": str(year)}
        )
        if "BEGIN:VCALENDAR" not in text:
            raise SphModuleError("calendar export unreadable")
        return text
