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
import { Component, useState, onWillStart, useExternalListener } from "@odoo/owl";
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
        this.state = useState({
            loaded: false, busy: false, busyMsg: "", detail: null,
            // which endpoint is mid-pull (id), so one chip spins and the rest
            // of the strip stays usable
            syncing: 0,
            // the header's overflow menu, and the credentials editor
            kebab: false,
            credOpen: false,
            // key -> what the admin typed. Write-only: nothing ever puts a
            // value INTO this object from the server (there is nothing to put
            // — the payload carries booleans), so a rendered input can never
            // display a secret.
            cred: {},
            credClear: {},
            credSaving: false,
        });
        // A click anywhere else closes the overflow menu. An event handler, not
        // a lifecycle hook — it only ever writes this component's own state.
        useExternalListener(window, "click", () => { this.state.kebab = false; });
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
    // ===================================================================== feeds
    get endpoints() { return this.d.endpoints || []; }

    /** May this caller change anything here? Derived from the model's own ACL. */
    get canWrite() { return !!this.d.can_write; }

    /**
     * The chip's second line — the data type, unless that IS the name.
     *
     * A feed derived from the data store is named after its data type, so the
     * obvious two-line header printed "Employee Master Data" directly above
     * "EMPLOYEE MASTER DATA". A label that repeats the line above it is not a
     * label, and the reader learns to stop reading both.
     */
    subLabel(ep) {
        const l = (ep.data_type_label || "").trim();
        return l && l.toLowerCase() !== (ep.name || "").trim().toLowerCase() ? l : "";
    }

    /**
     * "3 hours ago", from the ISO twin rather than from the display string.
     *
     * The server sends both (W46): the trimmed one is what a table column
     * prints, the ISO one is the only one that can be parsed. Doing the
     * arithmetic on the display string is how a chip ends up saying "NaN days".
     */
    since(iso) {
        if (!iso) { return _t("Never synced"); }
        const t = new Date(iso.endsWith("Z") ? iso : iso + "Z").getTime();
        if (isNaN(t)) { return _t("Never synced"); }
        const h = (Date.now() - t) / 3600000;
        if (h < 1) { return _t("Synced <1h ago"); }
        if (h < 24) { return _t("Synced %sh ago", Math.round(h)); }
        return _t("Synced %sd ago", Math.round(h / 24));
    }

    /** The status dot's tone — pbim semantics only, never a new hex (W1). */
    tone(ep) {
        if (ep.status === "failed") { return "err"; }
        if (ep.status === "partial") { return "warn"; }
        if (ep.status === "success") { return "ok"; }
        return "muted";
    }

    /**
     * One sentence, one msgid (W80): a translator cannot reorder fragments, and
     * this line is three numbers in a row, which is exactly where word order
     * differs.
     */
    counts(ep) {
        return _t("%(staged)s staged · %(synced)s pulled · %(mapped)s mapped", {
            staged: ep.staged, synced: ep.synced, mapped: ep.mapping_count,
        });
    }

    async syncEndpoint(ep) {
        if (this.state.syncing) { return; }
        this.state.syncing = ep.id;
        try {
            const res = await this.orm.call(
                MODEL, "sync_endpoint", [this.connectorId, ep.id]);
            if (res && res.endpoint) {
                // Replace the row in place so the strip does not reflow while
                // the user is looking at it.
                const list = this.state.detail.endpoints || [];
                const i = list.findIndex((e) => e.id === res.endpoint.id);
                if (i >= 0) { list[i] = res.endpoint; }
            }
            // The side panel's staged total moves with the feed that changed it,
            // or the two numbers on this screen disagree (found live).
            if (res && typeof res.data_store_count === "number") {
                this.state.detail.data_store_count = res.data_store_count;
            }
            if (res && res.error) { this.notif.add(res.error, { type: "warning" }); }
            else { this.notif.add(_t("Feed synced."), { type: "success" }); }
        } catch (e) {
            console.warn("pb_import_advanced: endpoint sync failed", e);
            this.notif.add(_t("That feed could not be synced."), { type: "danger" });
        } finally {
            this.state.syncing = 0;
        }
    }

    /** Derive the feeds from the vendor catalogue and from what is in the store. */
    detectFeeds() {
        return this._run(
            this.orm.call(MODEL, "sync_catalog", [this.connectorId]),
            _t("Detecting feeds…"));
    }

    /** This feed's rows, in the Integrations Data view, scoped both ways. */
    viewEndpointData(ep) {
        if (!this.hasLedgers) { return; }
        openHub(this.action, {
            tag: "pb_integrations",
            context: {
                pb_ledger: "store",
                pb_connector: this.connectorId,
                pb_connector_name: this.d.name || "",
                pb_data_type: ep.data_type,
                pb_data_type_name: ep.data_type_label || "",
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

    // ============================================================ mapping door
    /**
     * Is the Mapping Studio on this database?
     *
     * Same probe, same reason as `hasLedgers`: `pb_formula_studio` is not a
     * dependency of this module, so the actions registry is the only honest
     * question, and a button that would open nothing is simply not rendered
     * (W29). Cycle 1 shipped this strip with NO map button precisely because
     * the studio did not exist yet; it does now.
     */
    get hasMapping() {
        return registry.category("actions").contains("pb_mapping_studio");
    }

    /**
     * "Map fields", from a feed — the studio, already pointed at both ends.
     *
     * The whole point of the door is that it arrives CONFIGURED: this
     * connector as the source, this feed as the source's feed, the API mode,
     * and a chip back to this cockpit. A deep link that lands on the studio's
     * defaults would be a link that makes the user do the work twice.
     */
    openMapping(ep) {
        if (!this.hasMapping) { return; }
        openHub(this.action, {
            tag: "pb_mapping_studio",
            context: {
                pb_connector: this.connectorId,
                pb_endpoint: (ep && ep.id) || 0,
                pb_mode: "api",
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

    // =============================================================== credentials
    get credentials() { return this.d.credentials || { fields: [], editable: false }; }
    get canAdmin() { return !!this.credentials.editable; }

    toggleCredentials() { this.state.credOpen = !this.state.credOpen; }

    onCredInput(key, ev) { this.state.cred[key] = ev.target.value || ""; }
    toggleClear(key) { this.state.credClear[key] = !this.state.credClear[key]; }

    async saveCredentials() {
        if (this.state.credSaving) { return; }
        this.state.credSaving = true;
        try {
            const clear = Object.keys(this.state.credClear)
                .filter((k) => this.state.credClear[k]);
            const res = await this.orm.call(
                MODEL, "save_credentials",
                [this.connectorId, { ...this.state.cred }, clear]);
            if (res && res.credentials) {
                this.state.detail.credentials = res.credentials;
                this.state.detail.api_endpoint = res.api_endpoint || "";
            }
            // Typed values are dropped the moment they are saved, and the
            // editor CLOSES so the inputs unmount with them. Clearing the state
            // alone would not be enough: an input's `value` attribute does not
            // reset what the user typed into the live DOM node, so the secret
            // would stay on the page until a navigation.
            this.state.cred = {};
            this.state.credClear = {};
            this.state.credOpen = false;
            this.notif.add(_t("Credentials saved."), { type: "success" });
        } catch (e) {
            console.warn("pb_import_advanced: save_credentials failed", e);
            this.notif.add(
                (e && e.data && e.data.message) || _t("Those could not be saved."),
                { type: "danger" });
        } finally {
            this.state.credSaving = false;
        }
    }

    // ==================================================================== kebab
    /** A CLICK handler; `stopPropagation` so the window listener does not
     *  immediately close what this just opened. */
    toggleKebab(ev) {
        ev.stopPropagation();
        this.state.kebab = !this.state.kebab;
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
