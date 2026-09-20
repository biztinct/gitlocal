/** @odoo-module **/
/**
 * The Statutory cockpit — insurance rates, tax brackets, and (IA Cycle 4) the
 * four VN tables that used to be launch tiles.
 *
 * The board is what it always was: KPIs, the active policy's rates, the active
 * tax table's brackets, and the two rosters. What changed is the FIVE TILES
 * that used to sit at the bottom of it, each opening an `act_window` in
 * `pb_hr_payroll_vietnam` — four raw `list,form` views and one modal wizard.
 *
 *   * the four tables are now a **Data view** of this cockpit: a tab strip, a
 *     grid, and the shared 320px drawer on row click. No native list is a
 *     destination any more (flow doctrine 2);
 *   * the fifth, Insurance Analytics, is a `target: "new"` WIZARD and not a
 *     table at all. It stays a modal, launched from a labelled button in the
 *     header rather than from a tile that looks like navigation. Calling it a
 *     ledger would have meant inventing a table it does not have.
 *
 * The legacy actions are untouched and still registered: this cycle replaces
 * the doors, not the models.
 *
 * The drawer is imported from `pb_wf_kit`, never forked (W6). The GRID around
 * it is a deliberate clone of the C3 integrations ledger's shape rather than an
 * import of it — `pb_integrations` is a Setup-area cockpit with connector
 * dependencies this module has no reason to acquire, and two hundred lines that
 * look alike cost less than a dependency that cannot install.
 *
 * READ PATH ONLY this cycle: the grid and the drawer, no edit UI. Records stay
 * editable through their existing native forms.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";
import { WfDrawer } from "@pb_wf_kit/js/wf_drawer";

/**
 * The four ledgers, in the order an operator meets them: what you contribute,
 * what you tax, what you corrected, and who is relieved.
 */
const LEDGER_TABS = [
    { id: "policy", icon: "checkCircle", label: _t("Insurance policies") },
    { id: "tax", icon: "sigma", label: _t("Tax tables") },
    { id: "adjustment", icon: "settings", label: _t("Adjustments") },
    { id: "dependent", icon: "users", label: _t("Dependents") },
];

export class PbStatutory extends Component {
    static template = "pb_statutory.PbStatutory";
    static components = { HubBackChip, WfDrawer };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        // The return door a caller passed (Settings, a hub, another cockpit).
        // Read ONCE, from props, never written back — the arrival protocol's
        // rule since Cycle 1. Null when nobody sent us, and the chip is then
        // ABSENT rather than inert (W5/W29).
        this.back = hubBack(this.props);
        const ctx = (this.props.action && this.props.action.context) || {};
        const askedKind = LEDGER_TABS.some((t) => t.id === ctx.pb_ledger)
            ? ctx.pb_ledger : "";

