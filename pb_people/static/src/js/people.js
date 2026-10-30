/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { useFilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

const STATE_CLS = { open: "ok", close: "warn", draft: "info", cancel: "muted", none: "muted" };
const PAGE = 60;
// What each figure on the numbers line means as a filter. The same filters
// as the built-in views, so pressing a figure lights the matching tab.
const GLANCE_FILTERS = {
    running: { status: ["open"] },
    expiring: { status: ["open"], ends: { preset: "next_30" } },
    new: { joined: { preset: "this_month" } },
    notready: { ready: ["no"] },
};

export class PbPeople extends Component {
    static template = "pb_people.PbPeople";
    static components = { PbFilterLayout };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false, currency: "", kpis: {}, departments: [],
            people: [], peopleTotal: 0, listLoaded: false, loadingMore: false,
            selectMode: false, selected: [], bulkDept: "",
            drawerEmpId: null,
            // The Contracts door (see `contractsDoor` below) and the contract
            // drawer it opens in place, one person at a time.
            canContracts: false, drawerContractId: null,
        });
        // The shared filter panel (pb_filter_kit): it owns the filters, the
        // counts and the views; this screen only loads a page for kit.query.
        this.kit = useFilterKit({
            model: "pb.people",
            noun: _t("employees"),
            onChange: () => this.loadPage(),
        });
        onWillStart(async () => {
            await Promise.all([this.load(), this._resolveContractsDoor()]);
        });
        // deep-link: ?emp=<id> (or an action param) opens the 360 drawer if the
        // Employee Vault is installed — otherwise it is simply ignored.
        const p = (this.props.action && (this.props.action.params || this.props.action.context)) || {};
        let emp = p.emp || p.emp_id;
        if (!emp) {
            try { emp = new URLSearchParams(window.location.search).get("emp"); } catch (e) { emp = null; }
        }
        if (emp && this.drawerCmp) { this.state.drawerEmpId = Number(emp); }
    }

    // Soft component registry (C18 overlay pattern): the vault registers its
    // drawer here. Absent (vault not installed) → null → we fall back to the
    // legacy full-page detail action. People stays installable standalone.
    get drawerCmp() {
        const r = registry.category("pb_people_drawer");
        return r.contains("employee_360") ? r.get("employee_360") : null;
    }
    get drawerProps() {
        return { empId: this.state.drawerEmpId, onClose: () => this.closeDrawer() };
    }
    closeDrawer() { this.state.drawerEmpId = null; }

    // ---- the Contracts door ----
    //
    // A contract belongs to a person, so Contracts is a door INSIDE Employees
    // rather than a tab beside it (owner, 2026-09-24). The host hands the door
    // in as a prop — `{ groups, open }` — because this cockpit cannot import
    // the People hub back (the hub depends on it). No door (the standalone
    // action), no button: the host is what knows where the board lives.
    get contractsDoor() {
        const d = this.props.contractsDoor;
        return d && typeof d.open === "function" ? d : null;
    }
    /**
     * Offered only to people the board would let in. Fails OPEN per group, the
     * shell's rule: an xmlid that does not resolve means a module is absent,
     * not a refusal, and the facade keeps its own boundary either way.
     */
    async _resolveContractsDoor() {
        const door = this.contractsDoor;
        if (!door) { return; }
        const groups = door.groups || [];
        if (!groups.length) { this.state.canContracts = true; return; }
        const flags = await Promise.all(groups.map(async (g) => {
            try { return await user.hasGroup(g); }
            catch (e) {
                console.warn("pb_people: could not resolve group", g, e);
                return true;
            }
        }));
        this.state.canContracts = flags.some(Boolean);
    }
    openContracts() {
        if (this.contractsDoor) { this.contractsDoor.open(); }
    }
    // The contract drawer, from the SAME soft registry the Contracts board
    // probes (`contracts.js` drawerCmp), so one person's contract opens exactly
    // as it does there. No hard import: pb_contracts depends on this module.
    get contractDrawerCmp() {
        const r = registry.category("pb_contracts_drawer");
        return r.contains("contract_360") ? r.get("contract_360") : null;
    }
    get contractDrawerProps() {
        return { contractId: this.state.drawerContractId,
                 onClose: () => this.closeContract() };
    }
    closeContract() { this.state.drawerContractId = null; }
    openContract(p) {
        if (!p || !p.contract_id) { return; }
        // One panel at a time: the two drawers share the right edge.
        this.state.drawerEmpId = null;
        if (this.contractDrawerCmp) { this.state.drawerContractId = Number(p.contract_id); return; }
        this.action.doAction({ type: "ir.actions.client", tag: "pb_contract_detail",
                               name: _t("Contract"), params: { contract_id: p.contract_id } });
    }

    /** The numbers line (counted over everyone, whatever is filtered). */
    async load() {
        const d = await this.orm.call("pb.people", "get_roster_head", []);
        Object.assign(this.state, {
            currency: d.currency, kpis: d.kpis, departments: d.departments, loaded: true,
        });
    }

    /** One page of the roster for the panel's current filters. */
    async loadPage({ more = false } = {}) {
        const q = this.kit.query;
        const offset = more ? this.state.people.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call("pb.people", "get_roster_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.people = more ? [...this.state.people, ...d.rows] : d.rows;
            this.state.peopleTotal = d.total;
            this.state.listLoaded = true;
            if (!more) {
                // somebody the new filters no longer list is unticked, so a
                // bulk action never reaches a person nobody can see
                const ids = new Set(d.rows.map((p) => p.id));
                this.state.selected = this.state.selected.filter((id) => ids.has(id));
            }
        } finally {
            this.state.loadingMore = false;
        }
    }
    loadMore() {
        if (!this.state.loadingMore) { this.loadPage({ more: true }); }
    }
    get hasMore() {
        return this.state.people.length < this.state.peopleTotal;
    }
    get nextPage() {
        return Math.min(PAGE, this.state.peopleTotal - this.state.people.length);
    }
    fmtInt(n) { return Number(n || 0).toLocaleString("en-US"); }

    ic(n, s = 16) { return ic(n, s); }

    // ---- formatting ----
    money(n) {
        if (n === null || n === undefined) return "—";
        const cur = this.state.currency || "₫";
        const a = Math.abs(n);
        if (a >= 1e9) return cur + (n / 1e9).toFixed(1) + "B";
        if (a >= 1e6) return cur + (n / 1e6).toFixed(1) + "M";
        if (a >= 1e3) return cur + (n / 1e3).toFixed(0) + "K";
        return cur + Math.round(n);
    }
    moneyFull(n) {
        if (!n) return (this.state.currency || "₫") + "0";
        return (this.state.currency || "₫") + Math.round(n).toLocaleString("en-US");
    }
    stateCls(s) { return STATE_CLS[s] || "muted"; }

    // ---- the numbers (quiet line) ----
    // One slim line instead of six tiles. The figures that filter now set
    // the filter panel: pressing one ticks exactly its filters (and lights
    // the matching view tab); pressing it again shows everyone.
    get glance() {
        const k = this.state.kpis || {};
        const tone = (v, t) => (v ? t : "");
        const pick = (id) => () => this.kit.toggleFilters(GLANCE_FILTERS[id]);
        return [
            { key: "all", n: k.headcount || 0, label: _t("Headcount"), tone: "", run: () => this.kit.toggleFilters({}) },
            { key: "running", n: k.running || 0, label: _t("Running contracts"), tone: "", run: pick("running") },
            { key: "expiring", n: k.expiring_soon || 0, label: _t("Expiring within 30 days"), tone: tone(k.expiring_soon, "amber"), run: pick("expiring") },
            { key: "new", n: k.new_hires || 0, label: _t("New this month"), tone: tone(k.new_hires, "green"), run: pick("new") },
            { key: "notready", n: k.not_ready || 0, label: _t("Not payroll-ready"), tone: tone(k.not_ready, "amber"), run: pick("notready") },
            { key: "wage", n: this.money(k.total_wage || 0), label: _t("Monthly wage"), tone: "", run: null },
            { key: "ready", n: (k.ready_pct || 0) + "%", label: _t("Payroll-ready"), tone: "", run: null },
        ];
    }

    /** Which figure is lit: the one whose filters are exactly what is on. */
    get glanceOn() {
        if (!this.kit.loaded) { return ""; }
        for (const [key, f] of Object.entries(GLANCE_FILTERS)) {
            if (this.kit.isExactly(f)) { return key; }
        }
        return "";
    }

    // ---- the list the filter panel produced ----
    get filteredPeople() { return this.state.people; }

    // ---- bulk selection ----
    toggleSelectMode() { this.state.selectMode = !this.state.selectMode; if (!this.state.selectMode) { this.state.selected = []; } }
    isSelected(id) { return this.state.selected.includes(id); }
    toggleSelect(id) {
        const i = this.state.selected.indexOf(id);
        if (i >= 0) this.state.selected.splice(i, 1); else this.state.selected.push(id);
    }
    selectAllVisible() { this.state.selected = this.filteredPeople.map(p => p.id); }
    clearSelection() { this.state.selected = []; }
    onCard(p) { if (this.state.selectMode) this.toggleSelect(p.id); else this.openEmployee(p.id); }

    async bulkSetDept(ev) {
        const deptId = ev.target.value;
        if (!deptId || !this.state.selected.length) return;
        const res = await this.orm.call("pb.people", "bulk_apply", [this.state.selected, "set_department", deptId]);
        if (res.error) { this.notif.add(res.error, { type: "danger" }); return; }
            this.notif.add(_t("%(count)s employees moved.", { count: res.count }), { type: "success" });
        this.state.selected = []; this.state.bulkDept = "";
        await Promise.all([this.load(), this.kit.refresh()]);
    }
    /**
     * The Records Desk, opened on the people currently ticked.
     *
     * A PROBE, not a dependency (the same soft-registry reasoning as
     * `drawerCmp` above): `pb_records` depends on this module, so importing it
     * back would be a cycle, and a hard import of a module that may not be
     * installed takes the whole bundle down with an unmet dependency (C18.53).
     * The action registry holding the desk's tag is proof its JS shipped.
     */
    get hasRecordsDesk() {
        return registry.category("actions").contains("pb_records_desk");
    }

    async bulkUpdate() {
        if (!this.state.selected.length) { return; }
        try {
            await this.action.doAction("pb_people_hub.action_pb_people_hub", {
                clearBreadcrumbs: true,
                additionalContext: {
                    // `pb_lens` is the hub arrival protocol (hub_nav.js); the
                    // employee ids ride beside it and the hub hands them to the
                    // lens as props.
                    pb_lens: "records",
                    records_employee_ids: [...this.state.selected],
                },
            });
        } catch (e) {
            this.notif.add(_t("The Records Desk is not available on this database."),
                           { type: "warning" });
        }
    }

    bulkExport() {
        const ids = this.state.selected.length ? this.state.selected : this.filteredPeople.map(p => p.id);
        const rows = this.state.people.filter(p => ids.includes(p.id));
        const head = ["Name", "Job", "Department", "Email", "Contract", "Wage", "Joined"];
        const esc = (v) => '"' + String(v == null ? "" : v).replace(/"/g, '""') + '"';
        const lines = [head.map(esc).join(",")];
        for (const p of rows) lines.push([p.name, p.job, p.dept, p.email, p.state_label, p.wage, p.join_date].map(esc).join(","));
        const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url; a.download = "employees.csv"; a.click();
        URL.revokeObjectURL(url);
    }

    // ---- navigation ----
    openEmployee(id) {
        if (!id) return;
        if (this.drawerCmp) { this.state.drawerContractId = null; this.state.drawerEmpId = Number(id); return; }
        this.action.doAction({ type: "ir.actions.client", tag: "pb_employee_detail", name: "Employee", params: { emp_id: id } });
    }
    addEmployee() {
        this.action.doAction({ type: "ir.actions.client", tag: "pb_onboard_wizard", name: "Add employee" });
    }
    openAllEmployees() { this.action.doAction("pb_hr_payroll_base.action_hr_employee_payroll", { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_people", PbPeople);
