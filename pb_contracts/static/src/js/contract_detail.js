/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.contracts";
const C_CLS = { open: "ok", close: "warn", draft: "info", cancel: "muted" };

export class PbContractDetail extends Component {
    static template = "pb_contracts.PbContractDetail";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        const p = (this.props.action && (this.props.action.params || this.props.action.context)) || {};
        this.cid = p.contract_id || p.active_id;
        this.state = useState({ loaded: false, busy: false, busyMsg: "", d: null });
        onWillStart(async () => { await this.refresh(); });
    }

    ic(n, s = 16) { return ic(n, s); }
    get d() { return this.state.d || {}; }
    cCls(s) { return C_CLS[s] || "muted"; }
    money(n) {
        if (!n) return (this.d.currency || "₫") + "0";
        return (this.d.currency || "₫") + Math.round(n).toLocaleString("en-US");
    }
    initials() { return (this.d.employee || "?").trim().slice(0, 2).toUpperCase(); }

    async refresh() {
        try { this.state.d = await this.orm.call(MODEL, "get_contract_detail", [this.cid]); }
        catch (e) { this.state.d = { error: "Could not load this contract." }; }
        finally { this.state.loaded = true; }
    }

    async runAction(method) {
        if (method === "renew") return this.renew();
        this.state.busy = true;
        this.state.busyMsg = { set_running: "Activating…", terminate: "Terminating…", cancel: "Cancelling…" }[method] || "Working…";
        try {
            const res = await this.orm.call(MODEL, "run_contract_action", [this.cid, method]);
            this.state.d = res;
            if (res.error) this.notif.add(res.error, { type: "warning" });
            else this.notif.add("Done.", { type: "success" });
        } catch (e) {
            this.notif.add((e && e.message && e.message.toString()) || "Action failed.", { type: "danger" });
        } finally { this.state.busy = false; }
    }
    renew() {
        this.action.doAction({ type: "ir.actions.client", tag: "pb_contract_wizard", name: "Renew contract",
                               params: { employee_id: this.d.employee_id, renew_from: this.cid } });
    }
    openEmployee() {
        if (this.d.employee_id) this.action.doAction({ type: "ir.actions.client", tag: "pb_employee_detail", name: "Employee", params: { emp_id: this.d.employee_id } });
    }
    openAdvancedForm() {
        this.action.doAction({ type: "ir.actions.act_window", res_model: "hr.contract", res_id: this.cid, views: [[false, "form"]], target: "current" });
    }
    back() { this.action.doAction("pb_contracts.action_pb_contracts", { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_contract_detail", PbContractDetail);
