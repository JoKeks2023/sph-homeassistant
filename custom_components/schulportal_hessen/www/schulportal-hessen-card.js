/* Schulportal Hessen card – shipped with the integration (MIT). */
const SPH_KINDS = ["next_lesson", "substitutions", "other_substitutions", "homework", "school_week"];
const DAY_MS = 24 * 3600 * 1000;
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
    this._config = {
      show_other: true,
      show_homework: true,
      show_next: true,
      show_substitutions: true,
      show_week: false, // weekly timetable (needs the "school week" sensor)
      compact: false, // only next lesson, school start and cancellations
      only_cancellations: false,
      account_select: false, // dropdown to switch between several accounts
      days: null, // e.g. [0, 1, 2] = Mon-Wed (0 = Monday) for the week view
      ...config,
    };
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
  // With several accounts (e.g. two children) set `entity:` to any sensor of
  // the wanted account; all other sensors are then taken from that account.
  _account() {
    if (this._selected) return this._selected;
    if (!this._config.entity) return null;
    const ref = this._hass.states[this._config.entity];
    return (ref && ref.attributes && ref.attributes.account) || null;
  }

  _entity(kind) {
    const explicit = this._config.entities && this._config.entities[kind];
    if (explicit) return this._hass.states[explicit];
    const account = this._account();
    return Object.values(this._hass.states).find(
      (s) => s.attributes && s.attributes.sph === kind && (!account || s.attributes.account === account)
    );
  }

  _render() {
    if (!this._hass || !this._config || !this.shadowRoot) return;
    const root = this.shadowRoot;
    root.replaceChildren(h("style", {}, STYLE));
    const card = h("ha-card", {});
    if (this._config.title) card.append(h("div", { class: "title" }, this._config.title));

    if (this._config.entity && !this._account()) {
      card.append(h("div", { class: "empty" }, `Entität ${this._config.entity} nicht gefunden.`));
      root.append(card);
      return;
    }
    const found = SPH_KINDS.map((k) => this._entity(k)).some(Boolean);
    if (!found) {
      card.append(h("div", { class: "empty" }, "Keine Schulportal-Entitäten gefunden."));
      root.append(card);
      return;
    }
    if (this._config.account_select) card.append(this._picker());
    const status = this._status();
    if (status) card.append(status);
    if (this._config.compact) {
      card.append(this._compact());
      root.append(card);
      return;
    }
    if (this._config.show_next) card.append(this._next());
    if (this._config.show_week) card.append(this._week());
    if (this._config.show_substitutions) card.append(this._substitutions("substitutions", "Vertretungen", true));
    if (this._config.show_other && !this._config.only_cancellations) {
      card.append(this._substitutions("other_substitutions", "Andere Klassen", false));
    }
    if (this._config.show_homework && !this._config.only_cancellations) card.append(this._homework());
    root.append(card);
  }

  // All accounts found (one entry per config entry) for the dropdown.
  _accounts() {
    const found = new Map();
    for (const s of Object.values(this._hass.states)) {
      const a = s.attributes;
      if (a && a.sph && a.account && !found.has(a.account)) found.set(a.account, a.account_name || a.account);
    }
    return found;
  }

  _picker() {
    const accounts = this._accounts();
    if (accounts.size < 2) return "";
    const current = this._account() || [...accounts.keys()][0];
    const select = h("select", { class: "picker" },
      ...[...accounts].map(([id, name]) => {
        const o = h("option", { value: id }, name);
        if (id === current) o.selected = true;
        return o;
      }));
    select.addEventListener("change", () => {
      this._selected = select.value;
      this._render();
    });
    return h("div", { class: "section" }, select);
  }

  // Data state: uses the integration's `stale` attribute and availability.
  _status() {
    const probe = this._entity("next_lesson") || this._entity("substitutions") || this._entity("school_week");
    if (!probe) return "";
    if (probe.state === "unavailable") {
      return h("div", { class: "status warn" }, "Noch keine Daten geladen oder Schulportal nicht erreichbar.");
    }
    if (probe.attributes.stale) {
      return h("div", { class: "status warn" }, "Daten veraltet: Verbindung zum Schulportal fehlgeschlagen.");
    }
    return "";
  }

  // Keys "date|period" of entries that changed in the last 24 hours (change history).
  _recent() {
    const keys = new Set();
    const history = this._entity("change_history");
    const now = Date.now();
    for (const e of (history && history.attributes.entries) || []) {
      const at = Date.parse(e.at);
      const d = e.data || {};
      if (!at || now - at > DAY_MS) continue;
      const date = d.date;
      const lesson = String(d.lesson || "").match(/\d+/);
      if (date && lesson) keys.add(`${date}|${lesson[0]}`);
    }
    return keys;
  }

  _isNew(date, lesson) {
    const m = String(lesson || "").match(/\d+/);
    return !!(m && this._recent().has(`${date}|${m[0]}`));
  }

  _compact() {
    const s = this._entity("next_lesson");
    const week = this._entity("school_week");
    const start = this._entity("school_start");
    const parts = [];
    if (s && !["unknown", "unavailable"].includes(s.state) && s.attributes.start) {
      const a = s.attributes;
      parts.push(h("div", { class: "subject" }, s.state),
        h("div", { class: "meta" }, `${fmtTime(a.start)}–${fmtTime(a.end)}`, a.room ? ` · Raum ${a.room}` : ""));
    } else {
      parts.push(h("div", { class: "muted" }, "Keine Stunde in den nächsten Tagen."));
    }
    if (start && start.state && !["unknown", "unavailable"].includes(start.state)) {
      parts.push(h("div", { class: "meta" }, `Unterrichtsbeginn ${fmtTime(start.state)}`));
    }
    const today = new Date().toISOString().slice(0, 10);
    const plan = (week && week.attributes.plan) || [];
    const cancelled = plan.filter((l) => l.date === today && l.status === "cancelled");
    if (cancelled.length) {
      parts.push(h("div", { class: "cancel-line" }, `Entfall heute: ${cancelled.map((l) => l.period + ". Std.").join(", ")}`));
    }
    return h("div", { class: "section" }, ...parts);
  }

  _week() {
    const week = this._entity("school_week");
    const plan = (week && week.attributes.plan) || [];
    if (!plan.length) return this._section("Woche", h("div", { class: "muted" }, "Kein Stundenplan vorhanden."));
    const days = new Map();
    for (const l of plan) {
      const d = new Date(l.date + "T00:00:00");
      const wd = (d.getDay() + 6) % 7; // Monday = 0
      if (this._config.days && !this._config.days.includes(wd)) continue;
      if (!days.has(l.date)) days.set(l.date, []);
      days.get(l.date).push(l);
    }
    const now = new Date();
    const grid = h("div", { class: "week" });
    for (const [date, lessons] of days) {
      const col = h("div", { class: "day" }, h("div", { class: "dayhead" }, fmtDate(date)));
      for (const l of lessons) {
        const [sh, sm] = l.start.split(":").map(Number);
        const [eh, em] = l.end.split(":").map(Number);
        const from = new Date(date + "T00:00:00"); from.setHours(sh, sm);
        const to = new Date(date + "T00:00:00"); to.setHours(eh, em);
        const current = now >= from && now < to;
        const changed = l.status === "changed";
        col.append(h("div", { class: `lesson ${l.status}${current ? " now" : ""}` },
          h("div", { class: "lname" }, `${l.period}. `, changed && l.new_subject ? l.new_subject : l.subject,
            this._isNew(date, l.period) ? h("span", { class: "badge new" }, "neu") : ""),
          h("div", { class: "meta" }, `${l.start}–${l.end}`),
          h("div", { class: "meta" },
            [changed && l.new_room ? l.new_room : l.room, changed && l.new_teacher ? l.new_teacher : l.teacher]
              .filter(Boolean).join(" · "))));
      }
      grid.append(col);
    }
    return this._section("Woche", grid);
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
    let entries = s.attributes.entries || [];
    if (this._config.only_cancellations) entries = entries.filter((e) => /entf|freisetz|unterrichtsfrei|fällt aus/i.test(e.type || ""));
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
            own && this._isNew(e.date, e.lesson) ? h("span", { class: "badge new" }, "neu") : "", " ",
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
  .status.warn { margin: 4px 16px; padding: 6px 10px; border-radius: 6px; font-size: .9em;
                 background: var(--warning-color, #ffa600); color: #000; }
  .picker { width: 100%; padding: 6px; }
  .week { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; }
  .dayhead { font-weight: 500; margin-bottom: 4px; }
  .lesson { padding: 4px 6px; margin-bottom: 4px; border-radius: 6px; border-left: 3px solid var(--divider-color); }
  .lesson.cancelled { border-left-color: var(--error-color, #db4437); }
  .lesson.cancelled .lname { text-decoration: line-through; color: var(--secondary-text-color); }
  .lesson.changed { border-left-color: var(--primary-color); background: color-mix(in srgb, var(--primary-color) 10%, transparent); }
  .lesson.now { outline: 2px solid var(--primary-color); }
  .badge.new { background: var(--accent-color, #ff9800); margin-left: 4px; }
  .cancel-line { color: var(--error-color, #db4437); font-weight: 500; margin-top: 4px; }
  .empty { padding: 16px; color: var(--secondary-text-color); }
`;

customElements.define("schulportal-hessen-card", SchulportalHessenCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "schulportal-hessen-card",
  name: "Schulportal Hessen",
  description: "Nächste Stunde, Wochenplan, Vertretungen, Entfall und Hausaufgaben (mehrere Konten, Kompaktmodus)",
});
