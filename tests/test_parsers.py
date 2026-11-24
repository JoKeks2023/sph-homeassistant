"""Tests for the portal HTML parsers (synthetic fixtures)."""

from datetime import date, datetime, time, timedelta, timezone
import importlib
from pathlib import Path
import sys
import types

# Load the pure modules through a stub package so that the integration's
# __init__.py (which needs Home Assistant) is not imported.
PKG_DIR = Path(__file__).parent.parent / "custom_components" / "schulportal_hessen"
_pkg = types.ModuleType("sph")
_pkg.__path__ = [str(PKG_DIR)]
sys.modules["sph"] = _pkg
parsers = importlib.import_module("sph.parsers")
timetable = importlib.import_module("sph.timetable")
parse_homework = parsers.parse_homework
parse_substitutions = parsers.parse_substitutions
parse_timetable = parsers.parse_timetable
lessons_between = timetable.lessons_between
next_lesson = timetable.next_lesson

FIX = Path(__file__).parent / "fixtures"
TZ = timezone(timedelta(hours=1))


def read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def test_substitutions():
    items = parse_substitutions(read("vertretungsplan.html"))
    assert len(items) == 3
    first = items[0]
    assert first.day == date(2026, 11, 10)
    assert first.classes == ("10A", "10B")
    assert (first.lesson, first.substitute, first.teacher) == ("3 - 4", "MUS", "ABC")
    assert (first.kind, first.subject, first.subject_old, first.room) == ("Vertretung", "M", "E", "R1.23")
    assert items[2].day == date(2026, 11, 11)
    assert len({i.uid for i in items}) == 3


def test_timetable_personal_plan_and_rowspan():
    own_class, lessons = parse_timetable(read("stundenplan.html"))
    assert own_class == "10A"
    subjects = [(l.weekday, l.subject) for l in lessons]
    # personal plan only (class plan has subject X)
    assert "X" not in {s for _, s in subjects}
    assert (0, "M") in subjects
    maths = next(l for l in lessons if l.subject == "M")
    # rowspan=2 -> lasts until end of second period
    assert (maths.start, maths.end, maths.room, maths.teacher) == (time(8, 0), time(9, 35), "R1.23", "ABC")
    # two lessons in one cell are returned separately, Wednesday = 2
    assert {l.subject for l in lessons if l.weekday == 2} == {"E", "F"}
    # Tuesday second period (cell shifts left because of the rowspan on Monday)
    deutsch = next(l for l in lessons if l.subject == "D")
    assert (deutsch.weekday, deutsch.start) == (1, time(8, 50))


def test_homework_only_rows_with_text():
    items = parse_homework(read("meinunterricht.html"))
    assert len(items) == 1
    assert items[0].course == "Mathematik 10A"
    assert items[0].day == date(2026, 11, 6)
    assert items[0].text.startswith("Aufgaben 1-5")
    assert items[0].uid == "3001-12"


def test_next_lesson_and_expansion():
    _, lessons = parse_timetable(read("stundenplan.html"))
    monday = datetime(2026, 11, 9, 7, 0, tzinfo=TZ)  # a Monday
    found = next_lesson(lessons, monday, TZ)
    assert found and found[0].subject == "M" and found[1].hour == 8
    # after Monday's lesson the next one is Tuesday
    after = datetime(2026, 11, 9, 12, 0, tzinfo=TZ)
    assert next_lesson(lessons, after, TZ)[0].subject == "D"
    week = list(lessons_between(lessons, monday, monday + timedelta(days=5), TZ))
    assert len(week) == len(lessons)


def test_full_subject():
    subjects = importlib.import_module("sph.subjects")
    assert subjects.full_subject("M") == "Mathematik"
    assert subjects.full_subject("AG_Astronomie") == "AG Astronomie"
    assert subjects.full_subject("XYZ") == "XYZ"


snapshot = importlib.import_module("sph.snapshot")


def test_snapshot_roundtrip():
    subs = parse_substitutions(read("vertretungsplan.html"))
    own_class, lessons = parse_timetable(read("stundenplan.html"))
    homework = parse_homework(read("meinunterricht.html"))
    fetched = {"substitutions": datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)}
    raw = snapshot.dump(
        applets=["Vertretungsplan"], own_class=own_class, substitutions=subs,
        lessons=lessons, homework=homework, fetched=fetched,
    )
    import json
    restored = snapshot.load(json.loads(json.dumps(raw)))  # must survive JSON
    assert restored["substitutions"] == subs
    assert restored["lessons"] == lessons
    assert restored["homework"] == homework
    assert restored["own_class"] == own_class
    assert restored["fetched"] == fetched


def test_snapshot_rejects_garbage():
    assert snapshot.load({"version": 99}) is None
    assert snapshot.load({"version": 1}) is None
    assert snapshot.load({}) is None
redaction = importlib.import_module("sph.redaction")


