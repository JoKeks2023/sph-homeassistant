/* Schulportal Hessen card – shipped with the integration (MIT). */
const SPH_KINDS = ["next_lesson", "substitutions", "other_substitutions", "homework"];
const WEEKDAYS = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];

function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") el.className = v;
    else el.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return el;
}

const fmtDate = (iso) => {
  if (!iso) return "";
  const d = new Date(iso + "T00:00:00");
  return `${WEEKDAYS[d.getDay()]} ${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.`;
};
const fmtTime = (iso) => {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};

class SchulportalHessenCard extends HTMLElement {
  setConfig(config) {
    this._config = { show_other: true, show_homework: true, show_next: true, ...config };
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 6;
  }

  static getStubConfig() {
    return {};
  }

  // Entities are found through the "sph" attribute set by the integration,
  // unless configured explicitly via `entities: {next_lesson: sensor.x, ...}`.
  _entity(kind) {
    const explicit = this._config.entities && this._config.entities[kind];
    if (explicit) return this._hass.states[explicit];
    return Object.values(this._hass.states).find((s) => s.attributes && s.attributes.sph === kind);
  }

  _render() {
    if (!this._hass || !this._config || !this.shadowRoot) return;
    const root = this.shadowRoot;
    root.replaceChildren(h("style", {}, STYLE));
    const card = h("ha-card", {});
    if (this._config.title) card.append(h("div", { class: "title" }, this._config.title));

    const found = SPH_KINDS.map((k) => this._entity(k)).some(Boolean);
    if (!found) {
      card.append(h("div", { class: "empty" }, "Keine Schulportal-Entitäten gefunden."));
      root.append(card);
      return;
    }
    if (this._config.show_next) card.append(this._next());
    card.append(this._substitutions("substitutions", "Vertretungen", true));
    if (this._config.show_other) card.append(this._substitutions("other_substitutions", "Andere Klassen", false));
    if (this._config.show_homework) card.append(this._homework());
    root.append(card);
  }

  _section(title, ...body) {
    return h("div", { class: "section" }, h("div", { class: "heading" }, title), ...body);
  }

  _next() {
    const s = this._entity("next_lesson");
    if (!s) return "";
    const a = s.attributes;
    if (["unknown", "unavailable"].includes(s.state) || !a.start) {
      return this._section("Nächste Stunde", h("div", { class: "muted" }, "Keine Stunde in den nächsten Tagen."));
    }
    const day = new Date(a.start);
    return this._section(
      "Nächste Stunde",
      h("div", { class: "next" },
        h("div", { class: "subject" }, s.state),
        h("div", { class: "meta" },
          `${WEEKDAYS[day.getDay()]} ${fmtTime(a.start)}–${fmtTime(a.end)}`,
          a.room ? ` · Raum ${a.room}` : "",
          a.teacher ? ` · ${a.teacher}` : "")),
    );
  }

  _substitutions(kind, title, own) {
    const s = this._entity(kind);
    if (!s) return "";
    const entries = s.attributes.entries || [];
    if (!entries.length) {
      return this._section(title, h("div", { class: "muted" }, "Keine Einträge."));
    }
    const rows = entries.map((e) => {
      const cancelled = !e.substitute && !e.type ? true : /entf/i.test(e.type || "");
      const label = e.type || (cancelled ? "Entfall" : "Vertretung");
      return h("div", { class: `row ${cancelled ? "cancel" : "subst"}` },
        h("div", { class: "when" }, fmtDate(e.date), h("br"), e.lesson ? `${e.lesson}. Std.` : ""),
        h("div", { class: "what" },
          h("div", {},
            h("span", { class: "badge" }, label), " ",
            !own && e.classes && e.classes.length ? h("b", {}, e.classes.join(", ") + " · ") : "",
            e.subject_old || e.subject,
            e.substitute && !cancelled ? ` → ${e.substitute}` : ""),
          h("div", { class: "meta" },
            [e.teacher && `statt ${e.teacher}`, e.room && `Raum ${e.room}`, e.note].filter(Boolean).join(" · "))),
      );
    });
    return this._section(title, ...rows);
  }

  _homework() {
    const s = this._entity("homework");
    if (!s) return "";
    const entries = s.attributes.entries || [];
    if (!entries.length) return this._section("Hausaufgaben", h("div", { class: "muted" }, "Keine Hausaufgaben."));
    return this._section(
      "Hausaufgaben",
      ...entries.map((e) =>
        h("div", { class: "row" },
          h("div", { class: "when" }, fmtDate(e.lesson_date)),
          h("div", { class: "what" }, h("div", {}, h("b", {}, e.course)), h("div", { class: "meta" }, e.text)))),
    );
  }
}

const STYLE = `
  ha-card { padding: 8px 0; }
  .title { font-size: 1.2em; font-weight: 500; padding: 8px 16px; }
  .section { padding: 8px 16px; }
  .section + .section { border-top: 1px solid var(--divider-color); }
  .heading { font-size: .8em; text-transform: uppercase; letter-spacing: .06em;
             color: var(--secondary-text-color); margin-bottom: 6px; }
  .subject { font-size: 1.5em; font-weight: 500; }
  .meta, .muted { color: var(--secondary-text-color); font-size: .9em; white-space: pre-wrap; }
  .row { display: flex; gap: 12px; padding: 4px 0; }
  .when { min-width: 64px; color: var(--secondary-text-color); font-size: .85em; }
  .what { flex: 1; }
  .badge { font-size: .75em; padding: 1px 6px; border-radius: 8px; color: #fff;
           background: var(--primary-color); }
  .cancel .badge { background: var(--error-color, #db4437); }
  .cancel .what > div:first-child { text-decoration: none; }
  .empty { padding: 16px; color: var(--secondary-text-color); }
`;

customElements.define("schulportal-hessen-card", SchulportalHessenCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "schulportal-hessen-card",
  name: "Schulportal Hessen",
  description: "Nächste Stunde, Vertretungen (eigene und andere Klassen) und Hausaufgaben",
});
