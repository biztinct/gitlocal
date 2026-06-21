/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.import.employee.wizard";
const STEPS = ["Source", "Preview", "Done"];

export class EmployeeWizard extends Component {
    static template = "pb_import_advanced.EmployeeWizard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.state = useState({
            step: 1, loading: false, busyMsg: "", defaults: null, summary: null,
            form: {
                import_source: "file", country_code: "", file_b64: "", file_name: "",
                data_source_url: "", update_existing: true, create_contracts: true,
                zoho_api_key: "", zoho_org_id: "",
            },
        });
        onWillStart(async () => { this.state.defaults = await this.orm.call(MODEL, "get_defaults", []); });
    }

    ic(n, s = 16) { return ic(n, s); }
    get steps() { return STEPS; }
    onField(f, ev) { this.state.form[f] = ev.target.value; }
    toggle(f) { this.state.form[f] = !this.state.form[f]; }
    setSource(id) { this.state.form.import_source = id; }
    onFile(ev) {
        const f = ev.target.files && ev.target.files[0];
        if (!f) return;
        const reader = new FileReader();
        reader.onload = () => {
            this.state.form.file_b64 = String(reader.result).split(",")[1] || "";
            this.state.form.file_name = f.name;
        };
        reader.readAsDataURL(f);
    }

    get canPreview() {
        const f = this.state.form;
        if (f.import_source === "file") return !!f.file_b64;
        if (f.import_source === "zoho") return !!(f.zoho_api_key && f.zoho_org_id);
        if (f.import_source === "api") return !!f.data_source_url;
        return false;
    }

    async testZoho() {
        this.state.loading = true; this.state.busyMsg = "Testing Zoho connection…";
        try {
            const res = await this.orm.call(MODEL, "test_zoho", [this.state.form]);
            this.notif.add(res.message, { type: res.ok ? "success" : "danger" });
        } finally { this.state.loading = false; }
    }

    async _run(promise, msg, nextStep) {
        this.state.loading = true; this.state.busyMsg = msg;
        try {
            const res = await promise;
            this.state.summary = res;
            if (res.error) this.notif.add(res.error, { type: "warning" });
            else if (nextStep) this.state.step = nextStep;
        } catch (e) {
            this.notif.add((e && e.message && e.message.toString()) || "Step failed.", { type: "danger" });
        } finally { this.state.loading = false; }
    }
    toPreview() { return this._run(this.orm.call(MODEL, "create_and_preview", [this.state.form]), "Loading preview…", 2); }
    doImport() { return this._run(this.orm.call(MODEL, "do_import", [this.state.summary.wizard_id]), "Importing employees…", 3); }

    async viewEmployees() {
        const act = await this.orm.call(MODEL, "get_link", [this.state.summary.wizard_id, "action_view_imported_employees"]);
        if (act) this.action.doAction(act);
    }
    back() { if (this.state.step > 1) this.state.step -= 1; }
    close() { this.action.doAction("pb_import.action_pb_import", { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_import_employee_wizard", EmployeeWizard);
