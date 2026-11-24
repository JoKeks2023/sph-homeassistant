"""Cancellation (Entfall) helpers (no Home Assistant dependencies)."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
import re

from .const import CANCELLATION_KINDS
from .parsers import Substitution

_RANGE_RE = re.compile(r"(\d+)\s*[-–—]\s*(\d+)")
_NUMBER_RE = re.compile(r"\d+")


def parse_periods(value: str) -> frozenset[int]:
    """Resolve a period cell ("5", "3 - 4", "1-2, 6") into a set of periods."""
    periods: set[int] = set()
    for start, end in _RANGE_RE.findall(value):
        low, high = sorted((int(start), int(end)))
        if high - low <= 12:  # guard against garbage input
            periods.update(range(low, high + 1))
    rest = _RANGE_RE.sub(" ", value)
    periods.update(int(n) for n in _NUMBER_RE.findall(rest))
    return frozenset(periods)


def is_cancellation(sub: Substitution) -> bool:
    """Return True if the row says the lesson does not take place."""
    return sub.kind.strip().casefold() in CANCELLATION_KINDS


def cancellations_on(subs: Iterable[Substitution], day: date) -> list[Substitution]:
    """Cancellation rows of one day, ordered by first period."""
    found = [s for s in subs if s.day == day and is_cancellation(s)]
    return sorted(found, key=lambda s: min(parse_periods(s.lesson), default=99))


def cancelled_periods(subs: Iterable[Substitution]) -> frozenset[int]:
    """All periods covered by the given cancellation rows."""
    periods: set[int] = set()
    for sub in subs:
        periods |= parse_periods(sub.lesson)
    return frozenset(periods)


def first_hours_cancelled(subs: Iterable[Substitution], count: int) -> bool:
    """True if any of periods 1..count is cancelled."""
    return any(p <= count for p in cancelled_periods(subs))
