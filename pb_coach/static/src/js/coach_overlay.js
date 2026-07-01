/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { coachIcon } from "./coach_icons";

const CARD_W = 344;               // fixed coach-card width (px)
const AUTOPLAY_DWELL = 3200;      // ms an autoplay step lingers before advancing
const WAIT_TIMEOUT = 9000;        // ms to poll for a step target before giving up
const WAIT_POLL = 120;            // ms between target polls

/**
 * CoachOverlay — globally mounted (main_components). Renders, above the whole
 * app: the spotlight, the animated pointer, the coach card, a first-run welcome
 * modal, a "Getting Started" launcher FAB and an ephemeral-demo-data chip.
 */
export class CoachOverlay extends Component {
    static template = "pb_coach.CoachOverlay";
    static props = {};

    setup() {
        this.coach = useService("pb_coach");
        this.state = useState(this.coach.state);      // shared reactive tour state
        this.cardRef = useRef("card");

        // local presentation state
        this.ui = useState({
            isDemo: false,
            showLauncher: false,
            launcherOpen: false,
            showDisclaimer: false,
            resolving: false,        // waiting for a target to appear
            hasTarget: false,
            hole: { top: 0, left: 0, w: 0, h: 0 },
            card: { top: 0, left: 0, place: "bottom" },
            pointer: { top: 0, left: 0, rot: 0 },
        });

        this._targetEl = null;
        this._stepKey = null;
        this._raf = null;
        this._clickCleanup = null;
        this._autoplayT = null;
        this._autoplayProgressEl = null;
        this._destroyed = false;

        this._onKey = this._onKey.bind(this);
        this._loop = this._loop.bind(this);

        onMounted(async () => {
            try { this.ui.isDemo = await user.hasGroup("pb_demo.group_payobook_demo"); }
            catch (e) { this.ui.isDemo = false; }

            this.ui.showLauncher = true;
            this.ui.showDisclaimer = this.ui.isDemo && !this._flag("disclaimer_off");

            // First-run welcome for demo/trial users.
            if (this.ui.isDemo && !this._flag("welcomed")) {
                this.coach.openWelcome();
            }
            window.addEventListener("keydown", this._onKey);
            this._raf = requestAnimationFrame(this._loop);
        });

        onWillUnmount(() => {
            this._destroyed = true;
            if (this._raf) cancelAnimationFrame(this._raf);
            this._detachClick();
            this._clearAutoplay();
            window.removeEventListener("keydown", this._onKey);
        });
    }

    // ---- persistence flags (localStorage; read-only-safe) --------------------
    _flag(k) { try { return localStorage.getItem("pb_coach_" + k) === "1"; } catch (e) { return false; } }
    _setFlag(k, v) { try { localStorage.setItem("pb_coach_" + k, v ? "1" : "0"); } catch (e) { /* ignore */ } }

    icon(name, size) { return coachIcon(name, size); }

    get step() { return this.state.steps[this.state.index] || null; }
    get isLast() { return this.state.index >= this.state.steps.length - 1; }
    get progressPct() {
        const n = this.state.steps.length || 1;
        return Math.round(((this.state.index + 1) / n) * 100);
    }

    // ---- inline-style getters (kept in JS to avoid brittle t-attf strings) ---
    get spotStyle() {
        const h = this.ui.hole;
        return `top:${h.top}px;left:${h.left}px;width:${h.w}px;height:${h.h}px;`;
    }
    get pointerStyle() {
        const p = this.ui.pointer;
        return `top:${p.top}px;left:${p.left}px;transform:translate(-50%,-50%) rotate(${p.rot}deg);`;
    }
    get cardStyle() {
        if (!this.ui.hasTarget) return "";
        return `top:${this.ui.card.top}px;left:${this.ui.card.left}px;`;
    }
    get cardPlaceClass() {
        return this.ui.hasTarget ? "pbc-card--" + this.ui.card.place : "pbc-card--center";
    }

