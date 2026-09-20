/** @odoo-module **/

import { Component, useState, onWillStart, onWillUpdateProps, onWillUnmount }
    from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";
import { _t } from "@web/core/l10n/translation";

import { STEP_META } from "./blueprint_steps";
import { agoFrom } from "./outputs_text";
import {
    blockedHeading, checksFraction, checksLine, decisionCount, decisionsEmpty,
    decisionsMore, decisionsNote, finishButton, finishNote, finishTiles,
    finishedNote, identityRows, optionalRow, packLine,
} from "./finish_text";

/**
 * Step 6 — everything you decided, on one page, and one button.
 *
 * Finishing marks the SETUP complete. It does not switch the configuration on
 * for real pay runs: that stays the existing, separately checked step, and the
 * line under the button says so — "Finish" that quietly starts paying people is
 * the single worst thing this screen could do.
 *
 * Three rules this step obeys:
 *
 * * **The server decides.** Every reason the button is disabled comes from
 *   `bp_finish_data`'s gate and is enforced again inside `bp_finish`. This
 *   component greys a button out; it never makes anything safe.
 * * **An open decision does not block.** Judgement calls are listed, counted
 *   and linked to the place that settles them — and a person may finish with
 *   every one of them still open. Only arithmetic and evidence block.
 * * **Nothing is a toast.** Every refusal is printed beside the button that
 *   refused, with the step that fixes it one click away.
 */
export class StepFinish extends Component {
    static template = "pb_blueprint.StepFinish";
    static props = {
        configId: { type: [Number, Boolean] },
        revision: { type: Number, optional: true },
        reloadKey: { type: Number, optional: true },
        // The footer's own primary button, asking this step to do the thing it
        // owns rather than keeping a second copy of the gate.
        runSignal: { type: Number, optional: true },
        // The shell opens the grid and shows the "setup complete" toast; this
        // step owns the call itself so a refusal is rendered where it happened.
        onFinished: { type: Function },
        onGo: { type: Function },            // (step, {tab, ruleId, task})
        onGrid: { type: Function },
        onDiscard: { type: Function },
        onRevision: { type: Function, optional: true },
        onChanged: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.state = useState({
            loading: true,
            error: "",
            data: null,
            busy: false,
            refusal: "",              // what the server said when Finish refused
            shown: { components: 0, formulas: 0, inputs: 0 },
        });

        onWillStart(() => this.load());
        onWillUpdateProps((next) => {
            if (next.reloadKey !== this.props.reloadKey
                    || next.configId !== this.props.configId) {
                this.load(next.configId);
            }
            if ((next.runSignal || 0) !== (this.props.runSignal || 0)) {
                this.onFinish();
            }
        });
        onWillUnmount(() => {
            if (this._raf) { cancelAnimationFrame(this._raf); }
        });
    }

    // ==================================================================
    // Loading
    // ==================================================================
    async rpc(method, args) {
        try {
            return await this.orm.call("pb.blueprint.studio", method, args || []);
        } catch (e) {
            const reason = (e && e.data && e.data.message) || (e && e.message) || "";
            return { ok: false, reason };
        }
    }

    async load(configId) {
        const cid = configId === undefined ? this.props.configId : configId;
        if (!cid) { return; }
        const res = await this.rpc("bp_finish_data", [cid]);
        this.state.loading = false;
        if (!res || !res.ok) {
            this.state.error = (res && res.reason)
                || _t("This page could not be read. Reload to try again.");
            return;
        }
        this.state.error = "";
        this.state.data = res;
        if (res.revision !== undefined && this.props.onRevision) {
            this.props.onRevision(res.revision);
        }
        this._countUp(res.counts || {});
    }

