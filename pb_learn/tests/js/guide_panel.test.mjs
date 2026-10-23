/**
 * LEARNREV P2 — the Guide panel and the (i) field cards, run in node.
 *
 *   T1  the six sections from the real Component treatment Guide (P1's own
 *       output, tests/data/guide_treatment_en.json): order, Right now rows
 *       and their buttons, the Fields count, Tasks chips, the empty states
 *       (a screen with no manifest; "no scheme selected"), the actions the
 *       buttons make (bus / openHub / doAction, stubbed), the Pay role card
 *       (six choices, "and N more"), the Ask chips, Vietnamese titles, the
 *       Access filter, and the drawer wiring (fetch, cache, render).
 *   T2  the header finder (pure) and the idempotent (i) injection.
 *
 * Run: node pb_learn/tests/js/guide_panel.test.mjs   (exit 1 on failure)
 */
import fs from "node:fs";
import path from "node:path";
import { check, load, summary, ROOT } from "./harness.mjs";

const pb = globalThis.__pb;
const noop = () => {};

// ---- just enough of a browser
globalThis.document = {
    addEventListener: noop, removeEventListener: noop,
    body: { classList: { add: noop, remove: noop, contains: () => false, toggle: noop } },
    documentElement: { style: { setProperty: noop } },
    querySelector: () => null, querySelectorAll: () => [], activeElement: null,
};
globalThis.window = {
    localStorage: { getItem: () => null, setItem: noop },
    matchMedia: () => ({ matches: false }),
    innerHeight: 800, innerWidth: 1440,
    addEventListener: noop,
};

const CONTENT = JSON.parse(fs.readFileSync(
    path.join(ROOT, "pb_learn", "static", "content", "learn_content.json"), "utf-8"));
const GUIDE = JSON.parse(fs.readFileSync(
    path.join(ROOT, "pb_learn", "tests", "data", "guide_treatment_en.json"), "utf-8"));
const COACH_XML = fs.readFileSync(
    path.join(ROOT, "pb_learn", "static", "src", "coach", "coach.xml"), "utf-8");

const runtime = await load("@pb_learn/engine/runtime");
const panel = await load("@pb_learn/coach/guide_panel", ["@pb_learn/engine/runtime"]);
const info = await load("@pb_learn/coach/field_info",
                        ["@pb_learn/engine/runtime", "@pb_learn/engine/glossary",
                         "@pb_learn/coach/guide_panel"]);
const { RT } = runtime;
RT.chrome = CONTENT.chrome;
RT.lang = "en";
const T = (k) => runtime.T(k);
const clone = (x) => JSON.parse(JSON.stringify(x));
const ALL_OPEN = { screen: true, now: true, fields: true, tasks: true, understand: true };
const stations = CONTENT.stations || [];
const acts = (html) => Array.from(String(html).matchAll(/data-act="([a-z-]+)"/g), (m) => m[1]);

