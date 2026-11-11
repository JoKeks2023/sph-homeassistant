"""HTML parsers for Schulportal Hessen pages.

Pure functions without Home Assistant dependencies so they can be unit tested.
The markup was analysed from the live portal; the portal has no official API
and may change at any time, so every parser fails soft (returns what it can).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
import re

from bs4 import BeautifulSoup, Tag

DATE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")
TIME_RE = re.compile(r"(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})")
ROOM_RE = re.compile(r"\bRaum\s+(\S+)", re.IGNORECASE)
CLASS_SPLIT_RE = re.compile(r"[,;\s]+")


@dataclass(frozen=True)
class Substitution:
    """One row of the substitution plan (Vertretungsplan)."""

    day: date
    lesson: str
    classes: tuple[str, ...]
    substitute: str
    teacher: str
    kind: str
    subject: str
    subject_old: str
    room: str
    note: str

    @property
    def uid(self) -> str:
        """Stable identity used to detect new entries."""
        return "|".join(
            (
                self.day.isoformat(),
                self.lesson,
                ",".join(self.classes),
                self.teacher,
                self.subject_old or self.subject,
                self.kind,
            )
        )

    def as_dict(self) -> dict[str, str | list[str]]:
        """Return a JSON serialisable dict."""
        return {
            "date": self.day.isoformat(),
            "lesson": self.lesson,
            "classes": list(self.classes),
            "substitute": self.substitute,
            "teacher": self.teacher,
            "type": self.kind,
            "subject": self.subject,
            "subject_old": self.subject_old,
            "room": self.room,
            "note": self.note,
        }


@dataclass(frozen=True)
class Lesson:
    """One lesson of the regular weekly timetable (Stundenplan)."""

    weekday: int  # Monday = 0
    period: str
    start: time
    end: time
    subject: str
    teacher: str
    room: str
    title: str

    def as_dict(self) -> dict[str, str | int]:
        """Return a JSON serialisable dict."""
        return {
            "weekday": self.weekday,
            "period": self.period,
            "start": self.start.strftime("%H:%M"),
            "end": self.end.strftime("%H:%M"),
            "subject": self.subject,
            "teacher": self.teacher,
            "room": self.room,
        }


@dataclass(frozen=True)
class Homework:
    """Latest homework entry of a course (mein Unterricht)."""

    uid: str
    course: str
    topic: str
    day: date | None  # date of the lesson, NOT a due date (portal has none)
    text: str

    def as_dict(self) -> dict[str, str | None]:
        """Return a JSON serialisable dict."""
        return {
            "course": self.course,
            "topic": self.topic,
            "lesson_date": self.day.isoformat() if self.day else None,
            "text": self.text,
        }


def _text(node: Tag | None) -> str:
    return node.get_text(" ", strip=True) if node else ""


def _parse_date(value: str) -> date | None:
    match = DATE_RE.search(value)
    if not match:
        return None
    try:
        return date(int(match[3]), int(match[2]), int(match[1]))
    except ValueError:
        return None


def parse_substitutions(html: str) -> list[Substitution]:
    """Parse vertretungsplan.php: one bootstrap table per day."""
    soup = BeautifulSoup(html, "html.parser")
    result: list[Substitution] = []
    for table in soup.find_all("table"):
        header = table.find("tr")
        if header is None:
            continue
        fields = [th.get("data-field") for th in header.find_all("th")]
        if "Fach_alt" not in fields and "Vertreter" not in fields:
            continue
        heading = table.find_previous("div", class_="panel-heading")
        day = _parse_date(_text(heading))
        if day is None:
            continue
        for row in table.find_all("tr")[1:]:
            cells = row.find_all("td")
            if not cells:
                continue
            values = {
                field: _text(cell)
                for field, cell in zip(fields, cells, strict=False)
                if field and field != "_farbe"
            }
            classes = tuple(
                part for part in CLASS_SPLIT_RE.split(values.get("Klasse", "")) if part
            )
            result.append(
                Substitution(
                    day=day,
                    lesson=values.get("Stunde", ""),
                    classes=classes,
                    substitute=values.get("Vertreter", ""),
                    teacher=values.get("Lehrer", ""),
                    kind=values.get("Art", ""),
                    subject=values.get("Fach", ""),
                    subject_old=values.get("Fach_alt", ""),
                    room=values.get("Raum", ""),
                    note=values.get("Hinweis", ""),
                )
            )
    return result


def _place_cells(table: Tag) -> list[tuple[int, int, Tag, int]]:
    """Return (row, column, cell, rowspan) for every cell, honouring rowspans."""
    placed: list[tuple[int, int, Tag, int]] = []
    occupied: dict[int, int] = {}
    for row_idx, tr in enumerate(table.find_all("tr")):
        col = 0
        for cell in tr.find_all(["td", "th"], recursive=False):
            while occupied.get(col, 0) > 0:
                col += 1
            rowspan = int(cell.get("rowspan", 1) or 1)
            colspan = int(cell.get("colspan", 1) or 1)
            placed.append((row_idx, col, cell, rowspan))
            if rowspan > 1:
                for c in range(col, col + colspan):
                    occupied[c] = rowspan
            col += colspan
        for key in list(occupied):
            occupied[key] -= 1
    return placed


def _hhmm(hours: str, minutes: str) -> time:
    return time(int(hours), int(minutes))


def parse_timetable(html: str) -> tuple[str | None, list[Lesson]]:
    """Parse stundenplan.php. Returns (own class, lessons of the personal plan)."""
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table", class_="table-bordered")
    if not tables:
        return None, []
    chosen = tables[0]
    for table in tables:
        heading = table.find_previous("h2")
        if heading and "persönlich" in _text(heading).casefold():
            chosen = table
            break
    heading = chosen.find_previous("h2")
    own_class = None
    if heading:
        groups = re.findall(r"\(([^()]+)\)", _text(heading))
        own_class = groups[-1].strip() if groups else None

    placed = _place_cells(chosen)
    row_times: dict[int, tuple[time, time, str]] = {}
    for row_idx, col, cell, _span in placed:
        if col != 0:
            continue
        match = TIME_RE.search(_text(cell))
        if match:
            period = _text(cell.find("b")) or str(len(row_times) + 1)
            row_times[row_idx] = (
                _hhmm(match[1], match[2]),
                _hhmm(match[3], match[4]),
                period,
            )

    lessons: list[Lesson] = []
    for row_idx, col, cell, rowspan in placed:
        if col < 1 or col > 5 or row_idx not in row_times:
            continue
        start, end, period = row_times[row_idx]
        last = row_times.get(row_idx + rowspan - 1)
        if last:
            end = last[1]
        for item in cell.select(".stunde"):
            title = item.get("title", "") or ""
            room_match = ROOM_RE.search(title)
            lessons.append(
                Lesson(
                    weekday=col - 1,
                    period=period,
                    start=start,
                    end=end,
                    subject=_text(item.find("b")),
                    teacher=_text(item.find("small")),
                    room=room_match[1].rstrip(".,;") if room_match else "",
                    title=title,
                )
            )
    lessons.sort(key=lambda lesson: (lesson.weekday, lesson.start, lesson.subject))
    return own_class, lessons


def parse_homework(html: str) -> list[Homework]:
    """Parse the course list of meinunterricht.php for current homework."""
    soup = BeautifulSoup(html, "html.parser")
    result: list[Homework] = []
    for row in soup.select("table#aktuellTable tr.printable"):
        text = _text(row.select_one(".realHomework"))
        if not text:
            continue
        result.append(
            Homework(
                uid=f"{row.get('data-book', '')}-{row.get('data-entry', '')}",
                course=_text(row.select_one(".name")),
                topic=_text(row.select_one(".thema")),
                day=_parse_date(_text(row.select_one(".datum"))),
                text=text,
            )
        )
    return result


def parse_applet_names(payload: dict) -> list[str]:
    """Extract applet names from startseite.php?a=ajax&f=apps."""
    return [str(entry.get("Name", "")) for entry in payload.get("entrys", [])]
