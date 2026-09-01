/** @odoo-module **/
/**
 * `pb_comp_ben_incentives` — the Awards lens on the Pay Run hub.
 *
 * THE HERO IS THE PREVIEW. "Queue this month" is the one control on this screen
 * that moves money, and it never does anything until somebody has read who gets
 * what, out of which pay run, and whether that run's pay scheme even has the pay
 * item the money would arrive under. The dialog IS the safety rail — the server
 * refuses the same things independently, but a refusal a person reads before
 * pressing is worth more than one they read after.
 *
 * FOUR NUMBERS, FOUR PLACES AN AWARD CAN BE STUCK: waiting for a decision,
 * decided but not in a run, in a run, paid. That is the whole board.
 *
 * R1 — no `t-as` variable is named lt/gt/lte/gte/and/or/not/in.
 * R2 — every sentence is one expression; JavaScript has no implicit string
 * concatenation and a stray one kills the whole backend bundle.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

/** What each stage of an award is called on this board. */
const FULFIL_LABEL = {
    pending: _t("Approved"),
    letter: _t("Letter sent"),
    queued: _t("In a pay run"),
    paid: _t("Paid"),
};

export class PbIncentivesBoard extends Component {
    static template = "pb_comp_ben.PbIncentivesBoard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.fulfilLabel = FULFIL_LABEL;

        this.state = useState({
            loaded: false,
            allowed: true,
            why: "",
            canWrite: false,
            canApprove: false,
            rows: [],
            kpis: {},
            runs: [],
            kinds: [],
            states: [],
            code: "",
            lettersOn: false,
            capped: false,

            // filters
            q: "",
            stateFilter: "all",
            kindFilter: "all",

            // dialogs
            creating: false,
            draft: { employee_id: 0, employee: "", kind: "bonus",
                     amount: "", period_month: "", reason: "" },
            people: [],
            searching: false,

            queueing: false,
            queueRun: 0,
            preview: null,
            busy: false,
        });

        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    async load() {
        try {
            const data = await this.orm.call("pb.incentives", "get_board", []);
            Object.assign(this.state, {
                allowed: data.allowed,
                why: data.why || "",
                canWrite: data.can_write,
                canApprove: data.can_approve,
                rows: data.rows || [],
                kpis: data.kpis || {},
                runs: data.runs || [],
                kinds: data.kinds || [],
                states: data.states || [],
                code: data.code || "",
                lettersOn: data.letters_on,
                capped: data.capped,
            });
            if (!this.state.queueRun && this.state.runs.length) {
                this.state.queueRun = this.state.runs[0].id;
            }
        } catch (e) {
            console.warn("pb_comp_ben: the awards board could not be read", e);
            this.state.allowed = false;
            this.state.why = _t("The awards could not be read just now.");
        } finally {
            this.state.loaded = true;
        }
    }

    async refresh() { await this.load(); }

    // ------------------------------------------------------------- filters
    get visibleRows() {
        const q = (this.state.q || "").trim().toLowerCase();
        return this.state.rows.filter((r) => {
            if (this.state.stateFilter !== "all"
                && r.state !== this.state.stateFilter) { return false; }
            if (this.state.kindFilter !== "all"
                && r.kind !== this.state.kindFilter) { return false; }
            if (!q) { return true; }
            return (r.employee || "").toLowerCase().includes(q)
                || (r.reason || "").toLowerCase().includes(q);
        });
    }

    onSearch(ev) { this.state.q = ev.target.value; }
    setStateFilter(key) { this.state.stateFilter = key; }
    setKindFilter(key) { this.state.kindFilter = key; }

    /** ONE expression, so the whitespace between the pieces survives (R34). */
    get countLine() {
        const shown = this.visibleRows.length;
        const total = this.state.rows.length;
        if (shown === total) {
            return total === 1 ? _t("1 award") : _t("%s awards", total);
        }
        return _t("%s of %s awards", shown, total);
    }

    // -------------------------------------------------------- the new award
    openCreate() {
        const now = new Date();
        const next = new Date(now.getFullYear(), now.getMonth() + 1, 1);
        this.state.draft = {
            employee_id: 0, employee: "", kind: "bonus", amount: "",
            period_month: next.toISOString().slice(0, 10), reason: "",
        };
        this.state.people = [];
        this.state.creating = true;
    }

