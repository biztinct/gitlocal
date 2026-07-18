/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";

const DATE_CHIPS = [
    { id: "all", label: "All time" },
    { id: "month", label: "This month" },
    { id: "year", label: "This year" },
    { id: "custom", label: "Custom" },
];

// One generic ledger cockpit rendered from a backend descriptor. Each screen is
// a thin subclass that only sets the RPC model; the descriptor supplies KPIs,
// facets and rows. Filtering/search/date are all client-side (à la pb.people).
class LedgerCockpit extends Component {
    static template = "pb_payrun_ledgers.Ledger";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false, data: {}, search: "", f: {},
            dateFilter: "all", from: "", to: "",
        });
        onWillStart(async () => { await this.load(); });
    }

    get MODEL() { return this.constructor.MODEL; }

    async load() {
        let d = {};
        try {
            d = await this.orm.call(this.MODEL, "get_data", []);
        } catch (e) {
            this.notif.add("Could not load data", { type: "danger" });
        }
        this.state.data = d || {};
        const f = {};
        for (const fac of (d.facets || [])) f[fac.key] = "";
        this.state.f = f;
        this.state.loaded = true;
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
    openRow(r) {
        if (!r.res_model || !r.id) return;
        this.action.doAction({
            type: "ir.actions.act_window", res_model: r.res_model, res_id: r.id,
            views: [[false, "form"]], target: "current",
        });
    }
    async rowAction(r, ev) {
        ev.stopPropagation();
        if (!r.action) return;
        try {
            const act = await this.orm.call(r.res_model, r.action.method, [[r.id]]);
            if (act) this.action.doAction(act);
        } catch (e) {
            this.notif.add("Action failed", { type: "danger" });
        }
    }
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
