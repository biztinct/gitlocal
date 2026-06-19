/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class PbStatutory extends Component {
    static template = "pb_statutory.PbStatutory";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loaded: false,
            currency: "",
            company: "",
            policy: null,
            tax: null,
            actuals: null,
            launches: [],
        });
        onWillStart(async () => { await this.load(); });
    }

    async load() {
        const d = await this.orm.call("pb.statutory", "get_statutory_data", []);
        Object.assign(this.state, {
            currency: d.currency, company: d.company, policy: d.policy,
            tax: d.tax, actuals: d.actuals, launches: d.launches, loaded: true,
        });
    }

    money(n) {
        if (n === null || n === undefined) return "—";
        const cur = this.state.currency || "₫";
        const a = Math.abs(n);
        if (a >= 1e9) return cur + (n / 1e9).toFixed(2) + "B";
        if (a >= 1e6) return cur + (n / 1e6).toFixed(1) + "M";
        if (a >= 1e3) return cur + (n / 1e3).toFixed(0) + "K";
        return cur + Math.round(n);
    }
    full(n) {
        if (!n) return (this.state.currency || "₫") + "0";
        return (this.state.currency || "₫") + Math.round(n).toLocaleString("en-US");
    }
    rate(n) { return (n || 0).toFixed(n % 1 ? 1 : 0) + "%"; }
    bracket(s) {
        const f = this.money(s.from);
        const t = s.to ? this.money(s.to) : "∞";
        return f + " – " + t;
    }
    pct(n, max) { return Math.max(2, Math.round((n / (max || 1)) * 100)); }

    open(xmlid) {
        if (!xmlid) return;
        this.action.doAction(xmlid, { clearBreadcrumbs: true });
    }
}

registry.category("actions").add("pb_statutory", PbStatutory);
