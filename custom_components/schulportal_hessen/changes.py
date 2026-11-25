"""Detect changes of already known entries (no Home Assistant dependencies)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from .parsers import Homework, Substitution


def _key(sub: Substitution) -> tuple[str, str, str, str, str]:
    """Identity of a substitution ignoring room and teacher (those may change)."""
    return (
        sub.day.isoformat(),
        sub.lesson,
        ",".join(sub.classes),
        sub.subject_old or sub.subject,
        sub.kind,
    )


def substitution_changes(
    old: Iterable[Substitution], new: Iterable[Substitution]
) -> list[tuple[str, dict[str, str]]]:
    """Return ("room"|"teacher", event data) for entries whose room/substitute changed.

    Entries are paired by day, period, class, subject and kind. If a key occurs
    more than once on either side the pairing is ambiguous and is skipped, so
    no false change is reported.
    """
    old = list(old)
    new = list(new)
    old_counts = Counter(_key(s) for s in old)
    new_counts = Counter(_key(s) for s in new)
    before = {_key(s): s for s in old if old_counts[_key(s)] == 1}
    result: list[tuple[str, dict[str, str]]] = []
    for sub in new:
        key = _key(sub)
        prev = before.get(key)
        if prev is None or new_counts[key] != 1:
            continue
        base = {
            "date": sub.day.isoformat(),
            "lesson": sub.lesson,
            "subject": sub.subject_old or sub.subject,
        }
        if prev.room != sub.room:
            result.append(("room", {**base, "old_room": prev.room, "new_room": sub.room}))
        if prev.substitute != sub.substitute:
            result.append(
                (
                    "teacher",
                    {**base, "old_teacher": prev.substitute, "new_teacher": sub.substitute},
                )
            )
    return result


def homework_changes(old: Iterable[Homework], new: Iterable[Homework]) -> list[dict[str, str]]:
    """Return event data for known homework entries whose text or topic changed."""
    before = {h.uid: h for h in old}
    result = []
    for item in new:
        prev = before.get(item.uid)
        if prev is None or (prev.text, prev.topic) == (item.text, item.topic):
            continue
        result.append(
            {
                **item.as_dict(),
                "old_text": prev.text,
                "new_text": item.text,
                "old_topic": prev.topic,
            }
        )
    return result
