/** @odoo-module **/
/**
 * WDGAP S8-A — the hire screens open with the wage filled from the scale.
 *
 * Patched, never edited (lane rule): People › Add a contract
 * (`ContractWizard`) and People › Add employee (`OnboardWizard`). Under the
 * wage box one line says where the figure came from ("₫6,900,000 — Senior
 * associate, step 1 of the Retail store scale"). A typed figure that is a
 * step keeps the person on the scale; any other figure wins, and a small
 * question asks why, so the contract is "Pinned" with that reason.
 *
 * The server does the same on its own for an EMPTY wage box (see
 * `models/joiners.py`), so a hire that skips this screen still starts on the
 * scale. Nothing is written by this file.
 */
import { useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ContractWizard } from "@pb_people_advanced/js/contract_wizard";
import { OnboardWizard } from "@pb_people_advanced/js/onboard_wizard";

const MODEL = "pb.pay.scales";

/**
 * What both screens share. `this` is the wizard. A FACTORY, so each class is
 * patched with its own object: `patch()` re-parents the object it is given,
 * and a method that calls `super` must be written in the very object literal
 * that is patched (copying it to another object keeps its old `super`, which
 * broke `setup` in the first walk).
 */
const hintMethods = () => ({
    get pbsHint() {
        return this.pbs.hint || null;
    },
    get pbsTypedStep() {
        const hint = this.pbsHint;
        const typed = Number(this.state.form.wage || 0);
        if (!hint || !hint.found || !typed) { return 0; }
        const row = (hint.steps || []).find((s) => Math.abs(s.amount - typed) < 0.005);
        return row ? row.step : 0;
    },
    get pbsOff() {
        const hint = this.pbsHint;
        return Boolean(hint && hint.found && Number(this.state.form.wage || 0) > 0 && !this.pbsTypedStep);
    },
    get pbsOnLine() {
        const step = this.pbsTypedStep;
        if (!step || step === 1) { return ""; }
        return _t("Step %(step)s of %(grade)s on %(scale)s.", { step, grade: this.pbsHint.grade, scale: this.pbsHint.scale });
    },
    get pbsOffLine() {
        return _t("This is not a step of the scale. The contract will be pinned at this pay. Why is it different?");
    },
    get pbsReasons() {
        return ((this.pbsHint && this.pbsHint.reasons) || []).filter((r) => r.value !== "typed");
    },
    onPbsReason(ev) {
        this.state.form.pb_scale_pin_reason = ev.target.value || "";
    },
    pbsUseScale() {
        const hint = this.pbsHint;
        if (!hint || !hint.found) { return; }
        this.state.form.wage = hint.amount;
        this.state.form.pb_scale_pin_reason = "";
    },
    async pbsAsk(extra) {
        try {
            const hint = await this.orm.silent.call(MODEL, "joiner_suggest", [], extra);
            this.pbs.hint = hint;
            if (hint && hint.found && !Number(this.state.form.wage || 0)) {
                this.state.form.wage = hint.amount;
            }
        } catch {
            this.pbs.hint = null;
        }
    },
});

patch(ContractWizard.prototype, hintMethods());
patch(OnboardWizard.prototype, hintMethods());

patch(ContractWizard.prototype, {
    setup() {
        super.setup(...arguments);
        this.pbs = useState({ hint: null });
    },
    // The dialog's own read (`get_defaults`) carries the first hint.
    get pbsHint() {
        return this.pbs.hint || (this.state.defaults && this.state.defaults.scale_hint) || null;
    },
    async pickOne(row) {
        await super.pickOne(row);
        const hint = this.state.defaults && this.state.defaults.scale_hint;
        this.pbs.hint = hint || null;
        if (hint && hint.found && !Number(this.state.form.wage || 0)) {
            this.state.form.wage = hint.amount;
        }
    },
    onField(f, ev) {
        super.onField(f, ev);
        if (f === "date_start" && this.empId) {
            this.pbsAsk({ employee_id: this.empId, date_start: this.state.form.date_start || false });
        }
    },
});

patch(OnboardWizard.prototype, {
    setup() {
        super.setup(...arguments);
        this.pbs = useState({ hint: null });
    },
    onField(f, ev) {
        super.onField(f, ev);
        if (f === "job_id" || f === "date_start") {
            if (!this.state.form.job_id) { this.pbs.hint = null; return; }
            this.pbsAsk({ job_id: Number(this.state.form.job_id), date_start: this.state.form.date_start || false });
        }
    },
    next() {
        super.next();
        if (this.state.step === 3 && this.state.form.job_id && !this.pbs.hint) {
            this.pbsAsk({ job_id: Number(this.state.form.job_id), date_start: this.state.form.date_start || false });
        }
    },
});
