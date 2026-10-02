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
import { Component, useState, useRef, useEffect, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

// There is ONE action a card can take on the run itself now: send it in. What
// happens next is a decision, and a decision is made where the request is —
// in Approvals — never from a board button that would have to guess which step
// it is answering.
const NEXT_METHOD = {
    submit: "action_approval_submit",
};
const NEXT_LABEL = {
    submit: _t("Submit for approval"),
    decide: _t("Open the approval"),
};
// Whole sentences, one msgid each. Building "%s done" out of the button label
// above would hand a translator two fragments and no way to reorder them (W80).
const DONE_MSG = {
    submit: _t("Pay run sent in for approval."),
};

export class PbPayruns extends Component {
    static template = "pb_payruns.PbPayruns";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.rejectWhy = useRef("rejectWhy");
        // the reason box takes the keyboard the moment the confirm opens
        useEffect((open) => {
            if (open && this.rejectWhy.el) { this.rejectWhy.el.focus(); }
        }, () => [this.state.confirming]);
        this.state = useState({
            loaded: false,
            busy: 0,
            confirming: 0,          // run id whose Reject is awaiting confirmation
            rejectNote: "",         // the "Why?" typed in that confirm
            currency: "",
            currencyName: "",
            manyCurrencies: false,
            currencies: [],
            columns: [],
            batches: [],
            kpis: {},
            divisions: [],
            division: "all",
            // quiet board: the step pressed ('' = every step) and the figure
            // pressed in the numbers line ('' = none). Both only narrow what
            // is drawn; the server's column counts are never touched (W82).
            step: "",
            focus: "",
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
            // GROUP P3 — each run is priced in its own company's money, and
            // a board holding two currencies says so instead of pretending.
            currencyName: d.currency_name || "",
            manyCurrencies: !!d.many_currencies,
            currencies: d.currencies || [],
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
            b => b.state === key && this._inDivision(b) && this._inFocus(b));
    }
    /** The columns drawn: every step, or only the one pressed. */
    get shownColumns() {
        const cols = this.state.columns;
        if (this.state.step) return cols.filter(c => c.key === this.state.step);
        if (this.state.focus === "pipeline") return cols.filter(c => c.key !== "done");
        if (this.state.focus === "done") return cols.filter(c => c.key === "done");
        return cols;
    }
    _inFocus(b) {
        const f = this.state.focus;
        if (f === "mine") return !!b.awaiting_me;
        if (f === "pipeline") return b.state === "draft" || b.state === "approval_pending";
        if (f === "done") return b.state === "done";
        return true;
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

    // ================================================ quiet board
    //
    // One slim numbers line instead of five tiles, and the three columns
    // drawn as numbered steps above the board. A run is at EXACTLY one step
    // (its state), so the step counts add up to every live run; a rejected
    // run is an outcome, at no step — it stays in the drawer below.
    _runsLabel(n) { return n === 1 ? _t("1 pay run") : _t("%s pay runs", n); }

    get liveBatches() {
        return this.state.batches.filter(b => b.state !== "cancel");
    }

    get steps() {
        const live = this.liveBatches;
        return this.state.columns.map((col, i) => {
            const at = live.filter(b => b.state === col.key);
            let flag = "";
            if (col.key === "approval_pending") {
                const mine = at.filter(b => b.awaiting_me).length;
                if (mine) {
                    flag = mine === 1 ? _t("1 waiting on you") : _t("%s waiting on you", mine);
                } else if (at.length) {
                    flag = at.length === 1 ? _t("1 waiting for a sign-off") : _t("%s waiting for a sign-off", at.length);
                }
            } else if (col.key === "draft") {
                const back = at.filter(b => b.return_note).length;
                if (back) {
                    flag = back === 1 ? _t("1 sent back to be fixed") : _t("%s sent back to be fixed", back);
                }
            }
            return {
                key: col.key,
                n: String(i + 1).padStart(2, "0"),
                title: col.label,
                count: at.length,
                countLabel: this._runsLabel(at.length),
                sub: "",
                flag,
                flagTone: "",
                on: this.state.step === col.key,
            };
        });
    }

    pickStep(key) {
        this.state.focus = "";
        this.state.step = this.state.step === key ? "" : key;
    }

    toggleFocus(key) {
        this.state.step = "";
        this.state.focus = this.state.focus === key ? "" : key;
    }

    get glance() {
        const k = this.state.kpis || {};
        const tone = (v, t) => (v ? t : "");
        const net = k.period_net ? this.money(k.period_net) : 0;
        return [
            { key: "total", n: k.total || 0, label: _t("Pay runs"), tone: "", run: null },
            { key: "pipeline", n: k.in_pipeline || 0, label: _t("In pipeline"), tone: "", run: () => this.toggleFocus("pipeline") },
            { key: "mine", n: k.my_pending || 0, label: _t("Awaiting your approval"), tone: tone(k.my_pending, "amber"), run: () => this.toggleFocus("mine") },
            { key: "done", n: k.done || 0, label: _t("Completed"), tone: "", run: () => this.toggleFocus("done") },
            { key: "net", n: net,
              label: this.state.currencyName
                  ? _t("Net paid (done), in %s", this.state.currencyName)
                  : _t("Net paid (done)"),
              tone: "", run: null },
        ];
    }

    get showingLine() {
        const all = this.liveBatches.length;
        const narrowed = this.state.step || this.state.focus || this.state.division !== "all";
        if (!narrowed) {
            return { all: true, text: !all ? _t("no pay runs yet") : all === 1 ? _t("all 1 pay run") : _t("all %s pay runs", all) };
        }
        const shown = this.shownColumns.reduce((n, c) => n + this.columnBatches(c.key).length, 0);
        const st = this.state.columns.find(c => c.key === this.state.step);
        return { all: false, text: _t("%s of %s pay runs", shown, all), where: st ? st.label : "" };
    }

    showAll() {
        this.state.step = "";
        this.state.focus = "";
        this.state.division = "all";
    }

    nextLabel(a) { return NEXT_LABEL[a] || _t("Open"); }

    /* A run's own figures are ALWAYS drawn through these two, never through
       `money()` directly. `money()` falls back to the board's currency, which
       is the reader's company — so an India run on a Vietnamese board came out
       in dong. One board can hold several currencies; a per-run figure has no
       business defaulting to any of them. */

    /** One run's gross, in the money that run was actually paid in. */
    runGross(b) { return this.money(b.gross, b.currency); }

    /** One run's net, in the money that run was actually paid in. */
    runMoney(b) { return this.money(b.net, b.currency); }

    money(n, symbol) {
        if (n === null || n === undefined) return "—";
        const cur = symbol || this.state.currency || "₫";
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
    async _run(method, id, okMsg, ctx) {
        if (!id || this.state.busy) return;
        this.state.busy = id;
        try {
            const res = await this.orm.call("hr.payslip.run", method, [[id]],
                ctx ? { context: ctx } : {});
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
        if (b.next_action === "decide") { return this.openApprovals(); }
        const method = NEXT_METHOD[b.next_action];
        if (method) this._run(method, b.id, DONE_MSG[b.next_action]);
    }

    /** The one door to a decision. Named as a plain string rather than
     *  imported, so this board never depends on the module that owns it. */
    async openApprovals() {
        try {
            await this.action.doAction(
                "pb_approval_config.action_pb_approval_inbox");
        } catch {
            this.notification.add(
                _t("Approvals are not available on this server."),
                { type: "warning" });
        }
    }

    // ---- reject: an in-card confirm, never a native dialog ----
    // LEARN REFRESH step 6: the confirm asks "Why?" and will not reject
    // without an answer; the reason rides the context (pb_reject_note) and is
    // kept on the run, shown in the Rejected list and on the run form.
    askReject(b) {
        this.state.rejectNote = "";
        this.state.confirming = b.id;
    }
    cancelReject() { this.state.confirming = 0; this.state.rejectNote = ""; }
    get rejectNoteOk() { return !!(this.state.rejectNote || "").trim(); }
    onRejectKey(ev, b) {
        if (ev.key === "Escape") { ev.preventDefault(); this.cancelReject(); }
        else if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey)) {
            ev.preventDefault(); this.confirmReject(b);
        }
    }
    confirmReject(b) {
        const note = (this.state.rejectNote || "").trim();
        if (!note) { this.rejectWhy.el && this.rejectWhy.el.focus(); return; }
        this.state.confirming = 0;
        this.state.rejectNote = "";
        this._run("action_payslip_run_cancel", b.id, _t("Pay run rejected"),
                  { pb_reject_note: note });
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
