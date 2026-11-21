/** @odoo-module **/
/* =============================================================================
   LEARNREV P2 — the (i) beside a column, and the card it opens.

   NO PRODUCT TEMPLATE IMPORTS THIS. The (i) is laid at run time: for every
   field card whose manifest names an `anchor`, find the anchor element
   (`[data-coach="…"]`), then the first header inside it whose words are the
   card's column, and append one small button. Idempotent (a header that
   already holds its button is left alone), and re-run after the screen
   redraws — OWL replaces a table's header when its rows reload.

   THE CARD is one element on `document.body`, placed beside the button the
   way the glossary hovercard is (engine/glossary.js), and it obeys the same
   rules: it opens on click (not hover), one card at a time, a click outside
   closes it, Escape closes it FIRST and swallows the key from every sibling
   listener (`stopImmediatePropagation`, test_assets test_06b), and a
   glossary card and a field card never show together.

   Keyboard: the (i) is a real <button>; focus returns to it on Escape.
   ========================================================================== */
import { T, esc, ic, SP, reduced } from "../engine/runtime";
import { closeGlossary } from "../engine/glossary";
import { fieldCardHTML } from "./guide_panel";

/** Where a column's words can sit, in the cockpits the manifests cover. */
export const HEADER_SEL = "th, label, .pbd-fig-l, .pbim-gl-l, .pbr-lbl, .pbd-close-lab, .psr-bk-h, h2, h3, h4, span";
const CARD_W = 360;
const DEBOUNCE_MS = 120;

const QUOTE = String.fromCharCode(34);
const ENT = { "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": QUOTE, "&#39;": "'",
              "&#x27;": "'", "&nbsp;": " " };

/** What a person reads: tags out (each one a space), entities resolved,
 *  curly apostrophes straight, whitespace collapsed — the truth gate's own
 *  `norm()` (tests/guide_truth.py). */
