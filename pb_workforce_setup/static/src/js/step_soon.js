/** @odoo-module **/
/**
 * Steps 3-7 in P1: the step's question as the heading and one calm card that
 * says what arrives here next. No fake controls. (Steps 3 and 4 are live
 * since P2 and P3.)
 */
import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { icon } from "./setup_util";

export class StepSoon extends Component {
    static template = "pb_workforce_setup.StepSoon";
    static props = { studio: Object, data: Object, stepKey: String };

    setup() {
        this.icon = icon;
    }

    get meta() {
        return this.props.studio.stepMeta(this.props.stepKey);
    }
    get status() {
        return this.props.data.steps.find((s) => s.key === this.props.stepKey) || {};
    }
    get copy() {
        const copy = {
            holidays: {
                question: _t("Which days is the company closed?"),
                lead: _t("Public holidays and company days off, on one calendar."),
                next: _t("Here you will see the year as a calendar and click a day to add or remove a company day off."),
            },
            clocks: {
                question: _t("How do people clock in?"),
                lead: _t("See each clock and whether it is sending data."),
                next: _t("Here you will see each clock, whether it is sending data, and send your IT person a ready-made setup link."),
            },
            live: {
                question: _t("Ready to go live?"),
                lead: _t("Nothing reaches the roster or payroll until you press Publish."),
                next: _t("Here you will check what is still missing, then publish the roster in one go."),
            },
        };
        return copy[this.props.stepKey] || copy.live;
    }
    get stepLine() {
        return _t("Step %(n)s of %(total)s", { n: this.meta.n, total: 7 });
    }
}
