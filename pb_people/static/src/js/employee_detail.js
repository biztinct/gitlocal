/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.people";
const C_CLS = { open: "ok", close: "warn", draft: "info", cancel: "muted", none: "muted" };

export class PbEmployeeDetail extends Component {
    static template = "pb_people.PbEmployeeDetail";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        const p = (this.props.action && (this.props.action.params || this.props.action.context)) || {};
        this.empId = p.emp_id || p.active_id;
        this.state = useState({ loaded: false, d: null });
        onWillStart(async () => { await this.refresh(); });
    }

    ic(n, s = 16) { return ic(n, s); }
    get d() { return this.state.d || {}; }
    cCls(s) { return C_CLS[s] || "muted"; }
    money(n) {
        if (!n) return (this.d.currency || "₫") + "0";
        return (this.d.currency || "₫") + Math.round(n).toLocaleString("en-US");
    }

    async refresh() {
        try { this.state.d = await this.orm.call(MODEL, "get_employee_detail", [this.empId]); }
        catch (e) { this.state.d = { error: "Could not load this employee." }; }
        finally { this.state.loaded = true; }
    }

    // ---- navigation / smart links ----
    openList(model, domain, name) {
        this.action.doAction({
            type: "ir.actions.act_window", name, res_model: model,
            domain: domain || [], views: [[false, "list"], [false, "form"]], target: "current",
        });
    }
    openPayslips() { this.openList("hr.payslip", [["employee_id", "=", this.empId]], "Payslips"); }
    openContracts() { this.openList("hr.contract", [["employee_id", "=", this.empId]], "Contracts"); }
    newContract() {
        this.action.doAction({ type: "ir.actions.client", tag: "pb_contract_wizard", name: "New contract", params: { employee_id: this.empId } });
    }
    openAdvancedForm() {
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "hr.employee",
            res_id: this.empId, views: [[false, "form"]], target: "current",
        });
    }
    back() { this.action.doAction("pb_people.action_pb_people", { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_employee_detail", PbEmployeeDetail);
