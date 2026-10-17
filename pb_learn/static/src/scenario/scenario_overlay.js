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

   NOTHING IN HERE ADVANCES BY ITSELF
   ----------------------------------
   In BOTH modes the learner decides when to move on, by pressing Next. The
   first cut of Watch dwelled 3.4s per step and walked on; it read as a video
   playing at somebody, and a reader who wanted a second look had no way to ask
   for one. The only automatic step change left in the module is in Do, AFTER
   the learner has pressed the real control themselves — which is not the
   engine deciding anything, it is the engine noticing.

   HOW THE TWO MODES DIFFER, IN ONE PARAGRAPH
   ------------------------------------------
   Watch may press an unguarded control to demonstrate it, so the screen the
   next step describes actually exists; Do never presses anything. On a guarded
   step Watch stops pressing and becomes an ordinary observe with a card that
   says what pressing would do; Do attaches a one-shot capture listener and
   says "you press it — I'll wait".

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
import { navPlace } from "../engine/places";
import { DOCK_BELOW, placeCard } from "../engine/spotlight";
import { linesHTML, stepView } from "../coach/lesson_panel";
import { hubPlace } from "@pb_hub/js/hub_place";

/* LEARN REFRESH step 4 — the words a screen uses when it refuses its reader,
   in both languages. Read only from alert-like elements, and only while the
   step's control has NOT appeared, so a screen that merely talks about access
   (Access & delegation) is never mistaken for one that refused. */
const REFUSED_TEXT = new RegExp([
    "you (do not|don't) have (access|permission|the right)",
    "you need [^.]{0,60}access",
    "could not be opened",
    "not allowed to (open|see|view|read)",
    "access (error|denied|refused)",
    "không có quyền", "chưa có quyền", "bạn cần quyền", "không mở được",
].join("|"), "i");
const REFUSAL_BOXES = [
    ".o_error_dialog", ".o_notification", "[role=alert]", ".alert",
    "[class*=error]", "[class*=denied]", "[class*=noaccess]", "[class*=no-access]",
    "[class*=blocked]", "[class*=refus]", "[class*=forbid]", "[class*=locked]",
    // LEARNREV P4 — the Component treatment board writes a refusal into its
    // own `.pct-empty` box (component_treatment.xml `state.error`).
    ".pct-empty",
].join(",");
const REFUSAL_GRACE = 700;     // ms a screen gets to load before we listen
const REFUSAL_PROBE = 2500;    // ms an anchorless step keeps listening
/* LEARNREV P4 — in Watch, a step whose control is not on the screen says
   what the control does and moves on by itself after this long (Watch is
   being shown something; Do and Try still wait for the person). */
const MISSING_SKIP = 4000;
/* LEARNREV P4 — a checked step (Try on the demo company, or Do with a
   declared check) asks the server this often whether the person's change is
   there (the live capstone's own rhythm, live_mission.js), and shows a passed
   check's note for a beat before moving on. */
const CHECK_EVERY = 3000;
const CHECK_OK_BEAT = 1400;
/* How far back a check looks for the person's change (clock skew between the
   browser and the server, and a change made just before the step opened). */
const CHECK_SLACK_MS = 120000;

function shown(el) {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
}

function said(el) {
    return " ".concat((el.textContent || "").split(/\s+/).join(" ")).trim().slice(0, 200);
}

/** Has the screen this step stands on refused its reader? Three signals:
 *  an error dialog, a tab the hub will not show this person, or a refusal
 *  sentence in an alert-like box on the page. LEARNREV P4: the answer is the
 *  screen's OWN WORDS when it said any (the card quotes them), `true` for a
 *  hidden tab, `false` when nothing refused. */
export function refusalOnScreen(expected) {
    for (const d of document.querySelectorAll(".o_error_dialog")) {
        if (shown(d)) {
            return said(d) || true;
        }
    }
    const pl = expected && navPlace(expected);
    if (pl && hubPlace.ready && hubPlace.tag === pl.tag && hubPlace.lenses.length
            && !hubPlace.lenses.some((l) => l.key === pl.lens)) {
        return true;
    }
    for (const el of document.querySelectorAll(REFUSAL_BOXES)) {
        if (el.closest(".lrn-scoverlay, .lrn-drawer, .lrn-coach")) {
            continue;
        }
        const text = (el.textContent || "").slice(0, 400);
        if (REFUSED_TEXT.test(text) && shown(el)) {
            return said(el) || true;
        }
    }
    return false;
}

