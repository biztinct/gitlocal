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
import { useFilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

/**
 * The three tables the raw-list tiles used to open, in the order an operator
 * meets them: what you mapped, what you pulled, what you derived from it.
 */
const LEDGER_TABS = [
    { id: "mapping", icon: "link", label: _t("Field mappings"), noun: () => _t("mappings") },
    { id: "store", icon: "database", label: _t("Data store"), noun: () => _t("stored records") },
    { id: "rule", icon: "sigma", label: _t("Transformation rules"), noun: () => _t("rules") },
];
const PAGE = 60;

export class PbIntegrations extends Component {
    static template = "pb_integrations.PbIntegrations";
    static components = { HubBackChip, WfDrawer, RuleComposer, PbFilterLayout };
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
            loaded: false, kpis: {}, connectors: [], types: [], total: 0, timeClocks: null,
            // the connector cards: one page at a time for the panel's state
            crows: [], ctotal: 0, clistLoaded: false, cloadingMore: false,

            // ---- the Data view ----
            view: askedKind ? "data" : "connectors",
            kind: askedKind || "mapping",
            ledger: null, ledgerLoading: false,
            lrows: [], ltotal: 0, llistLoaded: false, lloadingMore: false,
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

        // FILTER W6 — two shared filter panels, one per view: the connector
        // cards (screen `connectors`) and the Data tables (one record type at
        // a time, screens `integrations:<kind>`; a tab switch points the
        // panel at the next table). Both load the first time their view
        // opens.
        //
        // A deep link (a connector, a feed, a data type) arrives as FILTERS on
        // the Data panel — chips the reader can see and drop — never a hidden
        // scope; the server keeps them inside the connectors this reader may
        // read, so a link can never widen what is shown (W26).
        this._arrival = {
            connector: ctx.pb_connector ? Number(ctx.pb_connector) : 0,
            endpoint: ctx.pb_endpoint ? Number(ctx.pb_endpoint) : 0,
            dataType: ctx.pb_data_type || "",
        };
        this._dataStarted = false;
        this.ckit = useFilterKit({
            model: "pb.integrations",
            noun: _t("connectors"),
            ctx: { kind: "connectors" },
            defer: true,
            onChange: () => this.loadConnectors(),
        });
        this.dkit = useFilterKit({
            model: "pb.integrations",
            noun: this.kindNoun(this.state.kind),
            ctx: { kind: this.state.kind },
            defer: true,
            onChange: () => this.loadLedgerPage(),
        });

        onWillStart(async () => {
            await this.load();
            // Asked ONCE, and only about a group — the write itself is gated
            // server-side by `rule_save`, which fails CLOSED. This flag decides
            // whether a button is drawn, and a hidden control is never a gate.
            this.state.canEditRules = await this._readRuleRights();
            if (this.state.view === "data") { await this.loadLedger(); } else { await this.ckit.load(); }
        });
    }

    kindNoun(kind) {
        const t = LEDGER_TABS.find((x) => x.id === kind);
        return t ? t.noun() : _t("rows");
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
            // CLOCK-3: the attendance machines' row (absent without pb_clock
            // or for a reader who is not an attendance officer)
            timeClocks: d.time_clocks || null,
        });
    }

    /** "2 machines · last punch 3 min ago" — the Time clocks row's line. */
    get timeClocksLine() {
        const t = this.state.timeClocks;
        if (!t) { return ""; }
        if (!t.machines) {
            return t.pending
                ? (t.pending === 1 ? _t("1 machine is asking to connect") : _t("%s machines are asking to connect", t.pending))
                : _t("No machine connected yet");
        }
        const machines = t.machines === 1 ? _t("1 machine") : _t("%s machines", t.machines);
        const ago = this._ago(t.last_punch_at);
        return ago ? _t("%(machines)s · last punch %(ago)s", { machines, ago }) : machines;
    }

    _ago(utc) {
        if (!utc) { return ""; }
        const d = new Date(utc.replace(" ", "T") + "Z");
        if (isNaN(d.getTime())) { return ""; }
        const mins = Math.round((Date.now() - d.getTime()) / 60000);
        if (mins < 1) { return _t("just now"); }
        if (mins < 60) { return _t("%s min ago", mins); }
        if (mins < 24 * 60) { return _t("%s h ago", Math.round(mins / 60)); }
        return d.toLocaleDateString([], { day: "2-digit", month: "short" });
    }

    onTimeClocksKey(ev) {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); this.openTimeClocks(); }
    }

    /** The one door to Workforce › Time › Time clocks (pb_clock). */
    openTimeClocks() {
        Promise.resolve(this.action.doAction("pb_clock.action_pb_clock_lens")).catch(() => {
            this.notif.add(_t("That screen is not installed on this database."), { type: "warning" });
        });
    }

    /** One page of connector cards for the panel's current filters. */
    async loadConnectors({ more = false } = {}) {
        const q = this.ckit.query;
        const offset = more ? this.state.crows.length : 0;
        if (more) { this.state.cloadingMore = true; }
        try {
            const d = await this.orm.call("pb.integrations", "get_connector_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
            });
            if (!this.ckit.isCurrent(q.seq)) { return; }
            this.state.crows = more ? [...this.state.crows, ...d.rows] : d.rows;
            this.state.ctotal = d.total;
            this.state.clistLoaded = true;
        } catch (e) {
            console.warn("pb_integrations: could not load the connectors", e);
            if (this.ckit.isCurrent(q.seq)) {
                this.notif.add(_t("The connectors could not be loaded. Try again in a moment."), { type: "warning" });
                this.state.clistLoaded = true;
            }
        } finally {
            this.state.cloadingMore = false;
        }
    }
    loadMoreConnectors() { if (!this.state.cloadingMore) { this.loadConnectors({ more: true }); } }
    get connectorsHasMore() { return this.state.crows.length < this.state.ctotal; }
    get connectorsNextPage() { return Math.min(PAGE, this.state.ctotal - this.state.crows.length); }
    showAllConnectors() { this.ckit.home(); }

    /** Why the connector list is empty — one sentence each (R34). */
    get connectorsEmptyText() {
        if (!this.ckit.total) {
            return _t("No system is connected yet. Connect one to start pulling people and pay data.");
        }
        if (this.ckit.search && !this.ckit.chips.length) {
            return _t("No connector matches “%s”. Check the spelling, or search by name.", this.ckit.search);
        }
        return _t("No connector fits every filter you have set. Remove a filter above, or show every connector.");
    }

    ic(n, s = 16) { return ic(n, s); }
    get ledgerTabs() { return LEDGER_TABS; }

    _hoursSince(iso) {
        if (!iso) return null;
        const t = new Date(iso.replace(" ", "T") + "Z").getTime();
        if (isNaN(t)) return null;
        return (Date.now() - t) / 3600000;
    }
    syncLabel(c) {
        const h = this._hoursSince(c.last_sync);
        if (h === null) return _t("Never synced");
        if (h < 1) return _t("Synced <1h ago");
        if (h < 24) return _t("Synced %(hours)s hours ago", { hours: Math.round(h) });
        return _t("Synced %(days)s days ago", { days: Math.round(h / 24) });
    }

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

    /**
     * The numbers as one quiet line. Grey at zero; rose for connectors in
     * error, amber when a feed is overdue. Connected / Errors filter the
     * connector list (switching back to it from Data); pressing the lit one
     * again shows every connector.
     */
    get glance() {
        const k = this.state.kpis || {};
        // a figure ticks "Connection" in the connector panel (switching back
        // from Data first); pressing the lit one again shows every connector
        const pick = (id) => async () => {
            if (this.state.view !== "connectors") { await this.setView("connectors"); }
            this.ckit.toggleFilters({ status: [id] });
        };
        const rows = [
            { key: "all", n: k.connectors || 0, label: _t("Connectors"), tone: "", run: null },
            { key: "connected", n: k.connected || 0, label: _t("Connected"), tone: "", run: pick("connected") },
            { key: "error", n: k.errors || 0, label: _t("Errors"), tone: k.errors ? "rose" : "", run: pick("error") },
            { key: "synced", n: k.synced || 0, label: _t("Synced records"), tone: "", run: null },
            { key: "mappings", n: k.mappings || 0, label: _t("Field mappings"), tone: "", run: null },
            { key: "staged", n: k.staged || 0, label: _t("Staged records"), tone: "", run: null },
        ];
        if (this.feedsKnown) {
            rows.push({ key: "feeds", n: k.feeds || 0, label: this.feedsKpiLabel, tone: k.feeds_stale ? "amber" : "", run: null });
        }
        return rows;
    }

    /** The figure that is lit: the one whose filter is exactly what is on. */
    get glanceOn() {
        if (this.state.view !== "connectors" || !this.ckit.loaded) { return ""; }
        for (const id of ["connected", "error"]) {
            if (this.ckit.isExactly({ status: [id] })) { return id; }
        }
        return "";
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
        if (view === "connectors" && !this.ckit.loaded) { await this.ckit.load(); }
    }

    async setKind(kind) {
        if (this.state.kind === kind) { return; }
        this.state.kind = kind;
        this.state.drawer = null;
        await this.loadLedger();
    }

    /**
     * The filters a Data table opens with. The connector a deep link (or the
     * previous tab) narrowed to carries across the three tables — the same
     * section on each — until the reader drops its chip; a feed / data type
     * only means anything on the store, and applies the first time it opens.
     */
    _dataInitial(kind) {
        const f = {};
        const conn = this._dataStarted
            ? this.dkit.values("connector")
            : (this._arrival.connector ? [this._arrival.connector] : []);
        if (conn.length) { f.connector = [...conn]; }
        if (kind === "store") {
            if (this._arrival.endpoint) { f.feed = [this._arrival.endpoint]; }
            else if (this._arrival.dataType) { f.data_type = [this._arrival.dataType]; }
            this._arrival.endpoint = 0;
            this._arrival.dataType = "";
        }
        return Object.keys(f).length ? { filters: f } : null;
    }

    /** The table's words and columns, and the Data panel pointed at it. */
    async loadLedger() {
        const kind = this.state.kind;
        this.state.ledgerLoading = true;
        this.state.llistLoaded = false;
        this.state.lrows = [];
        const initial = this._dataInitial(kind);
        this._dataStarted = true;
        const panel = this.dkit.reconfigure({ ctx: { kind }, noun: this.kindNoun(kind), initial });
        try {
            const d = await this.orm.call("pb.integrations", "get_ledger_head", [kind]);
            if (kind === this.state.kind) { this.state.ledger = d; }
        } catch (e) {
            // Reported, never swallowed into an empty table (W40): an empty
            // grid and a failed read look identical and mean opposite things.
            console.warn("pb_integrations: could not load the ledger", e);
            this.notif.add(_t("Could not load this table."), { type: "danger" });
            this.state.ledger = null;
        } finally {
            this.state.ledgerLoading = false;
        }
        await panel;
    }

    /** One page of the table for the Data panel's current filters. */
    async loadLedgerPage({ more = false } = {}) {
        const q = this.dkit.query;
        const kind = this.state.kind;
        const offset = more ? this.state.lrows.length : 0;
        if (more) { this.state.lloadingMore = true; }
        try {
            const d = await this.orm.call("pb.integrations", "get_ledger_page", [kind], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
            });
            if (!this.dkit.isCurrent(q.seq) || kind !== this.state.kind) { return; }
            this.state.lrows = more ? [...this.state.lrows, ...d.rows] : d.rows;
            this.state.ltotal = d.total;
            this.state.llistLoaded = true;
        } catch (e) {
            console.warn("pb_integrations: could not load the rows", e);
            if (this.dkit.isCurrent(q.seq)) {
                this.notif.add(_t("The rows could not be loaded. Try again in a moment."), { type: "warning" });
                this.state.llistLoaded = true;
            }
        } finally {
            this.state.lloadingMore = false;
        }
    }
    loadMoreLedger() { if (!this.state.lloadingMore) { this.loadLedgerPage({ more: true }); } }
    get ledgerHasMore() { return this.state.lrows.length < this.state.ltotal; }
    get ledgerNextPage() { return Math.min(PAGE, this.state.ltotal - this.state.lrows.length); }
    showAllLedger() { this.dkit.home(); }

    /** The connector the Data panel is narrowed to, when exactly one. */
    get dataConnectorId() {
        const v = this.dkit.values("connector");
        return v.length === 1 ? Number(v[0]) || 0 : 0;
    }

    /** Why the table is empty — one translatable sentence each (R34). */
    get ledgerEmptyText() {
        if (!this.dkit.total) { return (this.state.ledger && this.state.ledger.empty) || _t("Nothing here yet."); }
        if (this.dkit.search && !this.dkit.chips.length) {
            return _t("Nothing matches “%s”. Check the spelling, or search by another word on the row.", this.dkit.search);
        }
        return _t("Nothing in this table fits every filter you have set. Remove a filter above, or show the whole table.");
    }

    /** One sentence, one msgid (W80). */
    get footLabel() {
        return _t("Showing %(shown)s of %(total)s",
                  { shown: this.state.lrows.length.toLocaleString("en-US"),
                    total: (this.state.ltotal || 0).toLocaleString("en-US") });
    }
    get connectorsFootLabel() {
        return _t("Showing %(shown)s of %(total)s",
                  { shown: this.state.crows.length.toLocaleString("en-US"),
                    total: (this.state.ctotal || 0).toLocaleString("en-US") });
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
                connectorId: r.connector_id || this.dataConnectorId || 0,
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
        this.state.composer = { ruleId: 0, connectorId: this.dataConnectorId || 0 };
    }

    closeComposer() { this.state.composer = null; }

    /**
     * A saved rule changes the SENTENCE the ledger prints for it, so the table
     * is re-read rather than patched: the summary is computed and stored on the
     * server, and guessing it here would be a second implementation of it.
     */
    async onRuleSaved() {
        this.state.composer = null;
        // the counts and the page again — the filters and the tab stay
        await this.dkit.refresh();
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
