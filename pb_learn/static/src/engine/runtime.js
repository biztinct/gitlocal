/** @odoo-module **/
/* =============================================================================
   Payobook Learn — runtime

   One mutable object the whole engine reads: the chosen language, the motion
   preference, the resolved tenant tokens and the chrome strings that arrived
   in the bundle. The client action owns it; the engine only reads it.

   Why not OWL reactivity: these values change about twice per session (a
   language toggle, a motion toggle) and are read thousands of times per render
   by string-building helpers that are not components. A plain object is the
   honest shape; the component re-renders itself when it changes one.

   ---------------------------------------------------------------------------
   MINIFIER HAZARD — applies to every file in this module that builds HTML
   ---------------------------------------------------------------------------
   Odoo's JS minifier deletes whitespace that immediately follows a `}`, and it
   does not except template literals. So an interpolation followed by a plain
   space — fullLesson, then space, then a middot, then the minutes — ships to
   the browser as "Full lesson· 7min". MEASURED on UAT by diffing
   web.assets_web.js against web.assets_web.min.js — the non-minified bundle
   has the spaces and the minified one does not, so it is invisible in dev.

   The rule: never leave a literal space directly after a closing `}`. Put it
   inside its own interpolation instead:

       `${esc(T("fullLesson"))}${SP}· ${mins}${SP}${esc(T("min"))}`

   SP is a bare identifier on purpose — see its definition below. Writing the
   space as a quoted literal inside the braces fixes this bug and causes a
   worse one.

   tests/test_assets.py enforces both, because this is exactly the kind of
   thing that comes straight back the next time someone writes a sentence.
   ========================================================================== */

export const RT = {
    lang: "en",          // "en" | "vi" — switchable live, never a page reload
    motion: "auto",      // "auto" | "reduced"
    tokens: {},          // {slot: {en, vi}} resolved for THIS company
    chrome: {},          // {dotted.key: {en, vi}}
};

/* Tenant slots fill NAMED SLOTS in prose. An unknown key renders as the key
   itself — visible on purpose, because a silently empty gap in a lesson is a
   sentence that now means something else. */
const TOKEN_RE = /\{\{([a-zA-Z][a-zA-Z0-9_]*)\}\}/g;

function tokenValue(key) {
    const slot = RT.tokens[key];
    if (!slot) {
        return "{{" + key + "}}";
    }
    return slot[RT.lang] || slot.en || "{{" + key + "}}";
}

/** Every translatable value passes through here, so token resolution is free
 *  everywhere — lesson steps, checks, screen chrome. Accepts either a
 *  {en, vi} pair (the bundle's shape and the fixture's) or a plain string. */
export function tx(o) {
    if (o === null || o === undefined) {
        return "";
    }
    const s = typeof o === "string" ? o : (o[RT.lang] || o.en || "");
    return s.indexOf("{{") === -1 ? s : s.replace(TOKEN_RE, (_, k) => tokenValue(k));
}

/** A chrome string by dotted key, e.g. T("lines.payrun"). Falls back to the key
 *  so a missing string is diagnosable rather than an empty button. */
export function T(key) {
    const v = RT.chrome[key];
    return v ? tx(v) : key;
}

export function reduced() {
    return RT.motion === "reduced" ||
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/* ------------------------------------------------------------------ escaping */
const ENT = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" };

/** For any value that reaches innerHTML as TEXT. Lesson bodies deliberately
 *  carry inline <b>/<i> and are inserted raw; everything else goes through
 *  here. */
export function esc(s) {
    return String(s === null || s === undefined ? "" : s).replace(/[&<>"]/g, (m) => ENT[m]);
}

export function ic(name, cls) {
    return `<svg class="lrn-ic ${cls || ""}" aria-hidden="true"><use href="#lrn-i-${name}"/></svg>`;
}

/* ------------------------------------------------------- locale-correct numbers
   Vietnamese groups thousands with "." and takes "," as the decimal mark. A
   tutorial that prints 224,000 to a Vietnamese reader has taught them to
   misread every figure on the real Dashboard. */
export function N(n) {
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, RT.lang === "vi" ? "." : ",");
}

export function P(n) {
    return (RT.lang === "vi" ? n.toFixed(1).replace(".", ",") : n.toFixed(1)) + "%";
}

export function M(n) {
    return N(Math.round(n)) + " ₫";
}

/** Vietnamese names put the given name last, so that is the initial to show. */
export function initial(name) {
    const parts = tx(name).trim().split(/\s+/);
    return ((parts[parts.length - 1] || "?")[0] || "?").toUpperCase();
}

/** A literal space, safe to interpolate.
 *
 *  A quoted space in the braces also survives brace-stripping — but the QUOTE
 *  makes rjsmin lose track of the enclosing template literal, and it then
 *  strips whitespace in the REST of that string as if it were code:
 *  "13 visits across 4 people. The one" shipped as "…people.The one".
 *  A bare identifier has no quote, so the parser stays oriented. */
export const SP = " ";

export const $ = (sel, root) => (root || document).querySelector(sel);
export const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
