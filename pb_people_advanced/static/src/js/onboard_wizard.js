/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.people.onboard.wizard";
const STEPS = [_t("Person"), _t("Role"), _t("Contract")];

export class OnboardWizard extends Component {
    static template = "pb_people_advanced.OnboardWizard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.state = useState({
            step: 1, loading: false, busyMsg: "", defaults: null, result: null,
            form: {
                name: "", work_email: "", work_phone: "", country_id: "",
                department_id: "", job_id: "", job_title: "", parent_id: "", fill_job_id: "",
                with_contract: true, struct_id: "", structure_type_id: "",
                wage: "", date_start: "", date_end: "", resource_calendar_id: "",
                activate: true, account_number: "", bank_name: "",
            },
        });
        // Opened from the org chart ("Add a team member › A new starter", "Fill
        // this role › A new starter"): manager, team, job and title arrive
        // pre-filled in the action's params (ORGCHART P2).
        const params = (this.props.action && this.props.action.params) || {};
        this.prefill = params.prefill || null;
        onWillStart(async () => {
            const d = await this.orm.call(MODEL, "get_defaults", []);
            this.state.defaults = d;
            this.state.form.date_start = d.today;
            this.state.form.struct_id = d.default_struct ? String(d.default_struct) : "";
            this.state.form.resource_calendar_id = d.default_calendar ? String(d.default_calendar) : "";
            const pre = this.prefill;
            if (pre) {
                const f = this.state.form;
                for (const k of ["department_id", "job_id", "parent_id"]) {
                    if (pre[k]) { f[k] = String(pre[k]); }
                }
                if (pre.job_title) { f.job_title = pre.job_title; }
                // "Fill this role › A new starter" (ORGCHART P3): saving the
                // person lowers that role's "to hire" count by one
                if (pre.fill_job_id) { f.fill_job_id = String(pre.fill_job_id); }
                // a pre-filled team or job that is not in the short lists is still shown
                const add = (list, id, name) => {
                    if (id && name && !list.some((x) => String(x.id) === String(id))) { list.unshift({ id, name }); }
                };
                add(d.departments || (d.departments = []), pre.department_id, pre.department_name);
                add(d.jobs || (d.jobs = []), pre.job_id, pre.job_title);
            }
        });
    }

    ic(n, s = 16) { return ic(n, s); }
    get steps() { return STEPS; }
    onField(f, ev) { this.state.form[f] = ev.target.value; }
    isSel(f, id) { return this.state.form[f] === String(id); }
    clearManager() { this.state.form.parent_id = ""; this.prefill = { ...this.prefill, parent_name: "" }; }
    toggle(f) { this.state.form[f] = !this.state.form[f]; }
    get cur() { return (this.state.defaults && this.state.defaults.currency) || "₫"; }

    get canNext() {
        if (this.state.step === 1) return !!this.state.form.name.trim();
        return true;
    }
    next() { if (this.canNext && this.state.step < 3) this.state.step += 1; }
    back() { if (this.state.step > 1) this.state.step -= 1; }

    async create() {
        this.state.loading = true; this.state.busyMsg = "Creating employee…";
        try {
            const res = await this.orm.call(MODEL, "create_employee", [this.state.form]);
            // A PENDING ANSWER IS NOT A FAILURE. It carries no employee id
            // because nobody has been added yet — that is the point.
            if (res.error && !res.employee_id && !res.pending) {
                this.notif.add(res.error, { type: "danger" }); return;
            }
            if (res.error && res.applied) {
                this.notif.add(_t("Employee created; contract: %(error)s", { error: res.error }), { type: "warning" });
            }
            this.state.result = res;
        } catch (e) {
            this.notif.add((e && e.message && e.message.toString()) || _t("Failed."), { type: "danger" });
        } finally { this.state.loading = false; }
    }
    openEmployee() {
        const id = this.state.result && this.state.result.employee_id;
        if (id) this.action.doAction({ type: "ir.actions.client", tag: "pb_employee_detail", name: "Employee", params: { emp_id: id } });
    }
    close() { this.action.doAction("pb_people.action_pb_people", { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_onboard_wizard", OnboardWizard);
