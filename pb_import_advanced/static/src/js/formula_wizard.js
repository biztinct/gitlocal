/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.import.formula.wizard";

export class FormulaWizard extends Component {
    static template = "pb_import_advanced.FormulaWizard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        const p = (this.props.action && (this.props.action.params || this.props.action.context)) || {};
        this.ctxConfig = p.config_id || p.active_id || false;
        this.state = useState({
            loading: false, busyMsg: "", defaults: null, rules: [], result: null,
            form: {
                config_id: "", import_source: "salary_rules", salary_rule_ids: [],
                structure_id: "", file_b64: "", file_name: "",
                create_input_columns: true, preserve_existing: true, map_categories: true,
            },
        });
        onWillStart(async () => {
            const d = await this.orm.call(MODEL, "get_defaults", [this.ctxConfig]);
            this.state.defaults = d;
            this.state.form.config_id = d.default_config_id ? String(d.default_config_id) : "";
            this.state.rules = await this.orm.call(MODEL, "get_rules", ["", 80]);
        });
    }

    ic(n, s = 16) { return ic(n, s); }
    onField(f, ev) { this.state.form[f] = ev.target.value; }
    toggle(f) { this.state.form[f] = !this.state.form[f]; }

    setSource(id) {
        this.state.form.import_source = id;
        this.state.form.salary_rule_ids = [];
    }
    isRuleOn(id) { return this.state.form.salary_rule_ids.includes(id); }
    toggleRule(id) {
        const arr = this.state.form.salary_rule_ids;
        const i = arr.indexOf(id);
        if (i >= 0) arr.splice(i, 1); else arr.push(id);
    }
    async onRuleSearch(ev) {
        this.state.rules = await this.orm.call(MODEL, "get_rules", [ev.target.value, 80]);
    }
    async onStructure(ev) {
        this.state.form.structure_id = ev.target.value;
        if (ev.target.value) {
            this.state.rules = await this.orm.call(MODEL, "get_structure_rules", [ev.target.value]);
            this.state.form.salary_rule_ids = this.state.rules.map((r) => r.id);
        }
    }
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

    get canImport() {
        const f = this.state.form;
        if (!f.config_id) return false;
        if (f.import_source === "salary_rules") return f.salary_rule_ids.length > 0;
        if (f.import_source === "structure") return !!f.structure_id;
        return !!f.file_b64;        // json / excel
    }

    async doImport() {
        this.state.loading = true; this.state.busyMsg = "Importing rules…";
        try {
            const res = await this.orm.call(MODEL, "run_import", [this.state.form]);
            this.state.result = res;
            if (res.error) this.notif.add(res.error, { type: "danger" });
        } catch (e) {
            this.notif.add((e && e.message && e.message.toString()) || "Import failed.", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }
    async downloadTemplate() {
        const act = await this.orm.call(MODEL, "download_template", [this.state.form.config_id]);
        if (act) this.action.doAction(act);
    }
    openConfig() {
        const id = this.state.result && this.state.result.config_id;
        if (id) this.action.doAction({
            type: "ir.actions.act_window", res_model: "hr.formula.config",
            res_id: id, views: [[false, "form"]], target: "current",
        });
    }
    close() { this.action.doAction("pb_import.action_pb_import", { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_import_formula_wizard", FormulaWizard);
