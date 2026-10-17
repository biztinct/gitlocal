/** @odoo-module **/
import { Component, useState, useRef, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";

const STATE_CLS = { open: "ok", close: "warn", draft: "info", cancel: "muted" };
// The contract's journey. A contract sits at exactly one step (stepOf);
// cancelled contracts are at no step and "Show all" still lists them.
const STEPS = [
    { key: "draft", title: _t("Draft"), sub: _t("Being prepared") },
    { key: "running", title: _t("Running"), sub: _t("In force") },
    { key: "ending", title: _t("Ending soon"), sub: _t("Ends within 30 days") },
    { key: "ended", title: _t("Ended"), sub: _t("Past its end date") },
];
const DATE_CHIPS = [
    { id: "all", label: _t("All time") }, { id: "month", label: _t("Started this month") },
    { id: "year", label: _t("Started this year") }, { id: "custom", label: _t("Custom") },
];

export class PbContracts extends Component {
    static template = "pb_contracts.PbContracts";
    static components = { HubBackChip };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        // The return door (hub_nav.js). The People hub no longer mounts this
        // board as a lens — the Employees lens opens it as its own page — so
        // the way back is read ONCE, from props, like every plain cockpit.
        this.back = hubBack(this.props);
        this.state = useState({
            loaded: false, currency: "", kpis: {}, structures: [],
            contracts: [], total: 0, stepCounts: {}, listedTotal: 0,
            search: "", step: "", structure: "", dateFilter: "all", from: "", to: "",
            drawerContractId: null,
        });
        this.searchRef = useRef("search");
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
        // A step lists that step's own newest contracts (the roster is
        // capped), so pressing one asks the server again.
        const d = await this.orm.call("pb.contracts", "get_board", [], { step: this.state.step || null });
        Object.assign(this.state, {
            currency: d.currency, kpis: d.kpis, structures: d.structures,
            contracts: d.contracts, total: d.total, loaded: true,
            stepCounts: d.step_counts || {}, listedTotal: d.listed_total || 0,
        });
    }

    ic(n, s = 16) { return ic(n, s); }
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

    setStructure(s) { this.state.structure = this.state.structure === s ? "" : s; }
    setDate(d) { this.state.dateFilter = d; }
    onSearch(ev) { this.state.search = (ev.target.value || "").toLowerCase(); }
    onFrom(ev) { this.state.from = ev.target.value; }
    onTo(ev) { this.state.to = ev.target.value; }

    _monthStart() { const t = new Date(); return new Date(t.getFullYear(), t.getMonth(), 1).toISOString().slice(0, 10); }
    _yearStart() { return new Date(new Date().getFullYear(), 0, 1).toISOString().slice(0, 10); }

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
            const step = this.state.step;
            if (step === "open" ? c.state !== "open" : (step && this.stepOf(c) !== step)) return false;
            if (!this._inDate(c)) return false;
            if (q && !((c.employee || "").toLowerCase().includes(q) || (c.name || "").toLowerCase().includes(q) || (c.structure || "").toLowerCase().includes(q))) return false;
            return true;
        });
    }
    // ---- the numbers (quiet line) ----
    get glance() {
        const k = this.state.kpis || {};
        const tone = (v, t) => (v ? t : "");
        // each figure is a step (Running = steps 02 + 03 together)
        const pick = (step) => () => this.pickStep(step);
        return [
            { key: "open", n: k.running || 0, label: _t("Running"), tone: "", run: pick("open") },
            { key: "expiring", n: k.expiring || 0, label: _t("Expiring within 30 days"), tone: tone(k.expiring, "amber"), run: pick("ending") },
            { key: "draft", n: k.draft || 0, label: _t("Draft"), tone: "", run: pick("draft") },
            { key: "close", n: k.expired || 0, label: _t("Expired"), tone: "", run: pick("ended") },
            { key: "wage", n: this.money(k.total_wage || 0), label: _t("Monthly wage"), tone: "", run: null },
            { key: "avg", n: this.money(k.avg_wage || 0), label: _t("Average wage"), tone: "", run: null },
        ];
    }

    // ---- the steps ----
    stepOf(c) {
        if (c.state === "draft") return "draft";
        if (c.state === "open") {
            return (c.days_to_expiry !== null && c.days_to_expiry !== undefined && c.days_to_expiry >= 0 && c.days_to_expiry <= 30) ? "ending" : "running";
        }
        if (c.state === "close") return "ended";
        return "";
    }
    // which figure in the numbers line is lit
    get glanceOn() {
        return { open: "open", ending: "expiring", draft: "draft", ended: "close" }[this.state.step] || "";
    }
    get steps() {
        // counted over every contract by the server, not the listed ones
        const counts = this.state.stepCounts || {};
        return STEPS.map((st, i) => {
            const count = counts[st.key] || 0;
            return {
                ...st, n: String(i + 1).padStart(2, "0"), count,
                countLabel: count === 1 ? _t("1 contract") : _t("%s contracts", count),
                flag: "", on: this.state.step === st.key,
            };
        });
    }
    async pickStep(key) {
        this.state.step = this.state.step === key ? "" : key;
        await this.load();
    }
    get anyFilter() {
        const s = this.state;
        return s.step || s.structure || s.dateFilter !== "all" || s.search;
    }
    get showingLine() {
        const all = this.state.total || 0;
        const st = STEPS.find((x) => x.key === this.state.step);
        if (!this.anyFilter) {
            return { all: true, text: !all ? _t("no contracts yet") : all === 1 ? _t("all 1 contract") : _t("all %s contracts", all) };
        }
        const s = this.state;
        const onlyStep = s.step && !s.structure && s.dateFilter === "all" && !s.search;
        const shown = onlyStep ? (s.stepCounts[s.step] || 0) : this.filtered.length;
        return { all: false, text: _t("%s of %s contracts", shown, all), where: st ? st.title : "" };
    }
    get listedNote() {
        const shown = this.state.contracts.length, total = this.state.listedTotal || this.state.total || 0;
        return total > shown ? _t("The newest %s of %s contracts are listed here", shown, total) : "";
    }
    showAll() {
        const hadStep = this.state.step;
        Object.assign(this.state, { step: "", structure: "", dateFilter: "all", from: "", to: "", search: "" });
        if (this.searchRef.el) this.searchRef.el.value = "";
        if (hadStep) this.load();
    }


    openContract(id) {
        if (!id) return;
        if (this.drawerCmp) { this.state.drawerContractId = Number(id); return; }
        this.action.doAction({ type: "ir.actions.client", tag: "pb_contract_detail", name: _t("Contract"), params: { contract_id: id } });
    }
    newContract() {
        this.action.doAction({ type: "ir.actions.client", tag: "pb_contract_wizard", name: _t("New contract") });
    }
    openAll() { this.action.doAction("pb_hr_payroll_base.action_hr_contract_payroll", { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_contracts", PbContracts);