def test_diagnostics_redacts_and_has_no_content():
    out = redaction.summarize(
        entry_data={"username": "max.muster", "password": "geheim", "school_id": "1234"},
        options={"first_hours": 2},
        applets=["Vertretungsplan"],
        own_class="10A",
        counts={"substitutions": 3},
        fetched={"substitutions": "2026-11-10T08:00:00+00:00"},
        last_update_success=True,
    )
    text = repr(out)
    assert "max.muster" not in text and "geheim" not in text and "1234" not in text
    assert "10A" not in text
    assert out["entry"]["password"] == redaction.REDACTED
    assert out["own_class_known"] is True
cancellations = importlib.import_module("sph.cancellations")


def test_parse_periods():
    pp = cancellations.parse_periods
    assert pp("5") == {5}
    assert pp("3 - 4") == {3, 4}
    assert pp("1-2, 6") == {1, 2, 6}
    assert pp("") == frozenset()
    assert pp("x") == frozenset()


def test_cancellations_from_fixture():
    items = parse_substitutions(read("vertretungsplan.html"))
    rows = cancellations.cancellations_on(items, date(2026, 11, 10))
    assert [r.lesson for r in rows] == ["5"]  # "Vertretung" 3-4 is not an Entfall
    assert cancellations.cancelled_periods(rows) == {5}
    assert not cancellations.first_hours_cancelled(rows, 2)
    assert cancellations.first_hours_cancelled(rows, 5)
    assert cancellations.cancellations_on(items, date(2026, 11, 11)) == []


def test_first_hours_with_range():
    sub = parsers.Substitution(
        day=date(2026, 11, 12), lesson="2 - 3", classes=("10A",), substitute="",
        teacher="ABC", kind="Entfall", subject="", subject_old="M", room="", note="",
    )
    assert cancellations.is_cancellation(sub)
    assert cancellations.first_hours_cancelled([sub], 2)
    assert not cancellations.first_hours_cancelled([sub], 1)


def _sub(day, lesson, subject_old="M", kind="Entfall"):
    return parsers.Substitution(
        day=day, lesson=lesson, classes=("10A",), substitute="", teacher="ABC",
        kind=kind, subject="", subject_old=subject_old, room="", note="",
    )


def _plan():
    mk = parsers.Lesson
    return [
        mk(0, "1", time(8, 0), time(8, 45), "M", "ABC", "R1", ""),
        mk(0, "2", time(8, 50), time(9, 35), "D", "DEF", "R2", ""),
        mk(2, "1", time(8, 0), time(8, 45), "E", "GHI", "R3", ""),
    ]


MONDAY = date(2026, 11, 9)


def test_next_lesson_skips_cancelled():
    now = datetime(2026, 11, 9, 7, 0, tzinfo=TZ)
    found, skipped = timetable.next_lesson_skipping_cancelled(
        _plan(), now, TZ, [_sub(MONDAY, "1")]
    )
    assert found[0].subject == "D"
    assert [item.subject for item, _ in skipped] == ["M"]


def test_cancellation_must_match_subject_and_period():
    now = datetime(2026, 11, 9, 7, 0, tzinfo=TZ)
    # other subject than the lesson -> not my lesson, must NOT be hidden
    found, skipped = timetable.next_lesson_skipping_cancelled(
        _plan(), now, TZ, [_sub(MONDAY, "1", subject_old="X")]
    )
    assert found[0].subject == "M" and skipped == []
    # row without subject matches by period alone
    found, _ = timetable.next_lesson_skipping_cancelled(
        _plan(), now, TZ, [_sub(MONDAY, "1", subject_old="")]
    )
    assert found[0].subject == "D"
    # a "Vertretung" is not a cancellation
    found, _ = timetable.next_lesson_skipping_cancelled(
        _plan(), now, TZ, [_sub(MONDAY, "1", kind="Vertretung")]
    )
    assert found[0].subject == "M"


def test_next_school_start():
    early = datetime(2026, 11, 9, 7, 0, tzinfo=TZ)
    assert timetable.next_school_start(_plan(), early, TZ)[1] == datetime(2026, 11, 9, 8, 0, tzinfo=TZ)
    # first lesson cancelled -> starts with the second one
    got = timetable.next_school_start(_plan(), early, TZ, [_sub(MONDAY, "1")])
    assert got[1] == datetime(2026, 11, 9, 8, 50, tzinfo=TZ)
    # whole Monday cancelled -> Wednesday
    got = timetable.next_school_start(
        _plan(), early, TZ, [_sub(MONDAY, "1"), _sub(MONDAY, "2", subject_old="D")]
    )
    assert got[1] == datetime(2026, 11, 11, 8, 0, tzinfo=TZ)
    # after today's first lesson began, today no longer counts -> Wednesday
    late = datetime(2026, 11, 9, 8, 10, tzinfo=TZ)
    assert timetable.next_school_start(_plan(), late, TZ)[1] == datetime(2026, 11, 11, 8, 0, tzinfo=TZ)
