/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.statutory.wizard";

export class PolicyWizard extends Component {
    static template = "pb_statutory.PolicyWizard";
    static props = ["*"];
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.state = useState({ loading: false, defaults: null, result: null, form: {
            name: "", code: "", effective_date: "",
            si_employer_rate: "", si_employee_rate: "", si_max_salary_ceiling: "",
            hi_employer_rate: "", hi_employee_rate: "", hi_max_salary_ceiling: "",
            ui_employer_rate: "", ui_employee_rate: "", ui_max_salary_ceiling: "",
        } });
        onWillStart(async () => {
            const d = await this.orm.call(MODEL, "get_defaults", []);
            this.state.defaults = d;
            const f = this.state.form, p = d.policy;
            f.effective_date = d.today;
            f.si_employer_rate = p.si_employer; f.si_employee_rate = p.si_employee; f.si_max_salary_ceiling = p.si_ceiling;
            f.hi_employer_rate = p.hi_employer; f.hi_employee_rate = p.hi_employee; f.hi_max_salary_ceiling = p.hi_ceiling;
            f.ui_employer_rate = p.ui_employer; f.ui_employee_rate = p.ui_employee; f.ui_max_salary_ceiling = p.ui_ceiling;
        });
    }
    ic(n, s = 16) { return ic(n, s); }
    onField(f, ev) { this.state.form[f] = ev.target.value; }
    get cur() { return (this.state.defaults && this.state.defaults.currency) || "₫"; }
    get canCreate() { return !!(this.state.form.name.trim() && this.state.form.code.trim()); }
    async create() {
        this.state.loading = true;
        try { const r = await this.orm.call(MODEL, "create_policy", [this.state.form]);
            if (r.error) { this.notif.add(r.error, { type: "danger" }); return; } this.state.result = r;
        } catch (e) { this.notif.add(_t("Failed."), { type: "danger" }); } finally { this.state.loading = false; }
    }
    openPolicy() { const id = this.state.result && this.state.result.policy_id; if (id) this.action.doAction({ type: "ir.actions.client", tag: "pb_policy_detail", name: "Policy", params: { policy_id: id } }); }
    close() { this.action.doAction("pb_statutory.action_pb_statutory", { clearBreadcrumbs: true }); }
}
registry.category("actions").add("pb_policy_wizard", PolicyWizard);


export class TaxWizard extends Component {
    static template = "pb_statutory.TaxWizard";
    static props = ["*"];
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.state = useState({ loading: false, defaults: null, result: null, form: {
            name: "", code: "", tax_year: "", personal_deduction: "", dependent_deduction: "", gen_slabs: true,
        } });
        onWillStart(async () => {
            const d = await this.orm.call(MODEL, "get_defaults", []);
            this.state.defaults = d;
            const f = this.state.form;
            f.tax_year = d.year; f.personal_deduction = d.tax.personal; f.dependent_deduction = d.tax.dependent;
        });
    }
    ic(n, s = 16) { return ic(n, s); }
    onField(f, ev) { this.state.form[f] = ev.target.value; }
    toggle(f) { this.state.form[f] = !this.state.form[f]; }
    get cur() { return (this.state.defaults && this.state.defaults.currency) || "₫"; }
    get canCreate() { return !!(this.state.form.name.trim() && this.state.form.code.trim() && this.state.form.tax_year); }
    async create() {
        this.state.loading = true;
        try { const r = await this.orm.call(MODEL, "create_tax_table", [this.state.form]);
            if (r.error) { this.notif.add(r.error, { type: "danger" }); return; } this.state.result = r;
        } catch (e) { this.notif.add(_t("Failed."), { type: "danger" }); } finally { this.state.loading = false; }
    }
    openTax() { const id = this.state.result && this.state.result.tax_id; if (id) this.action.doAction({ type: "ir.actions.client", tag: "pb_tax_detail", name: "Tax table", params: { tax_id: id } }); }
    close() { this.action.doAction("pb_statutory.action_pb_statutory", { clearBreadcrumbs: true }); }
}
registry.category("actions").add("pb_tax_wizard", TaxWizard);
