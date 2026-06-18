/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class PbApproval extends Component {
    static template = "pb_approval.PbApproval";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.state = useState({ loaded: false, pending: [], recent: [], summary: {} });
        onWillStart(async () => { await this.load(); });
    }

    async load() {
        const d = await this.orm.call("pb.approval", "get_approvals", []);
        this.state.pending = d.pending;
        this.state.recent = d.recent;
        this.state.summary = d.summary;
        this.state.loaded = true;
    }

    vnd(n) { if (n === null || n === undefined) return "—"; const a = Math.abs(n); if (a >= 1e9) return "₫" + (n / 1e9).toFixed(1) + "B"; if (a >= 1e6) return "₫" + (n / 1e6).toFixed(1) + "M"; if (a >= 1e3) return "₫" + (n / 1e3).toFixed(0) + "K"; return "₫" + Math.round(n); }
    initials(name) { return (name || "?").split(/[\s-]+/).filter(Boolean).map(p => p[0]).join("").slice(0, 2).toUpperCase(); }
    stageCls(state) { return state === "level1" ? "amber" : state === "level2" ? "indigo" : "green"; }

    async approve(id) {
        const res = await this.orm.call("pb.approval", "approve_run", [id]);
        if (!res.ok) this.notif.add(res.msg || "Action blocked", { type: "warning" });
        else this.notif.add("Run approved", { type: "success" });
        await this.load();
    }

    openRun(id) {
        this.action.doAction({ type: "ir.actions.act_window", res_model: "hr.payslip.run",
            res_id: id, views: [[false, "form"]], target: "current" });
    }
}

registry.category("actions").add("pb_approval", PbApproval);