    /**
     * The three tiles run up to their value over 520ms.
     *
     * `prefers-reduced-motion` is honoured HERE as well as in the stylesheet:
     * a count driven by `requestAnimationFrame` is not a CSS transition and the
     * media query cannot reach it, so somebody who asked their system to stop
     * moving things would still have seen the digits spin.
     */
    _countUp(counts) {
        const to = {
            components: Number(counts.components || 0),
            formulas: Number(counts.formulas || 0),
            inputs: Number(counts.inputs || 0),
        };
        const keys = ["components", "formulas", "inputs"];
        if (this._raf) { cancelAnimationFrame(this._raf); }
        if (this.stillness) {
            for (const key of keys) { this.state.shown[key] = to[key]; }
            return;
        }
        const from = { ...this.state.shown };
        const start = performance.now();
        const span = 520;
        const tick = (now) => {
            const t = Math.min(1, (now - start) / span);
            const eased = 1 - Math.pow(1 - t, 3);
            for (const key of keys) {
                this.state.shown[key] = Math.round(
                    from[key] + (to[key] - from[key]) * eased);
            }
            this._raf = t < 1 ? requestAnimationFrame(tick) : null;
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

    // ==================================================================
    // Small readers the template uses
    // ==================================================================
    ic(name, size = 16) { return ic(name, size); }

    get meta() { return STEP_META.finish; }
    get data() { return this.state.data || {}; }
    get finished() { return !!this.data.finished; }
    get editable() { return !!this.data.editable; }
    get identity() { return this.data.identity || {}; }

    get tiles() {
        return finishTiles(this.data.counts).map((tile) => ({
            ...tile, shown: this.state.shown[tile.key],
        }));
    }

    get rows() { return identityRows(this.identity); }
    get chips() { return this.identity.situations || []; }
    get pack() { return packLine(this.identity); }

    get decisions() { return this.data.decisions || []; }
    get decisionsTotal() { return Number(this.data.decisions_total || 0); }
    get decisionChip() { return decisionCount(this.decisionsTotal); }
    get decisionsNote() { return decisionsNote(); }
    get decisionsEmpty() { return decisionsEmpty(); }
    get decisionsMore() {
        return decisionsMore(this.decisions.length, this.decisionsTotal);
    }

    get checks() { return checksLine(this.data.checks || {}); }
    get checksFraction() { return checksFraction(this.data.checks || {}); }
    get everRun() { return !!(this.data.checks || {}).ever_run; }

    get optional() {
        return (this.data.optional || []).map((row) => optionalRow(row));
    }

    get gate() { return this.data.gate || { ok: false, reasons: [] }; }
    get button() { return finishButton(this.gate, this.finished); }
    get blockedHeading() { return blockedHeading(this.gate); }
    get note() { return finishNote(); }

    get finishedNote() {
        const id = this.identity;
        return finishedNote(id.finished_by || "", agoFrom(id.finished_at || ""));
    }

    // ==================================================================
    // What a person can press
    // ==================================================================
    /** A "Go" link: the step that settles this decision, already scoped. */
    go(item) {
        this.props.onGo(item.step || "rules", {
            tab: item.tab || "",
            ruleId: item.rule_id || 0,
            task: item.task || "",
        });
    }

    async onFinish() {
        if (this.state.busy) { return; }
        if (this.finished) {
            this.props.onGrid(this.props.configId);
            return;
        }
        this.state.busy = true;
        this.state.refusal = "";
        const res = await this.rpc("bp_finish", [this.props.configId]);
        this.state.busy = false;
        if (!res || !res.ok) {
            // The refusal is printed on the page, beside the button that
            // refused. The server may also have sent the whole gate — take it,
            // so the list of what is left says the same thing the button does.
            this.state.refusal = (res && res.reason)
                || _t("The setup could not be finished.");
            if (res && res.gate) { this.data.gate = res.gate; }
            await this.load();
            return;
        }
        this.props.onFinished(this.props.configId);
    }

    /** "Revisit the setup" — a finished journey, opened for editing again. */
    async onReopen() {
        const res = await this.rpc("bp_reopen", [this.props.configId]);
        if (!res || !res.ok) {
            this.notif.add((res && res.reason)
                || _t("The setup could not be reopened."), { type: "warning" });
            return;
        }
        await this.load();
        if (this.props.onChanged) { this.props.onChanged({ ok: true }); }
        this.props.onGo("start", {});
    }

    onDiscard() { this.props.onDiscard(); }
}
