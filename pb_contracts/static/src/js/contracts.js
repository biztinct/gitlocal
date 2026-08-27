/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const STATE_CLS = { open: "ok", close: "warn", draft: "info", cancel: "muted" };
const STATUS_CHIPS = [
    { id: "all", label: _t("All") }, { id: "draft", label: _t("Draft") },
    { id: "open", label: _t("Running") }, { id: "expiring", label: _t("Expiring soon") },
    { id: "close", label: _t("Expired") }, { id: "cancel", label: _t("Cancelled") },
];
const DATE_CHIPS = [
    { id: "all", label: _t("All time") }, { id: "month", label: _t("Started this month") },
    { id: "year", label: _t("Started this year") }, { id: "custom", label: _t("Custom") },
];

export class PbContracts extends Component {
    static template = "pb_contracts.PbContracts";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loaded: false, currency: "", kpis: {}, structures: [],
            contracts: [], total: 0,
            search: "", status: "all", structure: "", dateFilter: "all", from: "", to: "",
        });
        onWillStart(async () => { await this.load(); });
    }

    async load() {
        const d = await this.orm.call("pb.contracts", "get_board", []);
        Object.assign(this.state, {
            currency: d.currency, kpis: d.kpis, structures: d.structures,
            contracts: d.contracts, total: d.total, loaded: true,
        });
    }

    ic(n, s = 16) { return ic(n, s); }
    get statusChips() { return STATUS_CHIPS; }
    get dateChips() { return DATE_CHIPS; }
    stateCls(s) { return STATE_CLS[s] || "muted"; }
    money(n) {
        if (n === null || n === undefined) return "—";
        const cur = this.state.currency || "₫";
        const a = Math.abs(n);
        if (a >= 1e9) return cur + (n / 1e9).toFixed(1) + "B";
        if (a >= 1e6) return cur + (n / 1e6).toFixed(1) + "M";
        if (a >= 1e3) return cur + (n / 1e3).toFixed(0) + "K";
        return cur + Math.round(n);
    }

    setStatus(s) { this.state.status = s; }
    setStructure(s) { this.state.structure = this.state.structure === s ? "" : s; }
    setDate(d) { this.state.dateFilter = d; }
    onSearch(ev) { this.state.search = (ev.target.value || "").toLowerCase(); }
    onFrom(ev) { this.state.from = ev.target.value; }
    onTo(ev) { this.state.to = ev.target.value; }

    _monthStart() { const t = new Date(); return new Date(t.getFullYear(), t.getMonth(), 1).toISOString().slice(0, 10); }
    _yearStart() { return new Date(new Date().getFullYear(), 0, 1).toISOString().slice(0, 10); }

    _matchStatus(c, st) {
        if (st === "all") return true;
        if (st === "expiring") return c.days_to_expiry !== null && c.days_to_expiry >= 0 && c.days_to_expiry <= 30;
        return c.state === st;
    }
    _inDate(c) {
        const f = this.state.dateFilter;
        if (f === "all") return true;
        if (!c.date_start) return false;
        if (f === "month") return c.date_start >= this._monthStart();
        if (f === "year") return c.date_start >= this._yearStart();
        if (f === "custom") {
            if (this.state.from && c.date_start < this.state.from) return false;
            if (this.state.to && c.date_start > this.state.to) return false;
            return true;
        }
        return true;
    }
    get filtered() {
        const q = this.state.search, str = this.state.structure;
        return this.state.contracts.filter(c => {
            if (str && c.structure !== str) return false;
            if (!this._matchStatus(c, this.state.status)) return false;
            if (!this._inDate(c)) return false;
            if (q && !((c.employee || "").toLowerCase().includes(q) || (c.name || "").toLowerCase().includes(q) || (c.structure || "").toLowerCase().includes(q))) return false;
            return true;
        });
    }
    countStatus(id) { return this.state.contracts.filter(c => this._matchStatus(c, id)).length; }

    openContract(id) {
        if (!id) return;
        this.action.doAction({ type: "ir.actions.client", tag: "pb_contract_detail", name: "Contract", params: { contract_id: id } });
    }
    newContract() {
        this.action.doAction({ type: "ir.actions.client", tag: "pb_contract_wizard", name: "New contract" });
    }
    openAll() { this.action.doAction("pb_hr_payroll_base.action_hr_contract_payroll", { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_contracts", PbContracts);
