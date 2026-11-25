"""Timetable helpers (no Home Assistant dependencies)."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo

from .cancellations import is_cancellation, parse_periods
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


def matching_substitution(
    lesson: Lesson, day: date, rows: Iterable[Substitution]
) -> Substitution | None:
    """Return the substitution row that concerns this lesson on ``day``, if any.

    The substitution plan is per class while the timetable is personal, so a
    row only counts if its period matches the lesson's first period AND, when
    the row names a subject (old or new), that subject equals the lesson's.
    Anything uncertain counts as "no match" so a real lesson is never altered.
    Only the first period of double lessons is checked. A cancellation wins
    over other kinds if several rows match.
    """
    if not lesson.period.isdigit():
        return None
    number = int(lesson.period)
    own = lesson.subject.strip().casefold()
    matches: list[Substitution] = []
    for row in rows:
        if row.day != day or number not in parse_periods(row.lesson):
            continue
        named = {x.strip().casefold() for x in (row.subject_old, row.subject) if x.strip()}
        if named and own not in named:
            continue
        matches.append(row)
    if not matches:
        return None
    return next((m for m in matches if is_cancellation(m)), matches[0])


def is_lesson_cancelled(
    lesson: Lesson, day: date, cancellations: Iterable[Substitution]
) -> bool:
    """True if a cancellation row covers this lesson on ``day``."""
    row = matching_substitution(lesson, day, cancellations)
    return row is not None and is_cancellation(row)


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


FREE_PERIOD_MIN_GAP = timedelta(minutes=30)


@dataclass(frozen=True)
class DaySummary:
    """Computed overview of one school day."""

    day: date
    total: int
    cancelled: int
    substitutions: int
    first: tuple[Lesson, datetime] | None
    last: tuple[Lesson, datetime] | None
    free_periods: tuple[tuple[datetime, datetime], ...]


def day_summary(
    lessons: list[Lesson],
    day: date,
    tz: tzinfo,
    rows: Iterable[Substitution] = (),
) -> DaySummary | None:
    """Summarise ``day`` from the timetable and the class's substitution rows.

    First/last and free periods only consider lessons that take place. A free
    period is a gap longer than ``FREE_PERIOD_MIN_GAP`` between two lessons
    that take place (normal breaks are shorter); this is a heuristic.
    Returns None if the timetable has no lesson on that weekday.
    """
    rows = [r for r in rows if r.day == day]
    planned = sorted(
        (item for item in lessons if item.weekday == day.weekday()),
        key=lambda item: item.start,
    )
    if not planned:
        return None
    cancelled = 0
    changed = 0
    held: list[tuple[Lesson, datetime, datetime]] = []
    for lesson in planned:
        start, end = lesson_window(lesson, day, tz)
        row = matching_substitution(lesson, day, rows)
        if row is not None and is_cancellation(row):
            cancelled += 1
            continue
        if row is not None:
            changed += 1
        held.append((lesson, start, end))
    gaps = tuple(
        (a[2], b[1])
        for a, b in zip(held, held[1:], strict=False)
        if b[1] - a[2] > FREE_PERIOD_MIN_GAP
    )
    return DaySummary(
        day=day,
        total=len(planned),
        cancelled=cancelled,
        substitutions=changed,
        first=(held[0][0], held[0][1]) if held else None,
        last=(held[-1][0], held[-1][2]) if held else None,
        free_periods=gaps,
    )


def relevant_day_summary(
    lessons: list[Lesson], now: datetime, tz: tzinfo, rows: Iterable[Substitution] = ()
) -> DaySummary | None:
    """Today's summary while today still has a lesson to come, else the next school day."""
    rows = list(rows)
    day = now.astimezone(tz).date()
    for offset in range(14):
        summary = day_summary(lessons, day + timedelta(days=offset), tz, rows)
        if summary is None:
            continue
        if summary.last is None:  # whole day cancelled
            if offset == 0:
                return summary
            continue
        if summary.last[1] > now:
            return summary
    return None
