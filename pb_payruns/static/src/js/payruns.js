/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const NEXT_METHOD = {
    submit: "done_payslip_run",
    approve_hr: "action_payslip_run_level1_done",
    approve_gm: "action_payslip_run_level2_done",
};
const NEXT_LABEL = {
    submit: "Submit for review",
    approve_hr: "Approve (HR)",
    approve_gm: "Approve (GM)",
};

export class PbPayruns extends Component {
    static template = "pb_payruns.PbPayruns";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loaded: false,
            busy: 0,
            currency: "",
            columns: [],
            batches: [],
            kpis: {},
            rejectedCount: 0,
            showRejected: false,
        });
        onWillStart(async () => { await this.load(); });
    }

    async load() {
        const d = await this.orm.call("pb.payruns", "get_board_data", []);
        Object.assign(this.state, {
            currency: d.currency, columns: d.columns, batches: d.batches,
            kpis: d.kpis, rejectedCount: d.rejected_count, loaded: true,
        });
    }

    // ---- derived ----
    columnBatches(key) {
        if (key === "done") {
            // newest done first, cap visible to keep the column tidy
            return this.state.batches.filter(b => b.state === "done");
        }
        return this.state.batches.filter(b => b.state === key);
    }
    get rejectedBatches() { return this.state.batches.filter(b => b.state === "cancel"); }
    nextLabel(a) { return NEXT_LABEL[a] || "Open"; }

    money(n) {
        if (n === null || n === undefined) return "—";
        const cur = this.state.currency || "₫";
        const a = Math.abs(n);
        if (a >= 1e9) return cur + (n / 1e9).toFixed(2) + "B";
        if (a >= 1e6) return cur + (n / 1e6).toFixed(1) + "M";
        if (a >= 1e3) return cur + (n / 1e3).toFixed(0) + "K";
        return cur + Math.round(n);
    }

    // ---- navigation ----
    openBatch(id) {
        if (!id) return;
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "hr.payslip.run",
            res_id: id, views: [[false, "form"]], target: "current",
        });
    }
    newRun() { this.action.doAction("pb_payrun_wizard.action_pb_payrun_wizard", { clearBreadcrumbs: true }); }

    // ---- workflow actions ----
    async _run(method, id, okMsg) {
        if (!id || this.state.busy) return;
        this.state.busy = id;
        try {
            const res = await this.orm.call("hr.payslip.run", method, [[id]]);
            if (res && typeof res === "object" && res.type) {
                // act_url / client action → run it; notifications → toast
                await this.action.doAction(res);
            } else if (okMsg) {
                this.notification.add(okMsg, { type: "success" });
            }
            await this.load();
        } catch (e) {
            this.notification.add(e.message ? e.message.toString() : "Action failed", { type: "danger" });
        } finally {
            this.state.busy = 0;
        }
    }
    advance(b) {
        const method = NEXT_METHOD[b.next_action];
        if (method) this._run(method, b.id, NEXT_LABEL[b.next_action] + " done");
    }
    reject(b) {
        if (!window.confirm(`Reject "${b.name}"? All payslips in this batch will be cancelled.`)) return;
        this._run("action_payslip_run_cancel", b.id, "Pay run rejected");
    }
    report(b) { this._run("action_open_payroll_report", b.id); }
    excel(b) { this._run("action_download_payslip_xlsx", b.id); }
    email(b) { this._run("action_send_email_all", b.id, "Payslips emailed"); }

    toggleRejected() { this.state.showRejected = !this.state.showRejected; }
}

registry.category("actions").add("pb_payruns", PbPayruns);
