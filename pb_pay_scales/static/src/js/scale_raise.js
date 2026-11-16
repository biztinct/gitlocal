/** @odoo-module **/
/**
 * WDGAP S8-D (SC1) — "Raise the scale": one request that moves everybody on
 * a scale. Opened from the Scales tab as a wide side drawer.
 *
 *   1. The new table — from a date, by a percentage, a flat amount or typed.
 *   2. Who moves — quiet cards (Moves / Above step / Pinned / Cannot move /
 *      Left out), the people behind each, "Leave out" per person.
 *   3. What it costs — a month and a year, one line per currency (never added).
 *   4. One sign-off for the whole rise; take it back before it starts.
 *
 * Nothing is written to any contract from this screen: a draft is only the
 * request itself, and the wages move on the start date after the approval.
 * Rules kept from the Pay screen: icons from the shared `ic()` set; every
 * sentence on one line (PRD-3); the refusal ladder never reads
 * `error.message` (GR17).
 */
import { Component, onMounted, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.pay.scales";
const GROUPS = ["move", "above", "pinned", "cannot", "left_out"];

function parseNumber(text) {
    const clean = String(text === undefined || text === null ? "" : text)
        .replace(/[\s,]/g, "").replace(/[^0-9.\-]/g, "");
    if (clean === "" || clean === "-" || clean === ".") { return null; }
    const value = Number(clean);
    return Number.isFinite(value) ? value : null;
}

export class ScaleRaiseDrawer extends Component {
    static template = "pb_pay_scales.ScaleRaiseDrawer";
    static props = {
        scaleId: { type: Number },
        raiseId: { type: Number, optional: true },
        onClose: { type: Function },
        onChanged: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.state = useState({
            loading: true, busy: false, d: null, failed: "",
            form: { effective_date: "", method: "percent", pct: "", flat: "", new_base_rate: "", reason: "", typed: {} },
            group: "move", touched: false, seen: false,
        });
        onWillStart(() => this.start());
    }

    ic(name, size = 16) { return ic(name, size); }

    _msg(error, fallback) {
        const data = error && error.data;
        if (data && data.message) { return data.message; }
        const nested = error && error.message && error.message.data;
        if (nested && nested.message) { return nested.message; }
        return fallback;
    }
    _fail(error, fallback) {
        this.notif.add(this._msg(error, fallback), { type: "warning" });
    }

    async start() {
        try {
            const d = this.props.raiseId
                ? await this.orm.call(MODEL, "raise_read", [this.props.raiseId])
                : await this.orm.call(MODEL, "raise_save", [this.props.scaleId, {}, 0]);
            this.take(d);
            this.state.seen = Boolean(this.props.raiseId);
        } catch (error) {
            this.state.failed = this._msg(error, _t("The scale rise could not be opened just now."));
        }
        this.state.loading = false;
    }

    take(d) {
        this.state.d = d;
        const f = this.state.form;
        f.effective_date = d.effective_date || "";
        f.method = d.method || "percent";
        f.pct = d.pct ? String(d.pct) : "";
        f.flat = d.flat ? String(d.flat) : "";
        f.new_base_rate = d.new_base_rate ? String(d.new_base_rate) : "";
        f.reason = d.reason || "";
        const typed = {};
        for (const row of d.table || []) {
            for (const s of row.steps) {
                if (!s.old) { continue; }
                typed[row.grade_id + ":" + s.step] = this.isCoef ? (s.coefficient || 0) : (s.new || s.old);
            }
        }
        f.typed = typed;
        if (!this.groupRows(this.state.group).length) {
            this.state.group = GROUPS.find((g) => (d.counts || {})[g]) || "move";
        }
    }

    get d() { return this.state.d || {}; }
    get cur() { return (this.d.scale && this.d.scale.currency) || {}; }
    get isCoef() { return Boolean(this.d.scale && this.d.scale.mode === "coefficient"); }
    get editable() { return Boolean(this.d.editable); }
    get counts() { return this.d.counts || {}; }
    get table() { return this.d.table || []; }
    get steps() {
        const n = (this.d.scale && this.d.scale.step_count) || 0;
        return Array.from({ length: n }, (_v, i) => i + 1);
    }
    get title() { return this.d.name ? _t("Scale rise %s", this.d.name) : _t("Raise the scale"); }
    get stateClass() { return "pbrs-state is-" + (this.d.tone || "muted"); }
    groupRows(key) { return ((this.d.groups || {})[key]) || []; }
    get rows() { return this.groupRows(this.state.group); }
    groupLabel(key) {
        return {
            move: _t("Moves"), above: _t("Above step"), pinned: _t("Pinned"),
            cannot: _t("Cannot move"), left_out: _t("Left out"),
        }[key] || "";
    }
    groupSub(key) {
        return {
            move: _t("Their pay goes up to the new step."),
            above: _t("Already paid the new step or more. Their pay stays as it is."),
            pinned: _t("Paid differently on purpose. Left alone."),
            cannot: _t("Cannot be moved by this rise. The reason is beside each name."),
            left_out: _t("You took them out of this rise."),
        }[key] || "";
    }
    groupClass(key) {
        const n = this.counts[key] || 0;
        return {
            "pay-hc": true, "pbs-hc": true, "pbrs-card": true,
            "is-quiet": n === 0,
            "is-act": key === "move" && n > 0,
            "is-warn": key === "cannot" && n > 0,
            "is-on": this.state.group === key,
        };
    }
    pickGroup(key) { this.state.group = key; }
    get groups() { return GROUPS; }
    get sentenceUnplaced() {
        const n = this.d.unplaced || 0;
        return n === 1
            ? _t("1 person on these jobs is not placed on the scale yet, so the rise does not reach them.")
            : _t("%s people on these jobs are not placed on the scale yet, so the rise does not reach them.", n);
    }
    get pastLine() {
        const months = (this.d.paid_months || []).map((m) => m.label);
        const unique = [...new Set(months)];
        return _t("This rise starts in a month already paid (%s). After it is written, the pay team can re-work those months; nothing is paid back by itself.", unique.join(", "));
    }
    get baseLine() {
        return _t("Starts from the table %s. That version is kept exactly as it was.", this.d.base_label || "");
    }
    get waitingLine() { return _t("Waiting for %s.", this.d.waiting || ""); }
    get scheduledLine() {
        return _t("Approved. The new pay is written on %s. Until then it can be taken back and nobody's pay changes.", this.d.effective_label || "");
    }
    rowSub(row) {
        return _t("%(job)s · %(grade)s, step %(step)s", { job: row.job || "", grade: row.grade || "", step: row.step || "" });
    }
    costLine(row) { return _t("+%s a month", row.cost_label); }
    costMonth(c) { return _t("%s a month", c.month_label); }
    costYear(c) { return _t("%s for twelve months", c.year_label); }
    get resultLine() {
        return _t("Written for %(done)s. Not written for %(skipped)s.", { done: this.d.done || 0, skipped: this.d.skipped || 0 });
    }
    rowLine(row) {
        if (row.outcome === "move" || row.outcome === "left_out") {
            return row.old_label + "  →  " + row.new_label;
        }
        return row.old_label;
    }
    stepTone(status) {
        return { approved: "ok", done: "ok", open: "now", active: "now", pending: "wait", skipped: "muted", rejected: "bad", returned: "bad" }[status] || "wait";
    }

    // =========================================================== the form
    setForm(field, ev) {
        this.state.form[field] = ev.target.value;
        this.state.touched = true;
    }
    setMethod(method) {
        if (!this.editable) { return; }
        this.state.form.method = method;
        this.state.touched = true;
    }
    typedOf(gradeId, step) {
        const v = this.state.form.typed[gradeId + ":" + step];
        return v === undefined ? "" : v;
    }
    setTyped(gradeId, step, ev) {
        const value = parseNumber(ev.target.value);
        if (value === null || value < 0) { return; }
        this.state.form.typed[gradeId + ":" + step] = value;
        this.state.touched = true;
    }
    _vals() {
        const f = this.state.form;
        const typed = [];
        for (const [k, value] of Object.entries(f.typed)) {
            const [gid, step] = k.split(":").map(Number);
            typed.push(this.isCoef ? { grade_id: gid, step, coefficient: value } : { grade_id: gid, step, amount: value });
        }
        return {
            effective_date: f.effective_date || false, method: f.method,
            pct: parseNumber(f.pct) || 0, flat: parseNumber(f.flat) || 0,
            new_base_rate: parseNumber(f.new_base_rate) || 0, reason: f.reason || "", typed,
        };
    }
    async preview() {
        if (this.state.busy) { return; }
        this.state.busy = true;
        try {
            const d = await this.orm.call(MODEL, "raise_save", [this.props.scaleId, this._vals(), this.d.id]);
            this.take(d);
            this.state.seen = true;
            this.state.touched = false;
            if (this.props.onChanged) { this.props.onChanged(); }
        } catch (error) {
            this._fail(error, _t("The rise could not be worked out just now."));
        }
        this.state.busy = false;
    }
    async toggle(row, leaveOut) {
        if (!this.editable || this.state.busy) { return; }
        this.state.busy = true;
        try {
            const d = await this.orm.call(MODEL, "raise_toggle", [this.d.id, row.contract_id, leaveOut]);
            this.take(d);
        } catch (error) {
            this._fail(error, _t("This could not be saved just now."));
        }
        this.state.busy = false;
    }
    async act(verb) {
        if (this.state.busy) { return; }
        if (verb === "take_back" && !window.confirm(_t("Take this rise back? Nobody's pay has changed yet, and the new version of the scale goes with it."))) { return; }
        if (verb === "cancel" && !window.confirm(_t("Cancel this rise? Nothing is changed."))) { return; }
        this.state.busy = true;
        try {
            if (verb === "send" && this.state.touched) {
                const d = await this.orm.call(MODEL, "raise_save", [this.props.scaleId, this._vals(), this.d.id]);
                this.take(d);
                this.state.touched = false;
                if (!this.d.can_send) { this.state.busy = false; return; }
            }
            const res = await this.orm.call(MODEL, "raise_act", [this.d.id, verb]);
            if (verb === "rework") {
                await this.openRework(res.review_id);
            } else if (res.read) {
                this.take(res.read);
            }
            if (res.message) { this.notif.add(res.message, { type: "success" }); }
            if (this.props.onChanged) { this.props.onChanged(); }
        } catch (error) {
            this._fail(error, _t("That could not be done just now."));
        }
        this.state.busy = false;
    }
    async openRework(reviewId) {
        if (!reviewId) { return; }
        await this.action.doAction({
            type: "ir.actions.client", tag: "pb_pay_scales_open_rework",
            name: _t("Past-month re-work"), params: { review_id: reviewId },
        });
    }

    async close() {
        // A draft opened and never worked out is not kept.
        if (this.d.id && this.d.state === "draft" && !this.state.seen && !this.d.name) {
            try { await this.orm.call(MODEL, "raise_act", [this.d.id, "remove"]); } catch { /* kept */ }
            if (this.props.onChanged) { this.props.onChanged(); }
        }
        this.props.onClose();
    }
}

// ================================================== the re-work door (C-6)
// `pb_retro` is optional: its board is looked up in the actions registry when
// pressed, never imported, so a database without it loads none of its code.
let ReworkOpener = null;

function reworkOpener() {
    if (ReworkOpener) { return ReworkOpener; }
    const actions = registry.category("actions");
    if (!actions.contains("pb_retro_board")) { return null; }
    const Board = actions.get("pb_retro_board");
    ReworkOpener = class extends Board {
        setup() {
            super.setup(...arguments);
            const params = (this.props.action && this.props.action.params) || {};
            onMounted(async () => {
                if (params.review_id && this.state.allowed !== false) {
                    await this.openReview(params.review_id);
                }
            });
        }
    };
    actions.add("pb_pay_scales_rework_board", ReworkOpener, { force: true });
    return ReworkOpener;
}

registry.category("actions").add("pb_pay_scales_open_rework", (env, action) => {
    const params = action.params || {};
    if (!reworkOpener()) {
        env.services.notification.add(
            _t("Past-month re-work is not part of this database. The pay team can work out any difference by hand on the next pay run."),
            { type: "warning" });
        return;
    }
    return {
        type: "ir.actions.client", tag: "pb_pay_scales_rework_board",
        name: _t("Past-month re-work"), params: { review_id: params.review_id },
    };
});
