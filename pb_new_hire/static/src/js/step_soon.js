/** @odoo-module **/
/**
 * Steps 4-6 (NEWHIRE P1): real rail entries, and here ONE calm card each —
 * the step's question and a plain sentence of what will be set here, and
 * what happens today (the team's usual ones). No fake controls; they never
 * block sending.
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
        const f = this.props.api.first;
        switch (this.props.stepKey) {
            case "sched":
                return {
                    icon: "calendarClock",
                    question: _t("When does %s work?", f),
                    line: _t("The working week, the late and overtime rule and the clock number are chosen here in a later release."),
                    today: _t("Today %s gets your company's usual working hours and holiday list.", f),
                };
            case "docs":
                return {
                    icon: "fileText",
                    question: _t("Who fills in the rest?"),
                    line: _t("Personal details, tax numbers, the bank account and papers are asked for here in a later release."),
                    today: _t("Today you add them from the employee's side panel after approval."),
                };
            default:
                return {
                    icon: "userCheck",
                    question: _t("How will %s be welcomed?", f),
                    line: _t("The sign-in, a buddy, equipment and the joining checklist are chosen here in a later release."),
                    today: _t("Today no sign-in or welcome message is sent when the hire is added."),
                };
        }
    }
    get eyebrow() { return _t("Step %s of 7 · optional", this.meta.n); }
}
