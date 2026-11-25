/** @odoo-module **/
/**
 * Step 1 — Who is joining (NEWHIRE P1). Four boxes; the "already an
 * employee?" check runs as the name is typed (400 ms, newest reply wins) and
 * never blocks.
 *
 * P4: three ways to start (POC `vWho`): Type it in, From Hiring (the signed
 * offers waiting to join, each with what the candidate already sent), and
 * Many at once (the Updates desk's new-employee sheet).
 */
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { icon, rich, initials, fmtDay, money } from "./studio_util";

export class StepWho extends Component {
    static template = "pb_new_hire.StepWho";
    static props = { api: Object };

    setup() {
        this.icon = icon;
        this.nh = useState(this.props.api.nh);
    }

    get d() { return this.nh.draft; }
    err(field) { return this.nh.fieldErr[field] || ""; }
    onText(key, ev) { this.props.api.set(key, ev.target.value); }

    get dup() {
        const same = (this.nh.dup && this.nh.dup.same_name) || [];
        if (!same.length) {
            return null;
        }
        const p = same[0];
        const where = [p.job, p.team].filter(Boolean).join(", ");
        const line = where
            ? _t("%(name)s is already an employee (%(where)s). Carry on only if this is a different person.")
            : _t("%(name)s is already an employee. Carry on only if this is a different person.");
        return rich(line, { name: p.name }, { where });
    }
    get dupMore() {
        const n = ((this.nh.dup && this.nh.dup.same_name) || []).length - 1;
        return n > 0 ? _t("%s more employees have the same name.", n) : "";
    }
    get emailTaken() { return Boolean(this.nh.dup && this.nh.dup.email_taken); }

    // ------------------------------------------------------------ P4: the ways in
    get hiring() { return (this.nh.data && this.nh.data.hiring) || { on: false, count: 0 }; }
    get many() { return Boolean(this.nh.data && this.nh.data.features && this.nh.data.features.many); }
    get showWays() { return this.hiring.on || this.many; }
    get hiringSub() {
        const n = this.nh.offers ? this.nh.offers.length : this.hiring.count;
        if (!n) {
            return _t("No signed offers are waiting");
        }
        return n === 1 ? _t("1 signed offer is waiting. The papers they sent come across")
            : _t("%s signed offers are waiting. The papers they sent come across", n);
    }
    wayClass(key) { return `pbnh-way${this.nh.source === key ? " is-on" : ""}`; }
    pick(key) { this.props.api.setSource(key); }
    initials(name) { return initials(name); }
    offerLine(row) {
        const bits = [row.job, row.team].filter(Boolean);
        if (row.signed_on) {
            bits.push(_t("signed %s", fmtDay(row.signed_on)));
        }
        return bits.join(" · ");
    }
    offerStart(row) {
        const bits = [];
        if (row.first_day) {
            bits.push(_t("Starts %s", fmtDay(row.first_day)));
        }
        if (row.wage > 0) {
            bits.push(_t("%s a month", money(row.wage, row.wage_currency)));
        }
        return bits.join(" · ");
    }
    isBrought(row) { return this.nh.draft.offer_id === row.offer_id; }
    async bring(row) {
        if (this.isBrought(row)) {
            return;
        }
        await this.props.api.bringAcross(row.offer_id);
    }
    missingLine(chip) { return _t("%s not sent yet", chip.label); }
    get firstOf() { return this.props.api.first; }
    get acrossInfo() {
        const first = this.nh.offer ? this.props.api.first : _t("the new person");
        return _t("Files the candidate sent come across to %s's record. The bank paper becomes a bank request for a second person to approve. Numbers are asked for in the welcome link.", first);
    }
}