export function norm(s) {
    return String(s === null || s === undefined ? "" : s)
        .replace(/<[^>]+>/g, " ")
        .replace(/&(amp|lt|gt|quot|#39|#x27|nbsp);/g, (m) => ENT[m] || m)
        .replace(/’/g, "'")
        .replace(/\s+/g, " ")
        .trim();
}

/* A label that wraps its own control ("Value type<select>…</select>") reads
   as its own words: a select's options, a button (an (i) already laid, a
   Change link) and a text box are not the header's text. */
const CONTROL_RE = /<(select|button|textarea)\b[\s\S]*?<\/\1>/gi;

/** A header's words, ignoring any (i) already inside it. */
export function headerText(el) {
    return norm(String((el && el.innerHTML) || "").replace(CONTROL_RE, " "));
}

/** The first header under `root` that reads exactly `column` (any of the
 *  given spellings — the English and the Vietnamese), or null. */
export function findHeader(root, column) {
    const wants = (Array.isArray(column) ? column : [column])
        .map((c) => norm(c).toLowerCase()).filter(Boolean);
    if (!root || !wants.length || !root.querySelectorAll) {
        return null;
    }
    for (const el of Array.from(root.querySelectorAll(HEADER_SEL))) {
        if (el.closest && el.closest(".lrn-coachhost, .lrn-fieldcard")) {
            continue;
        }
        if (wants.includes(headerText(el).toLowerCase())) {
            return el;
        }
    }
    return null;
}

function spellings(card) {
    const out = [card.column];
    for (const c of card.columns || []) {
        if (c && !out.includes(c)) {
            out.push(c);
        }
    }
    return out;
}

/**
 * Lay one (i) per field card that has an anchor and a visible header.
 * Returns {added, present, missing: [keys with no header on screen]}.
 * `onOpen(key, button)` runs on a press; the press never reaches the header
 * (a sortable column must not sort).
 */
export function injectInfo(doc, fields, onOpen) {
    const out = { added: 0, present: 0, missing: [] };
    for (const card of fields || []) {
        if (!card || !card.anchor || !card.key) {
            continue;
        }
        let header = null;
        for (const anchor of Array.from(doc.querySelectorAll(`[data-coach="${card.anchor}"]`))) {
            header = findHeader(anchor, spellings(card));
            if (header) {
                break;
            }
        }
        if (!header) {
            out.missing.push(card.key);
            continue;
        }
        if (header.querySelector(`.lrn-i[data-learn-field="${card.key}"]`)) {
            out.present += 1;
            continue;
        }
        // A label inside a clickable tile (a KPI button) cannot hold a second
        // <button>: there the (i) is a span with the button role, reachable
        // by Tab and pressed with Enter or Space.
        const nested = !!(header.closest && header.closest("button, a, [role='button']"));
        const btn = doc.createElement(nested ? "span" : "button");
        if (nested) {
            btn.setAttribute("role", "button");
            btn.setAttribute("tabindex", "0");
            btn.addEventListener("keydown", (ev) => {
                if (ev.key === "Enter" || ev.key === " ") {
                    ev.preventDefault();
                    ev.stopPropagation();
                    onOpen(card.key, btn);
                }
            });
        } else {
            btn.type = "button";
        }
        btn.className = "lrn-i";
        btn.setAttribute("data-learn-field", card.key);
        const label = `${T("explainField")}${SP}${card.column}`;
        btn.setAttribute("aria-label", label);
        btn.setAttribute("title", label);
        btn.innerHTML = ic("info");
        const press = (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            onOpen(card.key, btn);
        };
        btn.addEventListener("click", press);
        // A sortable header listens for the press on its own element; the
        // button keeps the whole gesture to itself.
        btn.addEventListener("pointerdown", (ev) => ev.stopPropagation());
        header.appendChild(btn);
        out.added += 1;
    }
    return out;
}

/** Take every (i) off the page (the switch went off, or another screen). */
export function removeInfo(doc, keep) {
    for (const el of Array.from(doc.querySelectorAll(".lrn-i[data-learn-field]"))) {
        if (!keep || !keep.includes(el.getAttribute("data-learn-field"))) {
            el.remove();
        }
    }
}

/**
 * Keeps the (i) on screen while OWL redraws: one MutationObserver on the
 * action manager, debounced, that re-runs the (idempotent) injection.
 */
export class InfoLayer {
    constructor(doc, getFields, onOpen) {
        this.doc = doc;
        this.getFields = getFields;
        this.onOpen = onOpen;
        this.timer = null;
        this.observer = null;
        this.last = { added: 0, present: 0, missing: [] };
    }

    run() {
        const fields = this.getFields() || [];
        removeInfo(this.doc, fields.map((f) => f.key));
        this.last = injectInfo(this.doc, fields, this.onOpen);
        return this.last;
    }

    start() {
        this.run();
        if (this.observer || typeof MutationObserver === "undefined") {
            return;
        }
        const root = this.doc.querySelector(".o_action_manager") || this.doc.body;
        if (!root) {
            return;
        }
        this.observer = new MutationObserver(() => {
            clearTimeout(this.timer);
            this.timer = setTimeout(() => this.run(), DEBOUNCE_MS);
        });
        this.observer.observe(root, { childList: true, subtree: true });
    }

    stop() {
        clearTimeout(this.timer);
        if (this.observer) {
            this.observer.disconnect();
            this.observer = null;
        }
        removeInfo(this.doc);
    }
}

// ---------------------------------------------------------------- the card
let cardEl = null;
let cardBtn = null;
let installed = false;
let handler = null;

function ensureCard() {
    if (cardEl && cardEl.isConnected) {
        return cardEl;
    }
    cardEl = document.createElement("div");
    cardEl.className = "lrn-fieldcard";
    cardEl.setAttribute("role", "dialog");
    cardEl.hidden = true;
    document.body.appendChild(cardEl);
    return cardEl;
}

/** Whether a field card is showing (the drawer's Escape ladder asks). */
export function fieldCardOpen() {
    return !!(cardEl && !cardEl.hidden);
}

/** Close the card; true when one was open. Focus goes back to its (i). */
export function closeFieldCard(refocus) {
    if (!fieldCardOpen()) {
        return false;
    }
    cardEl.hidden = true;
    cardEl.classList.remove("in");
    const btn = cardBtn;
    cardBtn = null;
    if (refocus && btn && btn.isConnected) {
        btn.focus();
    }
    return true;
}

/** The width the dock takes on the right, or 0. */
function dockWidth() {
    if (!document.body.classList.contains("lrn-docked") || window.innerWidth < 1280) {
        return 0;
    }
    const el = document.querySelector(".lrn-drawer");
    return el ? el.getBoundingClientRect().width : 420;
}

function place(el, btn) {
    const r = btn.getBoundingClientRect();
    const right = window.innerWidth - dockWidth() - 8;
    const w = Math.min(CARD_W, right - 8);
    el.style.width = `${Math.round(w)}px`;
    const h = el.offsetHeight || 320;
    const vh = window.innerHeight;
    // Below, else above, else beside (right, then left) — never on top of
    // the (i) itself, which a plain clamp did for a tall card (B3 walk).
    let left = Math.max(8, Math.min(r.left + r.width / 2 - w / 2, right - w));
    let top;
    let side = "below";
    if (vh - r.bottom > h + 16) {
        top = r.bottom + 8;
    } else if (r.top > h + 16) {
        top = r.top - h - 8;
        side = "above";
    } else if (r.right + 12 + w < right) {
        left = r.right + 12;
        top = r.top + r.height / 2 - h / 2;
        side = "beside";
    } else if (r.left - 12 - w > 8) {
        left = r.left - 12 - w;
        top = r.top + r.height / 2 - h / 2;
        side = "beside";
    } else {
        top = r.bottom + 8;
    }
    top = Math.max(8, Math.min(top, vh - Math.min(h, vh - 16) - 8));
    el.style.left = `${Math.round(left)}px`;
    el.style.top = `${Math.round(top)}px`;
    el.classList.toggle("above", side === "above");
}

/**
 * Open the card for `card` beside `btn`. `opts.watch`: a walkthrough step
 * points at this field's anchor. `opts.onAction(kind, key)` receives the
 * footer's presses: "guide", "watch", "up", "down".
 */
export function openFieldCard(btn, card, opts = {}) {
    install();
    closeGlossary();
    const el = ensureCard();
    if (fieldCardOpen() && el.dataset.key === card.key && cardBtn === btn) {
        closeFieldCard(true);
        return;
    }
    handler = opts.onAction || null;
    el.dataset.key = card.key;
    el.setAttribute("aria-label", card.column || "");
    el.innerHTML = `<button type="button" class="lrn-fc-x" data-fc="close" aria-label="${esc(T("close"))}">${ic("x")}</button>
        ${fieldCardHTML(card, { footer: true, watch: !!opts.watch })}`;
    el.hidden = false;
    cardBtn = btn;
    place(el, btn);
    el.classList.remove("in");
    if (!reduced()) {
        // Reflow, then the 160 ms fade-up (coach.scss lrn-fc-in).
        void el.offsetWidth;
    }
    el.classList.add("in");
}

/** The card's "and N more": the rest of the chips, in place. Works in the
 *  floating card and in the Fields section alike. */
function expandMore(btn) {
    const box = btn.parentElement;
    for (const chip of Array.from(box.querySelectorAll(".lrn-fc-chip[hidden]"))) {
        chip.hidden = false;
    }
    btn.remove();
}

function install() {
    if (installed) {
        return;
    }
    installed = true;
    document.addEventListener("click", (ev) => {
        const t = ev.target;
        const more = t.closest && t.closest("[data-fcmore]");
        if (more) {
            ev.preventDefault();
            expandMore(more);
            return;
        }
        if (!fieldCardOpen()) {
            return;
        }
        const inCard = t.closest && t.closest(".lrn-fieldcard");
        if (inCard) {
            const act = t.closest("[data-fc]");
            if (!act) {
                return;
            }
            ev.preventDefault();
            const kind = act.getAttribute("data-fc");
            const key = cardEl.dataset.key;
            if (kind === "close") {
                closeFieldCard(true);
                return;
            }
            if (handler) {
                handler(kind, key, act);
            }
            if (kind === "guide" || kind === "watch") {
                closeFieldCard(false);
            }
            return;
        }
        if (!(t.closest && t.closest(".lrn-i"))) {
            closeFieldCard(false);
        }
    }, true);
    document.addEventListener("keydown", (ev) => {
        if (ev.key === "Escape" && closeFieldCard(true)) {
            // Every surface's Escape listener is on `document` at capture
            // too; only stopImmediatePropagation keeps one Escape to one rung.
            ev.stopImmediatePropagation();
            ev.preventDefault();
        }
    }, true);
    // A glossary card and a field card never show together.
    const gloss = (ev) => {
        if (ev.target.closest && ev.target.closest(".lrn-gloss") && fieldCardOpen()) {
            closeFieldCard(false);
        }
    };
    document.addEventListener("mouseover", gloss, true);
    document.addEventListener("focusin", gloss, true);
    window.addEventListener("scroll", (ev) => {
        if (fieldCardOpen() && !(ev.target && ev.target.closest
                && cardEl.contains(ev.target))) {
            if (cardBtn && cardBtn.isConnected) {
                place(cardEl, cardBtn);
            } else {
                closeFieldCard(false);
            }
        }
    }, true);
    window.addEventListener("resize", () => closeFieldCard(false));
}

/** Mark a thumbs press as done on every copy of that card on the page. */
export function markFeedback(key, up) {
    for (const el of Array.from(document.querySelectorAll(`.lrn-fbbtn[data-key="${key}"]`))) {
        const mine = el.getAttribute("data-fc") === (up ? "up" : "down");
        el.classList.toggle("on", mine);
        el.disabled = true;
        const group = el.parentElement;
        if (group && mine && !group.querySelector(".lrn-fbthanks")) {
            const note = document.createElement("span");
            note.className = "lrn-fbthanks";
            note.textContent = T("gThanks");
            group.appendChild(note);
        }
    }
}
