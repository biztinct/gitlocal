/** @odoo-module **/
/* =============================================================================
   LEARNREV P2 — the Guide panel: six sections above the one chat.

   PURE ON PURPOSE. Everything here takes the Guide JSON (`learn.guide.
   rpc_guide`, learn_guide.py) plus a small `ui` object and returns HTML or a
   plain decision. No component, no service, no DOM — so the node harness
   (tests/js/guide_panel.test.mjs) renders the real thing from a fixture, and
   the drawer (coach.js) owns only state, fetching and the click wiring.

   THE ORDER IS FIXED AND THERE ARE NO TABS (ONECHAT ruling): This screen ·
   Right now · Fields on this screen · Tasks · Understand · Ask. Ask is the
   one chat itself, drawn by the drawer under these five.

   Every control is a `data-act` the drawer declares in COACH_ACTIONS. None
   reaches a product method from here: `runAction` below opens a screen, asks
   a board to filter itself through the bus, or opens a record's form — the
   same three things a person could do by clicking.

   MINIFIER HAZARD (runtime.js): never a literal space straight after `}` in
   a template literal — SP instead.
   ========================================================================== */
import { T, esc, ic, SP } from "../engine/runtime";

/** The five sections drawn above the chat, in order. */
export const SECTIONS = ["screen", "now", "fields", "tasks", "understand"];
const SECTION_COPY = {
    screen: ["map-pin", "gSecScreen"],
    now: ["zap", "gSecNow"],
    fields: ["list-checks", "gSecFields"],
    tasks: ["flask", "gSecTasks"],
    understand: ["book-open", "gSecUnderstand"],
};

/* The reasons `missing` can hold (learn_guide.py), as the panel says them. */
export const NO_MANIFEST = "no manifest for this screen yet";
export const RN_NONE = "right_now: nothing live for this screen yet";
const RN_COPY = {
    "right_now: no scheme selected": "gNoScheme",
    "right_now: no access": "gNoAccess",
    "right_now: could not be read": "gReadFailed",
    "right_now: not available on this database": "gUnavailable",
};

/** How many "Used by" chips a card shows before "and N more". */
export const USED_BY_SHOWN = 6;
/** A search box over the Fields section above this many fields. */
export const FIND_ABOVE = 6;

/** `{name}` placeholders, filled in. */
export function fmt(text, vars = {}) {
    return String(text || "").replace(/\{(\w+)\}/g, (m, k) =>
        (Object.prototype.hasOwnProperty.call(vars, k) ? String(vars[k]) : m));
}

// ------------------------------------------------------------ the Access ruling
/* Settings › Access and delegations and the menu editor are never offered by
   the Guide (owner ruling 2026-10-13). The server drops them too; this is the
   client half, so a stale or hand-made Guide cannot draw one either. */
const ACCESS_HUB_XMLID = "pb_settings.action_pb_settings_hub";
const ACCESS_LENSES = ["access", "nav"];

export function isAccessTarget(open) {
    return !!open && open.xmlid === ACCESS_HUB_XMLID
        && ACCESS_LENSES.includes(open.lens || "");
}

/** A copy of the Guide with every door into Access removed. */
export function dropAccess(guide) {
    if (!guide || typeof guide !== "object") {
        return guide;
    }
    const out = Object.assign({}, guide);
    const screen = Object.assign({}, guide.screen || {});
    const path = screen.path || [];
    screen.path = path.some((p) => isAccessTarget(p.open)) ? [] : path.slice();
    out.screen = screen;
    const rn = Object.assign({ items: [] }, guide.right_now || {});
    rn.items = (rn.items || []).map((i) => (i && i.action && isAccessTarget(i.action)
        ? Object.assign({}, i, { action: null }) : i));
    out.right_now = rn;
    return out;
}

// ------------------------------------------------------------- right now
/** True when the screen has a live list at all (a provider is declared). */
export function hasProvider(guide) {
    const rn = (guide && guide.right_now) || {};
    if (typeof rn.provider === "boolean") {
        return rn.provider;
    }
    const missing = (guide && guide.missing) || [];
    return !missing.includes(RN_NONE) && !missing.includes(NO_MANIFEST);
}

/** The right-now reason worth saying, or "". */
export function rightNowReason(guide) {
    const missing = (guide && guide.missing) || [];
    return missing.find((m) => m.startsWith("right_now:") && m !== RN_NONE) || "";
}

