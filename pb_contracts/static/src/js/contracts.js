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
            drawerContractId: null,
        });
        onWillStart(async () => { await this.load(); });
        // deep link: ?contract=<id>, or an action param, opens the drawer when
        // it is registered — otherwise it is simply ignored and the roster
        // renders as it always did.
        const p = (this.props.action && (this.props.action.params || this.props.action.context)) || {};
        let cid = p.contract || p.contract_id || p.active_id;
        if (!cid) {
            try { cid = new URLSearchParams(window.location.search).get("contract"); } catch (e) { cid = null; }
        }
        if (cid && this.drawerCmp) { this.state.drawerContractId = Number(cid); }
    }

    // Soft component registry (the People precedent): the drawer registers
    // itself here, so this file carries no hard import of it and the cockpit
    // still works with the full-page contract screen if it is ever absent.
    get drawerCmp() {
        const r = registry.category("pb_contracts_drawer");
        return r.contains("contract_360") ? r.get("contract_360") : null;
    }
    // Props come off stable state and a bound closure, exactly as
    // `people.js:57` builds them; the mount point's `t-key` is the contract id,
    // so switching records remounts and the panel slides in again.
    get drawerProps() {
        return { contractId: this.state.drawerContractId, onClose: () => this.closeDrawer() };
    }
    closeDrawer() { this.state.drawerContractId = null; }

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
        if (this.drawerCmp) { this.state.drawerContractId = Number(id); return; }
        this.action.doAction({ type: "ir.actions.client", tag: "pb_contract_detail", name: "Contract", params: { contract_id: id } });
    }
    newContract() {
        this.action.doAction({ type: "ir.actions.client", tag: "pb_contract_wizard", name: "New contract" });
    }
    openAll() { this.action.doAction("pb_hr_payroll_base.action_hr_contract_payroll", { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_contracts", PbContracts);
