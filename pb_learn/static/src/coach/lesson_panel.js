/** @odoo-module **/
/* =============================================================================
   LEARNREV P4 — a lesson played INSIDE the Guide panel, beside the real screen.

   PURE ON PURPOSE, like guide_panel.js: step + a small `ui` object in, HTML or
   a plain decision out. No component, no service, no DOM, so the node harness
   (tests/js/lesson_panel.test.mjs) renders the real thing from the real
   content. The drawer (coach.js) owns the state, the spotlight and the clicks.

   ONE STEP, FOUR LINES. A rewritten step says one thing four ways:
     Look at     what to look at on the screen
     It means    what it means
     It affects  what it changes or feeds (a field step adds its readers)
     Press       what to press — only on a real control
   A step not rewritten yet keeps its `body`, shown as the "It means" line.

   WHERE A STEP PLAYS (`placeFor`). On the real screen, in the panel, when the
   reader can reach the screen and the step points at a real control. A step
   about the practice copy's own drawing (`rep-*`) or a screen this reader
   cannot open plays in the practice copy instead, with one line that says so.

   COUNTRY (`pickCountry`, `stepView`). A statutory step may carry `variants`
   per country (VN, ID, IN, SG) and a `generic` one; the active scheme's country
   wins over the company's, and anything unknown reads the generic one.

   MINIFIER HAZARD (runtime.js): never a literal space straight after `}` in a
   template literal — SP instead.
   ========================================================================== */
import { T, esc, ic, SP } from "../engine/runtime";

/** The lines a step can carry, in the order the card draws them. */
export const LINES = ["look", "means", "affects", "press"];
const LINE_COPY = {
    look: ["eye", "lpLook"],
    means: ["lightbulb", "lpMeans"],
    affects: ["git-branch", "lpAffects"],
    press: ["target", "lpPress"],
};
/** What a country variant may change. */
export const VARIANT_FIELDS = ["look", "means", "affects", "press", "tip"];

/** The country a lesson speaks to: the open scheme's, else the company's. */
export function pickCountry(company, scheme) {
    const c = String(scheme || company || "").trim().toUpperCase();
    return c || "";
}

/** The variant a step shows for `country`: its own, else the generic one. */
export function pickVariant(step, country) {
    const v = (step && step.variants) || null;
    if (!v) {
        return null;
    }
    return v[country] || v.generic || null;
}

/** One step as the card reads it, with the country's lines laid over the
 *  shared ones. Pairs stay pairs: `ui.text` picks the language at render. */
export function stepView(step, country) {
    const s = step || {};
    const v = pickVariant(s, country) || {};
    const out = {
        kicker: s.kicker || "",
        title: s.title || "",
        tip: v.tip || s.tip || "",
        consequence: s.consequence || "",
        uses: s.uses || [],
        field: s.field || "",
        anchor: s.anchor || "",
        legacy: false,
    };
    for (const line of LINES) {
        out[line] = v[line] || s[line] || "";
    }
    if (!out.look && !out.means && s.body) {
        // Not rewritten yet: the paragraph is the "It means" line.
        out.means = s.body;
        out.legacy = true;
    }
    return out;
}

/** A practice-copy anchor: drawn only by the replica, never on a real screen. */
export function isPracticeAnchor(anchor) {
    return String(anchor || "").startsWith("rep-");
}

/**
 * Where a step plays. `ctx`:
 *   screen     the content screen the step stands on (or null)
 *   reachable  `places.reachable(screen)`: true / false / null (unknown)
 *   current    the screen key on show now
 * → {where: "panel"|"replica", reason: ""|"practice"|"unreachable", navigate}
 */
export function placeFor(step, ctx = {}) {
    const anchor = (step && step.anchor) || "";
    if (isPracticeAnchor(anchor)) {
        return { where: "replica", reason: "practice", navigate: false };
    }
    if (ctx.reachable === false) {
        return { where: "replica", reason: "unreachable", navigate: false };
    }
    const key = step && step.screen;
    return { where: "panel", reason: "", navigate: !!key && key !== ctx.current };
}

// ------------------------------------------------------------------ the card
function line(key, value, ui, extra) {
    if (!value && !extra) {
        return "";
    }
    const [icon, label] = LINE_COPY[key];
    const raw = key === "means" && ui.legacy;
    // A legacy body carries its own inline <b> (authored, trusted content —
    // the Journey has always drawn it raw through the glossary pass).
    const text = value ? (raw && ui.html ? ui.html(value) : esc(ui.text(value))) : "";
    return `<div class="lrn-lp-line ${key}"><dt>${ic(icon)}<span>${esc(T(label))}</span></dt>
        <dd>${text ? `<p>${text}</p>` : ""}${extra || ""}</dd></div>`;
}

