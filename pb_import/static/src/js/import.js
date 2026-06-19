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
