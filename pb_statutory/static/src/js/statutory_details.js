/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";

function money(cur, n) { return (cur || "₫") + Math.round(n || 0).toLocaleString("en-US"); }

export class PbPolicyDetail extends Component {
    static template = "pb_statutory.PbPolicyDetail";
    static props = ["*"];
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        const p = (this.props.action && (this.props.action.params || this.props.action.context)) || {};
        this.pid = p.policy_id || p.active_id;
        this.state = useState({ loaded: false, d: null });
        onWillStart(async () => {
            try { this.state.d = await this.orm.call("pb.statutory", "get_policy_detail", [this.pid]); }
            catch (e) { this.state.d = { error: "Could not load this policy." }; }
            finally { this.state.loaded = true; }
        });
    }
    ic(n, s = 16) { return ic(n, s); }
    get d() { return this.state.d || {}; }
    money(n) { return money(this.d.currency, n); }
    openAdvancedForm() { this.action.doAction({ type: "ir.actions.act_window", res_model: "vietnam.insurance.policy", res_id: this.pid, views: [[false, "form"]], target: "current" }); }
    back() { this.action.doAction("pb_statutory.action_pb_statutory", { clearBreadcrumbs: true }); }
}
registry.category("actions").add("pb_policy_detail", PbPolicyDetail);


export class PbTaxDetail extends Component {
    static template = "pb_statutory.PbTaxDetail";
    static props = ["*"];
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        const p = (this.props.action && (this.props.action.params || this.props.action.context)) || {};
        this.tid = p.tax_id || p.active_id;
        this.state = useState({ loaded: false, d: null });
        onWillStart(async () => {
            try { this.state.d = await this.orm.call("pb.statutory", "get_tax_detail", [this.tid]); }
            catch (e) { this.state.d = { error: "Could not load this tax table." }; }
            finally { this.state.loaded = true; }
        });
    }
    ic(n, s = 16) { return ic(n, s); }
    get d() { return this.state.d || {}; }
    money(n) { return money(this.d.currency, n); }
    openAdvancedForm() { this.action.doAction({ type: "ir.actions.act_window", res_model: "vietnam.tax.table", res_id: this.tid, views: [[false, "form"]], target: "current" }); }
    back() { this.action.doAction("pb_statutory.action_pb_statutory", { clearBreadcrumbs: true }); }
}
registry.category("actions").add("pb_tax_detail", PbTaxDetail);
