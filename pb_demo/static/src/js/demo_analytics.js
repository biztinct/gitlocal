/** @odoo-module **/

import { Component, useState, onWillStart, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const PALETTE = ["#5A4BB0", "#2563EB", "#2E7D4F", "#D97706", "#DC2668", "#0EA5E9", "#7C3AED"];

export class DemoAnalytics extends Component {
    static template = "pb_demo.DemoAnalytics";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({ loading: true, data: null });
        onWillStart(async () => {
            this.state.data = await this.orm.call("pb.demo.analytics", "get_analytics_data", []);
            this.state.loading = false;
        });
    }

    money(n) {
        n = n || 0;
        if (Math.abs(n) >= 1e9) return "₫" + (n / 1e9).toFixed(2) + "B";
        if (Math.abs(n) >= 1e6) return "₫" + (n / 1e6).toFixed(1) + "M";
        if (Math.abs(n) >= 1e3) return "₫" + (n / 1e3).toFixed(0) + "K";
        return "₫" + Math.round(n);
    }
    num(n) { return (n || 0).toLocaleString("en-US"); }
    color(i) { return PALETTE[i % PALETTE.length]; }

    // width % relative to the max value in a list, given a value accessor
    pct(rows, val, v) {
        const max = Math.max(1, ...rows.map(val));
        return Math.round((v / max) * 100);
    }
    g(r) { return r.gross || 0; }
    c(r) { return r.count || 0; }
    h(r) { return r.headcount || 0; }
    otb(r) { return (r.ot || 0) + (r.bonus || 0); }
}

registry.category("actions").add("pb_demo_analytics", DemoAnalytics);