/** Items a person should act on (not the "nothing needs you" line). */
export function actionable(guide) {
    return (((guide && guide.right_now) || {}).items || []).filter((i) => i.severity !== "ok");
}

/** The button an item gets: its label key and icon, or null for none. */
export function actionButton(item) {
    const a = item && item.action;
    if (!a || !a.kind) {
        return null;
    }
    if (a.kind === "filter") {
        return a.value === "conflict" ? { label: "gFix", icon: "check" } : { label: "gShow", icon: "eye" };
    }
    if (a.kind === "open") {
        return isAccessTarget(a) ? null
            : { label: item.key === "recompute" ? "gOpenRun" : "gOpen", icon: "arrow-right" };
    }
    if (a.kind === "open_record") {
        return { label: "gOpen", icon: "arrow-right" };
    }
    return null;
}

/**
 * Do what an item's button says. `deps` = {action, openHub, bus, doAction}
 * (the drawer's own services). Returns what was done, for the caller's
 * follow-up (a filter scrolls the board and re-reads "Right now").
 *
 *   filter       the board on screen SETS that chip (`pb-learn:act` bus);
 *   open         a hub (or a screen) with its lens, focus and context;
 *   open_record  that record's form.
 *
 * An older provider's `ids` / `config_id` are read as `focus` / `pb_config`,
 * so a Guide cached across a deploy still lands in the right place.
 */
export function runAction(a, deps = {}) {
    if (!a || !a.kind) {
        return null;
    }
    if (a.kind === "filter") {
        if (deps.bus) {
            deps.bus.trigger("pb-learn:act", { kind: "filter", value: a.value || "" });
        }
        return { kind: "filter", value: a.value || "" };
    }
    if (a.kind === "open") {
        if (isAccessTarget(a) || !a.xmlid) {
            return null;
        }
        const context = Object.assign({}, a.context || {});
        if (!context.pb_config && a.config_id) {
            context.pb_config = a.config_id;
        }
        let focus = a.focus || null;
        if (!focus && Array.isArray(a.ids) && a.ids.length) {
            focus = String(a.ids[0]);
        }
        const opts = { xmlid: a.xmlid, lens: a.lens || undefined, lensKey: a.lens_key || undefined,
                       context };
        if (focus) {
            opts.focus = focus;
        }
        deps.openHub(deps.action, opts);
        return { kind: "open", opts };
    }
    if (a.kind === "open_record") {
        const res_model = a.res_model || a.model;
        const res_id = a.res_id || a.id;
        if (!res_model || !res_id) {
            return null;
        }
        const act = { type: "ir.actions.act_window", res_model, res_id,
                      views: [[false, "form"]], target: "current" };
        deps.doAction(act);
        return { kind: "open_record", act };
    }
    return null;
}

// ------------------------------------------------------------ rendering bits
function chev() {
    return `<span class="lrn-gchev" aria-hidden="true">${ic("chevron-down")}</span>`;
}

function badge(n, tone) {
    return n ? `<span class="lrn-gbadge ${tone || ""}">${esc(String(n))}</span>` : "";
}

function stateLine(icon, text, tone, retry) {
    const btn = retry ? `<button type="button" class="lrn-btn sm ghost lrn-gretry" data-act="c-gretry">${ic("rotate-ccw")}${esc(T("retry"))}</button>` : "";
    return `<div class="lrn-gstate ${tone || ""}" role="status">${ic(icon)}<span>${esc(text)}</span>${btn}</div>`;
}

function skeleton() {
    return `<div class="lrn-gskel" aria-hidden="true"><i></i><i></i><i></i></div>`;
}

function section(key, open, body, extra) {
    const [icon, title] = SECTION_COPY[key];
    return `<section class="lrn-gsec${open ? " open" : ""}" data-sec="${key}">
        <h3 class="lrn-gsech"><button type="button" class="lrn-gsecbtn" data-act="c-gsec" data-sec="${key}"
            aria-expanded="${open ? "true" : "false"}" aria-controls="lrn-gs-${key}">
            <span class="lrn-gsecic">${ic(icon)}</span><span class="lrn-gsect">${esc(T(title))}</span>${extra || ""}${chev()}</button></h3>
        <div class="lrn-gsecb" id="lrn-gs-${key}"${open ? "" : " hidden"}>${open ? body : ""}</div>
    </section>`;
}

