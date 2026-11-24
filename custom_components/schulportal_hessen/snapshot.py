"""(De)serialise cached portal data for restart recovery (no HA dependencies)."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from .parsers import Homework, Lesson, Substitution

SNAPSHOT_VERSION = 1


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def dump(
    *,
    applets: list[str],
    own_class: str | None,
    substitutions: list[Substitution],
    lessons: list[Lesson],
    homework: list[Homework],
    fetched: dict[str, datetime],
) -> dict[str, Any]:
    """Return a JSON serialisable snapshot (no credentials, no tokens)."""
    return {
        "version": SNAPSHOT_VERSION,
        "applets": list(applets),
        "own_class": own_class,
        "substitutions": [
            {
                "day": s.day.isoformat(),
                "lesson": s.lesson,
                "classes": list(s.classes),
                "substitute": s.substitute,
                "teacher": s.teacher,
                "kind": s.kind,
                "subject": s.subject,
                "subject_old": s.subject_old,
                "room": s.room,
                "note": s.note,
            }
            for s in substitutions
        ],
        "lessons": [
            {
                "weekday": item.weekday,
                "period": item.period,
                "start": item.start.strftime("%H:%M"),
                "end": item.end.strftime("%H:%M"),
                "subject": item.subject,
                "teacher": item.teacher,
                "room": item.room,
                "title": item.title,
            }
            for item in lessons
        ],
        "homework": [
            {
                "uid": h.uid,
                "course": h.course,
                "topic": h.topic,
                "day": h.day.isoformat() if h.day else None,
                "text": h.text,
            }
            for h in homework
        ],
        "fetched": {k: v.isoformat() for k, v in fetched.items()},
    }


def load(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Rebuild typed data from a snapshot. Returns None if unusable."""
    try:
        if raw.get("version") != SNAPSHOT_VERSION:
            return None
        return {
            "applets": list(raw["applets"]),
            "own_class": raw["own_class"],
            "substitutions": [
                Substitution(
                    day=date.fromisoformat(s["day"]),
                    lesson=s["lesson"],
                    classes=tuple(s["classes"]),
                    substitute=s["substitute"],
                    teacher=s["teacher"],
                    kind=s["kind"],
                    subject=s["subject"],
                    subject_old=s["subject_old"],
                    room=s["room"],
                    note=s["note"],
                )
                for s in raw["substitutions"]
            ],
            "lessons": [
                Lesson(
                    weekday=item["weekday"],
                    period=item["period"],
                    start=time.fromisoformat(item["start"]),
                    end=time.fromisoformat(item["end"]),
                    subject=item["subject"],
                    teacher=item["teacher"],
                    room=item["room"],
                    title=item["title"],
                )
                for item in raw["lessons"]
            ],
            "homework": [
                Homework(
                    uid=h["uid"],
                    course=h["course"],
                    topic=h["topic"],
                    day=_date(h["day"]),
                    text=h["text"],
                )
                for h in raw["homework"]
            ],
            "fetched": {
                k: datetime.fromisoformat(v) for k, v in raw["fetched"].items()
            },
        }
    except (KeyError, TypeError, ValueError):
        return None
