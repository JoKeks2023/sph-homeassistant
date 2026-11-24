# Changelog

## Unreleased

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
