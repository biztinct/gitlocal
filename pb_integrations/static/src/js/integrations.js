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
import { user } from "@web/core/user";
import { HubBackChip, hubBack, openHub } from "@pb_hub/js/hub_nav";
import { WfDrawer } from "@pb_wf_kit/js/wf_drawer";
import { RuleComposer } from "@pb_integrations/js/rule_composer";

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
    static components = { HubBackChip, WfDrawer, RuleComposer };
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
            // A FEED scope, from the connector cockpit's "View data" button.
            // Same shape and same rules as the connector one: it is a filter,
            // it says so on screen, and it can be dropped.
            dataType: ctx.pb_data_type || "",
            dataTypeName: ctx.pb_data_type_name || "",
            endpointId: ctx.pb_endpoint ? Number(ctx.pb_endpoint) : 0,
            endpointName: ctx.pb_endpoint_name || "",
            ledger: null, ledgerLoading: false,
            lsearch: "", f: {},
            drawer: null, drawerLoading: false,

            // ---- the Rule Composer (Cycle 8) ----
            // A SIBLING of the drawer, never a child of it: the drawer is a
            // 320px reading panel and a builder is not a reading panel. The
            // other three ledger kinds keep it exactly as they had it.
            composer: null,
            canEditRules: false,
        });

        // One navigation at a time (C1's flag).
        this._opening = false;

        onWillStart(async () => {
            await this.load();
            // Asked ONCE, and only about a group — the write itself is gated
            // server-side by `rule_save`, which fails CLOSED. This flag decides
            // whether a button is drawn, and a hidden control is never a gate.
            this.state.canEditRules = await this._readRuleRights();
            if (this.state.view === "data") { await this.loadLedger(); }
        });
    }

    // ================================================================== board
    async load() {
        const d = await this.orm.call("pb.integrations", "get_board", []);
        Object.assign(this.state, {
            kpis: d.kpis, connectors: d.connectors, types: d.types,
            total: d.total, loaded: true,
            // `!== false` at every read site (see `feedsKnown`), so an older
            // server that never sends the key still shows its feed counts.
            feeds_known: d.feeds_known,
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

    /**
     * The card's counts — minus the mappings, which are a DOOR now.
     *
     * It was four numbers assembled from `<t>` fragments in the template, which
     * a translator cannot reorder; the feed count made it five and forced the
     * issue. Cycle 2 then made "N mappings" clickable — it opens the Mapping
     * Studio on this connector, so the number on the board is also the way to
     * change it — and it therefore had to leave the sentence, because a
     * translator cannot reorder a fragment out of a `t-esc` and back into a
     * button (W80). Two complete phrases, two msgids; never one sentence broken
     * into pieces.
     *
     * COUNT HONESTY (Cycle 3). `feeds_known` is false on a database whose
     * upgrade has not reached it, and every feed number in the payload is then
     * 0 because nothing could look — not because there are none. Printing that
     * as "0 feeds" makes an un-upgraded database indistinguishable from an
     * empty one (W79), which is the exact confusion `_schema_ready` logs a
     * warning about. So the phrase is DROPPED rather than zeroed: a whole
     * second msgid, not a fragment, for the same reason as above.
     */
    cardCounts(c) {
        if (!this.feedsKnown) {
            return _t("%(staged)s staged · %(synced)s synced",
                      { staged: c.staged, synced: c.synced });
        }
        return _t("%(feeds)s feeds · %(staged)s staged · %(synced)s synced",
                  { feeds: c.feeds || 0, staged: c.staged, synced: c.synced });
    }

    /**
     * Could the server count feeds at all?
     *
     * Defaults to TRUE when the key is absent, which is the honest default for
     * exactly one reason: every database that has this code also has the key,
     * so a missing key means a stale cached bundle rather than a missing table
     * — and hiding a real count because of a cache is a worse answer than
     * showing it.
     */
    get feedsKnown() {
        return this.state.feeds_known !== false;
    }

    /** The clickable half. Its own msgid, and a whole phrase. */
    mappingsLabel(c) { return _t("%s mappings", c.mappings); }

    /**
     * Is the Mapping Studio on this database? `pb_formula_studio` is not a
     * dependency of this module, so the registry is the probe and a link that
     * would open nothing is simply not rendered (W29).
     */
    get hasMapping() {
        return registry.category("actions").contains("pb_mapping_studio");
    }

    /** The count is a door: the studio, scoped to this connector. */
    openMappingStudio(c) {
        if (this._opening || !this.hasMapping) { return; }
        this._opening = true;
        try {
            openHub(this.action, {
                tag: "pb_mapping_studio",
                context: { pb_connector: c.id, pb_mode: "api" },
                back: { label: _t("Integrations"), tag: "pb_integrations" },
            });
        } catch (e) {
            this._opening = false;
            console.warn("pb_integrations: could not open Mapping", e);
        }
    }

    /** "Feeds", or "Feeds · N stale" when any of them are overdue. */
    get feedsKpiLabel() {
        const stale = (this.state.kpis && this.state.kpis.feeds_stale) || 0;
        return stale ? _t("Feeds · %s stale", stale) : _t("Feeds");
    }

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
        this.state.dataType = "";
        this.state.dataTypeName = "";
        this.state.endpointId = 0;
        this.state.endpointName = "";
        await this.loadLedger();
    }

    /** Drop the feed scope, keeping the connector one. */
    async clearDataTypeScope() {
        if (!this.state.dataType && !this.state.endpointId) { return; }
        this.state.dataType = "";
        this.state.dataTypeName = "";
        this.state.endpointId = 0;
        this.state.endpointName = "";
        await this.loadLedger();
    }

    async loadLedger() {
        this.state.ledgerLoading = true;
        try {
            const d = await this.orm.call(
                "pb.integrations", "get_ledger",
                [this.state.kind, this.state.connectorId || false,
                 this.state.dataType || false, this.state.endpointId || false]);
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

    /** The feed scope's sentence — one getter, one msgid (W80). */
    get feedScopeLabel() {
        return _t("Feed: %s", this.state.endpointName ||
                  this.state.dataTypeName || this.state.dataType);
    }

    /** The feed scope only means anything on the store tab. */
    get feedScopeActive() {
        return !!((this.state.endpointId || this.state.dataType) &&
                  this.state.kind === "store");
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
        // A transformation rule is not a row to READ, it is a rule to CHANGE —
        // so it opens the composer instead of the drawer (Cycle 8). Everything
        // below this line is the other three kinds, untouched.
        if (this.state.kind === "rule") {
            this.state.drawer = null;
            this.state.composer = {
                ruleId: r.id,
                connectorId: r.connector_id || this.state.connectorId || 0,
            };
            return;
        }
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

    // ================================================== the Rule Composer
    /**
     * May this user change a transformation rule?
     *
     * The group, not a probe RPC: `rule_save` is the real gate and it fails
     * CLOSED, so this only decides whether "New rule" is drawn. A failure to
     * READ the group is reported rather than swallowed (W40) and answers no —
     * a button that is certain to be refused is worse than an absent one.
     */
    async _readRuleRights() {
        try {
            if (await user.hasGroup("pb_hr_payroll_formula.group_formula_manager")) {
                return true;
            }
            return await user.hasGroup("pb_hr_payroll_formula.group_formula_admin");
        } catch (e) {
            console.warn("pb_integrations: could not read the rule-editing rights", e);
            return false;
        }
    }

    /**
     * The composer needs a connector; the tab may not be scoped to one.
     *
     * MEMOISED on the source array's identity. A getter that builds a fresh
     * array on every render hands a child a prop that has "changed" every time
     * and re-renders it for nothing — the same shape of waste as writing a new
     * array into reactive state on every recompute (W148), one layer out. The
     * board's connector list only changes when `load()` reassigns it.
     */
    get composerConnectors() {
        if (this._cxSource !== this.state.connectors) {
            this._cxSource = this.state.connectors;
            this._cxCache = this.state.connectors.map(
                (c) => ({ id: c.id, name: c.name, icon: c.icon }));
        }
        return this._cxCache;
    }

    newRule() {
        this.state.drawer = null;
        this.state.composer = { ruleId: 0, connectorId: this.state.connectorId || 0 };
    }

    closeComposer() { this.state.composer = null; }

    /**
     * A saved rule changes the SENTENCE the ledger prints for it, so the table
     * is re-read rather than patched: the summary is computed and stored on the
     * server, and guessing it here would be a second implementation of it.
     */
    async onRuleSaved() {
        this.state.composer = null;
        await this.loadLedger();
    }

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