// =================================================================== T1
function sectionsSuite() {
    console.log("T1 the six sections");
    const html = panel.sectionsHTML(GUIDE, { open: ALL_OPEN, stations, offers: () => true,
                                             text: (p) => runtime.tx(p) });
    check(JSON.stringify(panel.sectionOrder(html)) === JSON.stringify(panel.SECTIONS),
          "five sections in the fixed order (This screen · Right now · Fields · Tasks · Understand)",
          panel.sectionOrder(html).join(","));
    const guideAt = COACH_XML.indexOf('class="lrn-guide"');
    const askAt = COACH_XML.indexOf('class="lrn-gask"');
    const chatAt = COACH_XML.indexOf('t-component="chat.Component"');
    check(guideAt > 0 && askAt > guideAt && chatAt > askAt,
          "… and Ask (the one chat) is the sixth, drawn under them in the drawer");
    for (const k of ["gSecScreen", "gSecNow", "gSecFields", "gSecTasks", "gSecUnderstand"]) {
        check(html.includes(runtime.esc(T(k))), `section title "${T(k)}"`);
    }
    check(!/class="[^"]*tab/.test(html) && !html.includes('role="tab'), "no tabs");
    // This screen
    check(html.includes("Tell the pay scheme what each component is"), "This screen: the purpose");
    check(html.includes('aria-current="page">Component treatment<') && html.includes('data-act="c-gpath" data-i="0">Mapping<'),
          "You are here: Mapping › Component treatment (Mapping is a door, the tab is here)");
    check(html.includes('lrn-gchip before') && html.includes("Formula Engine"), "came from: Formula Engine (grey)");
    check(html.includes('lrn-gchip after') && html.includes(">Run<"), "next: Run (indigo outline)");
    check(html.includes('title="Recompute the pay run so its figures use what you saved."'), "… with its why as the title");
    // Right now (the fixture: one run computed before the last change)
    check((html.match(/class="lrn-gtodo-i sev-/g) || []).length === 1, "Right now: one numbered row");
    check(html.includes("was computed before your last change") && html.includes(runtime.esc(T("gOpenRun"))),
          "… the recompute row has an Open run button");
    check(html.includes('<span class="lrn-gbadge warn">1</span>'), "… and the section counts it");
    // Fields
    check((html.match(/class="lrn-gfield(?: open)?" data-field=/g) || []).length === 6, "Fields: six rows");
    check(html.includes('<span class="lrn-gbadge mute">6</span>'), "… with a count badge of 6");
    check(!html.includes("data-gfind"), "… no search box at six fields");
    const seven = clone(GUIDE);
    seven.fields.push(Object.assign({}, seven.fields[0], { key: "x7", column: "Seventh" }));
    check(panel.sectionsHTML(seven, { open: ALL_OPEN }).includes("data-gfind"), "… a search box above six");
    // Tasks
    check(html.includes('data-act="c-scenario" data-key="sc_treatment" data-mode="watch"')
          && html.includes('data-key="sc_treatment" data-mode="try"'),
          "Tasks: Fix figures that do not add up — Watch and Practise");
    const noWatch = panel.sectionsHTML(GUIDE, { open: ALL_OPEN, offers: (k, m) => m === "try" });
    check(!noWatch.includes('data-mode="watch"'), "… a mode the engine does not offer is not drawn");
    // Understand
    check(html.includes("Component treatment") && html.includes('data-act="c-lesson"'), "Understand: the lesson door");
    check(html.includes('data-gloss="payRole"') && html.includes("lrn-gloss"), "… the terms as glossary chips");
    check(html.includes(runtime.esc(T("gMistakes"))) && html.includes("Setting hours or days to add to net pay"),
          "… the mistakes the lesson prevents");
    check(html.includes(`${T("min")}`) && /6[^0-9]/.test(html.split("lrn-glessontx")[1] || ""), "… and its minutes");
    // Folded
    const folded = panel.sectionsHTML(GUIDE, { open: { screen: true } });
    check((folded.match(/aria-expanded="false"/g) || []).length === 4 && folded.includes(" hidden>"),
          "a folded section draws only its header (aria-expanded false)");
}

function rightNowSuite() {
    console.log("T1 Right now rows and their buttons");
    const g = clone(GUIDE);
    g.right_now.items = [
        { key: "needs_answer", count: 3, severity: "warn", names: ["Loan Installment", "KPI Bonus", "Incentive"],
          text: "3 rows still need your answer on Pay role: Loan Installment, KPI Bonus, Incentive.",
          action: { kind: "filter", value: "review" } },
        { key: "type_conflict", count: 1, severity: "warn", text: "1 row's value type says otherwise.",
          action: { kind: "filter", value: "conflict" } },
        { key: "recompute", count: 1, severity: "warn", text: "June was computed before your last change.",
          action: { kind: "open", xmlid: "pb_payhub.action_pb_pay_hub", lens: "runs", lens_key: "pb_lens",
                    focus: "319", context: {} } },
        { key: "rec", count: 1, severity: "info", text: "Open the June run.",
          action: { kind: "open_record", res_model: "hr.payslip.run", res_id: 319 } },
    ];
    const html = panel.sectionsHTML(g, { open: ALL_OPEN });
    const buttons = Array.from(html.matchAll(/data-act="c-gact" data-i="(\d)">.*?<\/svg>([^<]+)<\/button>/g), (m) => [m[1], m[2]]);
    check(JSON.stringify(buttons) === JSON.stringify([["0", "Show"], ["1", "Fix"], ["2", "Open run"], ["3", "Open"]]),
          "Show / Fix / Open run / Open, one per action kind", JSON.stringify(buttons));
    check(html.includes("Loan Installment, KPI Bonus, Incentive"), "the hero row names the three components");
    check(html.includes('<span class="lrn-gbadge warn">4</span>'), "four things to do");
    check((html.match(/class="lrn-gnum">(\d)</g) || []).join("") === '<span class="lrn-gnum">1<<span class="lrn-gnum">2<<span class="lrn-gnum">3<<span class="lrn-gnum">4<'
          || /lrn-gnum">1<[\s\S]*lrn-gnum">4</.test(html), "numbered 1 to 4");
    const ok = clone(GUIDE);
    ok.right_now.items = [{ key: "ok", severity: "ok", text: "Nothing needs you here. Save is enabled only when you change a row.", action: null }];
    const okHtml = panel.sectionsHTML(ok, { open: ALL_OPEN });
    check(okHtml.includes("lrn-gnum ok") && !okHtml.includes('data-act="c-gact"') && !okHtml.includes("lrn-gbadge warn"),
          "the provider's own ok line: a tick, no button, no count");
    const empty = clone(GUIDE);
    empty.right_now.items = [];
    check(panel.sectionsHTML(empty, { open: ALL_OPEN }).includes(runtime.esc(T("gNothingHere"))),
          "a provider with nothing to say: Nothing needs you here");
}

function emptySuite() {
    console.log("T1 the designed empty states");
    const bare = {
        screen: { key: "about", name: "About", purpose: "What this system is.", path: [], before: [], after: [] },
        right_now: { ok: false, items: [] }, fields: [], actions: [],
        doors: { station: null, station_name: "", lesson: null, tasks: [], terms: [] },
        lang: "en_US", missing: [panel.NO_MANIFEST],
    };
    const html = panel.sectionsHTML(bare, { open: ALL_OPEN, fallbackNext: "Read the cards from the top." });
    check(html.includes(runtime.esc(T("gNothingLive"))) && html.includes("Read the cards from the top."),
          "no manifest: Nothing live for this screen yet + the static next sentence (fallback line)");
    check((html.match(/lrn-gfall/g) || []).length === 1, "… the sentence once, and no live list beside it");
    check(html.includes(runtime.esc(T("gNoFields"))), "… No field cards for this screen yet");
    check(html.includes(runtime.esc(T("gNoTask"))) && html.includes('data-act="c-gmap"'),
          "… No walkthrough for this screen yet + Open the lesson map");
    check(html.includes(runtime.esc(T("gNoLessonMap"))), "… No lesson for this screen yet, here is the map");
    check(html.includes("What this system is."), "… This screen still says what it is for");

    const noScheme = clone(GUIDE);
    noScheme.right_now = { ok: false, items: [], provider: true };
    noScheme.missing = ["right_now: no scheme selected"];
    const ns = panel.sectionsHTML(noScheme, { open: ALL_OPEN });
    check(ns.includes(runtime.esc(T("gNoScheme"))) && ns.includes('data-act="c-gretry"'),
          "missing: no scheme selected → \"No scheme selected: pick one above\" + Retry");
    check(!ns.includes(runtime.esc(T("gNothingLive"))), "… not the no-live-list line");
    const failed = clone(noScheme);
    failed.missing = ["right_now: could not be read"];
    check(panel.sectionsHTML(failed, { open: ALL_OPEN }).includes(runtime.esc(T("gReadFailed"))),
          "a provider that failed: its reason + Retry");
    check(panel.sectionsHTML(null, {}).includes(runtime.esc(T("gLoading"))), "loading: Loading the board…");
    const err = panel.sectionsHTML(null, { error: true });
    check(err.includes(runtime.esc(T("gFailed"))) && err.includes('data-act="c-gretry"'), "a failed call: its reason and a Retry");
}

function actionSuite() {
    console.log("T1 the actions the buttons make");
    const log = { bus: [], hub: [], act: [] };
    const deps = {
        action: { name: "action-service" },
        bus: { trigger: (name, detail) => log.bus.push([name, detail]) },
        openHub: (svc, opts) => log.hub.push([svc, opts]),
        doAction: (a) => log.act.push(a),
    };
    panel.runAction({ kind: "filter", value: "review" }, deps);
    check(JSON.stringify(log.bus) === JSON.stringify([["pb-learn:act", { kind: "filter", value: "review" }]]),
          "filter → env.bus.trigger('pb-learn:act', {kind:'filter', value})");
    panel.runAction({ kind: "open", xmlid: "pb_formula_studio.action_pb_mapping_studio", lens: "treatment",
                      lens_key: "pb_mode", focus: null, context: { pb_config: 7 } }, deps);
    const [svc, opts] = log.hub[0];
    check(svc === deps.action && opts.xmlid === "pb_formula_studio.action_pb_mapping_studio"
          && opts.lens === "treatment" && opts.lensKey === "pb_mode" && opts.context.pb_config === 7 && !("focus" in opts),
          "open → openHub(action, {xmlid, lens, lensKey, context})", JSON.stringify(opts));
    panel.runAction(GUIDE.right_now.items[0].action, deps);
    check(log.hub[1][1].focus === "319" && log.hub[1][1].lens === "runs",
          "… a cached older Guide's ids still land: focus = the first id", JSON.stringify(log.hub[1][1]));
    panel.runAction({ kind: "open", xmlid: "x.y", config_id: 9 }, deps);
    check(log.hub[2][1].context.pb_config === 9, "… and its config_id becomes pb_config");
    panel.runAction({ kind: "open_record", res_model: "hr.payslip.run", res_id: 319 }, deps);
    check(JSON.stringify(log.act[0]) === JSON.stringify({ type: "ir.actions.act_window", res_model: "hr.payslip.run",
                                                         res_id: 319, views: [[false, "form"]], target: "current" }),
          "open_record → doAction(the record's form, current)");
    const before = log.hub.length;
    check(panel.runAction({ kind: "open", xmlid: "pb_settings.action_pb_settings_hub", lens: "access" }, deps) === null
          && log.hub.length === before, "a door into Access and delegations does nothing (Access ruling)");
}

function accessSuite() {
    console.log("T1 the Access ruling, client side");
    const g = clone(GUIDE);
    g.screen.path = [{ label: "Settings", open: { xmlid: "pb_settings.action_pb_settings_hub" } },
                     { label: "Access and delegations", open: { xmlid: "pb_settings.action_pb_settings_hub", lens: "access" } }];
    g.right_now.items[0].action = { kind: "open", xmlid: "pb_settings.action_pb_settings_hub", lens: "nav" };
    const out = panel.dropAccess(g);
    check(out.screen.path.length === 0, "a path into Access is dropped");
    check(out.right_now.items[0].action === null, "an action into the menu editor is dropped");
    check(GUIDE.screen.path.length === 2 && panel.dropAccess(clone(GUIDE)).screen.path.length === 2,
          "an ordinary path is kept, and the input is never written");
    check(panel.actionButton({ action: { kind: "open", xmlid: "pb_settings.action_pb_settings_hub", lens: "access" } }) === null,
          "… and no button is drawn for one");
}

function cardSuite() {
    console.log("T1 the Pay role card");
    const role = GUIDE.fields.find((f) => f.key === "pay_role");
    const html = panel.fieldCardHTML(role, { footer: true, watch: true });
    const labels = role.choices.map((c) => c.label);
    check(labels.length === 6 && labels.every((l) => html.includes(`<b>${runtime.esc(l)}</b>`)),
          "the six choices, each in bold", labels.join(" | "));
    check(role.choices.every((c) => html.includes(runtime.esc(c.when))), "… each with when to pick it");
    check(html.includes(runtime.esc(T("gFilled"))) && html.includes("Set by a person"), "How it is filled + the set-by chips");
    const shown = (html.match(/class="lrn-fc-chip use"(?! hidden)>/g) || []).length;
    const rest = role.used_by.length - panel.USED_BY_SHOWN;
    check(shown === 6 && html.includes(`and ${rest} more`), `Used by: six chips + "and ${rest} more"`, `shown ${shown}`);
    const wide = Object.assign({}, role, { used_by: Array.from({ length: 33 }, (_x, i) => ({ label: `Reader ${i}` })) });
    check(panel.fieldCardHTML(wide).includes("and 27 more"), "33 readers fold to six + \"and 27 more\"");
    check(html.includes(runtime.esc(T("gIfChanged"))) && html.includes(runtime.esc(role.if_changed)), "If you change it");
    check(html.includes('data-fc="guide"') && html.includes('data-fc="watch"'), "footer: Open in the Guide, Watch this field");
    check(html.includes('data-fc="up"') && html.includes('data-fc="down"') && html.includes("thumbs-up"), "… and the thumbs");
    check(!panel.fieldCardHTML(role, {}).includes('data-fc="watch"'), "no Watch when no step points at the field");
    const lane = GUIDE.fields.find((f) => f.derived);
    const lh = panel.fieldCardHTML(lane);
    check(lh.includes(runtime.esc(T("gValues"))) && lh.includes("Calculated by a formula") && !lh.includes(runtime.esc(T("gChoices"))),
          "a derived card: what it can say, worked out from…");
    check(!/odoo/i.test(html + lh), "no brand word in a card");
}

function askSuite() {
    console.log("T1 the Ask chips");
    const g = clone(GUIDE);
    g.right_now.items.unshift({ key: "needs_answer", severity: "warn", names: ["Loan Installment"], text: "x", action: null });
    const chips = panel.askChips(g).map((c) => c.text);
    check(chips[0] === "What reads the pay role?", "What reads the pay role?", chips[0]);
    check(chips[1] === "Why does Loan Installment need my answer?", "Why does Loan Installment need my answer?", chips[1]);
    check(panel.askChips(GUIDE).length === 1, "no needs-answer row, no second question");
    const approvals = { lang: "en_US", right_now: { items: [] },
                        fields: [{ key: "state", column: "Waiting for a decision", label: "Status",
                                   used_by: [{ label: "x" }] }] };
    check(panel.askChips(approvals)[0].text === "What reads the status?",
          "a state-phrase column asks by the field's own name", panel.askChips(approvals)[0].text);
}

function viSuite() {
    console.log("T1 Vietnamese");
    RT.lang = "vi";
    const html = panel.sectionsHTML(GUIDE, { open: ALL_OPEN });
    for (const [k, vi] of [["gSecScreen", "Màn hình này"], ["gSecNow", "Ngay lúc này"],
                           ["gSecFields", "Các trường trên màn hình này"], ["gSecTasks", "Tác vụ"],
                           ["gSecUnderstand", "Hiểu rõ"]]) {
        check(html.includes(vi), `${k}: ${vi}`);
    }
    check(T("gSecAsk") === "Hỏi" && panel.fieldCardHTML(GUIDE.fields[2]).includes("Các lựa chọn"), "Ask, and the card's labels");
    RT.lang = "en";
}

// =================================================================== T2
class El {
    constructor(tag, html = "", opts = {}) {
        this.tagName = tag.toUpperCase();
        this._html = html;
        this.children = [];
        this.attrs = {};
        this.listeners = {};
        this.className = opts.className || "";
        this.parentElement = null;
    }
    get innerHTML() {
        return this._html + this.children.map((c) => c.outerHTML).join("");
    }
    set innerHTML(v) {
        this._html = v;
        this.children = [];
    }
    get outerHTML() {
        const t = this.tagName.toLowerCase();
        return `<${t} class="${this.className}">${this.innerHTML}</${t}>`;
    }
    set type(v) { this.attrs.type = v; }
    appendChild(c) { this.children.push(c); c.parentElement = this; }
    setAttribute(k, v) { this.attrs[k] = String(v); }
    getAttribute(k) { return this.attrs[k]; }
    addEventListener(t, f) { this.listeners[t] = f; }
    querySelector(sel) {
        const m = /data-learn-field="([^"]+)"/.exec(sel);
        return this.children.find((c) => c.className === "lrn-i" && c.attrs["data-learn-field"] === (m && m[1])) || null;
    }
    closest() { return null; }
    remove() {
        if (this.parentElement) {
            this.parentElement.children = this.parentElement.children.filter((c) => c !== this);
        }
    }
}

