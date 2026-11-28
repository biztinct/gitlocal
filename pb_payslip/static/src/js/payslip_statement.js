/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";
import { paySummary, statementMoney, statementChange } from "./pay_summary";

const PIPE = [
    { key: "draft", label: _t("Draft") },
    { key: "level1", label: _t("HR") },
    { key: "level2", label: _t("GM") },
    { key: "done", label: _t("Done") },
];
const IDX = { draft: 0, verify: 0, level1: 1, level2: 2, done: 3 };

export class PbPayslipStatement extends Component {
    static template = "pb_payslip.Statement";
    static props = { ...standardFieldProps };

    get data() {
        try {
            return JSON.parse(this.props.record.data[this.props.name] || "{}");
        } catch (e) {
            return {};
        }
    }

    money(n) {
        return statementMoney(n, this.data);
    }
    change(n) {
        return statementChange(n, this.data);
    }
    percent(n) {
        return n.toLocaleString("en-US", { maximumFractionDigits: 1 }) + "%";
    }

    get rejected() { return this.data.state === "cancel"; }

    get stages() {
        const cur = IDX[this.data.state] ?? 0;
        return PIPE.map((s, i) => ({
            ...s,
            cls: i < cur ? "done" : (i === cur ? "cur" : "future"),
        }));
    }

    get summary() {
        return paySummary(this.data);
    }
    get splitLabel() {
        return _t("Gross pay: %s; deductions: %s (%s); net pay: %s (%s).",
            this.money(this.data.gross), this.money(this.data.deductions_total),
            this.percent(this.summary.deductionPercent), this.money(this.data.net),
            this.percent(this.summary.netPercent));
    }
}

registry.category("fields").add("pb_payslip_statement", {
    component: PbPayslipStatement,
    supportedTypes: ["text"],
});
