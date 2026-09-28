/** @odoo-module **/
/* =============================================================================
   Spotlight, trace and point-at.

   The binding rule from the brief: NEVER cover the UI being explained. So the
   spotlight dims AROUND the target rather than drawing over it, and the coach
   card is placed in whichever direction has room — right, left, below, above —
   clamped to the viewport and above the control bar.
   ========================================================================== */
import { $, esc, reduced, SP, T } from "./runtime";

let OVER = null;

/** The engine draws into one host element the client action owns. */
export function setOverlayRoot(el) {
    OVER = el;
}

function anchorEl(key) {
    return key ? $(`[data-coach="${key}"]`) : null;
}

export const Trace = {
    svg: null,

    clear() {
        if (this.svg) {
            this.svg.remove();
            this.svg = null;
        }
    },

    /** An animated dot travels from a setup value to the line it produces, so
     *  cause and effect are one gesture rather than two paragraphs. Under
     *  reduced motion the path is drawn statically and both ends ring. */
    run(fromKey, toKey) {
        this.clear();
        const a = anchorEl(fromKey);
        const b = anchorEl(toKey);
        if (!a || !b || !OVER) {
            return;
        }
        const ra = a.getBoundingClientRect();
        const rb = b.getBoundingClientRect();
        const x1 = ra.left + ra.width / 2;
        const y1 = ra.top + ra.height / 2;
        const x2 = rb.left + rb.width / 2;
        const y2 = rb.top + rb.height / 2;
        const mx = (x1 + x2) / 2;

        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("class", "lrn-tracelayer");
        svg.innerHTML =
            `<path d="M ${x1}${SP}${y1}${SP}C ${mx}${SP}${y1}, ${mx}${SP}${y2}, ${x2}${SP}${y2}"/>` +
            `<circle r="6" cx="${x1}" cy="${y1}"/>`;
        OVER.appendChild(svg);
        this.svg = svg;

        ring(a);
        if (reduced()) {
            ring(b);
            return;
        }
        const path = svg.querySelector("path");
        const dot = svg.querySelector("circle");
        const len = path.getTotalLength();
        let t0 = null;
        const step = (ts) => {
            // The layer is torn down when the step changes; this frame can
            // still be queued when that happens.
            if (!this.svg) {
                return;
            }
            if (t0 === null) {
                t0 = ts;
            }
            const k = Math.min(1, (ts - t0) / 1250);
            const pt = path.getPointAtLength(len * k);
            dot.setAttribute("cx", pt.x);
            dot.setAttribute("cy", pt.y);
            if (k < 1) {
                requestAnimationFrame(step);
            } else {
                ring(b);
            }
        };
        requestAnimationFrame(step);
    },
};

function ring(el) {
    el.classList.add("lrn-hl");
    setTimeout(() => el.classList.remove("lrn-hl"), 3000);
}

/* LEARN REFRESH step 4 — at or below this width the card cannot sit BESIDE
   the control it explains, so it docks as a sheet along the bottom (above the
   play bar) and the page is scrolled so the control sits clear above it. The
   sheet folds down to one line on request, and stays folded for the rest of
   the lesson, so a reader on a phone can look at the whole board. */
export const DOCK_BELOW = 900;

function docked() {
    return window.innerWidth <= DOCK_BELOW;
}

/** How much of the bottom of the window the play bar takes (it wraps to two
 *  rows on a phone, so it is measured, not assumed). */
function barGuard() {
    const bar = $(".lrn-playbar");
    if (!bar) {
        return 12;
    }
    const top = bar.getBoundingClientRect().top;
    return Math.max(12, window.innerHeight - top + 8);
}

/** The nearest ancestor that actually scrolls, or null. */
function scrollParent(el) {
    let p = el && el.parentElement;
    while (p && p !== document.body) {
        const cs = window.getComputedStyle(p);
        if (/(auto|scroll)/.test(cs.overflowY) && p.scrollHeight > p.clientHeight + 2) {
            return p;
        }
        p = p.parentElement;
    }
    return null;
}

