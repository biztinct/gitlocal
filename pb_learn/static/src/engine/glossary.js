/** @odoo-module **/
/* =============================================================================
   The glossary hovercard — LEARNOS Phase 2.

   The product promise is that a complete beginner can learn payroll from the
   app. Short sentences and plain words carry most of that, and the rest is the
   handful of terms a payroll desk genuinely cannot do without: BHXH, the
   insurance base, a gate, a retro line. Those get taught inline the first time
   a lesson uses them, and every later occurrence gets a card.

   TWO PIECES, and only the first one is interesting:

     glossify(html, lang)   a PURE STRING TRANSFORM. Takes an already-safe
                            authored body, returns the same body with known
                            terms wrapped in
                            <span class="lrn-gloss" data-gloss="key">.
                            No DOM, no window — which is what makes it
                            testable in tools/replay_tests.py rather than only
                            in a browser.
     installGlossary()      ONE delegated listener and ONE card element for the
                            whole page, positioned on hover or tap.

   WHAT IT MUST NOT DO, and why each one is a rule rather than a preference:

     * never wrap inside <code>, <a>, <kbd> or <samp>. A code sample that says
       `net` means the component named NET, and turning it into a definition of
       take-home pay is teaching the wrong thing. An anchor already has a
       destination; a second one inside it is a control nobody can hit.
     * never touch ATTRIBUTE text. `title="Approve the pay run"` would become
       markup inside an attribute, which is how a tooltip becomes a tag. The
       walk below only ever rewrites the text BETWEEN tags, so this is
       structural rather than a check.
     * at most ONE card per term per rendered block. A body that says "payslip"
       six times with six dotted underlines is noise, and noise is what makes
       somebody stop reading the underlines that matter.
     * longest match first. "insurance base" is its own entry and must not be
       eaten by "insurance"; the table is emitted longest-first by the
       generator for exactly this reason.
     * language-aware. The EN render matches EN spellings, the VI render
       matches VI ones. A Vietnamese reader meeting an English trigger word
       is a card that opens on a term their sentence does not contain.

   THE MATCH TABLE IS AUTHORED, NOT DERIVED. It comes from `aliases` on each
   GLOSSARY entry in docs/tutorial_poc/author/data.js, and the SAME table is
   what tools/jargon.py refuses to build without. A term the gate demands and
   the card cannot reach is a definition nobody reads, so the two are not
   allowed to be two lists.
   ========================================================================== */
import { RT, tx, txHtml, esc, ic } from "./runtime";

/* {lang: [[phrase, key], ...]} longest phrase first, and {key: entry}. */
const INDEX = { en: [], vi: [] };
let BY_KEY = {};
let RE = { en: null, vi: null };

/* Tags whose CONTENT is never glossed. Closing one pops the skip. */
const OPAQUE = new Set(["code", "a", "kbd", "samp", "script", "style", "pre"]);

/* A phrase's spaces match any run of whitespace or hyphens, so "payroll-ready"
   and "payroll ready" are one entry. The boundaries are lookarounds on the
   letter/digit class rather than \b: `payroll-ready` starts and ends on word
   characters but `-` is not one, and `net` must not fire inside `network`. */
const BOUND_L = "(?<![0-9A-Za-zÀ-ỹ])";
const BOUND_R = "(?![0-9A-Za-zÀ-ỹ])";

