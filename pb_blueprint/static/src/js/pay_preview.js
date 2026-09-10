/** @odoo-module **/

import { Component, useState, onWillUpdateProps, onWillUnmount } from "@odoo/owl";
import { ic } from "@pb_import_kit/js/import_icons";
import { _t } from "@web/core/l10n/translation";
import { fmtShort, fmtFull, deltaLabel } from "./blueprint_steps";

/**
 * "See it in someone's pay" — the hero.
 *
 * The point of the whole journey is that a configuration is not an abstraction:
 * it is somebody's take-home pay, and you can watch it change. So the number is
 * ANIMATED (it counts from the old value to the new one over 420ms) and the
 * change is CHIPPED ("+1.20m") for four seconds. Motion with a purpose: it
 * tells you that what you just did had an effect, and how big.
 *
 * Before the draft exists the panel is not blank and it is not a spinner: it is
 * the same layout with a dotted outline and a sentence saying what will appear
 * there. An empty hero is a dead end on the very first screen.
 */
export class PayPreview extends Component {
    static template = "pb_blueprint.PayPreview";
    static props = {
        configId: { type: [Number, Boolean], optional: true },
        samples: { type: Array, optional: true },
        sampleId: { type: [Number, Boolean], optional: true },
        preview: { type: [Object, Boolean], optional: true },
        status: { type: String },          // "waiting" | "busy" | "live" | "error" | "empty"
        reason: { type: String, optional: true },
        currencyCode: { type: String, optional: true },
        onPickSample: { type: Function },
        onAdjust: { type: Function },
        onRetry: { type: Function },
        onAddSample: { type: Function },
    };

    setup() {
        this.state = useState({
            shown: null,       // the number currently painted
            delta: null,       // {text, up} or null
            // The bottom bar's disclosure, and it starts CLOSED. On a wide
            // screen this flag is ignored — the panel is always open there.
            // On a phone an open panel covered the whole step, so the journey
            // you came to walk was behind the answer to it; the bar still
            // carries the take-home figure, which is the fact worth pinning.
            open: false,
        });
        this._raf = null;
        this._deltaTimer = null;
        this._target = this._value(this.props);
        this.state.shown = this._target;
        onWillUpdateProps((next) => this._retarget(next));
        onWillUnmount(() => {
            if (this._raf) cancelAnimationFrame(this._raf);
            if (this._deltaTimer) clearTimeout(this._deltaTimer);
        });
    }

    ic(name, size = 16) { return ic(name, size); }

    _value(props) {
        const p = props.preview;
        if (!p || !p.take_home) return null;
        const v = p.take_home.value;
        return (v === null || v === undefined) ? null : Number(v);
    }

    /**
     * Count from where the number is now to where it has just become.
     *
     * `requestAnimationFrame`, not a CSS transition: the digits themselves have
     * to move, and easing them out (cubic) makes the last few frames read as
     * the number settling rather than as a jump.
     */
    _retarget(nextProps) {
        const to = this._value(nextProps);
        const from = this.state.shown;
        if (to === null) {
            this.state.shown = null;
            return;
        }
        if (from === null || from === to) {
            this.state.shown = to;
            this._target = to;
            return;
        }
        const chip = deltaLabel(from, to);
        if (chip) {
            this.state.delta = chip;
            if (this._deltaTimer) clearTimeout(this._deltaTimer);
            this._deltaTimer = setTimeout(() => { this.state.delta = null; }, 4000);
        }
        this._target = to;
        if (this._raf) cancelAnimationFrame(this._raf);
        // Somebody who has asked their system to stop moving things gets the
        // new number, not the journey to it. The stylesheet's blanket
        // `prefers-reduced-motion` rule cannot reach a count driven by
        // `requestAnimationFrame`, so it is asked here as well.
        if (this.stillness) {
            this.state.shown = to;
            return;
        }
        const start = performance.now();
        const span = 420;
        const tick = (now) => {
            const t = Math.min(1, (now - start) / span);
            const eased = 1 - Math.pow(1 - t, 3);
            this.state.shown = from + (to - from) * eased;
            if (t < 1) {
                this._raf = requestAnimationFrame(tick);
            } else {
                this.state.shown = to;
                this._raf = null;
            }
        };
        this._raf = requestAnimationFrame(tick);
    }

    /** True when this person has asked their system not to animate. */
    get stillness() {
        try {
            return !!(window.matchMedia
                && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
        } catch (e) {
            return false;
        }
    }

    // ---- what the panel says ------------------------------------------
    get headline() { return fmtShort(this.state.shown); }

    get currency() {
        const p = this.props.preview;
        return (p && p.currency && (p.currency.code || p.currency.symbol))
            || this.props.currencyCode || "";
    }

    get lines() {
        const p = this.props.preview;
        return (p && p.lines) || [];
    }

    full(value) { return fmtFull(value); }

    get sample() {
        const p = this.props.preview;
        return (p && p.sample) || null;
    }

    get initials() {
        const name = (this.sample && this.sample.name) || "";
        const parts = name.split(/[\s·]+/).filter(Boolean).slice(0, 2);
        return parts.map((w) => w[0].toUpperCase()).join("") || "?";
    }

    get pill() {
        switch (this.props.status) {
            case "live": return { cls: "live", text: _t("Live") };
            case "busy": return { cls: "busy", text: _t("Working…") };
            case "error": return { cls: "err", text: _t("Couldn't compute") };
            case "empty": return { cls: "wait", text: _t("No sample yet") };
            default: return { cls: "wait", text: _t("Waiting") };
        }
    }

    onPick(ev) {
        const id = Number(ev.target.value);
        if (id) this.props.onPickSample(id);
    }

    toggleOpen() { this.state.open = !this.state.open; }
}
