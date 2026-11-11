# Schulportal Hessen für Home Assistant

Inoffizielle, **rein lesende** Home-Assistant-Integration für das
[Schulportal Hessen](https://schulportal.hessen.de) (Lanis). Sie holt
Stundenplan, Vertretungsplan, Hausaufgaben und den Schulkalender direkt aus dem
Portal – ohne zusätzlichen Server, Container oder Cloud-Dienst.

> Keine offizielle Integration, nicht mit dem Schulportal Hessen verbunden.
> Das Portal hat keine offizielle API; Änderungen am Portal können die
> Integration jederzeit beeinträchtigen.

*English: unofficial read-only Home Assistant integration for Schulportal
Hessen (timetable, substitutions, homework, school calendar). See below.*

## Funktionen (v0.1)

| Bereich | Entität | Hinweise |
|---|---|---|
| Stundenplan | Kalender „Stundenplan“, Sensor „Nächste Stunde“ | regulärer Wochenplan, Vertretungen sind **nicht** eingerechnet |
| Vertretungsplan | Sensor „Vertretungen“ | Anzahl + Liste (Attribute) für die eigene Klasse, automatisch erkannt |
| Hausaufgaben | Sensor „Hausaufgaben“ | aktuelle Hausaufgabe pro Kurs; `lesson_date` ist das Datum der Stunde, **kein** Abgabetermin (das Portal liefert keinen) |
| Kalender | Kalender „Schulkalender“ | aus dem iCal-Export des Portals |

Nur Module, die für deinen Account im Portal freigeschaltet sind, werden als
Entitäten angelegt.

### Ereignisse für Automationen

* `schulportal_hessen_new_homework` – neue Hausaufgabe (Daten: `course`, `topic`, `text`, `lesson_date`)
* `schulportal_hessen_new_substitution` – neue Vertretung für die eigene Klasse

### Noch nicht enthalten

* **Nachrichten** und **Klausuren/Tests**: nicht umgesetzt. Beides war mit dem
  Testaccount des Autors im Portal nicht freigeschaltet und konnte deshalb nicht
  geprüft werden. Es wird nichts simuliert. Hilfe mit einem Account, bei dem diese
  Module aktiv sind, ist willkommen (Issue eröffnen).
* Anwesenheitsdaten werden bewusst nicht ausgelesen.

## Installation

### HACS (Custom Repository)

1. HACS → Integrationen → ⋮ → *Benutzerdefinierte Repositories*.
2. `https://github.com/JoKeks2023/sph-homeassistant` als Typ *Integration* hinzufügen.
3. „Schulportal Hessen“ installieren und Home Assistant neu starten.

### Manuell

`custom_components/schulportal_hessen` in den `custom_components`-Ordner deiner
Home-Assistant-Konfiguration kopieren und neu starten.

## Einrichtung

*Einstellungen → Geräte & Dienste → Integration hinzufügen → Schulportal Hessen.*
Schule suchen (Name, Ort oder Nummer), aus der Liste wählen, dann
Benutzername (`vorname.nachname`) und Passwort eingeben. Keine YAML-Konfiguration nötig.

## Datenschutz und Sicherheit

* Nur lesender Zugriff; die Integration sendet keine Nachrichten und ändert nichts.
* Zugangsdaten liegen im Config Entry von Home Assistant (wie bei anderen Integrationen)
  und werden nie geloggt oder als Attribut ausgegeben.
* Anfragen gehen ausschließlich an `*.schulportal.hessen.de`. Keine Telemetrie.
* Abfrage-Rhythmus: Koordinator alle 30 Minuten; Vertretungen ~25 min, Hausaufgaben 1 h,
  Kalender 6 h, Stundenplan 12 h – Anfragen werden also gespart.

## Status

Frühe Version (0.1). Parser und Client wurden gegen das echte Portal geprüft,
die Integration selbst ist noch nicht in vielen Home-Assistant-Setups getestet.
Bitte Fehler als [Issue](https://github.com/JoKeks2023/sph-homeassistant/issues) melden –
ohne Zugangsdaten und ohne persönliche Daten.

## Lizenz

[MIT](LICENSE). Protokollwissen stammt aus Beobachtung des Portals sowie aus dem
MIT-lizenzierten [liblanis-for-python](https://github.com/lanis-mobile/liblanis-for-python)
und der Arbeit des Lanis-Mobile-Projekts; es wurde kein GPL-Code übernommen.

---

## English summary

Read-only integration providing the weekly timetable (calendar + next-lesson
sensor), substitution plan, homework (latest entry per course; the date is the
lesson date, not a due date) and the school calendar. Messages and exams/tests are
**not** implemented because they are not enabled for the author's account and could
not be verified. Install via HACS (custom repository) or copy
`custom_components/schulportal_hessen`, then add it via *Settings → Devices &
services*. Unofficial; the portal has no public API and may change without notice.