function escapeRe(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function buildRe(pairs) {
    if (!pairs.length) {
        return null;
    }
    // Alternation in source order, and the source order is longest-first, so
    // at any given start position the longest listed phrase wins.
    const body = pairs.map(([p]) => escapeRe(p).replace(/\\?\s+/g, "[\\s-]+")).join("|");
    return new RegExp(BOUND_L + "(" + body + ")" + BOUND_R, "gi");
}

/** Called once, from whichever surface loads the content plane first. */
export function setGlossary(entries) {
    INDEX.en = [];
    INDEX.vi = [];
    BY_KEY = {};
    for (const e of entries || []) {
        BY_KEY[e.key] = e;
        for (const lang of ["en", "vi"]) {
            for (const phrase of (e.match && e.match[lang]) || []) {
                INDEX[lang].push([phrase, e.key]);
            }
        }
    }
    // Defensive: the generator already sorts, and a hand-edited asset would
    // otherwise let a short phrase eat a long one silently.
    for (const lang of ["en", "vi"]) {
        INDEX[lang].sort((a, b) => b[0].length - a[0].length || a[0].localeCompare(b[0]));
        RE[lang] = buildRe(INDEX[lang]);
    }
}

export function glossaryEntry(key) {
    return BY_KEY[key] || null;
}

function keyFor(phrase, lang) {
    const want = phrase.toLowerCase().replace(/[\s-]+/g, " ");
    for (const [p, k] of INDEX[lang]) {
        if (p.replace(/[\s-]+/g, " ") === want) {
            return k;
        }
    }
    return null;
}

/** The pure pass. `html` is authored, trusted markup; the return value adds
 *  only <span> wrappers around text that was already there. */
export function glossify(html, lang) {
    const L = lang === "vi" ? "vi" : "en";
    if (!html || !RE[L]) {
        return html || "";
    }
    // Idempotence guard. Running twice would wrap the term inside its own
    // span; cheap to prevent, and impossible to notice if it ever happened.
    if (html.indexOf("data-gloss=") !== -1) {
        return html;
    }
    const used = new Set();

    const wrap = (text) => {
        if (!text) {
            return text;
        }
        return text.replace(RE[L], (match) => {
            const key = keyFor(match, L);
            if (!key || used.has(key)) {
                return match;
            }
            used.add(key);
            return `<span class="lrn-gloss" data-gloss="${esc(key)}" tabindex="0"` +
                ` role="term">${match}</span>`;
        });
    };

    const out = [];
    const tagRe = /<[^>]*>/g;
    let last = 0;
    let skip = 0;
    let m;
    while ((m = tagRe.exec(html)) !== null) {
        const text = html.slice(last, m.index);
        out.push(skip ? text : wrap(text));
        const tag = m[0];
        out.push(tag);
        const named = /^<(\/?)([a-zA-Z][a-zA-Z0-9]*)/.exec(tag);
        if (named && OPAQUE.has(named[2].toLowerCase())) {
            if (named[1] === "/") {
                skip = Math.max(0, skip - 1);
            } else if (!/\/>$/.test(tag)) {
                skip += 1;
            }
        }
        last = m.index + tag.length;
    }
    const tail = html.slice(last);
    out.push(skip ? tail : wrap(tail));
    return out.join("");
}

/* ------------------------------------------------------------------ the card
   ONE element and ONE listener for the page, in the Coach's visual language.
   A card per span would be a hundred nodes in a lesson body; a listener per
   span would be a hundred listeners that have to be torn down on every
   re-render, and the Journey re-renders on every step. */
let cardEl = null;
let installed = false;

function ensureCard() {
    if (cardEl && cardEl.isConnected) {
        return cardEl;
    }
    cardEl = document.createElement("div");
    cardEl.className = "lrn-glosscard";
    /* `role="note"`, not `tooltip`. A tooltip is a short label for the thing
       it is attached to and is not meant to contain structure; this card has a
       heading and a paragraph. The trigger is `role="term"` rather than
       `button` for the matching reason — it reveals an explanation of itself,
       it does not perform an action, and calling it a button told a screen
       reader to expect something to happen. */
    cardEl.setAttribute("role", "note");
    cardEl.hidden = true;
    document.body.appendChild(cardEl);
    return cardEl;
}

function hideCard() {
    if (cardEl) {
        cardEl.hidden = true;
    }
}

/** The card's inner HTML for one entry. Exported so the replay harness can
 *  assert on it without a DOM. */
export function glossCardHTML(key) {
    const e = BY_KEY[key];
    if (!e) {
        return "";
    }
    /* NO "More" CONTROL. The definition is two sentences and the card shows
       both of them, so a button offering to take somebody somewhere that says
       the same thing is an offer made and not kept — the failure this module's
       honesty rules exist to prevent. If a term ever outgrows the card, the
       answer is a lesson link on the ENTRY, not a button that is always there
       and usually pointless. */
    return `<div class="lrn-glossterm">${ic("book-open")}<span>${esc(tx(e.term))}</span></div>
        <p class="lrn-glossdef">${esc(tx(e.definition))}</p>`;
}

function showCard(span) {
    const key = span.getAttribute("data-gloss");
    const html = glossCardHTML(key);
    if (!html) {
        return;
    }
    const el = ensureCard();
    el.innerHTML = html;
    el.hidden = false;
    // getBoundingClientRect, never offsetParent: the card is position:fixed and
    // offsetParent is null for fixed elements — the standing engine gotcha.
    const r = span.getBoundingClientRect();
    const w = el.offsetWidth || 280;
    const h = el.offsetHeight || 120;
    let left = r.left + r.width / 2 - w / 2;
    left = Math.max(8, Math.min(left, window.innerWidth - w - 8));
    const above = r.top > h + 12;
    el.style.left = `${Math.round(left)}px`;
    el.style.top = `${Math.round(above ? r.top - h - 8 : r.bottom + 8)}px`;
    el.classList.toggle("below", !above);
}

/** Tear the card down. Called from a component's onWillUnmount: the card is
 *  appended to document.body rather than into the component's own tree, so
 *  navigating away with one open would otherwise leave it floating over
 *  whatever screen came next. */
export function closeGlossary() {
    hideCard();
}

/** Idempotent. Every surface calls it; the first one wins. */
export function installGlossary() {
    if (installed) {
        return;
    }
    installed = true;
    const over = (ev) => {
        const span = ev.target.closest && ev.target.closest(".lrn-gloss");
        if (span) {
            showCard(span);
        } else if (!(ev.target.closest && ev.target.closest(".lrn-glosscard"))) {
            hideCard();
        }
    };
    document.addEventListener("mouseover", over, true);
    document.addEventListener("focusin", over, true);
    // Tap: the same card, and a second tap on the same term closes it. Touch
    // has no hover, so without this the card would be unreachable on a phone —
    // which is where somebody reads a lesson between shifts.
    document.addEventListener("click", (ev) => {
        const span = ev.target.closest && ev.target.closest(".lrn-gloss");
        if (span) {
            ev.preventDefault();
            if (!cardEl || cardEl.hidden || cardEl.dataset.key !== span.dataset.gloss) {
                showCard(span);
                cardEl.dataset.key = span.dataset.gloss;
            } else {
                hideCard();
            }
        } else if (!(ev.target.closest && ev.target.closest(".lrn-glosscard"))) {
            hideCard();
        }
    }, true);
    document.addEventListener("keydown", (ev) => {
        if (ev.key === "Escape") {
            hideCard();
        }
    }, true);
    window.addEventListener("scroll", hideCard, true);
}

/** THE ONE RAW-HTML ENTRY POINT. Gloss an authored body in the current
 *  language, with every {{token}} value escaped on the way in.
 *
 *  Two jobs in one call, deliberately: the eight sites in this module that
 *  insert an authored body raw all call `gtx`, so "is every raw position
 *  token-safe?" is answered by grepping for `gtx(` rather than by reading
 *  four files and hoping. `tx()` stays raw for the ~400 `esc(tx(...))`
 *  positions, which would otherwise double-escape.
 *
 *  Order matters and is not interchangeable: the token is escaped BEFORE the
 *  wrapper pass runs, so a tag in a tenant slot can never become a text node
 *  for the glossary to wrap, and can never split a body's markup. */
export function gtx(value) {
    return glossify(txHtml(value), RT.lang);
}
