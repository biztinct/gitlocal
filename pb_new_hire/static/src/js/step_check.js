/** @odoo-module **/
/**
 * Step 7 — Check and add (NEWHIRE P1). One last look, every problem in amber
 * with its fix, what pressing the button really does (from the approval
 * engine's own route), and the one button. After Send: the done card —
 * waiting ("Withdraw and change", D7) or added ("Open the record").
 */
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { icon, fmtDay, money, rich } from "./studio_util";

export class StepCheck extends Component {
    static template = "pb_new_hire.StepCheck";
    static props = { api: Object };

    setup() {
        this.icon = icon;
        this.nh = useState(this.props.api.nh);
    }

    get api() { return this.props.api; }
    get d() { return this.nh.draft; }
    get dec() { return this.nh.decides; }
    get first() { return this.api.first; }
    get name() { return String(this.d.name || "").trim(); }
    get approval() { return (this.nh.data && this.nh.data.approval) || { needs: true }; }
    get result() { return this.nh.result; }

    // ------------------------------------------------------------ the list
    get rows() {
        const api = this.api;
        const d = this.d;
        const out = [];
        out.push(api.status("who").state === "done"
            ? { key: "who", cls: "", icon: "check", b: this.name, s: _t("First day %s", fmtDay(d.date_start, true)), go: "who", field: "name" }
            : { key: "who", cls: "is-bad", icon: "alert", b: _t("Name and first day are missing"), s: _t("Step 1"), go: "who", field: d.name ? "date_start" : "name" });
        if (api.status("role").state !== "warn") {
            const bits = [api.countryName,
                d.parent_name ? _t("reports to %s", d.parent_name) : _t("no manager yet"),
                this.siteName || _t("no site")];
            out.push({ key: "role", cls: "", icon: "check", b: _t("%(job)s, %(team)s", { job: api.jobName, team: api.teamName }),
                       s: bits.join(" · "), go: "role", field: "department_id" });
        } else {
            out.push({ key: "role", cls: "is-bad", icon: "alert", b: _t("Team, job or country is missing"), s: _t("Step 2"), go: "role", field: "department_id" });
        }
        if (api.status("pay").state !== "warn") {
            const wage = d.wage > 0 ? money(d.wage, api.currency) : _t("Pay from the pay scale");
            const kind = d.contract_kind === "fixed"
                ? _t("fixed term to %s", fmtDay(d.date_end)) : _t("permanent");
            const trial = this.trialEnds ? _t("trial to %s", fmtDay(this.trialEnds)) : _t("no trial period");
            const scheme = this.dec && this.dec.scheme ? _t("Paid by %s", this.dec.scheme.name) : _t("No pay scheme yet");
            out.push({ key: "pay", cls: "", icon: "check", b: d.wage > 0 ? _t("%(wage)s a month, %(kind)s", { wage, kind }) : _t("%(wage)s, %(kind)s", { wage, kind }),
                       s: `${scheme} · ${trial}`, go: "pay", field: "wage" });
        } else {
            out.push({ key: "pay", cls: "is-bad", icon: "alert", b: _t("The wage is missing"), s: _t("Step 3"), go: "pay", field: "wage" });
        }
        out.push({ key: "soon", cls: "is-soon", icon: "hourglass", b: _t("Schedule, details and welcome"),
                   s: _t("These steps arrive next. Today the company's usual hours apply and nothing is sent to %s.", this.first), go: false });
        return out;
    }
    get siteName() {
        const s = ((this.nh.data && this.nh.data.sites) || []).find((x) => x.id === this.d.work_location_id);
        return s ? s.name : "";
    }
    get trialEnds() {
        const t = this.dec && this.dec.trial;
        return t && this.d.trial_on ? t.ends : "";
    }