// ---------------------------------------------------------------- 1. screen
function screenBody(g) {
    const s = g.screen || {};
    const parts = [];
    if (s.purpose) {
        parts.push(`<p class="lrn-gpurpose">${esc(s.purpose)}</p>`);
    }
    const sep = `<span class="lrn-gsep" aria-hidden="true">${ic("chevron-right")}</span>`;
    const chips = [];
    for (const b of s.before || []) {
        chips.push(`<button type="button" class="lrn-gchip before" data-act="c-gscreen" data-screen="${esc(b.screen)}"
            title="${esc(b.why || "")}"><small>${esc(T("gBefore"))}</small>${esc(b.name)}</button>`);
    }
    const path = s.path || [];
    path.forEach((p, i) => {
        const here = i === path.length - 1;
        chips.push(here
            ? `<span class="lrn-gchip here" aria-current="page">${esc(p.label)}</span>`
            : `<button type="button" class="lrn-gchip path" data-act="c-gpath" data-i="${i}">${esc(p.label)}</button>`);
    });
    for (const a of s.after || []) {
        chips.push(`<button type="button" class="lrn-gchip after" data-act="c-gscreen" data-screen="${esc(a.screen)}"
            title="${esc(a.why || "")}"><small>${esc(T("next"))}</small>${esc(a.name)}</button>`);
    }
    if (chips.length) {
        parts.push(`<div class="lrn-gstrip" role="group" aria-label="${esc(T("youAreHere"))}">
            <span class="lrn-gstripl">${ic("map-pin")}${esc(T("youAreHere"))}</span>
            <div class="lrn-gchips">${chips.join(sep)}</div></div>`);
    }
    return parts.join("") || stateLine("info", T("gNothingLive"), "mute");
}

// ---------------------------------------------------------------- 2. right now
function nowBody(g, ui) {
    const rn = g.right_now || {};
    const items = rn.items || [];
    if (!hasProvider(g)) {
        // No live list on this screen: the designed empty state, then the
        // screen's one authored sentence as a quiet fallback line — never
        // both a live list and the sentence.
        const fall = ui.fallbackNext ? `<p class="lrn-gfall">${esc(ui.fallbackNext)}</p>` : "";
        return `${stateLine("info", T("gNothingLive"), "mute")}${fall}`;
    }
    const reason = rightNowReason(g);
    if (reason && !items.length) {
        const copy = RN_COPY[reason] || "gReadFailed";
        return stateLine(copy === "gNoScheme" ? "layers" : "info", T(copy), "note", true);
    }
    if (!items.length) {
        return stateLine("check-circle", T("gNothingHere"), "ok");
    }
    let n = 0;
    const rows = items.map((item, i) => {
        if (item.severity === "ok") {
            return `<li class="lrn-gtodo-i ok"><span class="lrn-gnum ok">${ic("check")}</span>
                <span class="lrn-gtx">${esc(item.text)}</span></li>`;
        }
        n += 1;
        const btn = actionButton(item);
        const press = btn ? `<button type="button" class="lrn-btn sm lrn-gact" data-act="c-gact" data-i="${i}">${ic(btn.icon)}${esc(T(btn.label))}</button>` : "";
        return `<li class="lrn-gtodo-i sev-${esc(item.severity || "info")}"><span class="lrn-gnum">${n}</span>
            <span class="lrn-gtx">${esc(item.text)}</span>${press}</li>`;
    });
    return `<ol class="lrn-gtodo">${rows.join("")}</ol>`;
}

// ---------------------------------------------------------------- 3. fields
/** The one-line summary a Fields row shows under its column name. */
export function fieldLine(card) {
    const t = String((card && (card.derived ? card.filled_by : (card.help || card.filled_by))) || "");
    // No look-behind: a parse-time SyntaxError on Safari before 16.4 (OC49).
    const hit = /^.*?[.!?](?=\s|$)/.exec(t);
    const first = hit ? hit[0] : t;
    return first.length > 140 ? `${first.slice(0, 137)}…` : first;
}

/** Does a field row match the search words (column, help, choices)? */
export function fieldMatches(card, query) {
    const q = String(query || "").trim().toLowerCase();
    if (!q) {
        return true;
    }
    const hay = [card.column, card.label, card.help, card.filled_by,
                 ...(card.choices || []).map((c) => c.label),
                 ...(card.values || []).map((v) => v.label)].join(" ").toLowerCase();
    return q.split(/\s+/).every((w) => hay.includes(w));
}

