/** @odoo-module **/
/* =============================================================================
   The scenario overlay — Watch and Do, over the REAL product.

   THE ONE THING THIS FILE PROMISES
   --------------------------------
   There is exactly ONE synthesised press in this module — the single
   `el.click()` inside `_watchAutoClick` — and there is no code path that
   reaches it with a guarded step. Two independent facts make that structural
   rather than careful:

     1. `_watchAutoClick` has ONE call site, in `_enterStep`, inside a branch
        that is entered only when the mode is `watch` AND `step.guard` is false;
     2. `_watchAutoClick` re-asks both questions as its first statement and
        returns without doing anything if either has changed since.

   Nothing else in this file presses a control. `onNext` advances the STEP and
   never the screen — the retired tour overlay clicked the target when you pressed
   Next so the next anchor would exist, which is a reasonable thing for a demo
   tour and exactly the thing a guard is for. A learner who presses Next on a
   step they have not performed simply moves on with the screen unchanged.

   HOW THE TWO MODES DIFFER, IN ONE PARAGRAPH
   ------------------------------------------
   Watch dwells and advances by itself; Do never does. Watch may press an
   unguarded control; Do never presses anything. On a guarded step Watch stops
   pressing and becomes an ordinary observe with a card that says what pressing
   would do; Do attaches a one-shot capture listener, says "you press it — I'll
   wait", and has no timer that could walk past it.

   WHAT IT DOES NOT DO
   -------------------
   It does not block the app. The overlay is `pointer-events: none` and only the
   card takes clicks, because in Do mode the learner has to be able to press the
   very control the spotlight is drawn around.

   Ported plumbing, verbatim in behaviour and re-expressed in this module's
   visual language: the per-frame rAF measure loop, the 9000ms/120ms anchor
   poll, the one-shot capture listener, Esc/←/→, and the centred-card
   degradation when an anchor never appears. Source of the port: the retired
   guided-tour overlay (coach_overlay.js:138-162, :175-205, :220-224, :284-323,
   :375-380), deleted with its module in this phase — read it out of git if the
   plumbing here ever needs re-deriving.
   ========================================================================== */
