/** @odoo-module **/
/* =============================================================================
   The live capstone runner.

   WHAT IT IS
   ----------
   A slim card docked to the bottom-left of the REAL product, carrying one step
   at a time. It mounts beside the Coach in the web-client shell, so it survives
   the navigation its own steps ask for.

   WHAT IT WILL NOT DO, AND HOW YOU CAN TELL
   -----------------------------------------
   It never performs a product action and it never blocks one. There is exactly
   ONE content-bearing orm call in this file — `learn.live.live_check` — and
   that method is read-only on the server (models/learn_live.py, guarded by a
   contract check; it lived on `learn.mission` until Phase 1a deleted that
   model). The card patches no product component, synthesises no click and
   disables no button: a learner can ignore every word of it and use Payobook
   normally, and a learner who follows it presses Payobook's own controls.

   `nav` deep-links, and that IS an action — a deliberate one, sanctioned
   because the alternative is telling somebody to go and find a screen. It is
   resolved through the same screen entry the Coach grounds on, so the runner
   and the Coach can never disagree about what a screen is.

   POLLING
   -------
   10 seconds, and only while a mission is open and the current step is one the
   server can answer. Stops on ack, on completion, on leaving and on unmount.
   There is no polling anywhere else in this module.
   ========================================================================== */
import { Component, markup, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

import { RT, T, tx, esc, ic } from "../engine/runtime";
/* The glossary hovercard. `gtx` is the ONE raw-insertion wrapper in this
   module, and a mission step's `detail` is an authored body exactly like a
   lesson step's — the Journey has rendered it with `gtx` since Phase 2 and
   this card was still printing its `<b>` tags as text (ledger, accepted nit).
   Aligned rather than re-decided: `detail` is the authored HTML, the
   `instruction` is a title and stays escaped, which is what journey.js does. */
import { gtx, setGlossary, installGlossary } from "../engine/glossary";
import { loadContent, composeScreens } from "../content/content_loader";
import { LiveState } from "./live_state";

const POLL_MS = 10000;

export class LiveHost extends Component {
    static template = "pb_learn.LiveHost";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            running: !!LiveState.current,
            step: LiveState.current ? LiveState.current.step : 0,
            minimised: !!(LiveState.current && LiveState.current.minimised),
            checking: false,
            result: null,          // {ok, note} from the last live_check
            lang: RT.lang,
        });

        this.mission = null;       // the mission dict from the content plane
        this.missions = null;      // null = not loaded yet, [] = loaded, empty
        this.screens = [];         // composed screens, for nav deep links
        this._timer = null;

        // NOT fetched on mount. This component is on every screen for every
        // user, and almost none of them will ever run a capstone — two bundle
        // round-trips on every page load to render nothing is a cost the whole
        // product pays for a feature one tenant uses. Loaded the first time a
        // mission is actually running, and re-checked on every state change so
        // a mission started after mount still finds its content.
        onWillStart(async () => {
            await this._sync();
        });

        this._unsubscribe = LiveState.subscribe(() => this._sync());
        onWillUnmount(() => {
            this._unsubscribe();
            this._stopPolling();
        });
    }

    // ------------------------------------------------------------ plumbing
    /** Fetch the content this runner needs, once, and only if it is needed.
     *
     *  Two round trips became one RPC plus a shared, memoised asset fetch: the
     *  Coach is mounted on the same page and has already asked for the content
     *  plane, so in practice this costs the bootstrap call and nothing else. */
    async _load() {
        if (this.missions) {
            return;
        }
        try {
            const [content, runtime] = await Promise.all([
                loadContent(),
                this.orm.call("learn.runtime", "bootstrap", []),
            ]);
            RT.tokens = runtime.tokens || RT.tokens;
            RT.chrome = content.chrome || RT.chrome;
            this.missions = content.missions || [];
            this.screens = composeScreens(content, runtime);
            // The hovercard's table and its one delegated listener. The Coach
            // installs the same pair from the same content, and both calls are
            // idempotent — but a capstone can be resumed on a page where the
            // drawer was never opened, and a card that cannot be reached is a
            // definition nobody reads.
            setGlossary(content.glossary || []);
            installGlossary();
        } catch {
            // A runner that cannot load must not break the screen it sits on.
            this.missions = [];
        }
    }

    async _sync() {
        const cur = LiveState.current;
        if (cur) {
            await this._load();
        }
        this.state.running = !!cur;
        this.state.step = cur ? cur.step : 0;
        this.state.minimised = !!(cur && cur.minimised);
        this.mission = cur
            ? (this.missions || []).find((m) => m.key === cur.mission) || null
            : null;
        this.state.result = null;
        this._schedule();
    }

    get steps() {
        return this.mission ? this.mission.steps || [] : [];
    }

    get current() {
        return this.steps[this.state.step] || null;
    }

    get isLast() {
        return this.state.step >= this.steps.length - 1;
    }

    /** Only a step the SERVER can answer is worth polling for. */
    _schedule() {
        this._stopPolling();
        const step = this.current;
        if (!this.state.running || this.state.minimised || !step || !step.check_key) {
            return;
        }
        this._timer = window.setInterval(() => this.check(true), POLL_MS);
    }

    _stopPolling() {
        if (this._timer) {
            window.clearInterval(this._timer);
            this._timer = null;
        }
    }

    // ------------------------------------------------------------- actions
    async check(quiet) {
        const step = this.current;
        if (!step || !step.check_key || this.state.checking) {
            return;
        }
        if (!quiet) {
            this.state.checking = true;
        }
        try {
            const res = await this.orm.call("learn.live", "live_check",
                                            [this.mission.key, step.key]);
            this.state.result = res;
            // A pass advances; a fail says why and leaves the learner exactly
            // where they are. Neither branch touches a product record.
            if (res && res.ok) {
                this._advance();
            }
        } catch {
            // A failed check must never look like a passed one.
            this.state.result = null;
        } finally {
            this.state.checking = false;
        }
    }

    ackStep() {
        const step = this.current;
        if (!step) {
            return;
        }
        LiveState.ack(step.key);
        this._advance();
    }

    _advance() {
        if (this.isLast) {
            this.finish();
            return;
        }
        LiveState.setStep(this.state.step + 1);
    }

    back() {
        if (this.state.step > 0) {
            LiveState.setStep(this.state.step - 1);
        }
    }

    async finish() {
        const key = this.mission ? this.mission.key : null;
        this._stopPolling();
        LiveState.stop();
        if (!key) {
            return;
        }
        // Learner state only — progress and confidence. The same two models the
        // fixture runner touches, and the same two the isolation test allows.
        try {
            await this.orm.call("learn.progress", "record",
                                ["mission:" + key, { state: "done" }]);
            await this.orm.call("learn.confidence", "award", [key, false]);
        } catch {
            // Losing a tick is not worth an error dialog over a finished run.
        }
    }

    leave() {
        this._stopPolling();
        LiveState.stop();
    }

    toggleMinimised() {
        LiveState.setMinimised(!this.state.minimised);
    }

    /** Deep-link to the screen a step names, through the composed screen. */
    openScreen() {
        const step = this.current;
        if (!step || !step.nav) {
            return;
        }
        const screen = this.screens.find((s) => s.key === step.nav);
        if (!screen) {
            return;
        }
        if (screen.own_xmlid) {
            this.action.doAction(screen.own_xmlid);
        } else if (screen.own_tag) {
            this.action.doAction({ type: "ir.actions.client", tag: screen.own_tag });
        }
    }

    // -------------------------------------------------------------- render
    get title() {
        return this.mission ? tx(this.mission.name) : "";
    }

    /* Chrome through T(), never hard-coded in the template: the card sits on
       the product, where a learner may flip language at any moment, and a
       button that stayed English beside a Vietnamese step would be the one
       thing on screen that did not follow. */
    get liveBadge() { return T("liveBadge"); }
    get backLabel() { return T("back"); }
    get openScreenLabel() { return T("liveOpenScreen"); }
    get checkNowLabel() { return T("liveCheckNow"); }
    get checkingLabel() { return T("liveChecking"); }
    get ackLabel() { return T("liveAck"); }
    get nextLabel() { return T("liveNext"); }
    get finishLabel() { return T("liveFinish"); }
    get leaveLabel() { return T("liveLeave"); }
    get minimiseLabel() { return T("liveMinimise"); }

    get stepLabel() {
        return T("step") + " " + (this.state.step + 1) + " " + T("of") + " " + this.steps.length;
    }

    // t-out renders a plain string as TEXT — the card must be handed markup()
    // or it paints its own source. Same rule as coach.js / journey.js.
    get bodyHTML() {
        return markup(this._bodyStr());
    }

    _bodyStr() {
        const step = this.current;
        if (!step) {
            return "";
        }
        const consequence = step.is_consequence && this.mission.consequence
            ? `<div class="lrn-lvconseq">
                   <h4>${ic("alert-triangle")}${esc(tx(this.mission.consequence.title))}</h4>
                   <dl>
                       <dt>${esc(T("scope"))}</dt><dd>${esc(tx(this.mission.consequence.scope))}</dd>
                       <dt>${esc(T("reversible"))}</dt><dd>${esc(tx(this.mission.consequence.reversible))}</dd>
                       <dt>${esc(T("verify"))}</dt><dd>${esc(tx(this.mission.consequence.verify))}</dd>
                   </dl>
               </div>`
            : "";
        const result = this.state.result
            ? `<p class="lrn-lvnote ${this.state.result.ok ? "ok" : "wait"}">${
                ic(this.state.result.ok ? "check-circle" : "clock")}<span>${
                esc(tx(this.state.result.note))}</span></p>`
            : (step.check_key
                ? `<p class="lrn-lvnote wait">${ic("clock")}<span>${
                    esc(T("liveWaiting"))}</span></p>`
                : "");
        const hint = step.hint
            ? `<p class="lrn-lvhint">${ic("lightbulb")}<span>${esc(tx(step.hint))}</span></p>`
            : "";
        return `
            <h3>${esc(tx(step.instruction))}</h3>
            ${step.detail ? `<p class="lrn-lvdetail">${gtx(step.detail)}</p>` : ""}
            ${consequence}
            ${result}
            ${hint}`;
    }
}