const NOTE_COPY = {
    practice: ["flask", "lpPracticeNote"],
    unreachable: ["lock", "lpUnreachableNote"],
    loading: ["hourglass", "lpLoading"],
    nothere: ["info", "lpNotHere"],
};

function noteHTML(note) {
    if (!note || !NOTE_COPY[note.kind]) {
        return "";
    }
    const [icon, key] = NOTE_COPY[note.kind];
    const retry = note.kind === "loading"
        ? `<button type="button" class="lrn-btn sm ghost" data-act="c-lpretry">${ic("rotate-ccw")}${esc(T("retry"))}</button>` : "";
    const practice = note.kind === "practice" || note.kind === "unreachable"
        ? `<button type="button" class="lrn-btn sm" data-act="c-lppractice">${ic("flask")}${esc(T("lpOpenPractice"))}</button>` : "";
    return `<div class="lrn-lp-note ${note.kind}" role="status">${ic(icon)}<span>${esc(T(key))}</span>${retry}${practice}</div>`;
}

/**
 * The step card that replaces the Understand section's body. `ui`:
 *   index, total     where we are (0-based index)
 *   text(pair)       the reader's language; html(pair) for a legacy body
 *   note             {kind: practice|unreachable|loading|nothere} or null
 */
/** The four lines alone (+ uses), as a `<dl>` — shared by the panel card and
 *  the practice copy's card in the Journey, so the two never disagree. */
export function linesHTML(view, ui) {
    const v = view || {};
    const uses = (v.uses || []).length
        ? `<div class="lrn-lp-uses">${v.uses.map((u) => `<span class="lrn-fc-chip use">${esc(ui.text(u))}</span>`).join("")}</div>`
        : "";
    return `<dl class="lrn-lp-lines">${[
        line("look", v.look, ui),
        line("means", v.means, Object.assign({}, ui, { legacy: v.legacy })),
        line("affects", v.affects, ui, uses),
        line("press", v.press, ui),
    ].join("")}</dl>`;
}

/** LEARNREV P5b — the reference a step's thumbs send through the field
 *  cards' seam (`learn.guide.rpc_feedback`): `lesson.<key>.<index as
 *  shipped>` or `walk.<scenario>.<step key>`. "" when there is nothing to
 *  rate (no key), so a card without one simply draws no thumbs. */
export function stepRef(kind, holderKey, which) {
    if (!holderKey || which === undefined || which === null || which === "" || which < 0) {
        return "";
    }
    return `${kind === "walk" ? "walk" : "lesson"}.${holderKey}.${which}`;
}

/** The thumbs under a lesson step or a walkthrough card: the field card's
 *  own buttons and words ("Was this helpful?"), so one look everywhere.
 *  `rated`: "up" | "down" | "" — a rated step shows its choice and thanks,
 *  and cannot be rated twice in the same play. `act` is the host's action. */
export function rateHTML(ref, rated, act = "c-lprate") {
    if (!ref) {
        return "";
    }
    const btn = (v, icon, label) => {
        const on = rated === v;
        // The space before aria-label sits in its own interpolation (the
        // minifier strips whitespace straight after a `}`).
        return `<button type="button" class="lrn-fbbtn${on ? " on" : ""}" data-act="${act}" data-v="${v}" data-key="${esc(ref)}"${rated ? " disabled" : ""}${SP}aria-label="${esc(T(label))}" title="${esc(T(label))}" aria-pressed="${on ? "true" : "false"}">${ic(icon)}</button>`;
    };
    return `<div class="lrn-lp-rate"><span class="lrn-fb" role="group" aria-label="${esc(T("gHelpful"))}">
        <span class="lrn-lp-ratel">${esc(T("gHelpful"))}</span>${btn("up", "thumbs-up", "gHelpfulYes")}${btn("down", "thumbs-down", "gHelpfulNo")}${rated
            ? `<span class="lrn-fbthanks" role="status">${esc(T("gThanks"))}</span>` : ""}</span></div>`;
}

