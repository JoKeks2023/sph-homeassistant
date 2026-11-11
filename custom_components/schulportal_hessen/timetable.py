"""Timetable helpers (no Home Assistant dependencies)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, timedelta, tzinfo

from .parsers import Lesson


def lesson_window(lesson: Lesson, day: date, tz: tzinfo) -> tuple[datetime, datetime]:
    """Return start/end datetimes of a lesson on a given day."""
    return (
        datetime.combine(day, lesson.start, tzinfo=tz),
        datetime.combine(day, lesson.end, tzinfo=tz),
    )


def lessons_between(
    lessons: list[Lesson], start: datetime, end: datetime, tz: tzinfo
) -> Iterator[tuple[Lesson, datetime, datetime]]:
    """Yield lessons overlapping [start, end) by expanding the weekly plan."""
    day = start.astimezone(tz).date()
    last_day = end.astimezone(tz).date()
    while day <= last_day:
        for lesson in lessons:
            if lesson.weekday != day.weekday():
                continue
            lesson_start, lesson_end = lesson_window(lesson, day, tz)
            if lesson_end > start and lesson_start < end:
                yield lesson, lesson_start, lesson_end
        day += timedelta(days=1)


def next_lesson(
    lessons: list[Lesson], now: datetime, tz: tzinfo
) -> tuple[Lesson, datetime, datetime] | None:
    """Return the current or next lesson within the next 14 days."""
    found = list(lessons_between(lessons, now, now + timedelta(days=14), tz))
    found = [item for item in found if item[2] > now]
    return min(found, key=lambda item: item[1]) if found else None
