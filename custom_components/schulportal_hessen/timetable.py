"""Timetable helpers (no Home Assistant dependencies)."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import date, datetime, timedelta, tzinfo

from .cancellations import cancellations_on, parse_periods
from .parsers import Lesson, Substitution


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


def is_lesson_cancelled(
    lesson: Lesson, day: date, cancellations: Iterable[Substitution]
) -> bool:
    """True if a cancellation row covers this lesson on ``day``.

    The substitution plan is per class while the timetable is personal, so a
    row only counts if its period matches the lesson's first period AND the
    cancelled subject equals the lesson's subject (when the row names one).
    Anything uncertain counts as "not cancelled" so a real lesson is never
    hidden. Only the first period of double lessons is checked.
    """
    if not lesson.period.isdigit():
        return False
    number = int(lesson.period)
    for row in cancellations_on(cancellations, day):
        if number not in parse_periods(row.lesson):
            continue
        if row.subject_old and row.subject_old.strip().casefold() != lesson.subject.strip().casefold():
            continue
        return True
    return False


def upcoming_lessons(
    lessons: list[Lesson],
    now: datetime,
    tz: tzinfo,
    cancellations: Iterable[Substitution] = (),
    days: int = 14,
) -> list[tuple[Lesson, datetime, datetime, bool]]:
    """Lessons that have not ended yet, ordered by start, with a cancelled flag."""
    cancellations = list(cancellations)
    result = [
        (lesson, start, end, is_lesson_cancelled(lesson, start.date(), cancellations))
        for lesson, start, end in lessons_between(lessons, now, now + timedelta(days=days), tz)
        if end > now
    ]
    return sorted(result, key=lambda item: item[1])


def next_lesson_skipping_cancelled(
    lessons: list[Lesson],
    now: datetime,
    tz: tzinfo,
    cancellations: Iterable[Substitution] = (),
) -> tuple[tuple[Lesson, datetime, datetime] | None, list[tuple[Lesson, datetime]]]:
    """Return (next lesson that takes place, cancelled lessons skipped on the way)."""
    skipped: list[tuple[Lesson, datetime]] = []
    for lesson, start, end, cancelled in upcoming_lessons(lessons, now, tz, cancellations):
        if cancelled:
            skipped.append((lesson, start))
            continue
        return (lesson, start, end), skipped
    return None, skipped


def next_school_start(
    lessons: list[Lesson],
    now: datetime,
    tz: tzinfo,
    cancellations: Iterable[Substitution] = (),
) -> tuple[Lesson, datetime] | None:
    """Start of the first lesson that takes place on the next day that has one.

    Only days whose first non-cancelled lesson starts after ``now`` count, so
    after today's first lesson began this points to the next school day.
    """
    first_per_day: dict[date, tuple[Lesson, datetime]] = {}
    for lesson, start, _end, cancelled in upcoming_lessons(lessons, now, tz, cancellations):
        if cancelled:
            continue
        day = start.date()
        if day not in first_per_day or start < first_per_day[day][1]:
            first_per_day[day] = (lesson, start)
    later = [item for item in first_per_day.values() if item[1] > now]
    return min(later, key=lambda item: item[1]) if later else None
