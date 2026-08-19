/** @odoo-module **/
/**
 * `pb_integrations` — the one home for connectors (IA Cycle 3).
 *
 * The board is what it always was: KPIs, filters, a connector card per system.
 * What changed is everything AROUND it.
 *
 *   - it used to end in three link tiles that opened raw `list,form` windows on
 *     field mappings, the API data store and transformation rules. Those tiles
 *     are gone. The same three tables are now a **Data view** of this cockpit —
 *     a tab strip, a grid, and the shared 320px drawer on row click. No native
 *     list is a destination any more (flow doctrine 2);
 *   - "Connect a system" used to open a 30-field stock Odoo modal. It now opens
 *     a full-screen four-step flow (flow doctrine 1). The modal action is still
 *     registered and nothing in Payobook opens it;
 *   - it is now a DESTINATION as well as a home: Import and the connector
 *     cockpit deep-link into it with a `pb_back` chip, so "the same cockpit,
 *     different back button" — the bug the audit found between Import and
 *     Integrations — cannot recur. The chip is rendered here, from whatever the
 *     caller passed, and this file never has to know who that was.
 *
 * The drawer is imported from `pb_wf_kit`, never forked (W6). The GRID around it
 * is a deliberate clone of the pay-run ledger's shape rather than an import of
 * it — see the module's README note and the cycle report: `pb_payrun_ledgers`
 * depends on `pb_hr_fullandfinal` and the whole pay-run domain, and a Setup-area
 * cockpit that cannot install without settlement tables is a worse coupling than
 * two hundred lines that look alike.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack, openHub } from "@pb_hub/js/hub_nav";
import { WfDrawer } from "@pb_wf_kit/js/wf_drawer";

const STATUS_CHIPS = [
    { id: "all", label: "All" }, { id: "connected", label: "Connected" },
    { id: "error", label: "Error" }, { id: "disconnected", label: "Disconnected" },
];
const RECENCY_CHIPS = [
    { id: "all", label: "Any time" }, { id: "1h", label: "Synced ≤1h" },
    { id: "1d", label: "Synced ≤1d" }, { id: "old", label: "Older" }, { id: "never", label: "Never" },
];

/**
 * The three tables the raw-list tiles used to open, in the order an operator
 * meets them: what you mapped, what you pulled, what you derived from it.
 */
const LEDGER_TABS = [
    { id: "mapping", icon: "link", label: _t("Field mappings") },
    { id: "store", icon: "database", label: _t("Data store") },
    { id: "rule", icon: "sigma", label: _t("Transformation rules") },
];

export class PbIntegrations extends Component {
    static template = "pb_integrations.PbIntegrations";
    static components = { HubBackChip, WfDrawer };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");

        // Read ONCE, from props, never written back — the arrival protocol's
        // rule since C1's shell.
        this.back = hubBack(this.props);
        const ctx = (this.props.action && this.props.action.context) || {};
        const askedKind = LEDGER_TABS.some((t) => t.id === ctx.pb_ledger)
            ? ctx.pb_ledger : "";

        this.state = useState({
            loaded: false, kpis: {}, connectors: [], types: [], total: 0,
            search: "", status: "all", type: "", recency: "all",

            // ---- the Data view ----
            view: askedKind ? "data" : "connectors",
            kind: askedKind || "mapping",
            // A connector deep-link SCOPES the ledger. It is a filter, not a
            // selection — the same distinction `pb_focus` draws in the hub
            // arrival protocol (W26): arriving from a connector must not also
            // pop a drawer over the table you were sent to read.
            connectorId: ctx.pb_connector ? Number(ctx.pb_connector) : 0,
            connectorName: ctx.pb_connector_name || "",
            ledger: null, ledgerLoading: false,
            lsearch: "", f: {},
            drawer: null, drawerLoading: false,
        });

        // One navigation at a time (C1's flag).
        this._opening = false;