export const Spot = {
    hole: null,
    card: null,
    // Folded by the reader on a narrow screen. Kept across steps (a reader who
    // folded the card wants to keep looking at the board), cleared on hide().
    folded: false,

    show(anchorKey, cardHTML) {
        // A trace belongs to ONE step. Clearing here rather than at teardown is
        // what stops step 5's line from still being drawn on step 8.
        Trace.clear();
        if (!OVER) {
            return;
        }
        const el = anchorEl(anchorKey);
        if (!this.hole) {
            this.hole = document.createElement("div");
            this.hole.className = "lrn-spot-hole";
            this.card = document.createElement("div");
            this.card.className = "lrn-coach";
            this.card.setAttribute("role", "region");
            this.card.setAttribute("aria-live", "polite");
            // The fold toggle is the card's own control, never a data-act the
            // host would also route (LR12): handled here and stopped here.
            this.card.addEventListener("click", (ev) => {
                const t = ev.target.closest("[data-spot-fold]");
                if (!t) {
                    return;
                }
                ev.preventDefault();
                ev.stopPropagation();
                this.folded = !this.folded;
                t.outerHTML = this._foldBar();
                this._applyFold();
                this.position(this._lastRect || null);
            });
            OVER.appendChild(this.hole);
            OVER.appendChild(this.card);
        }
        this.card.innerHTML = this._foldBar() + cardHTML;
        this._applyFold();

        if (!el) {
            this.hole.style.display = "none";
            this.position(null);
            return;
        }
        el.scrollIntoView({ block: docked() ? "start" : "center",
                            behavior: reduced() || docked() ? "auto" : "smooth" });
        const place = () => {
            // Deferred a frame to let scrollIntoView settle, so it can outlive
            // the step that scheduled it — leaving a lesson calls hide() and
            // this fires afterwards against a torn-down overlay.
            if (!this.hole || !this.card) {
                return;
            }
            let r = el.getBoundingClientRect();
            if (docked()) {
                r = this._clearOfSheet(el, r);
            }
            const pad = 8;
            this.hole.style.display = "block";
            this.hole.style.top = r.top - pad + "px";
            this.hole.style.left = r.left - pad + "px";
            this.hole.style.width = r.width + pad * 2 + "px";
            this.hole.style.height = r.height + pad * 2 + "px";
            this.position(r);
        };
        if (reduced()) {
            place();
        } else {
            setTimeout(place, 190);
        }
    },

    /** The one-line bar a docked card folds to. Drawn on every card and
     *  shown only while docked (CSS), so a resize needs no re-render. */
    _foldBar() {
        const label = esc(T(this.folded ? "cardUnfold" : "cardFold"));
        return `<button type="button" class="lrn-coachfold" data-spot-fold="1"
            aria-label="${label}" title="${label}"
            aria-expanded="${this.folded ? "false" : "true"}"><span class="lrn-coachgrip"></span></button>`;
    },

    _applyFold() {
        // Room under the last control, so even the bottom of a board can be
        // scrolled clear of a docked sheet.
        document.body.classList.toggle("lrn-docked", !!this.card && docked());
        if (!this.card) {
            return;
        }
        const fold = docked() && this.folded;
        this.card.classList.toggle("docked", docked());
        this.card.classList.toggle("folded", fold);
        const b = this.card.querySelector("[data-spot-fold]");
        if (b) {
            b.setAttribute("aria-expanded", fold ? "false" : "true");
        }
    },

    /** Scroll the control up until it sits above the docked sheet; returns
     *  its rectangle afterwards. */
    _clearOfSheet(el, r) {
        const c = this.card;
        const H = window.innerHeight;
        const sheetTop = H - barGuard() - ((c && c.offsetHeight) || 220) - 12;
        if (r.top >= 64 && r.bottom <= sheetTop - 8) {
            return r;
        }
        // The scroller here may be overflow:hidden (the hub canvas), which
        // only scrollIntoView can move — so ask for the top, then give back
        // a little room under the header if there is any above.
        try {
            el.scrollIntoView({ block: "start", behavior: "auto" });
        } catch {
            return r;
        }
        const sp = scrollParent(el);
        if (sp && sp.scrollTop > 64) {
            sp.scrollTop -= 64;
        }
        return el.getBoundingClientRect();
    },

    /** right -> left -> below -> above, clamped to the viewport. At or below
     *  DOCK_BELOW the card is a bottom sheet instead (see above). */
    position(r) {
        const c = this.card;
        if (!c) {
            return;
        }
        this._lastRect = r;
        const W = window.innerWidth;
        const H = window.innerHeight;
        // Reserve the strip the control bar occupies, so the card's own
        // Back/Next never end up underneath it.
        const bottomGuard = docked() ? barGuard() : ($(".lrn-playbar") ? 88 : 12);
        const usable = H - bottomGuard;
        this._applyFold();
        if (docked()) {
            const cw = W - 24;
            c.style.width = cw + "px";
            c.style.left = "12px";
            c.style.top = Math.max(12, usable - c.offsetHeight - 8) + "px";
            return;
        }
        c.style.top = "0px";
        c.style.left = "0px";
        const cw = Math.min(372, W - 32);
        const ch = c.offsetHeight || 260;
        let top;
        let left;
        if (!r) {
            top = Math.max(16, (usable - ch) / 2);
            left = (W - cw) / 2;
        } else if (r.right + cw + 28 < W) {
            left = r.right + 20;
            top = r.top + r.height / 2 - ch / 2;
        } else if (r.left - cw - 28 > 0) {
            left = r.left - cw - 20;
            top = r.top + r.height / 2 - ch / 2;
        } else if (r.bottom + ch + 28 < usable) {
            top = r.bottom + 20;
            left = Math.min(Math.max(16, r.left), W - cw - 16);
        } else {
            top = Math.max(16, r.top - ch - 20);
            left = Math.min(Math.max(16, r.left), W - cw - 16);
        }
        c.style.top = Math.max(12, Math.min(top, usable - ch)) + "px";
        c.style.left = Math.max(12, Math.min(left, W - cw - 12)) + "px";
        c.style.width = cw + "px";
    },

    hide() {
        if (this.hole) {
            this.hole.remove();
            this.card.remove();
            this.hole = null;
            this.card = null;
        }
        this.folded = false;
        this._lastRect = null;
        document.body.classList.remove("lrn-docked");
        Trace.clear();
    },
};

/** Scroll a control into view and ring it. Returns false when the anchor is
 *  not on screen, so a caller can say so honestly instead of pointing at
 *  nothing. */
export function flashRing(anchorKey) {
    const el = anchorEl(anchorKey);
    if (!el) {
        return false;
    }
    el.scrollIntoView({ block: "center", behavior: reduced() ? "auto" : "smooth" });
    ring(el);
    return true;
}
