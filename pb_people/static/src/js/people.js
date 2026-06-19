/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const STATE_CLS = { open: "running", close: "expired", draft: "new", cancel: "cancel", none: "none" };

export class PbPeople extends Component {
    static template = "pb_people.PbPeople";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loaded: false,
            view: "people",          // people | contracts
            currency: "",
            kpis: {},
            departments: [],
            people: [],
            contracts: [],
            peopleTotal: 0,
            contractsTotal: 0,
            shown: 0,
            search: "",
            dept: "",
            status: "",             // "", running, expired, none, ready
        });
        onWillStart(async () => { await this.load(); });
    }

    async load() {
        const d = await this.orm.call("pb.people", "get_roster_data", []);
        Object.assign(this.state, {
            currency: d.currency, kpis: d.kpis, departments: d.departments,
            people: d.people, contracts: d.contracts,
            peopleTotal: d.people_total, contractsTotal: d.contracts_total,
            shown: d.shown, loaded: true,
        });
    }

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
    stateCls(s) { return STATE_CLS[s] || "none"; }

    // ---- filtering ----
    setView(v) { this.state.view = v; }
    setStatus(s) { this.state.status = this.state.status === s ? "" : s; }
    setDept(d) { this.state.dept = this.state.dept === d ? "" : d; }
    onSearch(ev) { this.state.search = (ev.target.value || "").toLowerCase(); }

    get filteredPeople() {
        const q = this.state.search, dept = this.state.dept, st = this.state.status;
        return this.state.people.filter(p => {
            if (dept && p.dept !== dept) return false;
            if (st === "ready" && !p.ready) return false;
            if (st && st !== "ready" && p.state !== st) return false;
            if (q && !(p.name.toLowerCase().includes(q) || (p.job || "").toLowerCase().includes(q) || (p.dept || "").toLowerCase().includes(q))) return false;
            return true;
        });
    }
    get filteredContracts() {
        const q = this.state.search, st = this.state.status;
        return this.state.contracts.filter(c => {
            if (st && st !== "ready" && c.state !== st) return false;
            if (q && !(c.employee.toLowerCase().includes(q) || (c.name || "").toLowerCase().includes(q))) return false;
            return true;
        });
    }

    // ---- navigation ----
    openEmployee(id) {
        if (!id) return;
        this.action.doAction({ type: "ir.actions.act_window", res_model: "hr.employee", res_id: id, views: [[false, "form"]], target: "current" });
    }
    openContract(id) {
        if (!id) return;
        this.action.doAction({ type: "ir.actions.act_window", res_model: "hr.contract", res_id: id, views: [[false, "form"]], target: "current" });
    }
    openAllEmployees() { this.action.doAction("pb_hr_payroll_base.action_hr_employee_payroll", { clearBreadcrumbs: true }); }
    openAllContracts() { this.action.doAction("pb_hr_payroll_base.action_hr_contract_payroll", { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_people", PbPeople);