const REFUSED = { refused: true };

const CARD_W = 372;          // matches the Journey's coach card
const PRESS_SETTLE = 400;    // ms before Watch performs a demonstrated press
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
            // LEARNREV P4 — a checked step: waiting for the server to see the
            // person's own change, what is still missing, and the pass.
            checking: false,
            checkNote: null,
            checkOk: false,
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
        this._poll = null;
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
        // LEARN REFRESH step 4 — narrow screens dock the card along the
        // bottom, full width, and the control is scrolled up clear of it.
        if (this.ui.card.docked) {
            return `top:${this.ui.card.top}px;left:12px;width:calc(100vw - 24px);`;
        }
        return `top:${this.ui.card.top}px;left:${this.ui.card.left}px;width:${CARD_W}px;`;
    }

    // =====================================================================
    //  One rAF: cheap geometry every frame, heavy step setup only on change
    // =====================================================================
    _loop() {
        if (this._destroyed) {
            return;
        }
        if (this.state.active && (this.state.done || this.state.blocked)) {
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
        this.ui.checking = false;
        this.ui.checkNote = null;
        this.ui.checkOk = false;
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

        const got = step.anchor ? await this._waitFor(step.anchor, step) : null;

        // A late frame can already have moved us on while the poll was running.
        if (!this.state.active || this.step !== step) {
            return;
        }
        // LEARN REFRESH step 4 — the screen opened and then refused this
        // reader. The no-access ending, not a centred card explaining a
        // control they will never see.
        if (got === REFUSED) {
            this.ui.resolving = false;
            this.sc.refuse(this.sc.screenOfStep(this.state.index), this._refusal);
            return;
        }
        const el = got;
        this.ui.resolving = false;
        if (!step.anchor) {
            this._probeRefusal(step);
        }

        if (el) {
            this._targetEl = el;
            this.ui.hasTarget = true;
            try {
                // Docked (narrow): the control goes near the top, because the
                // bottom of the screen is the card's.
                el.scrollIntoView({
                    behavior: reduced() ? "auto" : "smooth",
                    block: window.innerWidth <= DOCK_BELOW ? "start" : "center",
                    inline: "nearest",
                });
            } catch {
                // A detached or exotic element must not end the walkthrough.
            }
            this._measure();
        }

        // LEARNREV P4 — a CHECKED step (Try on the demo company, or Do with a
        // declared check): nothing is pressed for the person and a click is
        // not taken as done — the step moves on when the server sees their
        // own change (`_pollCheck`). The person can always Skip.
        if (!this.isWatch && (this.state.checks || []).includes(step.key)) {
            this._startCheck(step);
            return;
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

        // LEARNREV P4 (G23) — Watch, and the control never appeared: the card
        // says what it does ("That control is not on this screen right now")
        // and the walkthrough moves on by itself, instead of waiting on a
        // step nobody can see. Do and Try still wait for the person.
        if (!el && step.anchor && this.isWatch) {
            this._timer = window.setTimeout(() => this._skipMissing(step), MISSING_SKIP);
        }

        // AND THEN IT WAITS. There is deliberately no timer here in either
        // mode: a step ends when the learner presses Next and at no other
        // moment. Watch may still have pressed a control above to set the
        // screen up — that is the demonstration — but the CARD does not move.
    }

    /** Mid-scenario navigation.
     *
     *  `doAction` is a promise, so the guard has to be `.catch`/`await` and not
     *  a synchronous try/catch around the call (ledger, Phase C review). A
     *  navigation that fails leaves the next anchor unresolvable, which already
     *  degrades to a centred card — a worse explanation, never a broken screen.
     */
    async _navigate(ref) {
        // Through the service, which opens the screen WHERE IT LIVES (hub ›
        // tab) and blocks the walkthrough with a plain reason when it cannot
        // — the same door the entry navigation uses (LEARN REFRESH step 1).
        try {
            await this.sc.navigate(ref);
        } catch {
            // The anchor will not resolve and the card says so instead.
        }
    }

    /** An anchorless card (an introduction) is on screen at once; for a
     *  moment afterwards, listen for the screen behind it refusing the reader,
     *  so a walkthrough of a gated screen still ends on the no-access card
     *  before its second step. */
    _probeRefusal(step) {
        const t0 = Date.now();
        const tick = () => {
            if (this._destroyed || !this.state.active || this.step !== step
                    || this.state.blocked) {
                return;
            }
            const refused = Date.now() - t0 > REFUSAL_GRACE
                && refusalOnScreen(this.sc.screenOfStep(this.state.index));
            if (refused) {
                this.sc.refuse(this.sc.screenOfStep(this.state.index), refused);
                return;
            }
            if (Date.now() - t0 < REFUSAL_PROBE) {
                setTimeout(tick, WAIT_POLL * 2);
            }
        };
        setTimeout(tick, WAIT_POLL * 2);
    }

    /** Poll until the anchor resolves to something with a visible box.
     *
     *  `offsetParent` is null for `position: fixed` elements — the PayAI pill
     *  is one, and it is the last step of the welcome scenario — so visibility
     *  is measured off the rectangle, never off the layout parent. */
    _waitFor(anchorKey, step) {
        return new Promise((resolve) => {
            const t0 = Date.now();
            const deadline = t0 + (step.timeout || WAIT_TIMEOUT);
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
                const refused = Date.now() - t0 > REFUSAL_GRACE
                    && refusalOnScreen(this.sc.screenOfStep(this.state.index));
                if (refused) {
                    this._refusal = refused;
                    return resolve(REFUSED);
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
        // LEARNREV P4 (walk B3) — a screen that redraws its control (the
        // treatment board reloads its table after Save) leaves the old node
        // detached: find the control again by its anchor instead of saying
        // it is not on the screen and re-centring the card over the board.
        const step = this.step;
        if (this._targetEl && !this._targetEl.isConnected && step && step.anchor) {
            const again = document.querySelector(`[data-coach="${step.anchor}"]`);
            if (again) {
                this._targetEl = again;
            }
        }
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
        if (!this.ui.hasTarget) {
            // Back on screen after a redraw (see above).
            this.ui.hasTarget = true;
        }
        const pad = 8;
        // LEARNREV P2 — the docked Guide takes 420 px on the right (≥ 1280).
        // LEARNREV P4 — Watch now keeps the Guide open, docked OR floating,
        // so the strip it holds on the right is measured, not assumed.
        const W = window.innerWidth;
        const drawer = document.querySelector(".lrn-drawer");
        const dr = drawer ? drawer.getBoundingClientRect() : null;
        const guideW = dr && dr.width && dr.left > W / 2 ? Math.max(0, W - dr.left + 8) : 0;
        const vw = W - guideW;
        const vh = window.innerHeight;
        const hole = {
            top: Math.max(4, r.top - pad),
            left: Math.max(4, r.left - pad),
            w: Math.min(W - 8, r.width + pad * 2),
            h: Math.min(vh - 8, r.height + pad * 2),
        };
        this._setUi("hole", hole);

        const ch = (this.cardRef.el && this.cardRef.el.offsetHeight) || 260;
        if (vw <= DOCK_BELOW) {
            this._setUi("card", { top: Math.max(12, vh - ch - 12), left: 12, docked: true });
            return;
        }
        // right -> left -> below -> above: the same rule the lessons use
        // (engine/spotlight.js placeCard, tested never to cover the control),
        // with the Guide's strip kept clear.
        const p = placeCard({ top: hole.top, left: hole.left, width: hole.w, height: hole.h,
                              right: hole.left + hole.w, bottom: hole.top + hole.h },
                            { W, H: vh, cw: CARD_W, ch, guard: 12, dock: guideW });
        this._setUi("card", { top: Math.round(p.top), left: Math.round(p.left) });
    }

    /** Write a geometry box into `ui` ONLY when it moved.
     *
     *  `_measure` runs every animation frame, and a fresh object is always a
     *  change to OWL — so the whole card re-rendered ~60 times a second, and
     *  every render re-built the `t-out` markup, i.e. a NEW Next button. A real
     *  mouse press and its release then landed on two different buttons and
     *  no click ever fired: "Next is not working" (2026-10-11). A scripted
     *  `.click()` is instant and passed. */
    _setUi(name, box) {
        const cur = this.ui[name];
        if (cur && Object.keys(box).length === Object.keys(cur).length
                && Object.keys(box).every((k) => cur[k] === box[k])) {
            return;
        }
        this.ui[name] = box;
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
            // AND NOTHING ELSE. The press is the demonstration; moving on is
            // the learner's to decide. A press that also advanced was how the
            // first cut of Watch outran its own reader.
        }, PRESS_SETTLE);
    }

    /** LEARNREV P4 — start waiting on a checked step. */
    _startCheck(step) {
        this.ui.checking = true;
        this.ui.waiting = true;
        this.ui.checkNote = null;
        this.ui.checkOk = false;
        this._checkSince = new Date(Date.now() - CHECK_SLACK_MS).toISOString()
            .slice(0, 19).replace("T", " ");
        this._pollCheck(step);
    }

    /** One poll of a checked step: ask the server whether the person's own
     *  change is there (`learn.scenario.check`, read-only), say what is still
     *  missing, and move on — after a beat that shows the pass — when it is.
     *  Re-asks the step, the mode and that the walkthrough is still running
     *  after every await; presses nothing, ever. */
    async _pollCheck(step) {
        if (this._destroyed || !this.state.active || this.state.blocked
                || this.step !== step || this.isWatch) {
            return;
        }
        // The scheme Mapping published, remembered for the walkthrough: a
        // later step ("recompute the run") is checked from the Runs board.
        const extra = (hubPlace && hubPlace.extra) || {};
        if (Number(extra.config_id)) {
            this._cfg = { key: this.state.key, id: Number(extra.config_id) };
        }
        const cfg = this._cfg && this._cfg.key === this.state.key ? this._cfg.id : 0;
        let res = null;
        try {
            res = await this.sc.check(step.key, { since: this._checkSince, config_id: cfg });
        } catch {
            res = null;
        }
        if (this._destroyed || !this.state.active || this.step !== step || this.isWatch) {
            return;
        }
        this.ui.checkNote = res && res.note ? res.note : null;
        if (res && res.ok) {
            this.ui.checkOk = true;
            this._timer = window.setTimeout(() => {
                if (this.state.active && this.step === step && !this.isWatch) {
                    this.sc.next();
                }
            }, CHECK_OK_BEAT);
            return;
        }
        this._poll = window.setTimeout(() => this._pollCheck(step), CHECK_EVERY);
    }

    /** LEARNREV P4 — the one automatic step change in Watch, and only for a
     *  step whose control never appeared: re-asks every condition at the
     *  moment it fires (the step, the mode, that the control is still not
     *  there, that nothing blocked the walkthrough) and presses nothing. */
    _skipMissing(step) {
        if (!this.state.active || this.state.blocked || this.state.done
                || this.step !== step || !this.isWatch || this.ui.hasTarget) {
            return;
        }
        this.sc.next();
    }

    _clearTimer() {
        if (this._timer) {
            window.clearTimeout(this._timer);
            this._timer = null;
        }
        // LEARNREV P4 — a checked step's poll goes with every other timer.
        if (this._poll) {
            window.clearTimeout(this._poll);
            this._poll = null;
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
        if (this.state.blocked) {
            return;
        }
        this._detachClick();
        this._clearTimer();
        this.sc.next();
    }

    onBack() {
        if (this.state.blocked) {
            return;
        }
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
        if (act === "s-practice") {
            this._detachClick();
            this._clearTimer();
            this._clearTyper();
            this.sc.practiceInstead();
        } else if (act === "s-retry") {
            // LEARNREV P4 — a slow screen, opened again.
            this.sc.retry();
        } else if (act === "s-next" || act === "s-skip") {
            this.onNext();
        } else if (act === "s-back") {
            this.onBack();
        } else if (act === "s-leave") {
            this.onLeave();
        } else if (act === "s-jump") {
            // LEARN v3 — the step bar. Only BACKWARDS: jumping ahead would
            // walk past a step the learner has not been shown.
            const i = parseInt(el.dataset.i, 10);
            if (i >= 0 && i < this.state.index) {
                this.sc.goTo(i);
            }
        } else if (act === "s-mode") {
            this.switchMode(el.dataset.mode);
        }
    }

    /** LEARN v3 — one switch for Watch / Try / Do, keeping your place.
     *
     *  The place is the step KEY, never the index: a step may narrow itself
     *  to one mode, so step 4 of Watch is not step 4 of Do. Try belongs to
     *  the lesson map (over the practice copy), so switching to it hands the
     *  walkthrough over there from the start. */
    async switchMode(mode) {
        const sc = this.scenario;
        if (!sc || mode === this.state.mode || !(sc.modes || []).includes(mode)) {
            return;
        }
        const key = sc.key;
        const stepKey = this.step ? this.step.key : "";
        this._detachClick();
        this._clearTimer();
        this._clearTyper();
        if (mode === "try") {
            this.sc.stop();
            await this.sc.begin(key, "try");
            return;
        }
        const started = await this.sc.begin(key, mode);
        if (!started || !stepKey) {
            return;
        }
        const index = this.sc.steps(key, mode).findIndex((st) => st.key === stepKey);
        if (index > 0) {
            this.sc.goTo(index);
        }
    }

    // -------------------------------------------------------------- render
    get modeBadge() {
        // LEARNREV P4 — Try on the real screen of the demo company.
        return T(this.state.real ? "scTryReal" : "scRealBadge");
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
        if (this.state.blocked) {
            // LEARNREV P4 (G23) — a screen that is merely SLOW says so, with
            // Retry; it is never told it has no access.
            if (this.state.blocked.kind === "slow") {
                return `
            <h3>${esc(tx(this.scenario ? this.scenario.name : ""))}</h3>
            <div class="lrn-cbody">${esc(T("scSlowBody"))}</div>`;
            }
            // LEARN REFRESH step 1 — the screen could not be opened for this
            // reader. One sentence that names it and says what to do instead;
            // never step one waiting for an anchor that is not coming.
            const label = this.state.blocked.label
                || tx(this.scenario ? this.scenario.name : "");
            // LEARNREV P4 — and the screen's own words, when it said any.
            const reason = this.state.blocked.reason
                ? `<p class="lrn-screason">${esc(T("scRefusedBecause"))}${SP}<q>${esc(this.state.blocked.reason)}</q></p>` : "";
            // The header chip already says "You can't open this screen".
            return `
            <h3>${esc(tx(this.scenario ? this.scenario.name : ""))}</h3>
            <div class="lrn-cbody">${esc(T("scNoAccessA"))}${SP}<b>${esc(label)}</b>${esc(T("scNoAccessB"))}</div>${reason}`;
        }
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
        // LEARNREV P4 — a rewritten step is four lines (Look at · It means ·
        // It affects · Press), drawn by the Guide's own renderer; a step not
        // rewritten keeps its body.
        const view = stepView(step, "");
        parts.push(view.look && !view.legacy
            ? linesHTML(view, { text: (p) => tx(p), html: (p) => gtx(p) })
            : `<div class="lrn-cbody">${gtx(step.body)}</div>`);

        if (this.ui.checking) {
            // LEARNREV P4 — a checked step: do it on the screen, I look.
            const note = this.ui.checkNote ? esc(tx(this.ui.checkNote)) : "";
            const line = this.ui.checkOk
                ? `<p class="lrn-sccheck ok">${ic("check-circle")}<span>${esc(T("scCheckOk"))}${SP}${note}</span></p>`
                : (note ? `<p class="lrn-sccheck">${esc(T("scCheckMissing"))}${SP}${note}</p>` : "");
            parts.push(`<div class="lrn-scwait">
                <h4>${ic("target")}${esc(T("scYourTurn"))}</h4>
                <p>${esc(T("scCheckWait"))}</p>${line}
            </div>`);
        } else if (this.guardedInWatch) {
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
            // LEARNREV P4 — in Watch it then moves on by itself (_skipMissing).
            const soon = this.isWatch ? `${SP}${esc(T("scSkipSoon"))}` : "";
            parts.push(`<div class="lrn-tip">${ic("info")}
                <span>${esc(T("scNotOnScreen"))}${soon}</span></div>`);
        }

        if (step.tip) {
            parts.push(`<div class="lrn-tip">${ic("lightbulb")}
                <span>${esc(tx(step.tip))}</span></div>`);
        }
        return parts.join("");
    }

    _toolsStr() {
        if (this.state.blocked && this.state.blocked.kind === "slow") {
            return `<div class="lrn-ctools">
                <button class="lrn-btn sm pri" data-act="s-retry"
                    >${ic("rotate-ccw")}${esc(T("retry"))}</button>
                <button class="lrn-btn sm ghost" data-act="s-leave"
                    >${ic("x")}${esc(T("exit"))}</button>
            </div>`;
        }
        if (this.state.blocked) {
            return `<div class="lrn-ctools">
                <button class="lrn-btn sm pri" data-act="s-practice"
                    >${ic("flask")}${esc(T("scTryPractice"))}</button>
                <button class="lrn-btn sm ghost" data-act="s-leave"
                    >${ic("x")}${esc(T("exit"))}</button>
            </div>`;
        }
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
        if (this.state.blocked) {
            const slow = this.state.blocked.kind === "slow";
            return `<div class="lrn-schead"><span class="lrn-chip">${ic(slow ? "hourglass" : "lock")}${
                esc(T(slow ? "scSlowT" : "scNoAccessT"))}</span></div>`;
        }
        const counter = this.state.done
            ? ""
            : `<span class="lrn-scstep">${esc(T("step"))}${SP}${this.state.index + 1}${
                SP}${esc(T("of"))}${SP}${this.steps.length}</span>`;
        // LEARN v3 — the modes this walkthrough offers, as one switch. The
        // current one is the solid choice; the chip underneath still says
        // that this is the real screen.
        const label = { watch: "scWatch", try: "scTry", do: "scDo" };
        const icon = { watch: "play", try: "flask", do: "target" };
        const modes = (s.modes || []).length > 1 && !this.state.done
            ? `<span class="lrn-scmodes" role="group" aria-label="${esc(T("scSwitch"))}">${
                s.modes.map((m) => `<button class="lrn-scmode" data-act="s-mode" data-mode="${m}"
                    aria-pressed="${m === this.state.mode ? "true" : "false"}"
                    >${ic(icon[m])}${esc(T(label[m]))}</button>`).join("")}</span>`
            : `<span class="lrn-chip a">${ic(this.isWatch ? "play" : "target")}${
                esc(this.isWatch ? T("scWatch") : T("scDo"))}</span>`;
        // LEARN v3 — one segment per step; the finished ones take you back.
        const segs = this.state.done ? "" : `<div class="lrn-scsegs">${
            this.steps.map((st, i) => {
                const cls = i < this.state.index ? "done" : (i === this.state.index ? "cur" : "");
                return `<button class="lrn-scseg ${cls}" data-act="s-jump" data-i="${i}"
                    ${i < this.state.index ? "" : "disabled"}
                    title="${esc(i < this.state.index ? T("scJump") + " · " + tx(st.title) : tx(st.title))}"
                    aria-label="${esc(T("step"))}${SP}${i + 1}"></button>`;
            }).join("")}</div>`;
        return `
        <div class="lrn-schead">
            ${modes}
            <span class="lrn-chip">${ic("shield-check")}${esc(this.modeBadge)}</span>
            ${counter}
        </div>
        ${segs}`;
    }
}

registry.category("main_components").add("PbLearnScenarioOverlay", {
    Component: ScenarioOverlay,
});
