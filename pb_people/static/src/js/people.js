/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const STATE_CLS = { open: "ok", close: "warn", draft: "info", cancel: "muted", none: "muted" };
const STATUS_CHIPS = [
    { id: "all", label: _t("All") },
    { id: "running", label: _t("Running") },
    { id: "expiring", label: _t("Expiring soon") },
    { id: "new", label: _t("New this month") },
    { id: "none", label: _t("No contract") },
];
const DATE_CHIPS = [
    { id: "all", label: _t("All time") },
    { id: "month", label: _t("Joined this month") },
    { id: "year", label: _t("Joined this year") },
    { id: "custom", label: _t("Custom") },
];

export class PbPeople extends Component {
    static template = "pb_people.PbPeople";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false, currency: "", kpis: {}, departments: [],
            people: [], peopleTotal: 0, shown: 0,
            search: "", dept: "", status: "all",
            dateFilter: "all", from: "", to: "",
            selectMode: false, selected: [], bulkDept: "",
            drawerEmpId: null,
        });
        onWillStart(async () => { await this.load(); });
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

    async load() {
        const d = await this.orm.call("pb.people", "get_roster_data", []);
        Object.assign(this.state, {
            currency: d.currency, kpis: d.kpis, departments: d.departments,
            people: d.people, peopleTotal: d.people_total, shown: d.shown, loaded: true,
        });
    }

    ic(n, s = 16) { return ic(n, s); }
    get statusChips() { return STATUS_CHIPS; }
    get dateChips() { return DATE_CHIPS; }

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

    // ---- filtering ----
    setStatus(s) { this.state.status = s; }
    setDept(d) { this.state.dept = this.state.dept === d ? "" : d; }
    setDate(d) { this.state.dateFilter = d; }
    onSearch(ev) { this.state.search = (ev.target.value || "").toLowerCase(); }
    onFrom(ev) { this.state.from = ev.target.value; }
    onTo(ev) { this.state.to = ev.target.value; }

    _monthStart() { const t = new Date(); return new Date(t.getFullYear(), t.getMonth(), 1).toISOString().slice(0, 10); }
    _yearStart() { return new Date(new Date().getFullYear(), 0, 1).toISOString().slice(0, 10); }

    _matchStatus(p, st) {
        if (st === "all") return true;
        if (st === "running") return p.state === "open";
        if (st === "expiring") return p.days_to_expiry !== null && p.days_to_expiry >= 0 && p.days_to_expiry <= 30;
        if (st === "new") return p.join_date && p.join_date >= this._monthStart();
        if (st === "none") return p.state === "none";
        return true;
    }
    _inStatus(p) { return this._matchStatus(p, this.state.status); }
    _inDate(p) {
        const f = this.state.dateFilter;
        if (f === "all") return true;
        if (!p.join_date) return false;
        if (f === "month") return p.join_date >= this._monthStart();
        if (f === "year") return p.join_date >= this._yearStart();
        if (f === "custom") {
            if (this.state.from && p.join_date < this.state.from) return false;
            if (this.state.to && p.join_date > this.state.to) return false;
            return true;
        }
        return true;
    }
    get filteredPeople() {
        const q = this.state.search, dept = this.state.dept;
        return this.state.people.filter(p => {
            if (dept && p.dept !== dept) return false;
            if (!this._inStatus(p)) return false;
            if (!this._inDate(p)) return false;
            if (q && !(p.name.toLowerCase().includes(q) || (p.job || "").toLowerCase().includes(q) || (p.dept || "").toLowerCase().includes(q))) return false;
            return true;
        });
    }
    countStatus(id) { return this.state.people.filter(p => this._matchStatus(p, id)).length; }

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
        this.state.selected = []; this.state.bulkDept = ""; await this.load();
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
        if (this.drawerCmp) { this.state.drawerEmpId = Number(id); return; }
        this.action.doAction({ type: "ir.actions.client", tag: "pb_employee_detail", name: "Employee", params: { emp_id: id } });
    }
    addEmployee() {
        this.action.doAction({ type: "ir.actions.client", tag: "pb_onboard_wizard", name: "Add employee" });
    }
    openAllEmployees() { this.action.doAction("pb_hr_payroll_base.action_hr_employee_payroll", { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_people", PbPeople);
