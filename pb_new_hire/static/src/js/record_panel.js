/** @odoo-module **/
/**
 * "The record so far" (NEWHIRE P1): the employee record assembling itself as
 * the steps are answered. Honest only: two Payroll-ready lines, the Paid by
 * card from the server's answer, and a quiet line where the first-payslip
 * example will be (D9) — no made-up numbers.
 */
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { icon, initials, fmtDay, weekNameOf, docItemsOf, docChoiceOf, docTallyOf } from "./studio_util";

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
            { k: "week", label: _t("Working week"), value: weekNameOf(this.nh) || (this.nh.sched ? _t("Usual hours") : "") },
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
    /** P3a: the bank line tells the truth about step 5's answer. */
    get bankItem() { return docItemsOf(this.nh).find((i) => i.key === "bank") || null; }
    get bank() {
        const item = this.bankItem;
        const first = this.api.first;
        if (!item) {
            return { cls: "is-w", icon: "shield", text: _t("Bank account: choose who gives it in step 5.") };
        }
        const c = docChoiceOf(this.nh, item);
        if (c === "have") {
            return { cls: "is-w", icon: "shield", text: _t("Bank account: waiting for a second approval after sending") };
        }
        if (c === "ask") {
            return { cls: "is-p", icon: "send", text: _t("Bank account: %s will be asked", first) };
        }
        return { cls: "is-w", icon: "alert", text: _t("Bank account: not asked yet") };
    }
    /** "Who does what": you (typed here + your own fields), the new person
     *  (asks), the manager and IT (their steps of the joining checklist). */
    get who() {
        if (!this.d.payroll_country || !this.nh.docs) {
            return null;
        }
        const t = docTallyOf(this.nh);
        const own = Object.values(this.d.own || {}).filter((v) => v !== "" && v !== null && v !== undefined && v !== false).length;
        const w = this.nh.welcome;
        const other = this.d.open_case === false ? 0
            : ((w && w.timeline) || []).filter((e) => ["manager", "buddy", "it"].includes(e.role)).length;
        const you = t.have + own;
        return {
            you, them: t.ask, other,
            youStyle: `flex:${you}`, themStyle: `flex:${t.ask}`, otherStyle: `flex:${other}`,
            youLine: _t("You %s", you),
            themLine: _t("%(first)s %(n)s", { first: this.api.first, n: t.ask }),
            otherLine: _t("Manager and IT %s", other),
        };
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