function fakeBoard(headers) {
    const ths = headers.map((h) => new El("th", h));
    const anchor = new El("table");
    anchor.querySelectorAll = () => ths;
    const doc = {
        createElement: (t) => new El(t),
        querySelectorAll: (sel) => {
            if (sel === '[data-coach="tr-table"]') { return [anchor]; }
            if (sel.startsWith(".lrn-i")) { return ths.flatMap((th) => th.children); }
            return [];
        },
    };
    return { ths, anchor, doc };
}

function finderSuite() {
    console.log("T2 the header finder");
    check(info.norm("Included in<br/>another total") === "Included in another total", "norm: a <br/> is a space");
    check(info.norm("Figures don’t add up") === "Figures don't add up", "norm: a curly apostrophe is straight");
    check(info.norm("  Pay&nbsp;role \n ") === "Pay role", "norm: entities and whitespace");
    const { anchor } = fakeBoard(["Component", "Included in<br/>another total", "Figures don’t add up",
                                  '<span class="pct-th-wrap">Included in another total</span>']);
    const a = info.findHeader(anchor, "Included in another total");
    check(a && a.innerHTML === "Included in<br/>another total", "findHeader matches Included in<br/>another total");
    const b = info.findHeader(anchor, "Figures don't add up");
    check(b && b.innerHTML.includes("Figures don’t add up"), "findHeader matches Figures don’t add up");
    check(info.findHeader(anchor, ["Đã tính trong một tổng khác", "Included in another total"]) === a,
          "either spelling (VI or EN) finds it");
    check(info.findHeader(anchor, "Pay role") === null, "a column that is not drawn: null");
    const { anchor: desk } = fakeBoard(['Value type<select><option>Amount (currency)</option></select>']);
    check(!!info.findHeader(desk, "Value type"), "a label that wraps its own select reads as its words");
    const { anchor: wrapped } = fakeBoard(['<span class="pct-th-wrap">Included in another total</span>']);
    check(!!info.findHeader(wrapped, "Included in another total"), "the one-text header inside its wrap span (LR30)");
}