import { Component, markup, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { T, tx, esc, ic, reduced, SP } from "../engine/runtime";
/* The glossary hovercard (LEARNOS Phase 2). The step body is the only
   raw-HTML insertion in this overlay, so it is the only `gtx`. */
import { gtx, glossaryOpen, closeGlossary } from "../engine/glossary";

const CARD_W = 372;          // matches the Journey's coach card
const DWELL = 3400;          // ms a Watch step lingers before advancing
const AFTER_CLICK = 520;     // ms to let the app's own handler run
const WAIT_TIMEOUT = 9000;   // ms to poll for a step's anchor before giving up
const WAIT_POLL = 120;       // ms between polls
const TYPE_MS = 55;          // ms per character of the Watch-mode "typing"

export class ScenarioOverlay extends Component {
    static template = "pb_learn.ScenarioOverlay";
    static props = {};

    setup() {
        this.sc = useService("learn.scenario");
        this.action = useService("action");
        this.state = useState(this.sc.state);
        this.cardRef = useRef("card");

        this.ui = useState({
            resolving: false,
            hasTarget: false,
            waiting: false,        // Do mode: listening for the learner's press
            typed: "",             // Watch mode: the value being "typed"
            hole: { top: 0, left: 0, w: 0, h: 0 },
            card: { top: 0, left: 0 },
        });

        this._targetEl = null;
        this._stepKey = null;
        this._raf = null;
        this._clickCleanup = null;
        this._timer = null;
        this._typer = null;
        this._destroyed = false;

        this._onKey = this._onKey.bind(this);
        this._loop = this._loop.bind(this);

        onMounted(() => {
            // ON `document`, NOT `window` — and this is not a style choice.
            // Something between document and window stops keydown propagation
            // (Odoo's own hotkey service owns Escape), so a window-BUBBLE
            // listener never runs and the overlay's whole keyboard interface
            // — Escape, ArrowRight, ArrowLeft — is silently dead. coach.js:129
            // and journey.js:125 both bind `document` for exactly this reason.
            // CAPTURE PHASE, and it is not a style choice. "document, not
            // window" was necessary and NOT sufficient: Odoo's hotkey service
            // stops propagation at document-BUBBLE, so a bubble listener here
            // is silently dead in real Chrome while synthetic dispatch in a
            // test still works — measured on the Phase 2+3 deploy, on the
            // welcome card's Escape, and the reason first_login.js has bound
            // capture ever since. The removal has to match the phase or the
            // listener is never removed at all.
            document.addEventListener("keydown", this._onKey, true);
            this._raf = requestAnimationFrame(this._loop);
        });
        onWillUnmount(() => {
            this._destroyed = true;
            closeGlossary();
            if (this._raf) {
                cancelAnimationFrame(this._raf);
            }
            this._detachClick();
            this._clearTimer();
            this._clearTyper();
            document.removeEventListener("keydown", this._onKey, true);
        });
    }

    // ------------------------------------------------------------- lookups
    get scenario() {
        return this.state.key ? this.sc.get(this.state.key) : null;
    }

    /** The steps playable in THIS mode. A step may narrow itself to Watch or
     *  to Try (Phase 5), so the count, the index and the "step N of M" the
     *  card prints all have to come from the same filtered list — and from the
     *  same function the service advances through, or Next would walk past a
     *  step the card never showed. */
    get steps() {
        return this.sc.steps(this.state.key, this.state.mode);
    }

    get step() {
        return this.steps[this.state.index] || null;
    }

    get isLast() {
        return this.state.index >= this.steps.length - 1;
    }

    get isWatch() {
        return this.state.mode === "watch";
    }

    /** A guarded step in Watch is an OBSERVE. Not "a click we decline to make"
     *  — the whole step changes shape: no listener, no press, and a card that
     *  explains what the control would do rather than pretending to use it. */
    get guardedInWatch() {
        const st = this.step;
        return !!(st && st.act === "click" && st.guard && this.isWatch);
    }

    get progressPct() {
        const n = this.steps.length || 1;
        return Math.round(((this.state.index + 1) / n) * 100);
    }

    // ---------------------------------------------------- inline geometry
    get spotStyle() {
        const h = this.ui.hole;
        return `top:${h.top}px;left:${h.left}px;width:${h.w}px;height:${h.h}px;`;
    }

    get cardStyle() {
        return `top:${this.ui.card.top}px;left:${this.ui.card.left}px;width:${CARD_W}px;`;
    }

    // =====================================================================
    //  One rAF: cheap geometry every frame, heavy step setup only on change
    // =====================================================================
    _loop() {
        if (this._destroyed) {
            return;
        }
        if (this.state.active && this.state.done) {
            // The closing card. No target, no timers, no listener — the only
            // control left is the one that tears the overlay down.
            if (this._stepKey !== null) {
                this._stepKey = null;
                this._targetEl = null;
                this.ui.hasTarget = false;
                this.ui.waiting = false;
                this._detachClick();
                this._clearTimer();
                this._clearTyper();
            }
        } else if (this.state.active) {
            const key = `${this.state.key}#${this.state.index}#${this.state.mode}`;
            if (key !== this._stepKey) {
                this._stepKey = key;
                this._enterStep();          // async; deliberately not awaited
            } else if (this._targetEl) {
                this._measure();
            }
        } else if (this._stepKey !== null) {
            this._stepKey = null;
            this._targetEl = null;
            this.ui.hasTarget = false;
            this.ui.waiting = false;
            this._detachClick();
            this._clearTimer();
            this._clearTyper();
        }
        this._raf = requestAnimationFrame(this._loop);
    }

    async _enterStep() {
        this._detachClick();
        this._clearTimer();
        this._clearTyper();
        this.ui.hasTarget = false;
        this.ui.waiting = false;
        this.ui.typed = "";
        this._targetEl = null;

        const step = this.step;
        if (!step) {
            return;
        }
        this.ui.resolving = true;

        if (step.nav) {
            await this._navigate(step.nav);
            if (!this.state.active || this.step !== step) {
                return;
            }
        }

        const el = step.anchor ? await this._waitFor(step.anchor, step) : null;

        // A late frame can already have moved us on while the poll was running.
        if (!this.state.active || this.step !== step) {
            return;
        }
        this.ui.resolving = false;

        if (el) {
            this._targetEl = el;
            this.ui.hasTarget = true;
            try {
                el.scrollIntoView({
                    behavior: reduced() ? "auto" : "smooth",
                    block: "center", inline: "nearest",
                });
            } catch {
                // A detached or exotic element must not end the walkthrough.
            }
            this._measure();
        }

        if (step.act === "click" && el) {
            // THE GUARD BRANCH, and the only place `_watchAutoClick` is called
            // from. Read it with the function's own first statement, which asks
            // the same two questions again at the moment of the press: between
            // them there is no arrangement of state that presses a guarded
            // control, and no second call site that could grow one.
            if (this.isWatch && !step.guard) {
                this._watchAutoClick(el);
                return;
            }
            if (!this.isWatch) {
                this._awaitRealClick(el);
                return;
            }
            // Watch + guard falls through: it is an observe now.
        }

        if (step.act === "input" && this.isWatch) {
            this._typeIntoCard(step);
        }

        // Autoplay is a WATCH property. In Do the learner advances, always —
        // including on the steps that carry no risk, because a walkthrough that
        // moves under somebody working on their own payroll is worse than one
        // that waits a moment too long.
        if (this.isWatch) {
            this._dwell();
        }
    }

    /** Mid-scenario navigation.
     *
     *  `doAction` is a promise, so the guard has to be `.catch`/`await` and not
     *  a synchronous try/catch around the call (ledger, Phase C review). A
     *  navigation that fails leaves the next anchor unresolvable, which already
     *  degrades to a centred card — a worse explanation, never a broken screen.
     */
    async _navigate(ref) {
        try {
            await this.action.doAction(ref, { clearBreadcrumbs: true });
        } catch {
            // The anchor will not resolve and the card says so instead.
        }
    }

    /** Poll until the anchor resolves to something with a visible box.
     *
     *  `offsetParent` is null for `position: fixed` elements — the PayAI pill
     *  is one, and it is the last step of the welcome scenario — so visibility
     *  is measured off the rectangle, never off the layout parent. */
    _waitFor(anchorKey, step) {
        return new Promise((resolve) => {
            const deadline = Date.now() + (step.timeout || WAIT_TIMEOUT);
            const tick = () => {
                if (this._destroyed || !this.state.active || this.step !== step) {
                    return resolve(null);
                }
                let el = null;
                try {
                    el = document.querySelector(`[data-coach="${anchorKey}"]`);
                } catch {
                    el = null;
                }
                if (el) {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {
                        return resolve(el);
                    }
                }
                if (Date.now() > deadline) {
                    return resolve(null);
                }
                return setTimeout(tick, WAIT_POLL);
            };
            tick();
        });
    }

    // ------------------------------------------------------------ geometry
    _measure() {
        const el = this._targetEl;
        if (!el || !el.isConnected) {
            this.ui.hasTarget = false;
            return;
        }
        const r = el.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) {
            this.ui.hasTarget = false;
            return;
        }
        const pad = 8;
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        const hole = {
            top: Math.max(4, r.top - pad),
            left: Math.max(4, r.left - pad),
            w: Math.min(vw - 8, r.width + pad * 2),
            h: Math.min(vh - 8, r.height + pad * 2),
        };
        this.ui.hole = hole;

        // right -> left -> below -> above, clamped: the same order the Journey's
        // spotlight uses, so a learner who has done a lesson finds the card in
        // the place they already expect it.
        const ch = (this.cardRef.el && this.cardRef.el.offsetHeight) || 260;
        const gap = 20;
        let top;
        let left;
        if (r.right + CARD_W + gap + 8 < vw) {
            left = r.right + gap;
            top = r.top + r.height / 2 - ch / 2;
        } else if (r.left - CARD_W - gap - 8 > 0) {
            left = r.left - CARD_W - gap;
            top = r.top + r.height / 2 - ch / 2;
        } else if (hole.top + hole.h + gap + ch < vh - 12) {
            top = hole.top + hole.h + gap;
            left = hole.left + hole.w / 2 - CARD_W / 2;
        } else {
            top = Math.max(12, hole.top - gap - ch);
            left = hole.left + hole.w / 2 - CARD_W / 2;
        }
        this.ui.card = {
            top: Math.max(12, Math.min(top, vh - ch - 12)),
            left: Math.max(12, Math.min(left, vw - CARD_W - 12)),
        };
    }

    // -------------------------------------------------- the learner presses
    /** Do mode. A one-shot listener in the CAPTURE phase, so the product's own
     *  handler still runs and still navigates — the engine observes the press,
     *  it does not intercept it. */
    _awaitRealClick(el) {
        this.ui.waiting = true;
        const handler = () => {
            this._detachClick();
            this.ui.waiting = false;
            // Let the app's own handler run and settle before the next step
            // starts polling for an anchor that does not exist yet.
            this._timer = window.setTimeout(() => {
                if (this.state.active) {
                    this.sc.next();
                }
            }, AFTER_CLICK);
        };
        el.addEventListener("click", handler, { once: true, capture: true });
        this._clickCleanup = () => el.removeEventListener("click", handler, { capture: true });
    }

    _detachClick() {
        if (this._clickCleanup) {
            try {
                this._clickCleanup();
            } catch {
                // The element may already be gone with its screen.
            }
            this._clickCleanup = null;
        }
    }

    // -------------------------------------------------- the engine presses
    /** THE ONLY SYNTHESISED PRESS IN THIS MODULE.
     *
     *  Called from exactly one place, under `this.isWatch && !step.guard`, and
     *  it re-asks both before doing anything: a step can change under an async
     *  gap, and a guard that is only checked at the branch is a guard that is
     *  checked once. If either answer has changed, this returns having done
     *  nothing at all — no press, no advance.
     *
     *  Do not add a second caller. Do not lift the press into a helper. The
     *  promise this module makes is checkable precisely because there is one
     *  call to `.click()` in one function with a guard as its first line, and
     *  `tests/test_scenario.py` reads the source and asserts exactly that. */
    _watchAutoClick(el) {
        const step = this.step;
        if (!step || step.guard || !this.isWatch) {
            return;
        }
        this._timer = window.setTimeout(() => {
            const now = this.step;
            if (!now || now !== step || now.guard || !this.isWatch) {
                return;
            }
            try {
                el.click();
            } catch {
                // The product's own handler threw; the walkthrough carries on.
            }
            this._timer = window.setTimeout(() => {
                if (this.state.active) {
                    this.sc.next();
                }
            }, AFTER_CLICK);
        }, DWELL);
    }

    _dwell() {
        this._timer = window.setTimeout(() => {
            if (this.state.active) {
                this.sc.next();
            }
        }, DWELL);
    }

    _clearTimer() {
        if (this._timer) {
            window.clearTimeout(this._timer);
            this._timer = null;
        }
    }

    /** Watch mode's input step. The value is typed INTO THE CARD, never into
     *  the real field: a walkthrough that fills a form on somebody's own
     *  database has written something, whatever it called itself. */
    _typeIntoCard(step) {
        const full = tx(step.value) || "";
        if (!full) {
            return;
        }
        if (reduced()) {
            this.ui.typed = full;
            return;
        }
        let i = 0;
        this._typer = window.setInterval(() => {
            i += 1;
            this.ui.typed = full.slice(0, i);
            if (i >= full.length) {
                this._clearTyper();
            }
        }, TYPE_MS);
    }

    _clearTyper() {
        if (this._typer) {
            window.clearInterval(this._typer);
            this._typer = null;
        }
    }

    // ------------------------------------------------------------- controls
    /** Advance the STEP. Never the screen.
     *
     *  The retired tour's Next pressed the target so the following anchor
     *  would exist.
     *  That is the behaviour a guard exists to prevent, so it is gone: pressing
     *  Next on a step you have not performed moves the card on and leaves the
     *  product exactly as it was. The following step then degrades to a centred
     *  card, which is the honest outcome. */
    onNext() {
        this._detachClick();
        this._clearTimer();
        this.sc.next();
    }

    onBack() {
        this._detachClick();
        this._clearTimer();
        this.sc.back();
    }

    onLeave() {
        this._detachClick();
        this._clearTimer();
        this._clearTyper();
        this.sc.stop();
    }

    _onKey(ev) {
        if (!this.state.active) {
            return;
        }
        if (ev.key === "Escape") {
            // A hovercard over the card closes first (see glossaryOpen).
            if (glossaryOpen()) {
                return;
            }
            // A transient layer that closes on a key SWALLOWS that key, or one
            // Escape both closes the card and does whatever the screen behind
            // it does with Escape. The arrow branches below only move the
            // walkthrough, so they take the default and leave the key alone.
            ev.stopPropagation();
            ev.preventDefault();
            this.onLeave();
        } else if (ev.key === "ArrowRight") {
            ev.preventDefault();
            this.onNext();
        } else if (ev.key === "ArrowLeft") {
            ev.preventDefault();
            this.onBack();
        }
    }

    onClick(ev) {
        const el = ev.target.closest("[data-act]");
        if (!el) {
            return;
        }
        ev.preventDefault();
        const act = el.dataset.act;
        if (act === "s-next" || act === "s-skip") {
            this.onNext();
        } else if (act === "s-back") {
            this.onBack();
        } else if (act === "s-leave") {
            this.onLeave();
        }
    }

    // -------------------------------------------------------------- render
    get modeBadge() {
        return T("scRealBadge");
    }

    // t-out RENDERS A PLAIN STRING AS TEXT. Every one of these getters builds
    // markup out of esc()'d fragments, exactly as coach.js and journey.js do,
    // and every one of them must hand OWL a markup() value or the card paints
    // its own source. The three public getters below are the only thing the
    // template touches; the _*Str builders keep the logic.
    get headerHTML() {
        return markup(this._headerStr());
    }

    get bodyHTML() {
        return markup(this._bodyStr());
    }

    get toolsHTML() {
        return markup(this._toolsStr());
    }

    _bodyStr() {
        // THE RENDER-TIME SUBSCRIPTION, for the same reason coach.js has one:
        // every visible string goes through T()/tx(), which read RT.lang — a
        // plain module object OWL cannot observe. Reading the SERVICE's
        // reactive copy here is what makes flipping language in the drawer
        // re-draw a card that is already on screen, instead of leaving the
        // walkthrough in the other language until a reload.
        const lang = this.state.lang;
        void lang;
        if (this.state.done) {
            return `
            <div class="lrn-kicker">${esc(T("scDone"))}</div>
            <h3>${esc(tx(this.scenario ? this.scenario.name : ""))}</h3>
            <div class="lrn-cbody">${esc(T("scDoneBody"))}</div>`;
        }
        const step = this.step;
        if (!step) {
            return "";
        }
        const parts = [];
        if (step.kicker) {
            parts.push(`<div class="lrn-kicker">${esc(tx(step.kicker))}</div>`);
        }
        parts.push(`<h3>${esc(tx(step.title))}</h3>`);
        parts.push(`<div class="lrn-cbody">${gtx(step.body)}</div>`);

        if (this.guardedInWatch) {
            // The card says what pressing WOULD do, and says who is not
            // pressing it. Both halves matter: a spotlight on a Compute button
            // with no explanation reads as an invitation.
            parts.push(`<div class="lrn-scguard">
                <h4>${ic("lock")}${esc(T("scWouldDo"))}</h4>
                <p>${esc(T("scWatchHint"))}</p>
            </div>`);
        } else if (this.ui.waiting) {
            parts.push(`<div class="lrn-scwait">
                <h4>${ic("target")}${esc(step.guard ? T("scWaiting") : T("scYourTurn"))}</h4>
                <p>${esc(step.guard ? T("scWaitingBody") : T("scPressIt"))}</p>
            </div>`);
        }

        if (step.act === "input" && this.ui.typed) {
            parts.push(`<div class="lrn-sctype">
                <span class="lrn-kicker">${esc(T("scTyping"))}</span>
                <code>${esc(this.ui.typed)}</code>
            </div>`);
        }

        if (!this.ui.hasTarget && !this.ui.resolving && step.anchor) {
            parts.push(`<div class="lrn-tip">${ic("info")}
                <span>${esc(T("scNotOnScreen"))}</span></div>`);
        }

        if (step.tip) {
            parts.push(`<div class="lrn-tip">${ic("lightbulb")}
                <span>${esc(tx(step.tip))}</span></div>`);
        }
        return parts.join("");
    }

    _toolsStr() {
        if (this.state.done) {
            return `<div class="lrn-ctools">
                <button class="lrn-btn sm pri" data-act="s-leave"
                    >${ic("check")}${esc(T("finish"))}</button>
            </div>`;
        }
        const step = this.step;
        if (!step) {
            return "";
        }
        // On a step the engine is waiting for, the primary control is NOT
        // "Next" — offering one beside "you press it, I'll wait" is offering to
        // walk past the only thing being taught. Skip is a ghost, it says what
        // it does, and it never presses anything either.
        const advance = this.ui.waiting
            ? `<button class="lrn-btn sm ghost" data-act="s-skip"
                >${ic("skip-forward")}${esc(T("scSkip"))}</button>`
            : `<button class="lrn-btn sm pri" data-act="s-next"
                >${esc(this.isLast ? T("finish") : T("next"))}${ic("chevron-right")}</button>`;
        return `
        <div class="lrn-ctools">
            <button class="lrn-btn sm" data-act="s-back"
                ${this.state.index === 0 ? "disabled" : ""}
                >${ic("chevron-left")}${esc(T("back"))}</button>
            ${advance}
            <button class="lrn-btn sm ghost" data-act="s-leave"
                >${ic("x")}${esc(T("exit"))}</button>
        </div>`;
    }

    _headerStr() {
        const s = this.scenario;
        if (!s) {
            return "";
        }
        const counter = this.state.done
            ? ""
            : `<span class="lrn-scstep">${esc(T("step"))}${SP}${this.state.index + 1}${
                SP}${esc(T("of"))}${SP}${this.steps.length}</span>`;
        return `
        <div class="lrn-schead">
            <span class="lrn-chip a">${ic(this.isWatch ? "play" : "target")}${
                esc(this.isWatch ? T("scWatch") : T("scDo"))}</span>
            <span class="lrn-chip">${ic("shield-check")}${esc(this.modeBadge)}</span>
            ${counter}
        </div>`;
    }
}

registry.category("main_components").add("PbLearnScenarioOverlay", {
    Component: ScenarioOverlay,
});
