/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.structures.wizard";

export class StructureWizard extends Component {
    static template = "pb_structures.StructureWizard";
    static props = ["*"];
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.state = useState({
            loading: false, defaults: null, result: null,
            form: { name: "", code: "", payroll_country_code: "", schedule_pay: "monthly", is_base: false, activate: true },
        });
        onWillStart(async () => { this.state.defaults = await this.orm.call(MODEL, "get_defaults", []); });
    }
    ic(n, s = 16) { return ic(n, s); }
    onField(f, ev) { this.state.form[f] = ev.target.value; }
    toggle(f) { this.state.form[f] = !this.state.form[f]; }
    get canCreate() { return !!(this.state.form.name.trim() && this.state.form.code.trim()); }
    async create() {
        this.state.loading = true;
        try {
            const res = await this.orm.call(MODEL, "create_structure", [this.state.form]);
            if (res.error) { this.notif.add(res.error, { type: "danger" }); return; }
            this.state.result = res;
        } catch (e) { this.notif.add(_t("Failed."), { type: "danger" }); }
        finally { this.state.loading = false; }
    }
    openStructure() {
        const id = this.state.result && this.state.result.structure_id;
        if (id) this.action.doAction({ type: "ir.actions.client", tag: "pb_structure_detail", name: "Structure", params: { structure_id: id } });
    }
    close() { this.action.doAction("pb_structures.action_pb_structures", { clearBreadcrumbs: true }); }
}
registry.category("actions").add("pb_structure_wizard", StructureWizard);


export class StructureRuleWizard extends Component {
    static template = "pb_structures.StructureRuleWizard";
    static props = ["*"];
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        const p = (this.props.action && (this.props.action.params || this.props.action.context)) || {};
        this.sid = p.structure_id;
        this.state = useState({
            loading: false, defaults: null, result: null,
            form: { structure_id: this.sid, category_id: "", name: "", code: "", amount_select: "fix", value: "", appears: true },
        });
        onWillStart(async () => {
            const d = await this.orm.call(MODEL, "get_rule_defaults", [this.sid]);
            this.state.defaults = d;
            if (d.categories && d.categories.length) this.state.form.category_id = String(d.categories[0].id);
        });
    }
    ic(n, s = 16) { return ic(n, s); }
    onField(f, ev) { this.state.form[f] = ev.target.value; }
    setAmount(a) { this.state.form.amount_select = a; }
    toggle(f) { this.state.form[f] = !this.state.form[f]; }
    get canCreate() { const f = this.state.form; return !!(f.name.trim() && f.code.trim() && f.category_id); }
    async create() {
        this.state.loading = true;
        try {
            const res = await this.orm.call(MODEL, "add_rule", [{ ...this.state.form, structure_id: this.sid }]);
            if (res.error) { this.notif.add(res.error, { type: "danger" }); return; }
            this.state.result = res;
        } catch (e) { this.notif.add(_t("Failed."), { type: "danger" }); }
        finally { this.state.loading = false; }
    }
    backToStructure() {
        this.action.doAction({ type: "ir.actions.client", tag: "pb_structure_detail", name: "Structure", params: { structure_id: this.sid } });
    }
}
registry.category("actions").add("pb_structure_rule_wizard", StructureRuleWizard);