function injectSuite() {
    console.log("T2 the (i) injection");
    const cols = GUIDE.fields.map((f) => f.column);
    const { ths, doc } = fakeBoard(["Component", ...cols.map((c) => (c === "Included in another total" ? "Included in<br/>another total" : c))]);
    const opened = [];
    const first = info.injectInfo(doc, GUIDE.fields, (key) => opened.push(key));
    check(first.added === 6 && !first.missing.length, "six (i) laid on six headers", JSON.stringify(first));
    const second = info.injectInfo(doc, GUIDE.fields, () => {});
    check(second.added === 0 && second.present === 6, "a second run adds 0 buttons", JSON.stringify(second));
    const btn = ths[3].children[0];
    check(btn && btn.className === "lrn-i" && btn.attrs.type === "button"
          && btn.attrs["aria-label"] === "Explain Pay role" && btn.innerHTML.includes("lrn-i-info"),
          "a real <button>, aria-label \"Explain Pay role\", the info icon");
    let stopped = false;
    btn.listeners.click({ preventDefault: noop, stopPropagation: () => { stopped = true; } });
    check(stopped && opened[0] === "pay_role", "a press opens the card and never reaches the (sortable) header");
    check(ths[0].children.length === 0, "the Component header gets none (no card for it)");
    const noAnchor = info.injectInfo(doc, [{ key: "state", column: "Waiting for a decision", anchor: "" }], noop);
    check(noAnchor.added === 0 && !noAnchor.missing.length, "a field with no anchor gets no (i)");
    const missing = info.injectInfo(doc, [{ key: "zz", column: "Not drawn", anchor: "tr-table" }], noop);
    check(missing.missing[0] === "zz", "a field whose header is not on screen is reported");
    const tile = fakeBoard(["Need review"]);
    tile.ths[0].closest = (sel) => (sel.includes("button") ? { tagName: "BUTTON" } : null);
    info.injectInfo(tile.doc, [{ key: "need_review", column: "Need review", anchor: "tr-table" }], noop);
    const inner = tile.ths[0].children[0];
    check(inner && inner.tagName === "SPAN" && inner.attrs.role === "button" && inner.attrs.tabindex === "0"
          && typeof inner.listeners.keydown === "function",
          "inside a clickable tile the (i) is a span role=button, Tab + Enter/Space");
    info.removeInfo(doc, ["pay_role"]);
    check(ths[3].children.length === 1 && ths[1].children.length === 0, "removeInfo keeps only the named ones");
}

