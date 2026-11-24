/** @odoo-module **/
/**
 * Step 1 — Who is joining (NEWHIRE P1). Four boxes; the "already an
 * employee?" check runs as the name is typed (400 ms, newest reply wins) and
 * never blocks.
 */
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { icon, rich } from "./studio_util";

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
}