    // =========================================================================
    //  Main loop — one rAF; cheap geometry each frame, heavy step-setup on change
    // =========================================================================
    _loop() {
        if (this._destroyed) return;
        if (this.state.active) {
            const key = `${this.state.tourId}#${this.state.index}#${this.state.mode}`;
            if (key !== this._stepKey) {
                this._stepKey = key;
                this._enterStep();            // async; not awaited
            } else if (this._targetEl) {
                this._measure();
            }
        } else if (this._stepKey !== null) {
            // tour just ended / stopped
            this._stepKey = null;
            this._targetEl = null;
            this._detachClick();
            this._clearAutoplay();
        }
        this._raf = requestAnimationFrame(this._loop);
    }

    async _enterStep() {
        this._detachClick();
        this._clearAutoplay();
        this.ui.hasTarget = false;
        this.ui.resolving = true;
        this._targetEl = null;

        const step = this.step;
        if (!step) { this.ui.resolving = false; return; }

        // Optional cross-screen jump before resolving the target.
        if (step.navigate) {
            await this.coach.navigate(step.navigate);
        }

        const sel = step.waitFor || step.selector;
        const el = sel ? await this._waitFor(sel, step) : null;

        // Guard: a late frame may already have moved us to another step.
        if (!this.state.active || this.step !== step) return;

        this.ui.resolving = false;

        if (el) {
            this._targetEl = el;
            this.ui.hasTarget = true;
            try { el.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" }); } catch (e) { /* ignore */ }
            this._measure();

            if (step.action === "click") {
                if (this.state.mode === "interactive") {
                    this._attachClick(el);
                } else {
                    this._autoplayClick(el);
                }
                return;
            }
        } else {
            // No target — show a centered card so the tour never dead-ends.
            this._targetEl = null;
            this.ui.hasTarget = false;
        }

        if (this.state.mode === "autoplay") {
            this._autoplayAdvance();
        }
    }

    // Poll until the selector resolves to a visible element (or timeout).
    _waitFor(selector, step) {
        return new Promise((resolve) => {
            const deadline = Date.now() + (step.timeout || WAIT_TIMEOUT);
            const tick = () => {
                if (this._destroyed || !this.state.active || this.step !== step) return resolve(null);
                let el = null;
                try { el = document.querySelector(selector); } catch (e) { el = null; }
                // NB: offsetParent is null for position:fixed elements (e.g. the
                // PayAI pill), so measure the box instead.
                if (el) {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) return resolve(el);
                }
                if (Date.now() > deadline) return resolve(el || null);
                setTimeout(tick, WAIT_POLL);
            };
            tick();
        });
    }

    // ---- geometry -----------------------------------------------------------
    _measure() {
        const el = this._targetEl;
        if (!el || !el.isConnected) { this.ui.hasTarget = false; return; }
        const r = el.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) { this.ui.hasTarget = false; return; }
        const step = this.step || {};
        const pad = step.pad != null ? step.pad : 8;
        const vw = window.innerWidth, vh = window.innerHeight;

        const hole = {
            top: Math.max(4, r.top - pad),
            left: Math.max(4, r.left - pad),
            w: Math.min(vw - 8, r.width + pad * 2),
            h: Math.min(vh - 8, r.height + pad * 2),
        };
        this.ui.hole = hole;

        // Card placement: prefer below, else above, else right, clamped to viewport.
        const cardH = (this.cardRef.el && this.cardRef.el.offsetHeight) || 210;
        const gap = 18;
        let place = "bottom";
        let top = hole.top + hole.h + gap;
        let left = hole.left + hole.w / 2 - CARD_W / 2;

        if (top + cardH > vh - 12) {
            // not enough room below → try above
            if (hole.top - gap - cardH > 12) {
                place = "top";
                top = hole.top - gap - cardH;
            } else {
                // side-place to the right (or left)
                place = hole.left + hole.w + gap + CARD_W < vw - 12 ? "right" : "left";
                top = Math.max(12, Math.min(hole.top, vh - cardH - 12));
                left = place === "right" ? hole.left + hole.w + gap : hole.left - gap - CARD_W;
            }
        }
        left = Math.max(12, Math.min(left, vw - CARD_W - 12));
        top = Math.max(12, Math.min(top, vh - cardH - 12));
        this.ui.card = { top, left, place };

