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
import { useFilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

/** What each stage of an award is called on this board. */
const FULFIL_LABEL = {
    pending: _t("Approved"),
    letter: _t("Letter sent"),
    queued: _t("In a pay run"),
    paid: _t("Paid"),
};

const PAGE = 60;
// What each figure on the numbers line means as a filter: the same filters as
// the built-in views where one exists, so pressing a figure lights its tab.
const GLANCE_FILTERS = {
    submitted: { where: ["submitted"] },
    to_queue: { where: ["agreed"], month: { preset: "this_month" } },
    queued: { where: ["queued"] },
    paid_mtd: { where: ["paid"], month: { preset: "this_month" } },
    refused: { where: ["refused"] },
};

export class PbIncentivesBoard extends Component {
    static template = "pb_comp_ben.PbIncentivesBoard";
    static components = { PbFilterLayout };
    static props = ["*"];

    // A literal in a template expression is never extracted (step 6).
    get stepsLabel() { return _t("Where every award is"); }
    get searchLabel() { return _t("Find a person or a reason…"); }

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
            kpis: {},
            total: 0,
            runs: [],
            kinds: [],
            states: [],
            code: "",
            lettersOn: false,

            // the table, one page at a time for the filter panel's state
            rows: [],
            listTotal: 0,
            listLoaded: false,
            listError: false,
            loadingMore: false,
            stepCounts: {},

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

        // The shared filter panel (pb_filter_kit, FILTER W1): it owns the
        // filters, the counts and the views; this screen loads one page of
        // awards for kit.query. A reader this board refuses is refused by the
        // server too, and the panel stays out of the way.
        this.kit = useFilterKit({
            model: "pb.incentives",
            noun: _t("awards"),
            onChange: () => this.loadPage(),
        });
        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    /** The head: access, the numbers line, the runs and kinds. */
    async load() {
        try {
            const data = await this.orm.call("pb.incentives", "get_board", []);
            Object.assign(this.state, {
                allowed: data.allowed,
                why: data.why || "",
                canWrite: data.can_write,
                canApprove: data.can_approve,
                kpis: data.kpis || {},
                total: data.total || 0,
                runs: data.runs || [],
                kinds: data.kinds || [],
                states: data.states || [],
                code: data.code || "",
                lettersOn: data.letters_on,
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

    /** One page of awards for the panel's current filters. */
    async loadPage({ more = false } = {}) {
        if (this.kit.refusal) {
            this.state.listLoaded = true;
            return;
        }
        const q = this.kit.query;
        const offset = more ? this.state.rows.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call("pb.incentives", "get_awards_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.rows = more ? [...this.state.rows, ...d.rows] : d.rows;
            this.state.listTotal = d.total;
            if (d.steps) { this.state.stepCounts = d.steps; }
            this.state.listLoaded = true;
            this.state.listError = false;
        } catch (e) {
            if (!this.kit.isCurrent(q.seq)) { return; }
            console.error("pb_comp_ben: the awards could not load", e);
            if (!more) {
                this.state.listError = true;
                this.state.listLoaded = true;
            }
            this.notif.add(_t("The awards could not load. Check your connection, then press Try again."),
                           { type: "warning" });
        } finally {
            this.state.loadingMore = false;
        }
    }
    loadMore() {
        if (!this.state.loadingMore) { this.loadPage({ more: true }); }
    }
    retry() {
        this.state.listError = false;
        this.state.listLoaded = false;
        this.kit.refresh();
    }
    get hasMore() { return this.state.rows.length < this.state.listTotal; }
    get nextPage() { return Math.min(PAGE, this.state.listTotal - this.state.rows.length); }
    fmtInt(n) { return Number(n || 0).toLocaleString("en-US"); }

    /** Read the board again in place: the numbers, the page and the counts.
     * The filters stay as they are. */
    async refresh() { await Promise.all([this.load(), this.kit.refresh()]); }

    // ------------------------------------------------------ the quiet board
    //
    // Five steps, one per place an award can be. An award is at EXACTLY one
    // step (the server's WHERE_DOMAINS), so the counts add up to every live
    // award; one that was not approved is an outcome at no step. The counts
    // follow the filters (each step against every OTHER filter).
    get stepDefs() {
        return [
            { key: "draft", title: _t("Being prepared") },
            { key: "submitted", title: _t("Waiting for approval") },
            { key: "agreed", title: _t("Agreed, not in a run") },
            { key: "queued", title: _t("In a pay run") },
            { key: "paid", title: _t("Paid") },
        ];
    }

    _awardsLabel(n) { return n === 1 ? _t("1 award") : _t("%s awards", this.fmtInt(n)); }

    get steps() {
        const counts = this.state.stepCounts || {};
        return this.stepDefs.map((st, i) => {
            const count = counts[st.key] || 0;
            let flag = "";
            if (st.key === "submitted" && count) {
                flag = count === 1 ? _t("1 waiting for a sign-off") : _t("%s waiting for a sign-off", count);
            }
            return {
                ...st,
                n: String(i + 1).padStart(2, "0"),
                count,
                countLabel: this._awardsLabel(count),
                sub: "", flag, flagTone: "",
                on: this.kit.loaded && this.kit.isOn("where", st.key),
            };
        });
    }

    /** A step pressed: list that step. Pressed again: back to the start view
     * when it was the only filter, otherwise only that step comes off. */
    pickStep(key) {
        const kit = this.kit;
        if (kit.isOn("where", key) && !kit.isExactly({ where: [key] })) {
            kit.toggle("where", key);
            return;
        }
        kit.toggleFilters({ where: [key] });
    }

    get glance() {
        const k = this.state.kpis || {};
        const tone = (v, t) => (v ? t : "");
        const pick = (id) => () => this.kit.toggleFilters(GLANCE_FILTERS[id]);
        return [
            { key: "submitted", n: k.waiting || 0, label: _t("waiting for a decision"), tone: tone(k.waiting, "amber"), run: pick("submitted") },
            { key: "to_queue", n: k.to_queue || 0, label: _t("agreed, not in a run"), tone: tone(k.to_queue, "amber"), run: pick("to_queue") },
            { key: "queued", n: k.queued || 0, label: _t("in a pay run"), tone: "", run: pick("queued") },
            { key: "paid_mtd", n: k.paid_mtd || 0, label: _t("paid this month"), tone: tone(k.paid_mtd, "green"), run: pick("paid_mtd") },
            { key: "refused", n: k.refused || 0, label: _t("not approved"), tone: "", run: pick("refused") },
        ];
    }

    /** Which figure is lit: the one whose filters are exactly what is on. */
    get glanceOn() {
        if (!this.kit.loaded) { return ""; }
        for (const [key, f] of Object.entries(GLANCE_FILTERS)) {
            if (this.kit.isExactly(f)) { return key; }
        }
        return "";
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
            await this.refresh();
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
            await this.refresh();
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
            await this.refresh();
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