        this.state = useState({
            loaded: false, currency: "", kpis: {}, policy: null, tax: null, actuals: null,
            policies: [], tax_tables: [], analyticsAction: "", ledgers: [],
            view: askedKind ? "data" : "policies", year: "", showActive: false,

            // ---- the Data view ----
            kind: askedKind || "policy",
            ledger: null, ledgerLoading: false,
            lsearch: "", f: {},
            drawer: null, drawerLoading: false,
        });
        this._opening = false;
        onWillStart(async () => {
            await this.load();
            if (this.state.view === "data") { await this.loadLedger(); }
        });
    }

    async load() {
        const d = await this.orm.call("pb.statutory", "get_statutory_data", []);
        Object.assign(this.state, {
            currency: d.currency, kpis: d.kpis, policy: d.policy, tax: d.tax,
            actuals: d.actuals, policies: d.policies, tax_tables: d.tax_tables,
            analyticsAction: d.analytics_action || "",
            ledgers: d.ledgers || [], loaded: true,
        });
    }

    ic(n, s = 16) { return ic(n, s); }
    money(n) {
        if (!n) return (this.state.currency || "₫") + "0";
        const a = Math.abs(n);
        const cur = this.state.currency || "₫";
        if (a >= 1e9) return cur + (n / 1e9).toFixed(1) + "B";
        if (a >= 1e6) return cur + (n / 1e6).toFixed(1) + "M";
        if (a >= 1e3) return cur + (n / 1e3).toFixed(0) + "K";
        return cur + Math.round(n);
    }
    moneyFull(n) { return (this.state.currency || "₫") + Math.round(n || 0).toLocaleString("en-US"); }

    // ================================================================ the views
    get ledgerTabs() {
        return LEDGER_TABS.filter((t) => this.state.ledgers.includes(t.id));
    }
    get hasLedgers() { return this.ledgerTabs.length > 0; }

    /** A CLICK handler. Switching to Data loads it the first time only. */
    async setView(v) {
        if (this.state.view === v) { return; }
        this.state.view = v;
        this.state.year = "";
        this.state.drawer = null;
        if (v === "data" && !this.state.ledger) { await this.loadLedger(); }
    }

    async setKind(kind) {
        if (this.state.kind === kind) { return; }
        this.state.kind = kind;
        this.state.drawer = null;
        this.state.lsearch = "";
        this.state.f = {};
        await this.loadLedger();
    }

    async loadLedger() {
        this.state.ledgerLoading = true;
        try {
            const d = await this.orm.call("pb.statutory", "get_ledger",
                                          [this.state.kind]);
            this.state.ledger = d;
            const f = {};
            for (const fac of (d.facets || [])) { f[fac.key] = ""; }
            this.state.f = f;
        } catch (e) {
            // Reported, never swallowed into an empty table (W40): an empty
            // grid and a failed read look identical and mean opposite things.
            console.warn("pb_statutory: could not load the ledger", e);
            this.notif.add(_t("Could not load this table."), { type: "danger" });
            this.state.ledger = null;
        } finally {
            this.state.ledgerLoading = false;
        }
    }

    // ------------------------------------------------------------ ledger filters
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

    /**
     * ONE getter, ONE sentence, ONE msgid: a translator cannot reorder
     * fragments assembled out of `t` nodes, and word order is exactly what
     * differs between languages (W80). This is also the one string on the Data
     * view that carries numbers.
     */
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

    // ==================================================================== drawer
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
            const d = await this.orm.call("pb.statutory", "get_ledger_detail",
                                          [this.state.kind, r.id]);
            if (!this.state.drawer) { return; }        // closed while in flight
            this.state.drawer = {
                title: d.title || r.cells[0] || "—",
                subtitle: d.subtitle || "",
                sections: d.sections || [],
            };
        } catch (e) {
            console.warn("pb_statutory: get_ledger_detail failed", e);
            this.notif.add(_t("Could not load this row's detail."), { type: "danger" });
        } finally {
            this.state.drawerLoading = false;
        }
    }

    closeDrawer() { this.state.drawer = null; }

    // ================================================================ the board
    setYear(y) { this.state.year = this.state.year === y ? "" : y; }
    toggleActive() { this.state.showActive = !this.state.showActive; }
    get years() { return [...new Set(this.state.tax_tables.map(t => t.year))].sort((a, b) => b - a); }
    get filteredPolicies() { return this.state.policies.filter(p => !this.state.showActive || p.active); }
    get filteredTax() {
        return this.state.tax_tables.filter(t => (!this.state.showActive || t.active) && (!this.state.year || t.year === this.state.year));
    }

    openPolicy(id) { this.action.doAction({ type: "ir.actions.client", tag: "pb_policy_detail", name: "Insurance policy", params: { policy_id: id } }); }
    openTax(id) { this.action.doAction({ type: "ir.actions.client", tag: "pb_tax_detail", name: "Tax table", params: { tax_id: id } }); }
    newPolicy() { this.action.doAction({ type: "ir.actions.client", tag: "pb_policy_wizard", name: "New policy" }); }
    newTax() { this.action.doAction({ type: "ir.actions.client", tag: "pb_tax_wizard", name: "New tax table" }); }

    /**
     * The one legacy launch that survived, and it is a MODAL.
     *
     * `vietnam.insurance.analytics` is a transient with `target: "new"` — a
     * wizard, not a list. It is opened WITHOUT clearing the breadcrumbs, so it
     * lands on top of this cockpit and closing it comes straight back; the old
     * tile used `clearBreadcrumbs: true`, which is how a "launch" became a
     * one-way trip.
     */
    openAnalytics() {
        const xmlid = this.state.analyticsAction;
        if (!xmlid || this._opening) { return; }
        this._opening = true;
        try {
            this.action.doAction(xmlid, { clearBreadcrumbs: false });
            this._opening = false;          // a modal does not replace this page
        } catch (e) {
            this._opening = false;
            console.warn("pb_statutory: could not open the analytics wizard", e);
        }
    }
}

registry.category("actions").add("pb_statutory", PbStatutory);
