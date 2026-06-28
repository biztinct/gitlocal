/** @odoo-module **/

import { Component, useState, onWillStart, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

const IC = {
    check:'<path d="M20 6 9 17l-5-5"/>',
    calendar:'<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    zap:'<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
    alert:'<path d="m21.7 18-8-14a2 2 0 0 0-3.4 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    arrow:'<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
};
const STEPS = ["Select period", "Compute", "Review exceptions", "Approve"];

export class PayrunWizard extends Component {
    static template = "pb_payrun_wizard.PayrunWizard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.dialog = useService("dialog");
        this.state = useState({
            step: 1, loading: false, busyMsg: "",
            defaults: null, form: { name: "", date_start: "", date_end: "", struct_id: null },
            summary: null,
        });
        onWillStart(async () => {
            const d = await this.orm.call("pb.payrun.wizard", "get_defaults", []);
            this.state.defaults = d;
            this.state.form.name = d.name;
            this.state.form.date_start = d.date_start;
            this.state.form.date_end = d.date_end;
        });
    }

    ic(n, s = 16) { return markup(`<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${IC[n] || IC.check}</svg>`); }
    vnd(n) { n = n || 0; if (n >= 1e9) return "₫" + (n / 1e9).toFixed(1) + "B"; if (n >= 1e6) return "₫" + (n / 1e6).toFixed(1) + "M"; if (n >= 1e3) return "₫" + (n / 1e3).toFixed(0) + "K"; return "₫" + Math.round(n); }
    get steps() { return STEPS; }

    onField(f, ev) { this.state.form[f] = ev.target.value; }

    async toCompute() {
        // Step 1 -> 2: create + compute a (draft) run, guarding existing payroll.
        this.state.step = 2;
        this.state.loading = true;
        this.state.busyMsg = "Creating run and computing payslips…";
        try {
            await this._compute(false);
        } catch (e) {
            this.notif.add("Could not compute the run. See server logs.", { type: "danger" });
            this.state.step = 1;
        } finally {
            this.state.loading = false;
        }
    }

    async _compute(force) {
        const payload = { ...this.state.form, force_clean: force };
        const res = await this.orm.call("pb.payrun.wizard", "create_and_compute", [payload]);
        if (res && res.needs_confirmation) {
            this.state.step = 1;          // sit behind the dialog on step 1
            this._confirmOverwrite(res);
            return;
        }
        this.state.summary = res;
    }

    _confirmOverwrite(res) {
        const historical = res.kind === "historical";
        this.dialog.add(ConfirmationDialog, {
            title: historical ? "Historical payroll is locked" : "Payroll already exists",
            body: res.message,
            confirmLabel: historical ? "Clean July & Run" : "Clean and Run",
            cancelLabel: "Cancel",
            confirm: async () => {
                if (historical && res.july) {
                    this.state.form.name = res.july.name;
                    this.state.form.date_start = res.july.date_start;
                    this.state.form.date_end = res.july.date_end;
                }
                this.state.step = 2;
                this.state.loading = true;
                this.state.busyMsg = "Cleaning previous data and re-running payroll…";
                try { await this._compute(true); }
                catch (e) { this.notif.add("Re-run failed. See server logs.", { type: "danger" }); this.state.step = 1; }
                finally { this.state.loading = false; }
            },
            cancel: () => { this.state.step = 1; },
        });
    }

    goto(n) {
        if (n === 2 && !this.state.summary) { return this.toCompute(); }
        if (n >= 1 && n <= 4) this.state.step = n;
    }

    async submit() {
        this.state.loading = true;
        this.state.busyMsg = "Submitting for approval…";
        try {
            await this.orm.call("pb.payrun.wizard", "submit_for_approval", [this.state.summary.run_id]);
        } catch (e) { /* guarded */ }
        this.state.loading = false;
        this.state.step = 4;
    }

    openRun() {
        if (this.state.summary?.run_id) {
            this.action.doAction({
                type: "ir.actions.act_window", res_model: "hr.payslip.run",
                res_id: this.state.summary.run_id, views: [[false, "form"]], target: "current",
            });
        }
    }
    cancel() { this.action.doAction("pb_dashboard.action_pb_dashboard", { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_payrun_wizard", PayrunWizard);
