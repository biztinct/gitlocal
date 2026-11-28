/** @odoo-module **/
/**
 * Step 5 (NEWHIRE P1; steps 4 and 6 arrived in P2): a real rail entry, and
 * here ONE calm card — the step's question, a plain sentence of what will be
 * asked here, and what happens today. No fake controls; it never blocks
 * sending.
 */
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { icon } from "./studio_util";

export class StepSoon extends Component {
    static template = "pb_new_hire.StepSoon";
    static props = { api: Object, stepKey: String };

    setup() {
        this.icon = icon;
        this.nh = useState(this.props.api.nh);
    }

    get meta() { return this.props.api.stepMeta(this.props.stepKey); }
    get card() {
        return {
            icon: "fileText",
            question: _t("Who fills in the rest?"),
            line: _t("Personal details, tax numbers, the bank account and papers are asked for here in a later release."),
            today: _t("Today you add them from the employee's side panel after approval."),
        };
    }
    get eyebrow() { return _t("Step %s of 7 · optional", this.meta.n); }
}
