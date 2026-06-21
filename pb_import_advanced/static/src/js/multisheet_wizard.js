/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.import.multisheet.wizard";
const STEPS = ["Upload", "Sheets"];

export class MultisheetWizard extends Component {
    static template = "pb_import_advanced.MultisheetWizard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.state = useState({
            step: 1, loading: false, busyMsg: "", defaults: null,
            form: { config_id: "", file_b64: "", file_name: "" },
            data: null,        // serialized wizard (sheets)
            columns: [],
        });
        onWillStart(async () => {
            const d = await this.orm.call(MODEL, "get_defaults", []);
            this.state.defaults = d;
            this.state.form.config_id = d.default_config_id ? String(d.default_config_id) : "";
        });
    }

    ic(n, s = 16) { return ic(n, s); }
    get steps() { return STEPS; }
    onField(f, ev) { this.state.form[f] = ev.target.value; }
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
    get canStart() { return !!(this.state.form.config_id && this.state.form.file_b64); }

    async _run(promise, msg, after) {
        this.state.loading = true; this.state.busyMsg = msg;
        try {
            const res = await promise;
            if (res && res.error) { this.notif.add(res.error, { type: "danger" }); return null; }
            if (after) after(res);
            return res;
        } catch (e) {
            this.notif.add((e && e.message && e.message.toString()) || "Step failed.", { type: "danger" });
            return null;
        } finally { this.state.loading = false; }
    }

    async start() {
        await this._run(this.orm.call(MODEL, "start", [this.state.form]), "Analyzing workbook…", (res) => {
            this.state.data = res; this.state.step = 2;
        });
    }
    get sheets() { return (this.state.data && this.state.data.sheets) || []; }
    async toggleSheet(id, ev) {
        const res = await this.orm.call(MODEL, "save_sheet", [id, ev.target.checked]);
        if (res) this.state.data = res;
    }
    async setMain(id) {
        const res = await this.orm.call(MODEL, "set_main_sheet", [this.state.data.wizard_id, id]);
        if (res) this.state.data = res;
    }

    async finish() {
        const res = await this._run(this.orm.call(MODEL, "to_native", [this.state.data.wizard_id]),
                                    "Preparing advanced view…");
        if (res && res.type) this.action.doAction(res);
    }
    back() { if (this.state.step > 1) this.state.step -= 1; }
    close() { this.action.doAction("pb_import.action_pb_import", { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_import_multisheet_wizard", MultisheetWizard);
