/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";

const TILE_ICON = { shield: "checkCircle", percent: "sigma", "bar-chart": "layers", sliders: "settings", users: "users" };

export class PbStatutory extends Component {
    static template = "pb_statutory.PbStatutory";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loaded: false, currency: "", kpis: {}, policy: null, tax: null, actuals: null,
            policies: [], tax_tables: [], launches: [],
            view: "policies", year: "", showActive: false,
        });
        onWillStart(async () => { await this.load(); });
    }

    async load() {
        const d = await this.orm.call("pb.statutory", "get_statutory_data", []);
        Object.assign(this.state, {
            currency: d.currency, kpis: d.kpis, policy: d.policy, tax: d.tax, actuals: d.actuals,
            policies: d.policies, tax_tables: d.tax_tables, launches: d.launches, loaded: true,
        });
    }

    ic(n, s = 16) { return ic(n, s); }
    tileIcon(n) { return ic(TILE_ICON[n] || "settings", 18); }
    money(n) {
        if (!n) return (this.state.currency || "₫") + "0";
        const a = Math.abs(n);
        const cur = this.state.currency || "₫";
        if (a >= 1e9) return cur + (n / 1e9).toFixed(1) + "B";
        if (a >= 1e6) return cur + (n / 1e6).toFixed(1) + "M";
        if (a >= 1e3) return cur + (n / 1e3).toFixed(0) + "K";
        return cur + Math.round(n);
    }
    moneyFull(n) { return (this.state.currency || "₫") + Math.round(n || 0).toLocaleString("en-US"); }

    setView(v) { this.state.view = v; this.state.year = ""; }
    setYear(y) { this.state.year = this.state.year === y ? "" : y; }
    toggleActive() { this.state.showActive = !this.state.showActive; }
    get years() { return [...new Set(this.state.tax_tables.map(t => t.year))].sort((a, b) => b - a); }
    get filteredPolicies() { return this.state.policies.filter(p => !this.state.showActive || p.active); }
    get filteredTax() {
        return this.state.tax_tables.filter(t => (!this.state.showActive || t.active) && (!this.state.year || t.year === this.state.year));
    }

    openPolicy(id) { this.action.doAction({ type: "ir.actions.client", tag: "pb_policy_detail", name: "Insurance policy", params: { policy_id: id } }); }
    openTax(id) { this.action.doAction({ type: "ir.actions.client", tag: "pb_tax_detail", name: "Tax table", params: { tax_id: id } }); }
    newPolicy() { this.action.doAction({ type: "ir.actions.client", tag: "pb_policy_wizard", name: "New policy" }); }
    newTax() { this.action.doAction({ type: "ir.actions.client", tag: "pb_tax_wizard", name: "New tax table" }); }
    launch(xmlid) { if (xmlid) this.action.doAction(xmlid, { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_statutory", PbStatutory);
