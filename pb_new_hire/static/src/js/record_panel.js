/** @odoo-module **/
/**
 * "The record so far" (NEWHIRE P1): the employee record assembling itself as
 * the steps are answered. Honest only: two Payroll-ready lines, the Paid by
 * card from the server's answer, and a quiet line where the first-payslip
 * example will be (D9) — no made-up numbers.
 */
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { icon, initials, fmtDay } from "./studio_util";

export class RecordPanel extends Component {
    static template = "pb_new_hire.RecordPanel";
    static props = { api: Object };

    setup() {
        this.icon = icon;
        this.nh = useState(this.props.api.nh);
    }

    get api() { return this.props.api; }
    get d() { return this.nh.draft; }
    get dec() { return this.nh.decides; }
    get initials() { return initials(this.d.name); }
    get name() { return String(this.d.name || "").trim() || _t("New employee"); }
    get role() {
        const bits = [this.api.jobName, this.api.teamName].filter(Boolean);
        return bits.length ? bits.join(" · ") : _t("No role yet");
    }
    get complete() {
        const d = this.d;
        const v = [String(d.name || "").trim(), d.date_start, d.work_email || d.personal, d.department_id,
                   d.job_id || d.job_title, d.payroll_country, d.parent_id, d.wage > 0 || this.api.scaleFound,
                   this.dec && this.dec.scheme];
        return Math.round((v.filter(Boolean).length / v.length) * 100);
    }
    get ringStyle() { return `--v:${this.complete}`; }
    get facts() {
        const d = this.d;
        const t = this.dec && this.dec.trial;
        let trial = "";
        if (d.payroll_country && this.dec) {
            trial = t && d.trial_on ? fmtDay(t.ends) : _t("No trial");
        }
        return [
            { k: "start", label: _t("First day"), value: fmtDay(d.date_start) },
            { k: "country", label: _t("Country of work"), value: this.api.countryName },
            { k: "boss", label: _t("Manager"), value: d.parent_name || "" },
            { k: "trial", label: _t("Trial ends"), value: trial },
        ];
    }
    get notSet() { return _t("Not set"); }
    get contractReady() {
        const d = this.d;
        return Boolean(d.date_start && ((d.wage > 0) || this.api.scaleFound));
    }
    get contractLine() {
        return this.contractReady
            ? _t("Running contract from %s", fmtDay(this.d.date_start))
            : _t("Contract needs a wage and a first day");
    }
    get bankLine() {
        const needs = !this.nh.data || !this.nh.data.approval || this.nh.data.approval.needs;
        return needs
            ? _t("Bank account: add it from the employee's side panel after approval.")
            : _t("Bank account: add it from the employee's side panel once the person is added.");
    }
    get paid() {
        const dec = this.dec;
        const cur = this.api.currency;
        if (!this.d.department_id) {
            return null;
        }
        if (!dec) {
            return { cls: "", name: _t("Working it out"), sub: "" };
        }
        if (!dec.scheme) {
            return { cls: "is-warn", name: _t("No pay scheme yet"), sub: dec.fix || "" };
        }
        const money = cur ? _t("Pays in %s", cur.name) : "";
        return {
            cls: dec.scheme.match ? "is-set" : "is-warn",
            name: dec.scheme.name,
            sub: dec.scheme.match ? [money, dec.scheme.why].filter(Boolean).join(" · ") : dec.problem,
        };
    }
}