export function lessonCardHTML(view, ui) {
    const v = view || {};
    const n = (ui.index || 0) + 1;
    const total = ui.total || 1;
    const pct = Math.round((n / total) * 100);
    const lines = linesHTML(v, ui);
    const tip = v.tip ? `<div class="lrn-lp-tip">${ic("info")}<span>${esc(ui.text(v.tip))}</span></div>` : "";
    const conseq = v.consequence
        ? `<div class="lrn-lp-conseq">${ic("alert-triangle")}<span>${esc(ui.text(v.consequence))}</span></div>` : "";
    const last = n >= total;
    return `<div class="lrn-lp" data-lp="1" aria-live="polite">
        <div class="lrn-lp-top">
            <span class="lrn-lp-kicker">${esc(ui.text(v.kicker) || T("lpLesson"))}</span>
            <span class="lrn-lp-count">${esc(T("step"))}${SP}${n}${SP}${esc(T("of"))}${SP}${total}</span>
        </div>
        <div class="lrn-lp-meter" aria-hidden="true"><i style="width:${pct}%"></i></div>
        <h4 class="lrn-lp-title">${esc(ui.text(v.title))}</h4>
        ${lines}
        ${noteHTML(ui.note)}${tip}${conseq}
        ${rateHTML(ui.rateRef || "", ui.rated || "")}
        <div class="lrn-lp-foot">
            <button type="button" class="lrn-btn sm" data-act="c-lpback"${ui.index ? "" : " disabled"}>${ic("chevron-left")}${esc(T("back"))}</button>
            <button type="button" class="lrn-btn sm pri" data-act="c-lpnext">${esc(last ? T("check") : T("next"))}${ic("chevron-right")}</button>
            <button type="button" class="lrn-btn sm ghost" data-act="c-lpleave">${ic("x")}${esc(T("exit"))}</button>
        </div>
    </div>`;
}

/** The lesson's quiz, in the panel. `ui`: {answered (index|null), text}. */
export function quizHTML(quiz, ui) {
    if (!quiz) {
        return `<div class="lrn-lp lrn-lp-quiz"><h4 class="lrn-lp-title">${esc(T("finish"))}</h4>
            <div class="lrn-lp-foot"><button type="button" class="lrn-btn sm pri" data-act="c-lpfinish">${ic("check")}${esc(T("finish"))}</button></div></div>`;
    }
    const chosen = ui.answered === undefined ? null : ui.answered;
    const opts = (quiz.options || []).map((o, i) => {
        const picked = chosen === i;
        const cls = picked ? (o.correct ? "right" : "wrong") : "";
        return `<button type="button" class="lrn-opt ${cls}" data-act="c-lpans" data-i="${i}"${chosen !== null ? " disabled" : ""}>
            <span class="lrn-optmark">${picked ? ic(o.correct ? "check" : "rotate-ccw") : String.fromCharCode(65 + i)}</span>
            <span>${esc(ui.text(o.label))}</span></button>
            ${picked ? `<div class="lrn-explain ${o.correct ? "ok" : "warn"}"><p>${esc(ui.text(o.feedback))}</p></div>` : ""}`;
    }).join("");
    const right = chosen !== null && !!(quiz.options[chosen] || {}).correct;
    const foot = chosen === null
        ? `<button type="button" class="lrn-btn sm ghost" data-act="c-lpback">${ic("chevron-left")}${esc(T("back"))}</button>`
        : (right
            ? `<button type="button" class="lrn-btn sm pri" data-act="c-lpfinish">${ic("check")}${esc(T("finish"))}</button>`
            : `<button type="button" class="lrn-btn sm pri" data-act="c-lpretryq">${ic("rotate-ccw")}${esc(T("tryAgain"))}</button>`);
    return `<div class="lrn-lp lrn-lp-quiz" data-lp="1" aria-live="polite">
        <div class="lrn-lp-top"><span class="lrn-lp-kicker">${ic("help-circle")}${esc(T("check"))}</span></div>
        <h4 class="lrn-lp-title">${esc(ui.text(quiz.prompt))}</h4>
        <div class="lrn-opts">${opts}</div>
        <div class="lrn-lp-foot">${foot}
            <button type="button" class="lrn-btn sm ghost" data-act="c-lpleave">${ic("x")}${esc(T("exit"))}</button></div>
    </div>`;
}

/** The closing card: the station is done. */
export function doneHTML(name, ui) {
    return `<div class="lrn-lp lrn-lp-done" data-lp="1" role="status">
        <div class="lrn-lp-top"><span class="lrn-lp-kicker">${ic("check-circle")}${esc(T("lpDone"))}</span></div>
        <h4 class="lrn-lp-title">${esc(ui.text(name))}</h4>
        <p class="lrn-lp-p">${esc(T("lpDoneBody"))}</p>
        <div class="lrn-lp-foot"><button type="button" class="lrn-btn sm pri" data-act="c-lpleave">${ic("check")}${esc(T("lpClose"))}</button></div>
    </div>`;
}
