/** @odoo-module **/
/**
 * Step 3 — Contract and pay (NEWHIRE P1). "Paid by" is read-only (D3: no
 * per-person scheme); the wage box writes itself in the country's money and
 * groups thousands as you type (never NaN or "" into the draft — WS18); the
 * band and the pay-scale line come from the server's own answers; the
 * scheme's usual answers can be changed for this one person.
 */
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { icon, fmtDay, money, moneyNumber, parseMoney, groupTyped, rich } from "./studio_util";

export class StepPay extends Component {
    static template = "pb_new_hire.StepPay";
    static props = { api: Object };

    setup() {
        this.icon = icon;
        this.nh = useState(this.props.api.nh);
        this.ui = useState({ typing: null });
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
    get paidCls() { return this.scheme && this.scheme.match ? "" : "is-warn"; }
    get wagesIn() {
        return this.cur ? rich(_t("Wages are in %(code)s."), { code: this.cur.name }) : "";
    }

    // ------------------------------------------------------------ the wage
    get wageText() {
        if (this.ui.typing !== null) {
            return this.ui.typing;
        }
        return this.d.wage === null || this.d.wage === undefined ? "" : moneyNumber(this.d.wage, this.cur);
    }
    onWage(ev) {
        const el = ev.target;
        const shown = groupTyped(el.value, this.cur);
        if (shown !== el.value) {
            el.value = shown;
            el.setSelectionRange?.(shown.length, shown.length);
        }
        this.ui.typing = shown;
        const n = parseMoney(shown);
        this.api.set("wage", n === null ? null : n);
    }
    onWageBlur() { this.ui.typing = null; }
    get wageCode() { return this.cur ? _t("%s a month", this.cur.name) : _t("a month"); }

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
            this.ui.typing = null;
            this.api.patch({ wage: s.amount, pb_scale_pin_reason: "" });
        }
    }

    // ------------------------------------------------------------ contract and trial
    setKind(kind) { this.api.set("contract_kind", kind); }
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

    // ------------------------------------------------------------ usual answers
    get usual() { return this.nh.usual; }
    get usualIntro() {
        const s = this.scheme;
        return _t("Filled in for you from %(scheme)s. Change only what is different for %(first)s.",
                  { scheme: s ? s.name : "", first: this.first });
    }
    value(row) {
        const u = this.d.usual || {};
        return row.code in u ? u[row.code] : row.value;
    }
    changed(row) { return row.code in (this.d.usual || {}); }
    changedChip() { return _t("Changed for %s", this.first); }
    toggleRow(row) {
        const on = Number(this.value(row)) >= 0.5;
        this.api.setUsual(row.code, on ? 0 : 1);
    }
    isOn(row) { return Number(this.value(row)) >= 0.5; }
    onChoice(row, ev) { this.api.setUsual(row.code, Number(ev.target.value)); }
    onNumber(row, ev) {
        const n = parseMoney(ev.target.value);
        if (n !== null) {
            this.api.setUsual(row.code, n);
        }
    }
    numberText(row) { return moneyNumber(this.value(row), { decimals: 2 }).replace(/([.,]00)$/, ""); }
    optSelected(row, opt) { return Math.abs(Number(this.value(row)) - opt.value) < 1e-9; }
    back(row) { this.api.resetUsual(row.code); }
}
