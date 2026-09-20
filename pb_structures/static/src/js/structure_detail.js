/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";

export class PbStructureDetail extends Component {
    static template = "pb_structures.PbStructureDetail";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        const p = (this.props.action && (this.props.action.params || this.props.action.context)) || {};
        this.sid = p.structure_id || p.active_id;
        this.state = useState({ loaded: false, d: null });
        onWillStart(async () => { await this.refresh(); });
    }

    ic(n, s = 16) { return ic(n, s); }
    get d() { return this.state.d || {}; }

    async refresh() {
        try { this.state.d = await this.orm.call("pb.structures", "get_structure_detail", [this.sid]); }
        catch (e) { this.state.d = { error: "Could not load this structure." }; }
        finally { this.state.loaded = true; }
    }

    addRule() {
        this.action.doAction({ type: "ir.actions.client", tag: "pb_structure_rule_wizard", name: "Add rule", params: { structure_id: this.sid } });
    }
    openAdvancedForm() {
        this.action.doAction({ type: "ir.actions.act_window", res_model: "hr.payroll.structure", res_id: this.sid, views: [[false, "form"]], target: "current" });
    }
    back() { this.action.doAction("pb_structures.action_pb_structures", { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_structure_detail", PbStructureDetail);
