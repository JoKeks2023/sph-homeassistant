<div align="center">

# 🎒 Schulportal Hessen für Home Assistant

**Stundenplan, Vertretungen, Hausaufgaben und Schulkalender – direkt in deinem Smart Home.**

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Validate](https://github.com/JoKeks2023/sph-homeassistant/actions/workflows/validate.yml/badge.svg)](https://github.com/JoKeks2023/sph-homeassistant/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Status](https://img.shields.io/badge/status-early%20(v0.1)-yellow)
![Read-only](https://img.shields.io/badge/access-read--only-green)

🇩🇪 Deutsch · [🇬🇧 English](#-english)

</div>

> [!WARNING]
> **Inoffiziell.** Dieses Projekt ist nicht mit dem Schulportal Hessen oder dem
> Hessischen Kultusministerium verbunden. Das Portal hat keine offizielle API;
> Änderungen am Portal können die Integration jederzeit beeinträchtigen.

---

## ✨ Was kann das?

Die Integration liest dein Schulportal-Konto **nur lesend** aus – ohne zusätzlichen
Server, Container oder Cloud-Dienst. Alles läuft direkt in Home Assistant.

| | Bereich | Entität | Details |
|---|---|---|---|
| 🗓️ | **Stundenplan** | Kalender „Stundenplan“ · Sensor „Nächste Stunde“ | Regulärer Wochenplan. Vertretungen sind darin **nicht** eingerechnet. |
| 🔄 | **Vertretungsplan** | Sensor „Vertretungen“ | Anzahl + Liste (Attribute) für deine Klasse, automatisch erkannt. |
| 📚 | **Hausaufgaben** | Sensor „Hausaufgaben“ | Aktuelle Hausaufgabe je Kurs. |
| 🏫 | **Schulkalender** | Kalender „Schulkalender“ | Aus dem iCal-Export des Portals. |

Es werden nur Entitäten für Module angelegt, die in deinem Portal-Account
**freigeschaltet** sind.

### 🔔 Ereignisse für Automationen

| Event | Wann |
|---|---|
| `schulportal_hessen_new_homework` | neue Hausaufgabe (`course`, `topic`, `text`, `lesson_date`) |
| `schulportal_hessen_new_substitution` | neue Vertretung für deine Klasse |

Beim ersten Laden werden keine Events ausgelöst, nur bei späteren Neuigkeiten.

<details>
<summary><b>Beispiel-Automation</b> – Benachrichtigung bei neuer Hausaufgabe</summary>

```yaml
automation:
  - alias: "Neue Hausaufgabe"
    trigger:
      - platform: event
        event_type: schulportal_hessen_new_homework
    action:
      - service: notify.mobile_app_dein_handy
        data:
          title: "Neue Hausaufgabe: {{ trigger.event.data.course }}"
          message: "{{ trigger.event.data.text }}"
```

</details>

### 🚧 Noch nicht enthalten

- **Nachrichten** und **Klausuren/Tests** – nicht umgesetzt. Beide Module waren beim
  Testaccount des Autors nicht freigeschaltet und ließen sich daher nicht prüfen.
  Es wird nichts simuliert. Hilfe mit einem Account, bei dem diese Module aktiv sind,
  ist willkommen ([Issue eröffnen](https://github.com/JoKeks2023/sph-homeassistant/issues)).
- **Fälligkeitsdatum bei Hausaufgaben** – das Portal liefert nur das Datum der Stunde
  (`lesson_date`), keinen Abgabetermin.
- **Anwesenheitsdaten** werden bewusst nicht ausgelesen.

---

## 📦 Installation

### HACS (benutzerdefiniertes Repository)

1. HACS → **Integrationen** → ⋮ → **Benutzerdefinierte Repositories**
2. `https://github.com/JoKeks2023/sph-homeassistant` als Typ **Integration** hinzufügen
3. „Schulportal Hessen“ installieren und Home Assistant neu starten

### Manuell

Den Ordner `custom_components/schulportal_hessen` in das Verzeichnis
`config/custom_components/` deiner Home-Assistant-Installation kopieren und neu starten.

## ⚙️ Einrichtung

*Einstellungen → Geräte & Dienste → Integration hinzufügen → **Schulportal Hessen***

1. **Schule suchen** – Name, Ort oder Schulnummer eingeben
2. **Schule auswählen** – aus der Trefferliste
3. **Anmelden** – Benutzername (`vorname.nachname`) und Passwort

Keine YAML-Konfiguration nötig. Ändert sich dein Passwort, fragt Home Assistant
automatisch danach (Reauthentifizierung).

## 🔒 Datenschutz & Sicherheit

- **Nur lesend:** Es werden keine Nachrichten gesendet und nichts im Portal geändert.
- **Zugangsdaten** liegen im Config Entry von Home Assistant und werden nie geloggt
  oder als Attribut ausgegeben.
- **Nur Portal-Verkehr:** Anfragen gehen ausschließlich an `*.schulportal.hessen.de`.
  Keine Telemetrie, kein Drittanbieter.
- **Schonend:** Der Koordinator fragt alle 30 Minuten an, je Bereich mit eigener
  Wartezeit (Vertretungen ~25 min, Hausaufgaben 1 h, Kalender 6 h, Stundenplan 12 h).

## 🧪 Status

Frühe Version (0.1). Client und Parser wurden gegen das echte Portal geprüft; die
Integration selbst ist noch nicht in vielen Home-Assistant-Setups getestet.
Fehler bitte als [Issue](https://github.com/JoKeks2023/sph-homeassistant/issues)
melden – **ohne Zugangsdaten und ohne persönliche Daten**.

## 📄 Lizenz

[MIT](LICENSE). Das Protokollwissen stammt aus Beobachtung des Portals sowie aus dem
MIT-lizenzierten [liblanis-for-python](https://github.com/lanis-mobile/liblanis-for-python)
und der Arbeit des Lanis-Mobile-Projekts. Es wurde kein GPL-Code übernommen.

---

## 🇬🇧 English

Unofficial, **read-only** Home Assistant integration for
[Schulportal Hessen](https://schulportal.hessen.de) (Lanis, German school portal).
No extra server, container or cloud service.

| Area | Entities | Notes |
|---|---|---|
| Timetable | calendar + *next lesson* sensor | regular weekly plan, substitutions **not** merged in |
| Substitutions | sensor | count + list for your class (auto-detected) |
| Homework | sensor | latest entry per course; the date is the lesson date, **not** a due date |
| School calendar | calendar | from the portal's iCal export |

Events for automations: `schulportal_hessen_new_homework`,
`schulportal_hessen_new_substitution`.

**Not implemented:** messages and exams/tests – they are not enabled for the author's
account and could not be verified; nothing is simulated.

**Install:** HACS custom repository `JoKeks2023/sph-homeassistant` (type *Integration*)
or copy `custom_components/schulportal_hessen`, restart, then *Settings → Devices &
services → Add integration → Schulportal Hessen*. Read-only; credentials stay in the
config entry and are never logged. Unofficial: the portal has no public API and may
change without notice.
