/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.import.connector.cockpit";

export class ConnectorCockpit extends Component {
    static template = "pb_import_advanced.ConnectorCockpit";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        const p = (this.props.action && (this.props.action.params || this.props.action.context)) || {};
        this.connectorId = p.connector_id || p.active_id;
        this.backTo = p.back_to || "pb_import.action_pb_import";
        this.backLabel = p.back_label || "Import data";
        this.state = useState({ loaded: false, busy: false, busyMsg: "", detail: null });
        onWillStart(async () => { await this.refresh(); });
    }

    ic(n, s = 16) { return ic(n, s); }
    get d() { return this.state.detail || {}; }
    initials() { return (this.d.name || "?").trim().slice(0, 2).toUpperCase(); }

    async refresh() {
        try {
            this.state.detail = await this.orm.call(MODEL, "get_connector_detail", [this.connectorId]);
        } catch (e) {
            this.state.detail = { error: "Could not load this connector." };
        } finally {
            this.state.loaded = true;
        }
    }

    async _run(promise, msg) {
        this.state.busy = true; this.state.busyMsg = msg || "Working…";
        try {
            const res = await promise;
            if (res && typeof res === "object") {
                this.state.detail = res;
                if (res.error) this.notif.add(res.error, { type: "warning" });
                else this.notif.add("Done.", { type: "success" });
            }
        } catch (e) {
            this.notif.add((e && e.message && e.message.toString()) || "Action failed.", { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    runAction(method) {
        const msg = { action_test_connection: "Testing connection…", action_pull_data: "Pulling data…",
                      action_fetch_available_fields: "Fetching fields…", action_disconnect: "Disconnecting…" }[method] || "Working…";
        return this._run(this.orm.call(MODEL, "run_connector_action", [this.connectorId, method]), msg);
    }

    async openLink(method) {
        try {
            const act = await this.orm.call(MODEL, "get_link", [this.connectorId, method]);
            if (act) this.action.doAction(act);
        } catch (e) { /* ignore */ }
    }
    openSync() {
        this.action.doAction({
            type: "ir.actions.client", tag: "pb_import_sync_wizard",
            name: "Pull from Connector", params: { connector_id: this.connectorId },
        });
    }
    openAdvancedForm() {
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "hr.integration.connector",
            res_id: this.connectorId, views: [[false, "form"]], target: "current",
        });
    }
    back() { this.action.doAction(this.backTo, { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_import_connector_cockpit", ConnectorCockpit);