    /** Amber rows: things that may be wrong. None of them blocks sending. */
    get warnings() {
        const out = [];
        if (this.dec && this.dec.problem) {
            out.push({ key: "scheme", b: this.dec.problem, s: this.dec.fix || "", go: "role", field: "payroll_country" });
        }
        const same = (this.nh.dup && this.nh.dup.same_name) || [];
        if (same.length) {
            out.push({ key: "dup", b: _t("%s is already an employee", same[0].name),
                       s: _t("Carry on only if this is a different person."), go: "who", field: "name" });
        }
        if (this.nh.dup && this.nh.dup.email_taken) {
            out.push({ key: "email", b: _t("Another employee already uses this work email"),
                       s: _t("Check it, or leave the work email empty."), go: "who", field: "work_email" });
        }
        return out;
    }
    change(row) { this.api.go(row.go, row.field); }

    // ------------------------------------------------------------ what happens
    get then() {
        const out = [];
        const cur = this.api.currency;
        const code = cur ? cur.name : "";
        const scheme = this.dec && this.dec.scheme ? this.dec.scheme.name : "";
        if (this.approval.needs) {
            out.push(this.approval.with_whom
                ? rich(_t("%(who)s gets the hire to approve. Nothing is created until they agree."), { who: this.approval.with_whom })
                : rich(_t("A second person gets the hire to approve. Nothing is created until they agree.")));
            out.push(scheme
                ? rich(_t("On approval, the employee record and a running contract are created, in %(code)s, on %(scheme)s."), { code, scheme })
                : rich(_t("On approval, the employee record and a running contract are created, in %(code)s."), { code }));
        } else {
            out.push(scheme
                ? rich(_t("%(name)s is added straight away, with a running contract in %(code)s on %(scheme)s."), { name: this.name || this.first, code, scheme })
                : rich(_t("%(name)s is added straight away, with a running contract in %(code)s."), { name: this.name || this.first, code }));
        }
        if (this.trialEnds) {
            out.push(rich(_t("The trial period is set to end on %(day)s."), { day: fmtDay(this.trialEnds, true) }));
        }
        out.push(this.approval.needs
            ? rich(_t("Bank account: add it from the employee's side panel after approval."))
            : rich(_t("Bank account: add it from the employee's side panel once the person is added.")));
        return out;
    }
    get sendLabel() {
        return this.approval.needs ? _t("Send for approval") : _t("Add %s", this.first);
    }
    get launchTitle() {
        if (this.approval.problem) {
            return _t("This hire cannot be sent yet");
        }
        return this.api.ready ? _t("Ready to send") : _t("The three required steps still need you");
    }
    get launchLine() {
        if (this.approval.problem) {
            return this.approval.problem;
        }
        if (!this.api.ready) {
            return _t("Finish the steps marked in amber on the left, then come back.");
        }
        return this.approval.needs
            ? _t("After sending you can still withdraw it and change it, until it is approved.")
            : _t("Nobody needs to approve new hires here, so the person is added when you press the button.");
    }
    get heading() { return _t("Check, then add %s", this.first); }
    get intro() {
        return this.approval.needs
            ? _t("One last look. A second person approves every new hire, so nothing is created until they agree.")
            : _t("One last look. The person is added as soon as you press the button.");
    }
    get canSend() { return this.api.ready && !this.approval.problem && !this.nh.sending; }
    get refusal() { return this.nh.refusal; }
    refusalGo() {
        const r = this.refusal;
        if (r && r.step && r.step !== "check") {
            this.api.go(r.step, r.field);
        }
    }

    // ------------------------------------------------------------ after sending
    get doneTitle() {
        const r = this.result;
        if (r.applied) {
            return _t("%s is added", this.name);
        }
        return r.with_whom
            ? _t("%(name)s is with %(who)s for approval", { name: this.name, who: r.with_whom })
            : _t("%s is waiting for approval", this.name);
    }
    get doneLine() {
        return this.result.applied
            ? _t("The employee record and a running contract are ready. The bank account can be added from the side panel.")
            : _t("Nothing is created until the hire is approved. Then the record and the running contract are created by themselves.");
    }
    get reference() { return this.result && this.result.reference ? _t("Reference %s", this.result.reference) : ""; }
    get openLabel() { return _t("Open %s's record", this.first); }
}