    closeCreate() { this.state.creating = false; }

    onDraft(field, ev) { this.state.draft[field] = ev.target.value; }

    async onPersonSearch(ev) {
        const term = ev.target.value;
        this.state.draft.employee = term;
        this.state.draft.employee_id = 0;
        if (!term || term.length < 2) { this.state.people = []; return; }
        this.state.searching = true;
        try {
            this.state.people = await this.orm.call(
                "pb.incentives", "employee_options", [term]);
        } catch (e) {
            this.state.people = [];
        } finally {
            this.state.searching = false;
        }
    }

    pickPerson(person) {
        this.state.draft.employee_id = person.id;
        this.state.draft.employee = person.name;
        this.state.people = [];
    }

    async confirmCreate() {
        const d = this.state.draft;
        if (!d.employee_id) {
            this.notif.add(_t("Pick who the award is for."), { type: "warning" });
            return;
        }
        if (!parseFloat(d.amount)) {
            this.notif.add(_t("An award needs an amount above zero."),
                           { type: "warning" });
            return;
        }
        this.state.busy = true;
        try {
            await this.orm.call("pb.incentives", "create_award", [{
                employee_id: d.employee_id,
                kind: d.kind,
                amount: parseFloat(d.amount),
                period_month: d.period_month,
                reason: d.reason,
            }]);
            this.state.creating = false;
            await this.load();
            this.notif.add(_t("Award raised. Send it for approval when you are ready."),
                           { type: "success" });
        } catch (e) {
            this.notif.add(this._msg(e, _t("The award could not be raised.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------ the moves
    async move(row, method, ok) {
        this.state.busy = true;
        try {
            await this.orm.call("pb.incentives", method, [row.id]);
            await this.load();
            this.notif.add(ok, { type: "success" });
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be done.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    submitRow(row) {
        return this.move(row, "submit", _t("Sent for approval."));
    }

    approveRow(row) {
        return this.move(row, "approve", this.state.lettersOn
            ? _t("Approved. The award letter has been prepared and emailed.")
            : _t("Approved. The award letter is prepared and filed — emailing letters is switched off."));
    }

    refuseRow(row) {
        return this.move(row, "refuse", _t("Marked as not approved."));
    }

    letterRow(row) {
        return this.move(row, "make_letter", _t("The letter has been prepared again."));
    }

    // ------------------------------------------------------- queue this month
    async openQueue() {
        this.state.queueing = true;
        this.state.preview = null;
        await this.loadPreview();
    }

    closeQueue() { this.state.queueing = false; this.state.preview = null; }

    onRunPick(ev) {
        this.state.queueRun = parseInt(ev.target.value, 10);
        this.loadPreview();
    }

    async loadPreview() {
        if (!this.state.queueRun) { return; }
        this.state.busy = true;
        try {
            this.state.preview = await this.orm.call(
                "pb.incentives", "preview_queue", [this.state.queueRun]);
        } catch (e) {
            this.state.preview = { ok: false,
                                   problem: this._msg(e, _t("Nothing could be read.")),
                                   rows: [] };
        } finally {
            this.state.busy = false;
        }
    }

    async confirmQueue() {
        this.state.busy = true;
        try {
            const res = await this.orm.call(
                "pb.incentives", "confirm_queue", [this.state.queueRun]);
            this.state.queueing = false;
            await this.load();
            this.notif.add(res.msg || _t("Done."), { type: "success" });
        } catch (e) {
            this.notif.add(this._msg(e, _t("Nothing was put into the pay run.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    get selectedRun() {
        return this.state.runs.find((r) => r.id === this.state.queueRun) || null;
    }

    // ------------------------------------------------------------- plumbing
    _msg(e, fallback) {
        if (e && e.message && e.message.data && e.message.data.message) {
            return e.message.data.message;
        }
        if (e && e.data && e.data.message) { return e.data.message; }
        return fallback;
    }

    money(row) {
        const n = Number(row.amount || 0);
        return `${n.toLocaleString()} ${row.currency || ""}`.trim();
    }

    openAll() { this.action.doAction("pb_comp_ben.action_pb_incentive"); }
}

registry.category("actions").add("pb_comp_ben_incentives", PbIncentivesBoard);
