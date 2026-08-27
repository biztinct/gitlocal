/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";
import { _t } from "@web/core/l10n/translation";

const STATE_CLS = { active: "ok", draft: "info", deprecated: "warn", archived: "muted" };
const STATUS_CHIPS = [
    { id: "all", label: _t("All") }, { id: "active", label: _t("Active") },
    { id: "draft", label: _t("Draft") }, { id: "deprecated", label: _t("Deprecated") },
];
const DATE_CHIPS = [
    { id: "all", label: _t("All time") }, { id: "month", label: _t("Updated this month") },
    { id: "year", label: _t("Updated this year") }, { id: "custom", label: _t("Custom") },
];

export class PbStructures extends Component {
    static template = "pb_structures.PbStructures";
    static components = { HubBackChip };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        // The return door a caller passed (Settings, a hub, another cockpit).
        // Read ONCE, from props, never written back — the arrival protocol's
        // rule since Cycle 1. Null when nobody sent us, and the chip is then
        // ABSENT rather than inert (W5/W29).
        this.back = hubBack(this.props);
        this.state = useState({
            loaded: false, kpis: {}, countries: [], structures: [], total: 0,
            search: "", status: "all", country: "", schedule: "", dateFilter: "all", from: "", to: "",
        });
        onWillStart(async () => { await this.load(); });
    }

    async load() {
        const d = await this.orm.call("pb.structures", "get_board", []);
        Object.assign(this.state, { kpis: d.kpis, countries: d.countries, structures: d.structures, total: d.total, loaded: true });
    }

    ic(n, s = 16) { return ic(n, s); }
    get statusChips() { return STATUS_CHIPS; }
    get dateChips() { return DATE_CHIPS; }
    get schedules() {
        const set = new Set(this.state.structures.map(s => s.schedule).filter(x => x && x !== "—"));
        return [...set];
    }
    stateCls(s) { return STATE_CLS[s] || "muted"; }

    setStatus(s) { this.state.status = s; }
    setCountry(c) { this.state.country = this.state.country === c ? "" : c; }
    setSchedule(s) { this.state.schedule = this.state.schedule === s ? "" : s; }
    setDate(d) { this.state.dateFilter = d; }
    onSearch(ev) { this.state.search = (ev.target.value || "").toLowerCase(); }
    onFrom(ev) { this.state.from = ev.target.value; }
    onTo(ev) { this.state.to = ev.target.value; }

    _monthStart() { const t = new Date(); return new Date(t.getFullYear(), t.getMonth(), 1).toISOString().slice(0, 10); }
    _yearStart() { return new Date(new Date().getFullYear(), 0, 1).toISOString().slice(0, 10); }
    _matchStatus(s, st) { return st === "all" ? true : s.state === st; }
    _inDate(s) {
        const f = this.state.dateFilter;
        if (f === "all") return true;
        if (!s.updated) return false;
        if (f === "month") return s.updated >= this._monthStart();
        if (f === "year") return s.updated >= this._yearStart();
        if (f === "custom") { if (this.state.from && s.updated < this.state.from) return false; if (this.state.to && s.updated > this.state.to) return false; return true; }
        return true;
    }
    get filtered() {
        const q = this.state.search, c = this.state.country, sc = this.state.schedule;
        return this.state.structures.filter(s => {
            if (c && s.country !== c) return false;
            if (sc && s.schedule !== sc) return false;
            if (!this._matchStatus(s, this.state.status)) return false;
            if (!this._inDate(s)) return false;
            if (q && !((s.name || "").toLowerCase().includes(q) || (s.code || "").toLowerCase().includes(q))) return false;
            return true;
        });
    }
    countStatus(id) { return this.state.structures.filter(s => this._matchStatus(s, id)).length; }

    openStructure(id) {
        if (!id) return;
        this.action.doAction({ type: "ir.actions.client", tag: "pb_structure_detail", name: "Structure", params: { structure_id: id } });
    }
    newStructure() { this.action.doAction({ type: "ir.actions.client", tag: "pb_structure_wizard", name: "New structure" }); }
    openAll() { this.action.doAction("pb_hr_payroll_base.action_hr_payroll_structure_base", { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_structures", PbStructures);