function fieldsBody(g, ui) {
    const fields = g.fields || [];
    if (!fields.length) {
        return stateLine("info", T("gNoFields"), "mute");
    }
    const q = ui.query || "";
    const find = fields.length > FIND_ABOVE
        ? `<label class="lrn-gfind">${ic("search")}<input type="search" data-gfind="1"
            placeholder="${esc(T("gFindField"))}" aria-label="${esc(T("gFindField"))}" value="${esc(q)}"/></label>`
        : "";
    let shown = 0;
    const rows = fields.map((card) => {
        const ok = fieldMatches(card, q);
        shown += ok ? 1 : 0;
        const open = ui.expanded === card.key;
        const body = open
            ? `<div class="lrn-gfcard">${fieldCardHTML(card, { watch: ui.watchFor && ui.watchFor(card) })}</div>` : "";
        return `<div class="lrn-gfield${open ? " open" : ""}" data-field="${esc(card.key)}"${ok ? "" : " hidden"}>
            <button type="button" class="lrn-gfrow" data-act="c-gfield" data-key="${esc(card.key)}" aria-expanded="${open ? "true" : "false"}">
                <span class="lrn-gftx"><b>${esc(card.column)}</b><small>${esc(fieldLine(card))}</small></span>${chev()}</button>${body}</div>`;
    });
    const none = `<p class="lrn-gnomatch"${shown ? " hidden" : ""}>${esc(T("gNoFieldMatch"))}</p>`;
    return `${find}<div class="lrn-gfields">${rows.join("")}</div>${none}`;
}

// ---------------------------------------------------------------- 4. tasks
const MODE_LABEL = { watch: "scWatch", try: "scPractise", do: "scDo" };
const MODE_ICON = { watch: "play", try: "flask", do: "zap" };

/** LEARNREV P4 (S3) — the walkthrough running beside the Guide. */
function playingRow(p) {
    const label = fmt(T("gPlaying"), { n: (p.index || 0) + 1, m: p.total || 1 });
    return `<div class="lrn-gplaying" role="status"><span class="lrn-gplayic">${ic("play")}</span>
        <span class="lrn-gplaytx"><b>${esc(p.name || "")}</b><small>${esc(label)}</small></span>
        <button type="button" class="lrn-btn sm ghost" data-act="c-scstop">${ic("square")}${esc(T("gStop"))}</button></div>`;
}

function tasksBody(g, ui) {
    if (ui.playing) {
        return playingRow(ui.playing);
    }
    const offers = ui.offers || (() => true);
    const tasks = ((g.doors || {}).tasks || []).map((t) => {
        const modes = (t.modes || []).filter((m) => MODE_LABEL[m] && offers(t.key, m));
        if (!modes.length) {
            return "";
        }
        const chips = modes.map((m) => `<button type="button" class="lrn-tchip${m === "watch" ? " pri" : ""}"
            data-act="c-scenario" data-key="${esc(t.key)}" data-mode="${esc(m)}">${ic(MODE_ICON[m])}<span>${esc(T(MODE_LABEL[m]))}</span></button>`);
        return `<div class="lrn-gtask"><b>${esc(t.name)}</b><div class="lrn-tchips">${chips.join("")}</div></div>`;
    }).filter(Boolean);
    if (!tasks.length) {
        return `${stateLine("info", T("gNoTask"), "mute")}
            <button type="button" class="lrn-btn sm ghost" data-act="c-gmap">${ic("map")}${esc(T("gLessonMap"))}</button>`;
    }
    return tasks.join("");
}

