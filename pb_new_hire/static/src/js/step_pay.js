/** @odoo-module **/
/** Step 3 hosts the shared Pay Builder for the selected scheme.
 * Contract dates, band guidance and pay-scale choices belong to this step.
 */
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { PayBuilder } from "@pb_pay_builder/js/pay_builder";
import { icon, fmtDay, money, rich } from "./studio_util";

export class StepPay extends Component {
    static template = "pb_new_hire.StepPay";
    static props = { api: Object };
    static components = { PayBuilder };

    setup() {
        this.icon = icon;
        this.nh = useState(this.props.api.nh);
    }

    get d() { return this.nh.draft; }
    get api() { return this.props.api; }
    get cur() { return this.api.currency; }
    get dec() { return this.nh.decides; }
    get first() { return this.api.first; }
    err(field) { return this.nh.fieldErr[field] || ""; }
    get canPay() { return Boolean(this.d.department_id && this.d.payroll_country); }
    goRole() { this.api.go("role", this.d.department_id ? "payroll_country" : "department_id"); }

    // ------------------------------------------------------------ paid by
    get scheme() { return this.dec && this.dec.scheme; }
    get paidCls() { return this.scheme && this.scheme.match && !(this.dec && this.dec.problem) ? "" : "is-warn"; }
    get wagesIn() {
        return this.cur ? rich(_t("Wages are in %(code)s."), { code: this.cur.name }) : "";
    }

    get payRef() {
        return { scheme_id: this.scheme?.id || false, country: this.d.payroll_country,
                 date_start: this.d.date_start, name: this.d.name };
    }
    get payValues() {
        const suggested = this.scale?.found ? this.scale.amount : null;
        return { ...this.d.usual, wage: this.d.wage ?? suggested };
    }
    changePay(code, value) {
        if (code === "wage") this.api.set("wage", value);
        else this.api.setUsual(code, value);
    }
    acceptPay(answer) { this.api.acceptPay(answer); }

    // ------------------------------------------------------------ band and scale
    get band() { return this.nh.hint && this.nh.hint.band; }
    get bandNote() { return this.nh.hint && this.nh.hint.band_note; }
    get bandPos() {
        const b = this.band;
        const w = Number(this.d.wage) || 0;
        if (!b || !(b.max > b.min)) {
            return "left:50%";
        }
        const span = (b.max - b.min) / 0.7;
        const lo = b.min - span * 0.15;
        const pc = Math.max(2, Math.min(98, ((w - lo) / span) * 100));
        return `left:${pc}%`;
    }
    get bandChip() {
        const b = this.band;
        const w = Number(this.d.wage) || 0;
        const job = this.api.jobName || _t("this job");
        if (!w) {
            return { cls: "", text: _t("Band for %s", job) };
        }
        if (w < b.min) {
            return { cls: "pbnh-chip--warn", text: _t("Below the pay band for %s", job) };
        }
        if (w > b.max) {
            return { cls: "pbnh-chip--warn", text: _t("Above the pay band for %s", job) };
        }
        return { cls: "pbnh-chip--ok", text: _t("Inside the pay band for %s", job) };
    }
    get scale() { return this.nh.hint && this.nh.hint.scale; }
    get scaleEmpty() {
        const s = this.scale;
        return s && s.found && !(this.d.wage > 0)
            ? rich(_t("Leave it empty to use %(amount)s from the pay scale."), { amount: money(s.amount, this.cur) })
            : "";
    }
    get scaleOff() {
        const s = this.scale;
        return Boolean(s && s.found && this.d.wage > 0 && s.typed_off);
    }
    get reasons() { return ((this.scale && this.scale.reasons) || []).filter((r) => r.value !== "typed"); }
    onReason(ev) { this.api.set("pb_scale_pin_reason", ev.target.value || ""); }
    useScale() {
        const s = this.scale;
        if (s && s.found) {
            this.api.patch({ wage: s.amount, pb_scale_pin_reason: "" });
        }
    }

    // ------------------------------------------------------------ contract and trial
    setKind(kind) { this.api.set("contract_kind", kind); }
    /** P2: the employee category, asked only when there is a choice. */
    get cats() { return this.nh.cats || []; }
    get showCats() { return this.cats.length > 1; }
    get catSuggested() {
        const c = this.cats.find((x) => x.id === this.d.type_id);
        return Boolean(c && c.suggested && this.nh.auto.type_id);
    }
    get catWhy() {
        return this.catSuggested ? _t("Suggested for %s", this.api.countryName) : "";
    }
    get catNone() { return this.showCats && !this.cats.some((c) => c.suggested); }
    onCat(ev) { this.api.set("type_id", Number(ev.target.value) || false); }
    onDate(key, ev) { this.api.set(key, ev.target.value || ""); }
    get endErr() {
        const d = this.d;
        if (this.err("date_end")) {
            return this.err("date_end");
        }
        return d.contract_kind === "fixed" && d.date_end && d.date_start && d.date_end <= d.date_start
            ? _t("The contract must end after the first day.") : "";
    }
    get trial() { return this.dec && this.dec.trial; }
    get trialLine() {
        const t = this.trial;
        if (!t) {
            return "";
        }
        return this.d.trial_on
            ? _t("%(n)s months, ends %(day)s", { n: t.months, day: fmtDay(t.ends) })
            : _t("No trial period for %s", this.first);
    }
    get trialWhy() {
        const t = this.trial;
        if (t) {
            return this.d.trial_on ? _t("From the %s trial period rule", this.api.countryName) : _t("Switched off for this person");
        }
        return (this.dec && this.dec.trial_none) || "";
    }
    toggleTrial() { this.api.set("trial_on", !this.d.trial_on); }

}
