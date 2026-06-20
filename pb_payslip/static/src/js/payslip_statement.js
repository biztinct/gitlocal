/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const PIPE = [
    { key: "draft", label: "Draft" },
    { key: "level1", label: "HR" },
    { key: "level2", label: "GM" },
    { key: "done", label: "Done" },
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
        const cur = this.data.currency || "₫";
        if (n === null || n === undefined || isNaN(n)) return cur + "0";
        return cur + Math.round(n).toLocaleString("en-US");
    }
    moneyShort(n) {
        const cur = this.data.currency || "₫";
        const a = Math.abs(n || 0);
        if (a >= 1e9) return cur + (n / 1e9).toFixed(2) + "B";
        if (a >= 1e6) return cur + (n / 1e6).toFixed(1) + "M";
        if (a >= 1e3) return cur + (n / 1e3).toFixed(0) + "K";
        return cur + Math.round(n || 0);
    }

    get rejected() { return this.data.state === "cancel"; }

    get stages() {
        const cur = IDX[this.data.state] ?? 0;
        return PIPE.map((s, i) => ({
            ...s,
            cls: i < cur ? "done" : (i === cur ? "cur" : "future"),
        }));
    }

    // width % for the waterfall segments (gross is the 100% baseline)
    get segDed() {
        const g = this.data.gross || 0;
        return g ? Math.max(8, Math.min(60, Math.round((this.data.deductions_total / g) * 100))) : 0;
    }
}

registry.category("fields").add("pb_payslip_statement", {
    component: PbPayslipStatement,
    supportedTypes: ["text"],
});
