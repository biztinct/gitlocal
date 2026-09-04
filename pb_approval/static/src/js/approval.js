/** @odoo-module **/
/**
 * Approvals — the payroll approval pipeline as a 3-lane board
 * (Officer review → HR review → Finance approval), on pbim tokens.
 *
 * Read-and-act: every decision calls pb.approval, which calls hr.payslip.run's
 * own gated action. Cards the current user cannot decide render read-only with
 * a "waits on <role>" chip — the server refuses them anyway (the tier gate is
 * model-side; this is only honesty in the UI).
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_approval/js/pba_icons";

const MODEL = "pb.approval";

export class PbApproval extends Component {
    static template = "pb_approval.PbApproval";
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.ic = ic;
        this.state = useState({
            loaded: false,
            busy: 0,
            data: null,
            rejectRun: null,
            rejectNote: "",
        });
        onWillStart(async () => { await this.load(); });
    }

    async load() {
        try {
            this.state.data = await this.orm.call(MODEL, "get_approvals", []);
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        }
        this.state.loaded = true;
    }

    // ------------------------------------------------------------- getters
    get d() { return this.state.data || {}; }
    get lanes() { return this.d.lanes || []; }
    get summary() { return this.d.summary || {}; }
    get recent() { return this.d.recent || []; }
    get isEmpty() { return this.state.loaded && !(this.d.pending || []).length; }

    // ------------------------------------------------------------- format
    vnd(n) {
        if (n === null || n === undefined) return "—";
        const a = Math.abs(n);
        if (a >= 1e9) return "₫" + (n / 1e9).toFixed(2) + "B";
        if (a >= 1e6) return "₫" + (n / 1e6).toFixed(1) + "M";
        if (a >= 1e3) return "₫" + (n / 1e3).toFixed(0) + "K";
        return "₫" + Math.round(n);
    }
    laneCls(key) { return key === "level0" ? "l0" : key === "level1" ? "l1" : "l2"; }
    // 3-dot chain stepper: dots before `step` are cleared, `step` is current
    dotCls(run, i) { return i < run.step ? "done" : (i === run.step ? "current" : "future"); }
    waitsOn(run) { return _t("Waits on %s", run.role); }

    _err(e) {
        const m = (e && (e.data && e.data.message)) || (e && e.message) || "";
        return m ? m.toString() : _t("Action failed.");
    }

    // ------------------------------------------------------------- actions
    async approve(run) {
        if (this.state.busy) return;
        this.state.busy = run.id;
        try {
            const res = await this.orm.call(MODEL, "approve_run", [run.id]);
            if (res.ok) this.notif.add(_t("%s approved.", run.name), { type: "success" });
            else this.notif.add(res.msg || _t("Action failed."), { type: "warning" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = 0;
        }
        await this.load();
    }

    openReject(run) {
        this.state.rejectRun = run;
        this.state.rejectNote = "";
    }
    closeReject() { this.state.rejectRun = null; }
    onRejectNote(ev) { this.state.rejectNote = ev.target.value; }

    async confirmReject() {
        const run = this.state.rejectRun;
        const note = (this.state.rejectNote || "").trim();
        if (!run || !note) {
            this.notif.add(_t("Please give a reason for rejecting this pay run."),
                { type: "warning" });
            return;
        }
        this.state.busy = run.id;
        try {
            const res = await this.orm.call(MODEL, "reject_run", [run.id, note]);
            if (res.ok) {
                this.notif.add(_t("%s rejected.", run.name), { type: "success" });
                this.state.rejectRun = null;
            } else {
                this.notif.add(res.msg || _t("Action failed."), { type: "warning" });
            }
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = 0;
        }
        await this.load();
    }

    openRun(id) {
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "hr.payslip.run",
            res_id: id, views: [[false, "form"]], target: "current",
        });
    }
}

registry.category("actions").add("pb_approval", PbApproval);
