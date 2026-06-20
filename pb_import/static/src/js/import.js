/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const STATE_CLS = {
    draft: "draft", loaded: "info", matched: "info", validated: "info",
    processing: "info", done: "done", error: "error", cancelled: "muted",
};
const CONN_ICON = {
    zoho: "cloud", excel: "table", sap: "server", workday: "briefcase",
    oracle: "database", demo: "beaker",
};
const IN_PROGRESS = ["loaded", "matched", "validated", "processing"];

export class PbImport extends Component {
    static template = "pb_import.PbImport";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loaded: false,
            company: "",
            kpis: {},
            pipeline: [],
            batches: [],
            connectors: [],
            launches: [],
            filter: "all",
        });
        onWillStart(async () => { await this.load(); });
    }

    async load() {
        const d = await this.orm.call("pb.import", "get_import_data", []);
        Object.assign(this.state, {
            company: d.company, kpis: d.kpis, pipeline: d.pipeline,
            batches: d.batches, connectors: d.connectors,
            launches: d.launches, loaded: true,
        });
    }

    stateCls(s) { return STATE_CLS[s] || "muted"; }
    connIcon(t) { return CONN_ICON[t] || "plug"; }

    // ---- launches: primary tile becomes the hero CTA; rest stay as tiles ----
    get secondaryLaunches() { return this.state.launches.filter(l => !l.primary); }

    // ---- status filter chips ----
    _inFilter(b) {
        const f = this.state.filter;
        if (f === "all") return true;
        if (f === "in_progress") return IN_PROGRESS.includes(b.state);
        if (f === "errors") return b.state === "error" || (b.errors || 0) > 0;
        return b.state === f;     // draft, done
    }
    get filteredBatches() { return this.state.batches.filter(b => this._inFilter(b)); }
    countFor(key) {
        if (key === "all") return this.state.batches.length;
        return this.state.batches.filter(b => {
            if (key === "in_progress") return IN_PROGRESS.includes(b.state);
            if (key === "errors") return b.state === "error" || (b.errors || 0) > 0;
            return b.state === key;
        }).length;
    }
    setFilter(key) { this.state.filter = key; }

    // ---- actions ----
    startWizard() { this.action.doAction("pb_import_wizard.action_pb_import_wizard", { clearBreadcrumbs: true }); }
    openBatch(id) {
        if (!id) return;
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "hr.payroll.import.batch",
            res_id: id, views: [[false, "form"]], target: "current",
        });
    }
    openConnector(id) {
        if (!id) return;
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "hr.integration.connector",
            res_id: id, views: [[false, "form"]], target: "current",
        });
    }
    launch(xmlid) {
        if (!xmlid) return;
        this.action.doAction(xmlid, { clearBreadcrumbs: true });
    }
}

registry.category("actions").add("pb_import", PbImport);
