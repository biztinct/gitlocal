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

const FEED_OPERATIONS = [
    ["catalog_only", _t("Catalogue only")],
    ["generic", _t("Connector-defined operation")],
    ["employee", _t("Employee master")],
    ["salary", _t("Salary / compensation")],
    ["attendance_summary", _t("Attendance summary")],
    ["overtime", _t("Overtime requests")],
    ["attendance_daily", _t("Attendance by employee/date")],
    ["leave", _t("Leave records")],
    ["timesheet", _t("Timesheets")],
];
const FEED_DATA_TYPES = [
    ["employee", _t("Employee master data")], ["salary", _t("Salary / compensation")],
    ["attendance", _t("Attendance")], ["leave", _t("Leave / time-off")],
    ["dependent", _t("Dependants")], ["benefit", _t("Benefits")],
    ["tax", _t("Tax")], ["custom", _t("Custom / other")],
];
const OPERATION_DATA_TYPE = {
    employee: "employee", salary: "salary",
    attendance_summary: "attendance", attendance_daily: "attendance",
    overtime: "custom", timesheet: "custom", leave: "leave",
};

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
            // The window every dated pull asks for. Seeded from the server
            // (last window pulled, else this month) and left alone once the
            // user has chosen one, so a period picked for a July run is not
            // quietly reset by the next refresh.
            period: { from: "", to: "", label: "" },
            periodTouched: false,
            // which endpoint is mid-pull (id), so one chip spins and the rest
            // of the strip stays usable
            syncing: 0,
            // RD58 — the schedule's own switches; separate from `busy` so
            // flicking one does not grey the whole cockpit.
            schedBusy: false,
            // ditto for the C6 vendor field-list fetch, which is a different
            // call with a different failure mode and must not borrow `syncing`
            // — one spinner for two verbs is a strip that lies about which one
            // is running
            fetching: 0,
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
            // Full-screen configuration studio. Drafts are client-only until
            // the single Save; closing is therefore a real cancel operation.
            configOpen: false,
            configTab: "connection",
            config: {},
            feedDrafts: [],
            selectedFeedKey: "",
            configSaving: false,
        });
        // A click anywhere else closes the overflow menu. An event handler, not
        // a lifecycle hook — it only ever writes this component's own state.
        useExternalListener(window, "click", () => { this.state.kebab = false; });
        useExternalListener(window, "message", (ev) => this.onOAuthMessage(ev));
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
    get feedOperations() { return FEED_OPERATIONS; }
    get feedDataTypes() { return FEED_DATA_TYPES; }
    get feedMethods() { return [["get", "GET"], ["post", "POST"]]; }
    initials() { return (this.d.name || "?").trim().slice(0, 2).toUpperCase(); }

    async refresh() {
        try {
            this.state.detail = await this.orm.call(MODEL, "get_connector_detail", [this.connectorId]);
            const p = (this.state.detail || {}).pull_period;
            if (p && !this.state.periodTouched) { this.state.period = { ...p }; }
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
                else this.notif.add(_t("Done."), { type: "success" });
            }
        } catch (e) {
            this.notif.add((e && e.message && e.message.toString()) || _t("Action failed."), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    // RD58 — turn the monthly fetch, and the record update, on or off.
    async setSchedule(changes) {
        this.state.schedBusy = true;
        try {
            const r = await this.orm.call(MODEL, "set_schedule",
                [this.connectorId, changes.enabled, changes.writeback]);
            if (r && r.ok && this.state.detail) {
                this.state.detail.schedule = r.schedule;
            } else if (r && r.msg) {
                this.notif.add(r.msg, { type: "warning" });
            }
        } catch (e) {
            console.warn("connector cockpit: schedule change failed", e);
            this.notif.add("That could not be changed.", { type: "warning" });
        } finally {
            this.state.schedBusy = false;
        }
    }

    runAction(method) {
        const msg = { action_test_connection: "Testing connection…", action_pull_data: "Pulling data…",
                      action_fetch_available_fields: "Fetching fields…", action_disconnect: "Disconnecting…",
                      action_fetch_last_month_now: "Fetching last month…",
                      action_refresh_records_now: "Updating records…" }[method] || "Working…";
        const args = [this.connectorId, method];
        if (method === "action_pull_data") {
            // Only the pull reads a window; the other three take none and must
            // keep being called with none.
            args.push(this.pullFrom, this.pullTo);
        }
        return this._run(this.orm.call(MODEL, "run_connector_action", args), msg);
    }

    // ================================================== the window being pulled
    //
    // Every dated feed here (attendance, overtime, leave, timesheets) answers
    // for a WINDOW, and without one the server falls back to the current
    // calendar month. A July pay run refreshed from this screen in August
    // therefore pulled August's attendance and August's overtime, stamped them
    // onto rows the run then read as July's, and reported success. Nothing was
    // wrong except the month, and no screen said which month it was.
    get pullFrom() { return this.state.period.from; }
    get pullTo() { return this.state.period.to; }
    get pullPeriodLabel() { return this.state.period.label || ""; }

    setPeriod(which, ev) {
        const value = ev.target.value;
        if (!value) { return; }
        this.state.periodTouched = true;
        this.state.period[which] = value;
        if (which === "from" && this.state.period.to < value) {
            this.state.period.to = value;
        }
        this.state.period.label = "";
    }

    /** Jump the window a whole month at a time — the unit a pay run uses. */
    shiftPeriod(months) {
        const from = new Date(this.state.period.from + "T00:00:00Z");
        if (isNaN(from.getTime())) { return; }
        this.state.periodTouched = true;
        const y = from.getUTCFullYear();
        const m = from.getUTCMonth() + months;
        const start = new Date(Date.UTC(y, m, 1));
        const end = new Date(Date.UTC(y, m + 1, 0));
        this.state.period.from = start.toISOString().slice(0, 10);
        this.state.period.to = end.toISOString().slice(0, 10);
        this.state.period.label = "";
    }

    /** Does this feed's data depend on the window? Employees and salary do not. */
    isPeriodScoped(ep) { return !!ep.period_scoped; }

    /**
     * What a feed card should say about the month its rows are about.
     *
     * Deliberately separate from `since()`: that answers "when did we ask",
     * this answers "what did we ask for", and conflating them is what let a
     * feed full of August rows look correct during a July run.
     */
    periodNote(ep) {
        if (!ep.period_scoped || !ep.period_label) { return ""; }
        if (ep.period_from === this.state.period.from && ep.period_to === this.state.period.to) {
            return _t("Holds %s", ep.period_label);
        }
        return _t("Holds %s — not the selected period", ep.period_label);
    }
    periodMismatch(ep) {
        return !!(ep.period_scoped && ep.period_from &&
                  (ep.period_from !== this.state.period.from ||
                   ep.period_to !== this.state.period.to));
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
    legacyRowsLabel(ep) {
        return ep.legacy_unassigned
            ? _t("%s older rows are not tied to an exact feed", ep.legacy_unassigned)
            : "";
    }

    async syncEndpoint(ep) {
        if (this.state.syncing) { return; }
        this.state.syncing = ep.id;
        try {
            const res = await this.orm.call(
                MODEL, "sync_endpoint",
                [this.connectorId, ep.id, this.pullFrom, this.pullTo]);
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
            if (res && res.error) {
                this.notif.add(res.error, { type: "warning" });
            } else if (res && res.endpoint && res.endpoint.status === "failed") {
                this.notif.add(
                    res.endpoint.last_error || _t("The feed ran, but its records could not be staged."),
                    { type: "danger" });
            } else if (res && res.endpoint && res.endpoint.status === "partial") {
                this.notif.add(
                    _t("The feed synced with some staging errors. Review the feed card."),
                    { type: "warning" });
            } else {
                this.notif.add(_t("Feed synced."), { type: "success" });
            }
        } catch (e) {
            console.warn("pb_import_advanced: endpoint sync failed", e);
            this.notif.add(_t("That feed could not be synced."), { type: "danger" });
        } finally {
            this.state.syncing = 0;
        }
    }

    /**
     * "31 expected fields" — what this feed is KNOWN to deliver.
     *
     * Empty string, not "0 fields", when nothing is catalogued: a strip that
     * prints a zero next to every feed teaches the reader to stop reading it,
     * and on a database whose upgrade has not arrived the zero would be a lie
     * about the vendor rather than a fact (W79).
     */
    fieldsLabel(ep) {
        const n = ep.field_count || 0;
        return n ? _t("%s expected fields", n) : "";
    }

    /**
     * Ask the vendor for this feed's field list — Integrations Cycle 6.
     *
     * The button is offered only where the connector class really implements
     * metadata; the server refuses the three stubs by name and answers with a
     * sentence, which is surfaced verbatim rather than swallowed.
     */
    async fetchFields(ep) {
        if (this.state.fetching) { return; }
        this.state.fetching = ep.id;
        try {
            const res = await this.orm.call(
                MODEL, "fetch_endpoint_fields", [this.connectorId, ep.id]);
            if (res && res.endpoint) {
                const list = this.state.detail.endpoints || [];
                const i = list.findIndex((e) => e.id === res.endpoint.id);
                if (i >= 0) { list[i] = res.endpoint; }
            }
            if (res && res.ok) {
                this.notif.add(res.msg || _t("Field list updated."), { type: "success" });
            } else {
                this.notif.add((res && res.error) || _t("No field list was returned."),
                               { type: "warning" });
            }
        } catch (e) {
            console.warn("pb_import_advanced: field fetch failed", e);
            this.notif.add(_t("That field list could not be fetched."), { type: "danger" });
        } finally {
            this.state.fetching = 0;
        }
    }

    /** Add missing local catalogue rows; this is not a remote API scan. */
    async detectFeeds() {
        this.state.busy = true;
        this.state.busyMsg = _t("Checking the installed vendor catalogue…");
        try {
            const res = await this.orm.call(MODEL, "sync_catalog", [this.connectorId]);
            if (res && typeof res === "object") { this.state.detail = res; }
            if (res && res.error) {
                this.notif.add(res.error, { type: "warning" });
            } else {
                const cat = (res && res.catalog) || {};
                this.notif.add(
                    cat.created
                        ? _t("%s missing feeds added. Existing configuration was kept.", cat.created)
                        : _t("Feed catalogue is already complete. Nothing was overwritten."),
                    { type: "success" });
            }
        } catch (e) {
            this.notif.add(_t("The installed feed catalogue could not be checked."),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ==================================================== configuration studio
    openConfiguration(endpoint = null) {
        const cfg = this.d.configuration || {};
        this.state.config = { ...cfg };
        this.state.feedDrafts = (this.endpoints || []).map((ep) => ({
            id: ep.id,
            key: `feed-${ep.id}`,
            name: ep.name || "",
            code: ep.code || "",
            data_type: ep.data_type || "custom",
            operation: ep.operation || "catalog_only",
            http_method: (ep.method || "GET").toLowerCase(),
            path: ep.path || "",
            params_note: ep.params_note || "",
            active: ep.active !== false,
            template_backed: !!ep.template_backed,
        }));
        const selected = endpoint && endpoint.id
            ? this.state.feedDrafts.find((feed) => feed.id === endpoint.id) : null;
        this.state.selectedFeedKey = selected ? selected.key :
            (this.state.feedDrafts.length ? this.state.feedDrafts[0].key : "");
        this.state.configTab = selected ? "feeds" : "connection";
        this.state.configOpen = true;
    }

    closeConfiguration() {
        if (this.state.configSaving) { return; }
        this.state.configOpen = false;
        this.state.config = {};
        this.state.feedDrafts = [];
        this.state.selectedFeedKey = "";
    }

    get selectedFeed() {
        return this.state.feedDrafts.find(
            (feed) => feed.key === this.state.selectedFeedKey) || null;
    }
    get selectedFeedTypeLocked() {
        return !!(this.selectedFeed && OPERATION_DATA_TYPE[this.selectedFeed.operation]);
    }
    get draftRunnableCount() {
        return this.state.feedDrafts.filter(
            (feed) => feed.active && feed.operation !== "catalog_only" && !!feed.path).length;
    }

    selectFeed(feed) { this.state.selectedFeedKey = feed.key; }
    setConfigTab(tab) { this.state.configTab = tab; }
    onConfigInput(key, ev) {
        this.state.config[key] = ev.target.value || "";
        if (key === "api_endpoint") { this.state.config.api_endpoint_is_default = false; }
    }
    onFeedInput(key, ev) {
        if (!this.selectedFeed) { return; }
        const value = ev.target.value || "";
        this.selectedFeed[key] = value;
        // Built-in handlers have a fixed output contract. Keep the dependent
        // field aligned immediately instead of waiting for a server error.
        if (key === "operation" && OPERATION_DATA_TYPE[value]) {
            this.selectedFeed.data_type = OPERATION_DATA_TYPE[value];
        }
    }
    onFeedActive(ev) {
        if (this.selectedFeed) { this.selectedFeed.active = !!ev.target.checked; }
    }

    addFeed() {
        const key = `new-${Date.now()}-${this.state.feedDrafts.length}`;
        const feed = {
            id: 0, key, name: _t("New feed"), code: "newfeed",
            data_type: "custom", operation: "catalog_only",
            http_method: "get", path: "", params_note: "", active: true,
            template_backed: false,
        };
        this.state.feedDrafts.push(feed);
        this.state.selectedFeedKey = key;
        this.state.configTab = "feeds";
    }

    feedPreview(feed) {
        if (!feed || !feed.path) { return _t("Add a path to preview the URL"); }
        if (/^https?:\/\//i.test(feed.path)) { return feed.path; }
        const base = (this.state.config.api_endpoint || "").replace(/\/$/, "");
        return base ? `${base}/${feed.path.replace(/^\//, "")}` : feed.path;
    }

    async copyText(value) {
        if (!value || !navigator.clipboard) { return; }
        await navigator.clipboard.writeText(value);
        this.notif.add(_t("Copied."), { type: "success" });
    }

    _publicConfiguration() {
        const cfg = this.state.config;
        return {
            api_endpoint: cfg.api_endpoint || "",
            api_version: cfg.api_version || "",
            sync_interval: cfg.sync_interval || 0,
            oauth_authorize_url: cfg.oauth_authorize_url || "",
            oauth_token_url: cfg.oauth_token_url || "",
            oauth_scope: cfg.oauth_scope || "",
            oauth_redirect_uri: cfg.oauth_redirect_uri || "",
        };
    }

    _feedRows() {
        return this.state.feedDrafts.map((feed) => ({
            id: feed.id || 0, name: feed.name, code: feed.code,
            data_type: feed.data_type, operation: feed.operation,
            http_method: feed.http_method, path: feed.path,
            params_note: feed.params_note, active: !!feed.active,
        }));
    }

    async beginOAuth() {
        const popup = window.open(
            "about:blank",
            "pb_zoho_oauth", "popup=yes,width=620,height=760");
        if (!popup) {
            this.notif.add(_t("Allow pop-ups to connect Zoho."), { type: "warning" });
            return;
        }
        try {
            // The label says Save & connect: persist the entire visible draft
            // before leaving for Zoho, so the callback refresh loses nothing.
            const res = await this.orm.call(
                MODEL, "save_configuration",
                [this.connectorId, this._publicConfiguration(), this._feedRows()]);
            if (res && res.error) { throw new Error(res.error); }
            if (res) { this.state.detail = res; }
            popup.location.href = `/pb/integrations/oauth/${this.connectorId}/start`;
        } catch (e) {
            popup.close();
            this.notif.add(
                (e && e.message) || _t("OAuth settings could not be saved."),
                { type: "danger" });
        }
    }

    openCredentialSetup() {
        // OAuth provider locations are public configuration; the Client ID
        // and secret stay in the cockpit's established write-only editor.
        this.closeConfiguration();
        this.state.credOpen = true;
        requestAnimationFrame(() => {
            document.querySelector(".pbcc-cred")?.scrollIntoView({
                behavior: "smooth", block: "center",
            });
        });
    }

    async onOAuthMessage(ev) {
        if (ev.origin !== window.location.origin || !ev.data ||
                ev.data.type !== "pb-zoho-oauth") { return; }
        await this.refresh();
        if (this.state.configOpen) {
            const tab = this.state.configTab;
            this.openConfiguration();
            this.state.configTab = tab;
        }
        this.notif.add(
            ev.data.status === "success" ? _t("Zoho is connected.") :
                _t("Zoho authorization did not complete."),
            { type: ev.data.status === "success" ? "success" : "warning" });
    }

    async saveConfiguration() {
        if (this.state.configSaving) { return; }
        this.state.configSaving = true;
        try {
            const publicConfig = this._publicConfiguration();
            const rows = this._feedRows();
            const res = await this.orm.call(
                MODEL, "save_configuration", [this.connectorId, publicConfig, rows]);
            if (res && !res.error) {
                this.state.detail = res;
                this.state.configOpen = false;
                this.notif.add(_t("Connection and feeds saved."), { type: "success" });
            } else {
                this.notif.add((res && res.error) || _t("Configuration was not saved."),
                               { type: "warning" });
            }
        } catch (e) {
            const message = (e && e.data && e.data.message) ||
                (e && e.message) || _t("Configuration was not saved.");
            this.notif.add(message.toString(), { type: "danger" });
        } finally {
            this.state.configSaving = false;
        }
    }

    async restoreSelectedFeed() {
        const feed = this.selectedFeed;
        if (!feed || !feed.id) { return; }
        try {
            const res = await this.orm.call(
                MODEL, "restore_endpoint_template", [this.connectorId, feed.id]);
            if (res && !res.error) {
                this.state.detail = res;
                this.openConfiguration();
                this.state.configTab = "feeds";
                this.state.selectedFeedKey = `feed-${feed.id}`;
                this.notif.add(_t("Vendor template restored."), { type: "success" });
            } else {
                this.notif.add((res && res.error) || _t("Template was not restored."),
                               { type: "warning" });
            }
        } catch (e) {
            this.notif.add(_t("Template was not restored."), { type: "danger" });
        }
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
                pb_endpoint: ep.id,
                pb_endpoint_name: ep.name || ep.code || "",
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
