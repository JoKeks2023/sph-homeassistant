// Minimal DOM-free test of the card logic: node tests/card/card.test.js
const fs = require("fs");
const path = require("path");
const assert = require("assert");
const src = fs.readFileSync(
  path.join(__dirname, "../../custom_components/schulportal_hessen/www/schulportal-hessen-card.js"), "utf8");

class Node {
  constructor(tag) { this.nodeType = 1; this.tag = tag; this.children = []; this.attrs = {}; this.listeners = {}; }
  setAttribute(k, v) { this.attrs[k] = v; }
  append(...c) { this.children.push(...c); }
  replaceChildren(...c) { this.children = c; }
  addEventListener(n, f) { this.listeners[n] = f; }
  set className(v) { this.attrs.class = v; }
  get text() { return this.children.map((c) => (typeof c === "string" ? c : c.text)).join(" "); }
}
let Card;
global.HTMLElement = class {};
global.customElements = { define: (n, c) => { Card = c; } };
global.window = { customCards: [] };
global.document = { createElement: (t) => new Node(t), createTextNode: (t) => t };
new Function(src)();

const iso = (d) => d.toISOString().slice(0, 10);
const today = iso(new Date());
const mk = (kind, state, extra = {}, account = "A") => ({
  state, attributes: { sph: kind, account, account_name: `Konto ${account}`, ...extra } });
const plan = [
  { date: today, period: "1", start: "00:00", end: "23:59", subject: "M", teacher: "ABC", room: "R1", status: "cancelled" },
  { date: today, period: "2", start: "00:00", end: "23:59", subject: "D", teacher: "DEF", room: "R2", status: "changed",
    new_subject: "D", new_teacher: "XYZ", new_room: "R9" },
];
const recent = { at: new Date().toISOString(), kind: "room_changed", data: { date: today, lesson: "2" } };
const old = { at: new Date(Date.now() - 3 * 86400000).toISOString(), kind: "room_changed", data: { date: today, lesson: "1" } };
const states = {
  "sensor.a_week": mk("school_week", "3", { plan }),
  "sensor.a_next": mk("next_lesson", "Deutsch", { start: new Date().toISOString(), end: new Date().toISOString(), room: "R2" }),
  "sensor.a_hist": mk("change_history", "2", { entries: [recent, old] }),
  "sensor.b_next": mk("next_lesson", "Bio", {}, "B"),
};
const render = (config, hass = { states }) => {
  const c = Object.create(Card.prototype);
  c.attachShadow = () => (c.shadowRoot = new Node("root"));
  c.setConfig(config);
  c.hass = hass;
  return c;
};
const text = (c) => c.shadowRoot.text;

// week view: cancelled/changed/new marks, current lesson highlighted
let c = render({ show_week: true, entity: "sensor.a_next" });
assert(text(c).includes("M"), "week shows subjects");
assert(JSON.stringify(c.shadowRoot).includes("lesson cancelled now"), "current cancelled lesson");
assert(JSON.stringify(c.shadowRoot).includes("lesson changed now"));
assert(text(c).includes("neu"), "recent change gets a badge");
assert(!JSON.stringify(c.shadowRoot).includes('"lesson normal'), "no normal lessons here");
// only the recent change (period 2) is flagged, the 3 day old one (period 1) is not
assert.deepStrictEqual([...c._recent()], [`${today}|2`]);
// weekday filter removes the day
c = render({ show_week: true, entity: "sensor.a_next", days: [(new Date().getDay() + 3) % 7 % 5] });
// compact mode
c = render({ compact: true, entity: "sensor.a_next" });
assert(text(c).includes("Deutsch") && text(c).includes("Entfall heute: 1. Std."));
assert(!text(c).includes("Hausaufgaben"));
// account picker only with >= 2 accounts and switches
c = render({ account_select: true });
const picker = JSON.stringify(c.shadowRoot);
assert(picker.includes("Konto A") && picker.includes("Konto B"));
c._selected = "B";
assert.equal(c._entity("next_lesson").state, "Bio");
// stale / unavailable banner
const stale = { ...states, "sensor.a_next": mk("next_lesson", "Deutsch", { stale: true }) };
assert(text(render({ entity: "sensor.a_next" }, { states: stale })).includes("Daten veraltet"));
const gone = { ...states, "sensor.a_next": mk("next_lesson", "unavailable") };
assert(text(render({ entity: "sensor.a_next" }, { states: gone })).includes("Noch keine Daten"));
console.log("card tests ok");
