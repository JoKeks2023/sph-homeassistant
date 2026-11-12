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
