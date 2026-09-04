/** @odoo-module **/
/**
 * The Government Reports board — the country-aware catalogue of statutory
 * filings.
 *
 * IA Cycle 4 changed one thing about it and left the rest alone: "Generate" no
 * longer opens a `target: "new"` modal on a thirty-field wizard. For every
 * country this database can DRIVE through `pb.filing.flow`, the button opens
 * the full-screen filing flow with that filing preselected. For any country it
 * cannot, the old modal is still exactly what happens — a partial cutover that
 * says so is worth more than a complete one that quietly breaks a country
 * nobody here can test (flow doctrine 1, and the handover's own rule).
 *
 * Which countries are covered is a SERVER answer (`pb.filing.flow.
 * covered_countries`), not a list in this file: coverage depends on whether the
 * country module is installed, and a hard-coded list in the browser would offer
 * the flow on a database where the wizard model does not exist — W29's door
 * that can only produce an error.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";
import { _t } from "@web/core/l10n/translation";
import { HubBackChip, hubBack, openHub } from "@pb_hub/js/hub_nav";

export class PbGovtReports extends Component {
    static template = "pb_govt_reports.PbGovtReports";
    static components = { HubBackChip };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.ic = ic;
        // Read ONCE, from props, never written back (the arrival protocol).
        this.back = hubBack(this.props);
        this.state = useState({ loaded: false, data: {}, month: "", covered: [] });
        // One navigation at a time: two clicks on Generate 40ms apart are one
        // intent, and doAction is happy to run both (C1's flag, W21.1's lesson
        // applied to navigation rather than to writes).
        this._opening = false;
        onWillStart(async () => { await this.load(); });
    }

    async load(country) {
        const d = await this.orm.call("pb.govt.reports", "get_govt_reports_data", [country || false]);
        this.state.data = d;
        this.state.month = d.period.month;
        try {
            this.state.covered = await this.orm.call("pb.filing.flow", "covered_countries", []);
        } catch (e) {
            // Reported, never swallowed into a decoration (W40). A board whose
            // coverage probe failed still works; it simply keeps every country
            // on the modal path it has always had.
            console.warn("pb_govt_reports: could not read the flow coverage", e);
            this.state.covered = [];
        }
        this.state.loaded = true;
    }

    selectCountry(cc) { this.load(cc); }
    onMonth(ev) { this.state.month = ev.target.value || this.state.month; }

    /** Is this country's wizard drivable through the facade on this database? */
    get isCovered() {
        return (this.state.covered || []).includes(this.state.data.country_code);
    }

    // derive {from,to} for the chosen YYYY-MM month
    get range() {
        const m = this.state.month || this.state.data?.period?.month;
        if (!m) return this.state.data.period || {};
        const [y, mo] = m.split("-").map(Number);
        const pad = (n) => String(n).padStart(2, "0");
        const last = new Date(y, mo, 0).getDate();
        return { from: `${y}-${pad(mo)}-01`, to: `${y}-${pad(mo)}-${pad(last)}` };
    }

    /**
     * A CLICK handler, and the only door on this board.
     *
     * Covered countries get the flow with the filing preselected; the rest keep
     * the modal they have always had. The old wizard actions stay registered
     * either way — this cycle replaces the DOOR, not the model.
     */
    generate(key) {
        const d = this.state.data;
        if (!d.wizard_model || this._opening) return;
        this._opening = true;
        try {
            if (this.isCovered) {
                openHub(this.action, {
                    tag: "pb_filing_flow",
                    context: { pb_filing: key, pb_country: d.country_code },
                    // A back door to wherever the board itself was opened from,
                    // so a hub lens does not lose its hub on the way out.
                    back: this.back || { label: _t("Government Reports"),
                                         tag: "pb_govt_reports" },
                });
                return;
            }
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
            // A modal does not replace the surface, so the guard has to come
            // back down or the second filing of the day would do nothing.
            this._opening = false;
        } catch (e) {
            this._opening = false;
            console.warn("pb_govt_reports: could not open the filing", e);
        }
    }
}

registry.category("actions").add("pb_govt_reports", PbGovtReports);
