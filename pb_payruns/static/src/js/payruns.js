/** @odoo-module **/
/**
 * The Pay Runs pipeline board.
 *
 * HISTORY WORTH KNOWING. This cockpit was built, registered as the client action
 * `pb_payruns` — and then never pointed at: the rail item and the ⌘K entry both
 * open `pb_payruns.action_pb_payruns_kanban`, the native kanban with a KPI band
 * injected into it. So it has been dead code carrying three real defects nobody
 * could see (a `window.confirm`, two emoji glyphs, and a payload it asked the
 * server for and then ignored). IA Cycle 2 revives it as the Pay Run hub's
 * **Runs** lens, which is what it was always shaped for — the kanban's columns
 * ARE this board's columns, and the hub needs a lens, not an act_window.
 *
 * What the revival added, beyond the fixes:
 *   - `embedded` (W17) — the hub owns the title row, so it is suppressed;
 *   - `wantsArrival` — the wizard's terminal CTA hands over a run id, and the
 *     board highlights that card instead of dumping the user on a native form;
 *   - division chips + the gross column, so the lens is not poorer than the
 *     kanban it stands beside (the server already sent both);
 *   - an in-card confirm for Reject. `window.confirm` is a native dialog on a
 *     surface that owns a design system, and it blocks the whole browser tab.
 *
 * The standalone client action still exists and still works — this is one
 * component with two mount points, not a fork (W6/W17).
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const NEXT_METHOD = {
    submit: "done_payslip_run",
    approve_officer: "action_payslip_run_level0_done",
    approve_hr: "action_payslip_run_level1_done",
    approve_gm: "action_payslip_run_level2_done",
};
const NEXT_LABEL = {
    submit: _t("Submit for review"),
    approve_officer: _t("Approve (Officer)"),
    approve_hr: _t("Approve (HR)"),
    approve_gm: _t("Approve (Finance)"),
};
// Whole sentences, one msgid each. Building "%s done" out of the button label
// above would hand a translator two fragments and no way to reorder them (W80).
const DONE_MSG = {
    submit: _t("Pay run submitted for review."),
    approve_officer: _t("Pay run approved by the Payroll Officer."),
    approve_hr: _t("Pay run approved by HR."),
    approve_gm: _t("Pay run approved by Finance."),
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
            confirming: 0,          // run id whose Reject is awaiting confirmation
            currency: "",
            columns: [],
            batches: [],
            kpis: {},
            divisions: [],
            division: "all",
            rejectedCount: 0,
            showRejected: false,
            // the run the hub sent us to (arrival.focus), highlighted once
            focusId: this._arrivalFocus(),
        });
        onWillStart(async () => { await this.load(); });
    }

    /**
     * The run id the host asked us to show.
     *
     * Read ONCE, in setup, from a prop — a mount hook reads, it never writes
     * back to the host (W21). `arrival` only arrives when the lens declared
     * `wantsArrival`, so standalone this is always 0.
     */
    _arrivalFocus() {
        const f = (this.props.arrival || {}).focus;
        const n = parseInt(f, 10);
        return Number.isFinite(n) && n > 0 ? n : 0;
    }

    get embedded() { return !!this.props.embedded; }

    async load() {
        const d = await this.orm.call("pb.payruns", "get_board_data", []);
        Object.assign(this.state, {
            currency: d.currency, columns: d.columns, batches: d.batches,
            kpis: d.kpis, rejectedCount: d.rejected_count,
            divisions: d.divisions || [], loaded: true,
        });
    }

    ic(n, s = 15) { return ic(n, s); }

    // ---- derived ----
    /**
     * The board's cards for one column, narrowed by the division chip.
     *
     * The division is a way of LOOKING at the board and never changes what the
     * board IS (W82): the column COUNTS come from the server over the whole
     * scope and are left alone, so filtering to one division can never make the
     * pipeline look emptier than it is.
     */
    columnBatches(key) {
        return this.state.batches.filter(
            b => b.state === key && this._inDivision(b));
    }
    _inDivision(b) {
        const d = this.state.division;
        return d === "all" || (b.division || "") === d;
    }
    get rejectedBatches() {
        return this.state.batches.filter(b => b.state === "cancel" && this._inDivision(b));
    }
    get divisionChips() {
        return [{ key: "all", label: _t("All divisions") }, ...(this.state.divisions || [])];
    }
    setDivision(key) { this.state.division = key; }

    nextLabel(a) { return NEXT_LABEL[a] || _t("Open"); }

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
        // target:"current" WITHOUT clearBreadcrumbs — the breadcrumb is the way
        // back to the hub, and the run form is VU-skinned, so this is a real
        // door with a real return path (W5).
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "hr.payslip.run",
            res_id: id, views: [[false, "form"]], target: "current",
        });
    }

    /**
     * "Run payroll".
     *
     * Standalone it opens the wizard's own action. In a hub the wizard is
     * already a LENS, and replacing the whole workspace with a full-page action
     * would throw the user out of the hub to reach a surface that is one rail
     * click away — so the host hands in a callback and the hub switches lens.
     */
    newRun() {
        if (this.props.onRunPayroll) { return this.props.onRunPayroll(); }
        this.action.doAction("pb_payrun_wizard.action_pb_payrun_wizard", { clearBreadcrumbs: true });
    }

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
            this.notification.add(e.message ? e.message.toString() : _t("Action failed"), { type: "danger" });
        } finally {
            this.state.busy = 0;
        }
    }
    advance(b) {
        const method = NEXT_METHOD[b.next_action];
        if (method) this._run(method, b.id, DONE_MSG[b.next_action]);
    }

    // ---- reject: an in-card confirm, never a native dialog ----
    askReject(b) { this.state.confirming = b.id; }
    cancelReject() { this.state.confirming = 0; }
    confirmReject(b) {
        this.state.confirming = 0;
        this._run("action_payslip_run_cancel", b.id, _t("Pay run rejected"));
    }

    report(b) { this._run("action_open_payroll_report", b.id); }
    excel(b) { this._run("action_download_payslip_xlsx", b.id); }
    // Phase F: the bespoke Pay & Deliver experience replaces the legacy
    // "Bank file" + "Email" launchers (bank transfer file + payslip delivery).
    payDeliver(b) { this._run("action_pb_pay_deliver", b.id); }
    journals(b) { this._run("action_pb_journals", b.id); }
    payments(b) { this._run("action_pb_payments", b.id); }

    toggleRejected() { this.state.showRejected = !this.state.showRejected; }
}

registry.category("actions").add("pb_payruns", PbPayruns);