        // Animated pointer — sits just outside the hole, aimed inward.
        let px, py, rot;
        if (place === "bottom") { px = hole.left + hole.w / 2; py = hole.top + hole.h + 6; rot = -90; }
        else if (place === "top") { px = hole.left + hole.w / 2; py = hole.top - 30; rot = 90; }
        else if (place === "right") { px = hole.left + hole.w + 6; py = hole.top + hole.h / 2; rot = 180; }
        else { px = hole.left - 30; py = hole.top + hole.h / 2; rot = 0; }
        this.ui.pointer = { top: py, left: px, rot };
    }

    // ---- interactive click bridge ------------------------------------------
    _attachClick(el) {
        const handler = () => {
            this._detachClick();
            // let the app's own handler run + navigate, then advance
            setTimeout(() => { if (this.state.active) this.coach.next(); }, 420);
        };
        el.addEventListener("click", handler, { once: true, capture: true });
        this._clickCleanup = () => el.removeEventListener("click", handler, { capture: true });
    }
    _detachClick() { if (this._clickCleanup) { try { this._clickCleanup(); } catch (e) { /* */ } this._clickCleanup = null; } }

    // ---- autoplay -----------------------------------------------------------
    _autoplayClick(el) {
        this._autoplayT = setTimeout(() => {
            try { el.click(); } catch (e) { /* ignore */ }
            this._autoplayT = setTimeout(() => { if (this.state.active) this.coach.next(); }, 520);
        }, AUTOPLAY_DWELL);
    }
    _autoplayAdvance() {
        this._autoplayT = setTimeout(() => { if (this.state.active) this.coach.next(); }, AUTOPLAY_DWELL);
    }
    _clearAutoplay() { if (this._autoplayT) { clearTimeout(this._autoplayT); this._autoplayT = null; } }

    // =========================================================================
    //  User actions (bound in template)
    // =========================================================================
    onNext() {
        // For a "click" step, advancing via the card should do the same thing as
        // clicking the real target (e.g. open the pay-run wizard) so the next
        // step's anchor actually exists. Detach the one-shot listener first so we
        // don't double-advance.
        const step = this.step;
        if (step && step.action === "click" && this._targetEl && this._targetEl.isConnected) {
            this._detachClick();
            try { this._targetEl.click(); } catch (e) { /* ignore */ }
        }
        this.coach.next();
    }
    onBack() { this.coach.back(); }
    onSkip() { this.coach.stop(); }
    toggleMode() {
        this.coach.setMode(this.state.mode === "autoplay" ? "interactive" : "autoplay");
        this._stepKey = null; // force re-entry so listeners/timers reset for the mode
    }

    // welcome modal
    startHero(mode) {
        this._setFlag("welcomed", true);
        this.coach.start("hero_path", { mode: mode || "interactive" });
    }
    dismissWelcome() {
        this._setFlag("welcomed", true);
        this.coach.closeWelcome();
    }

    // launcher FAB
    toggleLauncher() { this.ui.launcherOpen = !this.ui.launcherOpen; }
    launch(tourId) {
        this.ui.launcherOpen = false;
        this.coach.start(tourId, { mode: "interactive" });
    }
    get tourList() { return this.coach.list(); }

    // disclaimer chip
    dismissDisclaimer() { this._setFlag("disclaimer_off", true); this.ui.showDisclaimer = false; }
    requestCustomDemo() {
        window.open("mailto:hello@payobook.com?subject=Request%20a%20personalised%20Payobook%20demo", "_blank");
    }

    _onKey(ev) {
        if (!this.state.active) return;
        if (ev.key === "Escape") { this.coach.stop(); }
        else if (ev.key === "ArrowRight") { this.coach.next(); }
        else if (ev.key === "ArrowLeft") { this.coach.back(); }
    }
}

registry.category("main_components").add("PbCoachOverlay", { Component: CoachOverlay });
