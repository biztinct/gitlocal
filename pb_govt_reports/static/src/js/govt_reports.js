/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";

export class PbGovtReports extends Component {
    static template = "pb_govt_reports.PbGovtReports";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.ic = ic;
        this.state = useState({ loaded: false, data: {}, month: "" });
        onWillStart(async () => { await this.load(); });
    }

    async load(country) {
        const d = await this.orm.call("pb.govt.reports", "get_govt_reports_data", [country || false]);
        this.state.data = d;
        this.state.month = d.period.month;
        this.state.loaded = true;
    }

    selectCountry(cc) { this.load(cc); }
    onMonth(ev) { this.state.month = ev.target.value || this.state.month; }

    // derive {from,to} for the chosen YYYY-MM month
    get range() {
        const m = this.state.month || this.state.data?.period?.month;
        if (!m) return this.state.data.period || {};
        const [y, mo] = m.split("-").map(Number);
        const pad = (n) => String(n).padStart(2, "0");
        const last = new Date(y, mo, 0).getDate();
        return { from: `${y}-${pad(mo)}-01`, to: `${y}-${pad(mo)}-${pad(last)}` };
    }

    generate(key) {
        const d = this.state.data;
        if (!d.wizard_model) return;
        const r = this.range;
        const ctx = { default_date_from: r.from, default_date_to: r.to };
        if (d.country_code === "VN") ctx.default_report_type = key;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Generate filing",
            res_model: d.wizard_model,
            views: [[false, "form"]],
            target: "new",
            context: ctx,
        });
    }
}

registry.category("actions").add("pb_govt_reports", PbGovtReports);
