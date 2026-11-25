# Changelog

## 0.3.0 – 2026-11-25

Neu: Tagesübersicht und Unterrichtsende, Änderungs-Events und -Historie, Diagnose-Sensoren, Karte 2.0. Alles wird aus den bereits geladenen Daten berechnet, es gibt keine zusätzlichen Portal-Abrufe. Keine Änderungen an bestehenden Entitäten und Events. Nicht enthalten: Ferien-Erkennung (der Schulkalender wurde nicht auf echte Ferien-Einträge geprüft).

* Karte 2.0 (SPHA-68): Wochenplan (`show_week`, `days`), Kompaktmodus (`compact`), Filter (`show_substitutions`, `only_cancellations`), Konto-Auswahl (`account_select`), Abzeichen „neu“ für Änderungen der letzten 24 h, Hinweis bei veralteten Daten. Bisherige Konfiguration funktioniert unverändert. Sensoren tragen zusätzlich das Attribut `account_name`.
* Neu: Diagnose-Sensor „Änderungshistorie“ (letzte 50 Änderungen/Events mit Zeitstempel, bleibt nach Neustart erhalten, Texte gekürzt) (SPHA-66).
* Neu: Sensor „Schultage diese Woche“ (verbleibende Schultage; Attribute: Kalenderwoche, nächster Schultag). Ferien werden **nicht** berücksichtigt (SPHA-62).
* Neu: Diagnose-Sensor „Datenqualität“ (ok / Auffälligkeiten) mit Liste, z. B. `timetable_empty`, `own_class_unknown`, `*_never_loaded`, `data_outdated` (SPHA-69).
* Neue Events für Änderungen an bekannten Einträgen: `schulportal_hessen_room_changed` (`date`, `lesson`, `subject`, `old_room`, `new_room`), `schulportal_hessen_teacher_changed` (`old_teacher`, `new_teacher` = Vertretungslehrkraft) und `schulportal_hessen_homework_changed` (Text/Thema einer bekannten Hausaufgabe geändert; `old_text`, `new_text`). Nur für die eigene Klasse; Zuordnung nach Tag, Stunde, Fach und Art, bei mehrdeutigen Einträgen wird nichts gemeldet. Nicht beim ersten Laden und nicht für Änderungen, die während eines Neustarts passieren (SPHA-64, SPHA-65).
* Neu: Diagnose-Sensor „Portal-Status“ (ok / Daten veraltet / keine Daten) mit letztem Erfolg/Fehler, Fehlerzähler und Alter der Daten. Keine Zugangsdaten oder Inhalte (SPHA-67).
* Neu: Sensoren „Unterrichtsende“ (Zeitstempel) und „Tagesübersicht“ (Anzahl stattfindender Stunden; Attribute: erste/letzte Stunde, Beginn/Ende, entfallene Stunden, Vertretungen, Freistunden). Reine Berechnung aus Stundenplan und Vertretungen, Entfall eingerechnet. Freistunde = Lücke > 30 min zwischen zwei stattfindenden Stunden (Heuristik) (SPHA-59, SPHA-60, SPHA-61).

## 0.2.0 – 2026-11-24

Neu: Entfall-Sensoren, Vertretungen im Stundenplan, Robustheit bei Portalausfall.
Voraussetzung jetzt **Home Assistant 2024.11**. Keine Änderungen an bestehenden Entitäten
und Event-Namen; bestehende Einträge bleiben unverändert.

* Doku: Hinweis, dass das Hausaufgaben-Datum das Stundendatum und kein Abgabetermin ist.
  Eine Fälligkeits-Erkennung im Text wurde bewusst nicht eingebaut (keine echten Daten als
  Beleg) (SPHA-46).
* Mehrere Konten: neue Einträge heißen „Schule (Benutzername)“ und tragen das im Gerät;
  Sensoren haben das Attribut `account`; die Karte hat die Option `entity` zur Auswahl
  des Kontos (SPHA-45). Bestehende Einträge bleiben unverändert.
* Repair-Hinweis, wenn der Stundenplan bei zwei Abrufen in Folge keine Stunden liefert
  (mögliche Portal-Änderung). Für Vertretungen/Hausaufgaben nicht aktiv, da dort „leer“
  normal ist (SPHA-44).
* Stundenplan-Kalender rechnet Vertretungen, Entfall und Raumänderungen der eigenen Klasse
  ein (Titel-Präfix, Beschreibung). Zuordnung nur bei passender Stundennummer und Fach
  (SPHA-41).
* „Nächste Stunde“ überspringt entfallene Stunden (Attribut `skipped_cancelled`); neuer
  Zeitstempel-Sensor „Unterrichtsbeginn“ (erste stattfindende Stunde des nächsten Schultags).
  Eine Stunde gilt nur als entfallen, wenn Stundennummer **und** Fach zum Entfall passen
  (SPHA-42).
* Neues Event `schulportal_hessen_new_cancellation` für neuen Entfall der eigenen Klasse
  (zusätzlich zu `new_substitution`) (SPHA-43).
* Entfall-Sensoren sind „nicht verfügbar“, solange der Vertretungsplan nie geladen
  wurde, und tragen das Attribut `stale` (Folgearbeit zu SPHA-19/SPHA-35).
* Mindestversion Home Assistant 2024.11 (`hacs.json`, README) (SPHA-39).
* Robustheit (SPHA-19): Bei Portalausfall werden die letzten Daten weiter angezeigt
  (Attribut `stale`), statt alle Entitäten auf „nicht verfügbar“ zu setzen. Sensoren sind
  „nicht verfügbar“, solange ihre Kategorie noch nie geladen wurde (statt „0 Einträge“).
  Die letzten Daten werden lokal gespeichert (`.storage`, ohne Zugangsdaten) und nach
  einem Neustart wiederhergestellt; beim Entfernen der Integration gelöscht.
* Diagnostics mit Schwärzung (nur Struktur und Anzahlen, keine Zugangsdaten, Namen oder
  Inhalte); Fehlerlog bei Login-Check ohne Traceback (SPHA-26).
* Neue Binary-Sensoren „Entfall heute“, „Entfall in den ersten Stunden“ (N einstellbar,
  Standard 2) und „Entfall morgen“ (SPHA-35).
* Neuer Options-Dialog (Anzahl der ersten Stunden).

## 0.1.0 – 2026-11-12

* Erste Version: Config Flow mit Schulsuche, Stundenplan (Kalender + Sensor),
  Vertretungsplan, Hausaufgaben, Schulkalender (iCal), Reauth, de/en Übersetzungen.
* Ausgeschriebene Fachnamen, Sensor „Vertretungen andere Klassen“, mitgelieferte
  Lovelace-Karte `custom:schulportal-hessen-card`, Dashboard-Beispiele.
* Nicht enthalten: Nachrichten, Klausuren/Tests.
