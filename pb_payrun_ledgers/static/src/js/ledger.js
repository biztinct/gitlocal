/** @odoo-module **/
/**
 * The generic pay-run ledger cockpit — one component, two mount points (W17).
 *
 * STANDALONE (`pb_fullfinal` / `pb_proration` / `pb_retro` client actions) it is
 * exactly what it has always been: one descriptor, its own title, a row click
 * that opens the native form, and an "Open full list →" escape at the bottom.
 *
 * IN A HUB (`embedded`, with `tabs`) it becomes an IN-LENS ledger:
 *   - the title row is the hub's, so it is suppressed here;
 *   - `tabs` puts two descriptors in one lens (Adjust = Retro | Proration) and
 *     the tab is what chooses the RPC model;
 *   - a row click opens a 320px WfDrawer with the line's whole story instead of
 *     navigating — the point of a hub is that reading a row does not cost you
 *     the surface you were reading it from;
 *   - "Open full list →" is NOT RENDERED. It is the escape the hub exists to
 *     remove, and a link that leaves a hub for a native list is worse than no
 *     link, because it looks like a filter and behaves like an exit.
 *
 * Nothing above changes one pixel of the standalone render: every hub-only
 * branch is guarded on `props.embedded`, which is absent there.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { WfDrawer } from "@pb_wf_kit/js/wf_drawer";

const DATE_CHIPS = [
    { id: "all", label: _t("All time") },
    { id: "month", label: _t("This month") },
    { id: "year", label: _t("This year") },
    { id: "custom", label: _t("Custom") },
];

// One generic ledger cockpit rendered from a backend descriptor. Each screen is
// a thin subclass that only sets the RPC model; the descriptor supplies KPIs,
// facets and rows. Filtering/search/date are all client-side (à la pb.people).
export class LedgerCockpit extends Component {
    static template = "pb_payrun_ledgers.Ledger";
    static components = { WfDrawer };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false, data: {}, search: "", f: {},
            dateFilter: "all", from: "", to: "",
            // hub mode only
            tab: this.tabs.length ? this.tabs[0].key : "",
            drawer: null,          // { title, subtitle, sections, currency }
            drawerLoading: false,
        });
        onWillStart(async () => { await this.load(); });
    }

    // ------------------------------------------------------------- hub shape
    /**
     * `embedded` alone suppresses chrome; `tabs` is what makes this an in-lens
     * ledger. They are separate because a future hub may embed ONE descriptor
     * with no tab strip, and a tab strip of one is a control that does nothing.
     */
    get embedded() { return !!this.props.embedded; }
    get tabs() { return this.props.tabs || []; }
    get tabDef() {
        return this.tabs.find((t) => t.key === this.state.tab) || this.tabs[0] || null;
    }

    /**
     * The model this mount reads from.
     *
     * A subclass's static MODEL is the standalone answer; a tab's is the hub's.
     * The tab wins, so one component serves both without a second class.
     */
    get MODEL() {
        const t = this.tabDef;
        return (t && t.model) || this.constructor.MODEL;
    }

    async load() {
        let d = {};
        try {
            d = await this.orm.call(this.MODEL, "get_data", []);
        } catch (e) {
            this.notif.add(_t("Could not load data"), { type: "danger" });
        }
        this.state.data = d || {};
        const f = {};
        for (const fac of (d.facets || [])) f[fac.key] = "";
        this.state.f = f;
        this.state.loaded = true;
    }

    /** A CLICK handler — the tab switch reloads, and mounts never write (W21). */
    async setTab(key) {
        if (this.state.tab === key) { return; }
        this.state.tab = key;
        this.state.drawer = null;
        this.state.loaded = false;
        this.state.search = "";
        this.state.dateFilter = "all";
        this.state.from = "";
        this.state.to = "";
        await this.load();
    }

    ic(n, s = 16) { return ic(n, s); }
    get dateChips() { return DATE_CHIPS; }

    // ---- formatting ----
    money(n) {
        if (n === null || n === undefined) return "—";
        const cur = this.state.data.currency || "₫";
        const a = Math.abs(n);
        if (a >= 1e9) return cur + (n / 1e9).toFixed(1) + "B";
        if (a >= 1e6) return cur + (n / 1e6).toFixed(1) + "M";
        if (a >= 1e3) return cur + (n / 1e3).toFixed(0) + "K";
        return cur + Math.round(n);
    }
    moneyFull(n) { return (this.state.data.currency || "₫") + Math.round(n || 0).toLocaleString("en-US"); }
    kpiVal(k) {
        if (k.money) return this.money(k.value);
        return (typeof k.value === "number") ? k.value.toLocaleString("en-US") : (k.value ?? "—");
    }
    metricVal(m) {
        if (m.money) return this.moneyFull(m.value);
        return (m.value === 0 || m.value) ? String(m.value) : "—";
    }
    /** Drawer values: money through the full formatter, everything else as-is. */
    detailVal(f) {
        if (f.money) return this.moneyFull(f.value);
        return (f.value === 0 || f.value) ? String(f.value) : "—";
    }

    // ---- filters (client-side) ----
    setFacet(key, val) { this.state.f[key] = this.state.f[key] === val ? "" : val; }
    onFacetSelect(key, ev) { this.state.f[key] = ev.target.value || ""; }
    setDate(d) { this.state.dateFilter = d; }
    onSearch(ev) { this.state.search = (ev.target.value || "").toLowerCase(); }
    onFrom(ev) { this.state.from = ev.target.value; }
    onTo(ev) { this.state.to = ev.target.value; }

    _monthStart() { const t = new Date(); return new Date(t.getFullYear(), t.getMonth(), 1).toISOString().slice(0, 10); }
    _yearStart() { return new Date(new Date().getFullYear(), 0, 1).toISOString().slice(0, 10); }
    _inDate(r) {
        const f = this.state.dateFilter;
        if (f === "all") return true;
        const d = r._d;
        if (!d) return false;
        if (f === "month") return d >= this._monthStart();
        if (f === "year") return d >= this._yearStart();
        if (f === "custom") {
            if (this.state.from && d < this.state.from) return false;
            if (this.state.to && d > this.state.to) return false;
            return true;
        }
        return true;
    }
    _match(r) {
        for (const [k, v] of Object.entries(this.state.f)) {
            if (v && String((r._f || {})[k]) !== String(v)) return false;
        }
        if (!this._inDate(r)) return false;
        const q = this.state.search;
        if (q && !(r._s || "").toLowerCase().includes(q)) return false;
        return true;
    }
    get rows() { return (this.state.data.rows || []).filter(r => this._match(r)); }
    chipCount(key, val) {
        return (this.state.data.rows || []).filter(r => String((r._f || {})[key]) === String(val)).length;
    }
    get dirty() {
        return !!(this.state.search || this.state.dateFilter !== "all"
            || Object.values(this.state.f).some(v => v));
    }
    clearFilters() {
        const f = {};
        for (const k of Object.keys(this.state.f)) f[k] = "";
        this.state.f = f;
        this.state.search = ""; this.state.dateFilter = "all"; this.state.from = ""; this.state.to = "";
    }

    // ---- navigation / actions ----
    /**
     * A row is a door either way — the hub's door just opens inwards.
     * Standalone: the native form (unchanged). Embedded: the drawer.
     */
    openRow(r) {
        if (this.embedded) { return this.openDrawer(r); }
        if (!r.res_model || !r.id) return;
        this.action.doAction({
            type: "ir.actions.act_window", res_model: r.res_model, res_id: r.id,
            views: [[false, "form"]], target: "current",
        });
    }

    async openDrawer(r) {
        if (!r.id) { return; }
        // Shown immediately from what the ROW already knows, then filled in:
        // an empty panel that appears instantly reads as loading, whereas a
        // click with nothing on screen for 200ms reads as a dead row.
        this.state.drawer = { title: r.title || "—", subtitle: r.subtitle || "", sections: [] };
        this.state.drawerLoading = true;
        try {
            const d = await this.orm.call(this.MODEL, "get_detail", [r.id]);
            if (!this.state.drawer) { return; }        // closed while in flight
            this.state.drawer = {
                title: d.title || r.title || "—",
                subtitle: d.subtitle || r.subtitle || "",
                sections: d.sections || [],
            };
        } catch (e) {
            // Reported, never swallowed (W40): the drawer stays open with what
            // the row knew, and the user is told the rest did not arrive.
            console.warn("pb_payrun_ledgers: get_detail failed", e);
            this.notif.add(_t("Could not load this line's detail."), { type: "danger" });
        } finally {
            this.state.drawerLoading = false;
        }
    }

    closeDrawer() { this.state.drawer = null; }

    async rowAction(r, ev) {
        ev.stopPropagation();
        if (!r.action) return;
        try {
            const act = await this.orm.call(r.res_model, r.action.method, [[r.id]]);
            if (act) this.action.doAction(act);
        } catch (e) {
            this.notif.add(_t("Action failed"), { type: "danger" });
        }
    }

    /** Standalone only — the template never renders the link in hub mode. */
    openFullList() {
        if (this.state.data.list_action) this.action.doAction(this.state.data.list_action, { clearBreadcrumbs: true });
    }
}

class PbFullFinal extends LedgerCockpit { static MODEL = "pb.fullfinal"; }
class PbProration extends LedgerCockpit { static MODEL = "pb.proration"; }
class PbRetro extends LedgerCockpit { static MODEL = "pb.retro"; }

registry.category("actions").add("pb_fullfinal", PbFullFinal);
registry.category("actions").add("pb_proration", PbProration);
registry.category("actions").add("pb_retro", PbRetro);
