/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.people.contract.wizard";

export class ContractWizard extends Component {
    static template = "pb_people_advanced.ContractWizard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        const p = (this.props.action && (this.props.action.params || this.props.action.context)) || {};
        this.empId = p.employee_id || p.emp_id;
        this.renewFrom = p.renew_from || false;
        this.state = useState({
            loading: false, busyMsg: "", defaults: null, result: null,
            form: { struct_id: "", structure_type_id: "", wage: "", date_start: "",
                    date_end: "", resource_calendar_id: "", activate: true },
        });
        onWillStart(async () => {
            const d = await this.orm.call(MODEL, "get_defaults", [this.empId, this.renewFrom]);
            this.state.defaults = d;
            const f = this.state.form;
            f.date_start = d.today;
            f.struct_id = d.default_struct ? String(d.default_struct) : "";
            f.resource_calendar_id = d.default_calendar ? String(d.default_calendar) : "";
            if (d.prefill) {
                if (d.prefill.wage) f.wage = d.prefill.wage;
                if (d.prefill.struct_id) f.struct_id = String(d.prefill.struct_id);
                if (d.prefill.structure_type_id) f.structure_type_id = String(d.prefill.structure_type_id);
                if (d.prefill.resource_calendar_id) f.resource_calendar_id = String(d.prefill.resource_calendar_id);
            }
        });
    }

    ic(n, s = 16) { return ic(n, s); }
    onField(f, ev) { this.state.form[f] = ev.target.value; }
    toggle(f) { this.state.form[f] = !this.state.form[f]; }
    get cur() { return (this.state.defaults && this.state.defaults.currency) || "₫"; }
    get canCreate() { return !!(this.empId && this.state.form.struct_id && this.state.form.date_start); }

    async create() {
        this.state.loading = true; this.state.busyMsg = "Creating contract…";
        try {
            const res = await this.orm.call(MODEL, "create_contract", [{ ...this.state.form, employee_id: this.empId }]);
            if (res.error) { this.notif.add(res.error, { type: "danger" }); return; }
            this.state.result = res;
        } catch (e) {
            this.notif.add((e && e.message && e.message.toString()) || "Failed.", { type: "danger" });
        } finally { this.state.loading = false; }
    }
    openContract() {
        const id = this.state.result && this.state.result.contract_id;
        if (id) this.action.doAction({ type: "ir.actions.client", tag: "pb_contract_detail", name: "Contract", params: { contract_id: id } });
    }
    close() {
        if (this.empId) this.action.doAction({ type: "ir.actions.client", tag: "pb_employee_detail", name: "Employee", params: { emp_id: this.empId } });
        else this.action.doAction("pb_contracts.action_pb_contracts", { clearBreadcrumbs: true });
    }
}

registry.category("actions").add("pb_contract_wizard", ContractWizard);