        onWillStart(async () => {
            await this.load();
            if (this.state.view === "data") { await this.loadLedger(); }
        });
    }

    // ================================================================== board
    async load() {
        const d = await this.orm.call("pb.integrations", "get_board", []);
        Object.assign(this.state, {
            kpis: d.kpis, connectors: d.connectors, types: d.types,
            total: d.total, loaded: true,
        });
    }

    ic(n, s = 16) { return ic(n, s); }
    get statusChips() { return STATUS_CHIPS; }
    get recencyChips() { return RECENCY_CHIPS; }
    get ledgerTabs() { return LEDGER_TABS; }

    setStatus(s) { this.state.status = s; }
    setType(t) { this.state.type = this.state.type === t ? "" : t; }
    setRecency(r) { this.state.recency = r; }
    onSearch(ev) { this.state.search = (ev.target.value || "").toLowerCase(); }

    _hoursSince(iso) {
        if (!iso) return null;
        const t = new Date(iso.replace(" ", "T") + "Z").getTime();
        if (isNaN(t)) return null;
        return (Date.now() - t) / 3600000;
    }
    syncLabel(c) {
        const h = this._hoursSince(c.last_sync);
        if (h === null) return "Never synced";
        if (h < 1) return "Synced <1h ago";
        if (h < 24) return "Synced " + Math.round(h) + "h ago";
        return "Synced " + Math.round(h / 24) + "d ago";
    }
    _matchStatus(c, st) { return st === "all" ? true : c.status === st; }
    _matchRecency(c) {
        const r = this.state.recency;
        if (r === "all") return true;
        const h = this._hoursSince(c.last_sync);
        if (r === "never") return h === null;
        if (h === null) return false;
        if (r === "1h") return h <= 1;
        if (r === "1d") return h <= 24;
        if (r === "old") return h > 24;
        return true;
    }
    get filtered() {
        const q = this.state.search, ty = this.state.type;
        return this.state.connectors.filter(c => {
            if (ty && c.type !== ty) return false;
            if (!this._matchStatus(c, this.state.status)) return false;
            if (!this._matchRecency(c)) return false;
            if (q && !((c.name || "").toLowerCase().includes(q) || (c.type_label || "").toLowerCase().includes(q))) return false;
            return true;
        });
    }
    countStatus(id) { return this.state.connectors.filter(c => this._matchStatus(c, id)).length; }

    // =============================================================== the views
    /** A CLICK handler. Switching to Data loads it the first time only. */
    async setView(view) {
        if (this.state.view === view) { return; }
        this.state.view = view;
        this.state.drawer = null;
        if (view === "data" && !this.state.ledger) { await this.loadLedger(); }
    }

    async setKind(kind) {
        if (this.state.kind === kind) { return; }
        this.state.kind = kind;
        this.state.drawer = null;
        this.state.lsearch = "";
        this.state.f = {};
        await this.loadLedger();
    }

    /** Drop the connector scope a deep link arrived with. */
    async clearConnectorScope() {
        if (!this.state.connectorId) { return; }
        this.state.connectorId = 0;
        this.state.connectorName = "";
        await this.loadLedger();
    }

    async loadLedger() {
        this.state.ledgerLoading = true;
        try {
            const d = await this.orm.call("pb.integrations", "get_ledger",
                                          [this.state.kind, this.state.connectorId || false]);
            this.state.ledger = d;
            const f = {};
            for (const fac of (d.facets || [])) { f[fac.key] = ""; }
            this.state.f = f;
        } catch (e) {
            // Reported, never swallowed into an empty table (W40): an empty
            // grid and a failed read look identical and mean opposite things.
            console.warn("pb_integrations: could not load the ledger", e);
            this.notif.add(_t("Could not load this table."), { type: "danger" });
            this.state.ledger = null;
        } finally {
            this.state.ledgerLoading = false;
        }
    }

    // ---------------------------------------------------------- ledger filters
    onLedgerSearch(ev) { this.state.lsearch = (ev.target.value || "").toLowerCase(); }
    setFacet(key, val) { this.state.f[key] = this.state.f[key] === val ? "" : val; }
    onFacetSelect(key, ev) { this.state.f[key] = ev.target.value || ""; }

    _matchRow(r) {
        for (const [k, v] of Object.entries(this.state.f)) {
            if (v && String((r._f || {})[k]) !== String(v)) { return false; }
        }
        const q = this.state.lsearch;
        if (q && !(r._s || "").toLowerCase().includes(q)) { return false; }
        return true;
    }
    get ledgerRows() {
        return ((this.state.ledger && this.state.ledger.rows) || [])
            .filter((r) => this._matchRow(r));
    }
    chipCount(key, val) {
        return ((this.state.ledger && this.state.ledger.rows) || [])
            .filter((r) => String((r._f || {})[key]) === String(val)).length;
    }
    get ledgerDirty() {
        return !!(this.state.lsearch || Object.values(this.state.f).some((v) => v));
    }
    clearLedgerFilters() {
        const f = {};
        for (const k of Object.keys(this.state.f)) { f[k] = ""; }
        this.state.f = f;
        this.state.lsearch = "";
    }

    // ---------------------------------------------------------- ledger labels
    /**
     * One sentence, one msgid.
     *
     * Both of these used to be the obvious thing — a chain of `<t t-esc>`
     * fragments in the template — and both are exactly what W80 forbids: a
     * translator cannot reorder fragments, and word order is the first thing
     * that differs. They are also the two strings on this surface that CARRY
     * numbers, so they are the two that must not silently stay English.
     */
    get scopeLabel() {
        return _t("Showing only %s", this.state.connectorName || _t("this connector"));
    }

    get footLabel() {
        const d = this.state.ledger || {};
        const shown = this.ledgerRows.length;
        if ((d.total || 0) > (d.shown || 0)) {
            return _t("Showing %(shown)s of %(total)s · the newest %(loaded)s are "
                      + "loaded, so narrow the search to reach the rest.",
                      { shown, total: d.total, loaded: d.shown });
        }
        return _t("Showing %(shown)s of %(total)s", { shown, total: d.total || 0 });
    }

    // ================================================================= drawer
    /**
     * A row is a door that opens INWARDS. There is no navigation here at all —
     * that is the whole point of the view.
     */
    async openRow(r) {
        if (!r.id) { return; }
        // Shown immediately from what the row already knows, then filled in: an
        // empty panel that appears at once reads as loading, a click with
        // nothing on screen for 200ms reads as a dead row.
        this.state.drawer = { title: r.cells[0] || "—", subtitle: "", sections: [] };
        this.state.drawerLoading = true;
        try {
            const d = await this.orm.call("pb.integrations", "get_ledger_detail",
                                          [this.state.kind, r.id]);
            if (!this.state.drawer) { return; }        // closed while in flight
            this.state.drawer = {
                title: d.title || r.cells[0] || "—",
                subtitle: d.subtitle || "",
                sections: d.sections || [],
            };
        } catch (e) {
            console.warn("pb_integrations: get_ledger_detail failed", e);
            this.notif.add(_t("Could not load this row's detail."), { type: "danger" });
        } finally {
            this.state.drawerLoading = false;
        }
    }

    closeDrawer() { this.state.drawer = null; }

    // ================================================================== doors
    /** The connector cockpit, told where it came from and how to get back. */
    openConnector(id) {
        if (this._opening) { return; }
        this._opening = true;
        try {
            this.action.doAction({
                type: "ir.actions.client", tag: "pb_import_connector_cockpit",
                name: "Connector",
                params: { connector_id: id,
                          back_to: "pb_integrations.action_pb_integrations",
                          back_label: _t("Integrations") },
            });
        } catch (e) {
            this._opening = false;
            console.warn("pb_integrations: could not open the connector", e);
        }
    }

    /**
     * "Connect a system" — the full-screen flow, not the modal.
     *
     * It carries a back door to this cockpit, so abandoning the flow lands
     * where it started rather than wherever the browser remembers.
     */
    connectSystem() {
        if (this._opening) { return; }
        this._opening = true;
        try {
            openHub(this.action, {
                tag: "pb_integration_onboarding",
                back: { label: _t("Integrations"), tag: "pb_integrations" },
            });
        } catch (e) {
            this._opening = false;
            console.warn("pb_integrations: could not open the onboarding flow", e);
        }
    }
}

registry.category("actions").add("pb_integrations", PbIntegrations);
