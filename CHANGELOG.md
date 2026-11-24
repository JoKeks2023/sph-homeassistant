# Changelog

## Unreleased

* Robustheit (SPHA-19): Bei Portalausfall werden die letzten Daten weiter angezeigt
  (Attribut `stale`), statt alle Entitäten auf „nicht verfügbar“ zu setzen. Sensoren sind
  „nicht verfügbar“, solange ihre Kategorie noch nie geladen wurde (statt „0 Einträge“).
  Die letzten Daten werden lokal gespeichert (`.storage`, ohne Zugangsdaten) und nach
  einem Neustart wiederhergestellt; beim Entfernen der Integration gelöscht.

## 0.1.0 – 2026-11-12

* Erste Version: Config Flow mit Schulsuche, Stundenplan (Kalender + Sensor),
  Vertretungsplan, Hausaufgaben, Schulkalender (iCal), Reauth, de/en Übersetzungen.
* Ausgeschriebene Fachnamen, Sensor „Vertretungen andere Klassen“, mitgelieferte
  Lovelace-Karte `custom:schulportal-hessen-card`, Dashboard-Beispiele.
* Nicht enthalten: Nachrichten, Klausuren/Tests.
