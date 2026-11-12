# Dashboard

## Custom Card (empfohlen)

Die Karte wird von der Integration selbst mitgeliefert und automatisch geladen
(nach dem Update Home Assistant neu starten und den Browser-Cache leeren/Seite neu laden).
Sie findet die Sensoren automatisch.

```yaml
type: custom:schulportal-hessen-card
title: Schule            # optional
show_next: true          # nächste Stunde
show_other: true         # Vertretungen anderer Klassen
show_homework: true
```

Optional lassen sich Entitäten fest zuordnen:

```yaml
type: custom:schulportal-hessen-card
entities:
  next_lesson: sensor.deine_schule_naechste_stunde
  substitutions: sensor.deine_schule_vertretungen
  other_substitutions: sensor.deine_schule_vertretungen_andere_klassen
  homework: sensor.deine_schule_hausaufgaben
```

Einträge ohne Art und ohne Vertreter werden als **Entfall** markiert.

## Alternative: Markdown-Karten (ohne Custom Card)

Die Beispiele nutzen die eingebaute **Markdown-Karte**. Ersetze die Entity-IDs
durch deine eigenen (*Einstellungen → Geräte & Dienste → Schulportal Hessen → Entitäten*);
der Präfix hängt vom Namen deiner Schule ab.

## Nächste Stunde

```yaml
type: markdown
title: Nächste Stunde
content: >
  {% set e = 'sensor.DEINE_SCHULE_naechste_stunde' %}
  {% if states(e) not in ['unknown', 'unavailable', 'None'] %}
  **{{ states(e) }}** · {{ as_timestamp(state_attr(e, 'start')) | timestamp_custom('%a %H:%M') }}–{{ as_timestamp(state_attr(e, 'end')) | timestamp_custom('%H:%M') }}
  Raum {{ state_attr(e, 'room') or '–' }} · {{ state_attr(e, 'teacher') or '–' }}
  {% else %}Keine Stunde in den nächsten Tagen.{% endif %}
```

## Vertretungen (eigene Klasse)

```yaml
type: markdown
title: Vertretungen
content: >
  {% set e = 'sensor.DEINE_SCHULE_vertretungen' %}
  {% for s in state_attr(e, 'entries') or [] %}
  - **{{ s.date[8:10] }}.{{ s.date[5:7] }}. · {{ s.lesson }}. Std.** {{ s.subject_old or s.subject }}{% if s.substitute %} → {{ s.substitute }}{% endif %}{% if s.room %}, Raum {{ s.room }}{% endif %}{% if s.note %} – {{ s.note }}{% endif %}
  {% else %}Keine Vertretungen.{% endfor %}
```

## Vertretungen anderer Klassen

Gleich wie oben, nur mit `sensor.DEINE_SCHULE_vertretungen_andere_klassen`
und zusätzlich `{{ s.classes | join(', ') }}` vor dem Fach.

## Hausaufgaben

```yaml
type: markdown
title: Hausaufgaben
content: >
  {% set e = 'sensor.DEINE_SCHULE_hausaufgaben' %}
  {% for h in state_attr(e, 'entries') or [] %}
  **{{ h.course }}**{% if h.lesson_date %} ({{ h.lesson_date[8:10] }}.{{ h.lesson_date[5:7] }}.){% endif %}
  {{ h.text }}

  {% else %}Keine Hausaufgaben.{% endfor %}
```

Hinweis: `lesson_date` ist das Datum der Stunde, kein Abgabetermin.
