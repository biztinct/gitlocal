/** @odoo-module **/
/**
 * The guided connector cockpit.
 *
 * IA Cycle 3 rewired its three link buttons. They used to call
 * `hr.integration.connector.action_view_mappings` / `action_view_data_store`,
 * each of which returns a raw `list,form` act_window — so reading which fields a
 * connector maps cost you the cockpit and dropped you into Odoo's own chrome
 * with no way back. They now deep-link into `pb_integrations`' Data view,
 * SCOPED to this connector and carrying a `pb_back` chip that returns here, to
 * this connector.
 *
 * The server methods behind the old links are untouched and still registered:
 * the cycle replaces the doors, not the models.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { openHub } from "@pb_hub/js/hub_nav";

const MODEL = "pb.import.connector.cockpit";

/** The cockpit's own tag, so the ledgers can send the user back TO A CONNECTOR. */
const SELF_TAG = "pb_import_connector_cockpit";

export class ConnectorCockpit extends Component {
    static template = "pb_import_advanced.ConnectorCockpit";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        // MERGED, params winning. The cockpit used to read `params || context`,
        // and an `ir.actions.client` record whose `params` is an empty object is
        // truthy — so a caller that passed its payload in the CONTEXT (which is
        // what `openHub` does, and what a back chip returning here must do) was
        // silently handed nothing and the cockpit opened on no connector.
        const a = this.props.action || {};
        const p = { ...(a.context || {}), ...(a.params || {}) };
        this.connectorId = p.connector_id || p.active_id;
        // Integrations is the connectors' home since Cycle 3, so it is the
        // honest default for a caller that did not say where it came from —
        // Import no longer opens this cockpit at all.
        this.backTo = p.back_to || "pb_integrations.action_pb_integrations";
        this.backLabel = p.back_label || _t("Integrations");
        this.state = useState({ loaded: false, busy: false, busyMsg: "", detail: null });
        onWillStart(async () => { await this.refresh(); });
    }

    /**
     * Is the connectors home on this database?
     *
     * `pb_integrations` DEPENDS ON this module, so it cannot be a dependency of
     * it — the actions registry is the probe instead, and a link that would open
     * nothing is simply not rendered (W29).
     */
    get hasLedgers() {
        return registry.category("actions").contains("pb_integrations");
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

    /**
     * A satellite table, IN the Integrations cockpit, scoped to this connector.
     *
     * `kind` is one of the three ledger keys. The chip on the other side comes
     * back HERE — with this connector's id in its context, because a back door
     * that lands on an empty cockpit is not a back door.
     */
    openLedger(kind) {
        if (!this.hasLedgers) { return; }
        openHub(this.action, {
            tag: "pb_integrations",
            context: {
                pb_ledger: kind,
                pb_connector: this.connectorId,
                pb_connector_name: this.d.name || "",
            },
            back: {
                label: this.d.name || _t("Connector"),
                tag: SELF_TAG,
                context: {
                    connector_id: this.connectorId,
                    back_to: this.backTo,
                    back_label: this.backLabel,
                },
            },
        });
    }

    /**
     * The remaining server-driven link: "Start payroll import", which returns a
     * batch FORM in create mode rather than a list. It is a door into the import
     * pipeline, not one of the three raw-list satellites this cycle closed, so
     * it stays exactly as it was.
     */
    async openLink(method) {
        try {
            const act = await this.orm.call(MODEL, "get_link", [this.connectorId, method]);
            if (act) this.action.doAction(act);
        } catch (e) {
            // Reported rather than swallowed: a silent catch here is what makes
            // a button look like it does nothing (W40).
            console.warn("pb_import_advanced: connector link failed", method, e);
            this.notif.add(_t("That could not be opened."), { type: "warning" });
        }
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
