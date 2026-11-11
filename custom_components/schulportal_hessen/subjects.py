"""Readable names for the subject abbreviations used in the portal."""

from __future__ import annotations

SUBJECTS: dict[str, str] = {
    "d": "Deutsch",
    "e": "Englisch",
    "f": "Französisch",
    "l": "Latein",
    "spa": "Spanisch",
    "m": "Mathematik",
    "bio": "Biologie",
    "ch": "Chemie",
    "ph": "Physik",
    "inf": "Informatik",
    "g": "Geschichte",
    "geo": "Geografie",
    "powi": "Politik und Wirtschaft",
    "rev": "Evangelische Religion",
    "rka": "Katholische Religion",
    "ethi": "Ethik",
    "mu": "Musik",
    "ku": "Kunst",
    "spo": "Sport",
    "ds": "Darstellendes Spiel",
}


def full_subject(code: str) -> str:
    """Return a readable subject name; unknown codes are returned unchanged."""
    key = code.strip()
    if key.casefold() in SUBJECTS:
        return SUBJECTS[key.casefold()]
    if key.upper().startswith("AG_"):
        return "AG " + key[3:].replace("_", " ")
    return key