// ---------------------------------------------------------------- 5. understand
function understandBody(g, ui) {
    const d = g.doors || {};
    const parts = [];
    const station = (ui.stations || []).find((s) => s.key === d.station) || null;
    if (d.station) {
        const mins = station && station.duration_min
            ? `<small>${esc(String(station.duration_min))}${SP}${esc(T("min"))}</small>` : "";
        // LEARNREV P4 — the lesson plays HERE, beside the real screen; the
        // Learn page's outline stays one press away as the quieter door.
        const start = d.lesson && ui.canPlay !== false
            ? `<button type="button" class="lrn-btn sm pri" data-act="c-lpstart">${ic("play")}${esc(T("lpStart"))}</button>` : "";
        parts.push(`<div class="lrn-glesson"><span class="lrn-glessonic">${ic("grad-cap")}</span>
            <span class="lrn-glessontx"><b>${esc(d.station_name || "")}</b>${mins}</span>
            ${start}<button type="button" class="lrn-btn sm${start ? " ghost" : " pri"}" data-act="c-lesson">${ic("book-open")}${esc(T("openLesson"))}</button></div>`);
    } else {
        parts.push(`${stateLine("info", T("gNoLessonMap"), "mute")}
            <button type="button" class="lrn-btn sm ghost" data-act="c-gmap">${ic("map")}${esc(T("gLessonMap"))}</button>`);
    }
    const terms = d.terms || [];
    if (terms.length) {
        // The glossary's own hovercard: `.lrn-gloss` is what it listens for.
        parts.push(`<div class="lrn-glabel">${esc(T("gTerms"))}</div><div class="lrn-gterms">${terms.map((t) =>
            `<span class="lrn-gloss lrn-gterm" data-gloss="${esc(t.key)}" tabindex="0" role="term">${esc(t.term)}</span>`).join("")}</div>`);
    }
    const mistakes = ((station && station.outline) || {}).mistakes || [];
    if (mistakes.length) {
        parts.push(`<div class="lrn-glabel">${esc(T("gMistakes"))}</div><ul class="lrn-gmist">${mistakes.map((m) =>
            `<li>${ic("alert-triangle")}<span>${esc(ui.text ? ui.text(m) : String(m))}</span></li>`).join("")}</ul>`);
    }
    return parts.join("");
}

/**
 * The five sections, in order. `ui`:
 *   open        {section: bool}
 *   loading     true while the first answer for this screen is on its way
 *   error       true when the call failed (the reason and a Retry show)
 *   fallbackNext the screen's static next sentence (no live list)
 *   query       the Fields search words; expanded the open field row
 *   offers(key, mode), stations, text(pair), watchFor(card)
 */
export function sectionsHTML(g, ui = {}) {
    const open = ui.open || {};
    if (!g) {
        if (ui.error) {
            return `<div class="lrn-gsecs">${stateLine("alert-triangle", T("gFailed"), "bad", true)}</div>`;
        }
        return `<div class="lrn-gsecs">${stateLine("hourglass", T("gLoading"), "mute")}${skeleton()}</div>`;
    }
    const n = actionable(g).length;
    const fields = (g.fields || []).length;
    const out = [
        section("screen", !!open.screen, screenBody(g)),
        section("now", !!open.now, nowBody(g, ui), badge(n, "warn")),
        section("fields", !!open.fields, fieldsBody(g, ui), badge(fields, "mute")),
        section("tasks", !!open.tasks || !!ui.playing, tasksBody(g, ui)),
        // LEARNREV P4 — while a lesson plays, its step card IS this section.
        ui.lessonHTML
            ? section("understand", true, ui.lessonHTML)
            : section("understand", !!open.understand, understandBody(g, ui)),
    ];
    return `<div class="lrn-gsecs${ui.loading ? " busy" : ""}">${out.join("")}</div>`;
}

/** Which section keys the drawer drew, in order (for the tests). */
export function sectionOrder(html) {
    return Array.from(String(html).matchAll(/data-sec="([a-z]+)"/g), (m) => m[1])
        .filter((k, i, all) => all.indexOf(k) === i);
}

// ---------------------------------------------------------------- the card
/**
 * One field's card — the (i) card beside the column AND the expanded row in
 * the Fields section (one renderer, so the two can never disagree).
 *   opts.footer  draw Open in the Guide (the floating card only)
 *   opts.watch   a scenario step key exists for this field's anchor
 */