// ============================================================ the drawer
async function drawerSuite() {
    console.log("T1 the drawer wiring");
    const calls = [];
    const doActions = [];
    pb.services.orm = {
        call: async (model, method, args = [], kwargs = {}) => {
            calls.push({ model, method, args, kwargs });
            if (model === "learn.guide" && method === "rpc_guide") { return clone(GUIDE); }
            return null;
        },
    };
    pb.services.action = { currentController: null, doAction: async (a, o) => { doActions.push([a, o]); } };
    pb.services["learn.scenario"] = {
        state: {}, load: async () => {}, forScreen: () => [], steps: () => [],
        get: (k) => (CONTENT.scenarios || []).find((s) => s.key === k) || null,
    };
    const coachMod = await load("@pb_learn/coach/coach",
                                ["@pb_learn/engine/runtime", "@pb_learn/engine/glossary",
                                 "@pb_learn/coach/guide_panel", "@pb_learn/coach/field_info",
                                 "@pb_hub/js/hub_nav"]);
    const { CoachHost, COACH_ACTIONS } = coachMod;
    const hooks = { willStart: [], mounted: [] };
    pb.hookCtx.current = hooks;
    const host = new CoachHost({}, { bus: { trigger: () => {} } });
    host.setup();
    pb.hookCtx.current = null;
    host.place = { tag: "pb_mapping_studio", lens: "treatment", subs: {}, lenses: [], seq: 1, detail: "",
                   ready: true, extra: { config_id: 5 } };
    host.bundle = { screens: CONTENT.screens, global_suggest: [], chrome: CONTENT.chrome, stations,
                    guide: true, collect_questions: false };
    host.state.ready = true;
    host.state.screen = "treatment";
    host.state.gSec = ALL_OPEN;
    await host._loadGuide();
    const call = calls.find((c) => c.method === "rpc_guide");
    check(call && JSON.stringify(call.args) === JSON.stringify(["treatment", { config_id: 5 }])
          && call.kwargs.context.lang === "en_US",
          "one rpc_guide(screen, {config_id}) in the helper's language", JSON.stringify(call));
    check(host.state.guide && host.state.guide.fields.length === 6, "the Guide is held for the screen");
    await host._loadGuide();
    check(calls.filter((c) => c.method === "rpc_guide").length === 1, "a second look at the same screen is a cache hit");
    await host._loadGuide({ refresh: true });
    check(calls.filter((c) => c.method === "rpc_guide").length === 2, "an open reads Right now again");
    const html = String(host.guideHTML);
    check(panel.sectionOrder(html).length === 5, "the drawer draws the five sections");
    check(host.guideHTML === host.guideHTML, "the same markup object while nothing changed (no flicker)");
    const drawn = new Set(acts(html));
    check([...drawn].every((a) => COACH_ACTIONS.has(a)), "every data-act the panel draws is declared", [...drawn].join(","));
    for (const a of ["c-gsec", "c-gpath", "c-gscreen", "c-gact", "c-gfield", "c-gretry", "c-gmap", "c-gdock", "c-guide", "c-fvguide"]) {
        check(COACH_ACTIONS.has(a), `COACH_ACTIONS has ${a}`);
    }
    host._guideAct(0);
    const [target, opts] = doActions[0] || [];
    check(target === "pb_payhub.action_pb_pay_hub" && opts.additionalContext.pb_lens === "runs"
          && opts.additionalContext.pb_focus === "319",
          "Open run lands on Payroll › Runs with the run's card in focus", JSON.stringify(doActions[0]));
    host._toggleSection("fields");
    check(host.state.gSec.fields === false, "a section header folds its section");
    // The chat's opening card: whatnext goes when there is a live list, two
    // questions from the Guide join.
    const ctx = host._notSureHTML({});
    check(!ctx.includes('data-key="whatnext"'), "the whatnext chip is gone where Right now is live");
    check(ctx.includes("What reads the pay role?"), "… \"What reads the pay role?\" joins the chips");
    const answer = { matched: true, key: "screen:treatment", label: { en: "Explain this screen", vi: "x" },
                     blocks: [], source_kind: "screen", guide_door: true, show_me: [] };
    check(host._answerHTML(answer).includes('data-act="c-guide"'), "Explain built from the Guide offers Open the Guide");
    host.bundle.guide = false;
    check(!host._answerHTML(answer).includes('data-act="c-guide"') && !host.guideShown,
          "switch off: no door, no panel");
    await host._loadGuide();
    check(host.state.guide === null, "switch off: no Guide is fetched or held");
}

sectionsSuite();
rightNowSuite();
emptySuite();
actionSuite();
accessSuite();
cardSuite();
askSuite();
viSuite();
finderSuite();
injectSuite();
await drawerSuite();
summary();
