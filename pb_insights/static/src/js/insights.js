/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class PbInsights extends Component {
    static template = "pb_insights.PbInsights";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loaded: false,
            currency: "",
            company: "",
            runName: "",
            kpis: {},
            trend: [],
            trendMax: 1,
            departments: [],
            deptMax: 1,
            reports: [],
        });
        onWillStart(async () => { await this.load(); });
    }

    async load() {
        const d = await this.orm.call("pb.insights", "get_insights_data", []);
        Object.assign(this.state, {
            currency: d.currency, company: d.company, runName: d.run_name,
            kpis: d.kpis, trend: d.trend, trendMax: d.trend_max,
            departments: d.departments, deptMax: d.dept_max,
            reports: d.reports, loaded: true,
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
    pct(n, max) { return Math.max(2, Math.round((n / (max || 1)) * 100)); }

    openReport(xmlid) {
        if (!xmlid) return;
        this.action.doAction(xmlid, { clearBreadcrumbs: true });
    }
}

registry.category("actions").add("pb_insights", PbInsights);