export function fieldCardHTML(card, opts = {}) {
    if (!card) {
        return "";
    }
    const parts = [`<div class="lrn-fc-h"><span class="lrn-fc-ic">${ic("info")}</span><b>${esc(card.column)}</b></div>`];
    const lead = card.derived ? card.filled_by : card.help;
    if (lead) {
        parts.push(`<p class="lrn-fc-help">${esc(lead)}</p>`);
    }
    const choices = card.choices || [];
    if (choices.length) {
        parts.push(`<div class="lrn-fc-l">${esc(T("gChoices"))}</div><ul class="lrn-fc-choices">${choices.map((c) =>
            `<li><b>${esc(c.label)}</b>${c.when ? `<span>${esc(c.when)}</span>` : ""}</li>`).join("")}</ul>`);
    }
    const values = card.values || [];
    if (values.length) {
        parts.push(`<div class="lrn-fc-l">${esc(T("gValues"))}</div><div class="lrn-fc-chips">${values.map((v) =>
            `<span class="lrn-fc-chip">${esc(v.label)}</span>`).join("")}</div>`);
    }
    if (!card.derived && card.filled_by) {
        const src = (card.source_values || []).map((v) => `<span class="lrn-fc-chip src">${esc(v.label)}</span>`).join("");
        parts.push(`<div class="lrn-fc-l">${esc(T("gFilled"))}</div><p>${esc(card.filled_by)}</p>${src ? `<div class="lrn-fc-chips">${src}</div>` : ""}`);
    }
    const used = card.used_by || [];
    if (used.length) {
        const chips = used.map((u, i) => `<span class="lrn-fc-chip use"${i < USED_BY_SHOWN ? "" : " hidden"}>${esc(u.label)}</span>`).join("");
        const rest = used.length - USED_BY_SHOWN;
        const more = rest > 0 ? `<button type="button" class="lrn-fc-more" data-fcmore="1" aria-expanded="false">${esc(fmt(T("gAndMore"), { n: rest }))}</button>` : "";
        parts.push(`<div class="lrn-fc-l">${esc(T("gUsedBy"))}</div><div class="lrn-fc-chips">${chips}${more}</div>`);
    }
    if (card.if_changed) {
        parts.push(`<div class="lrn-fc-l">${esc(T("gIfChanged"))}</div><p class="lrn-fc-if">${esc(card.if_changed)}</p>`);
    }
    const foot = [];
    if (opts.footer) {
        foot.push(`<button type="button" class="lrn-btn sm" data-fc="guide">${ic("panel-right")}${esc(T("gOpenInGuide"))}</button>`);
    }
    if (opts.watch) {
        foot.push(`<button type="button" class="lrn-btn sm" data-fc="watch">${ic("play")}${esc(T("gWatchField"))}</button>`);
    }
    foot.push(`<span class="lrn-fb" role="group" aria-label="${esc(T("gHelpful"))}">
        <button type="button" class="lrn-fbbtn" data-fc="up" data-key="${esc(card.key)}" aria-label="${esc(T("gHelpfulYes"))}" title="${esc(T("gHelpfulYes"))}">${ic("thumbs-up")}</button>
        <button type="button" class="lrn-fbbtn" data-fc="down" data-key="${esc(card.key)}" aria-label="${esc(T("gHelpfulNo"))}" title="${esc(T("gHelpfulNo"))}">${ic("thumbs-down")}</button></span>`);
    parts.push(`<div class="lrn-fc-foot">${foot.join("")}</div>`);
    return parts.join("");
}

// ------------------------------------------------------------ the Ask chips
/** The name a question uses for a field: its column, unless the column is a
 *  state phrase that shares no word with the field's own label ("Waiting for
 *  a decision" is the Status field) — then the label. */
function askName(card) {
    const words = (s) => new Set(String(s || "").toLowerCase().split(/\s+/).filter(Boolean));
    const col = words(card.column);
    const label = words(card.label);
    const shared = [...col].some((w) => label.has(w));
    return card.label && !shared ? card.label : card.column;
}

/** Two questions built from the Guide for the chat's opening chips:
 *  "What reads the pay role?" (the field most things read) and "Why does
 *  <first row that needs an answer> need my answer?". Each {text}. */
export function askChips(g) {
    const out = [];
    if (!g) {
        return out;
    }
    const fields = (g.fields || []).filter((f) => (f.used_by || []).length);
    const top = fields.slice().sort((a, b) => (b.used_by.length - a.used_by.length))[0];
    if (top && top.column) {
        const vi = String(g.lang || "").startsWith("vi");
        const name = askName(top);
        out.push({ text: fmt(T("gAskReads"), { field: vi ? name : name.toLowerCase() }) });
    }
    const need = ((g.right_now || {}).items || []).find((i) => i.key === "needs_answer" && (i.names || []).length);
    if (need) {
        out.push({ text: fmt(T("gAskWhy"), { name: need.names[0] }) });
    }
    return out;
}
