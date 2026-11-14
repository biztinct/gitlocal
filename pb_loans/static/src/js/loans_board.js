/** @odoo-module **/
/**
 * `pb_loans_board` — the Loans lens of the Payroll hub (and its own page).
 *
 * THE HERO IS THE LIVE PLAN. In "New loan" the instalments appear month by
 * month as the amount is typed: how much, from which pay run, until when, and
 * what the last one is. Nobody has to work out a schedule in their head.
 *
 * FIVE PLACES A LOAN CAN BE: being prepared, waiting for approval, running,
 * paused, closed. A loan is at exactly one, so the steps add up.
 *
 * R1 — no `t-as` variable is named lt/gt/lte/gte/and/or/not/in (UPDATES G60).
 * R2 — icons are the filter kit's CACHED markup (`pbfIcon`): a NEW markup()
 *      per render re-inserts the SVG on every patch (OWL markup flicker).
 * R3 — every sentence a person reads is a `_t()` literal or comes from the
 *      server already translated.
 */
import { Component, useState, onWillStart, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { useFilterKit, pbfIcon } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

const PAGE = 60;
const GLANCE_FILTERS = {
    waiting: { where: ["waiting"] },
    running: { where: ["running"] },
    paused: { where: ["paused"] },
    closed: { where: ["closed"] },
};

function blankDraft(month) {
    return {
        employee_id: 0, employee: "", currency_id: 0, currency: "", leaving: false,
        kind: "loan", amount: "", first_month: month, plan_mode: "amount",
        plan_amount: "", plan_months: "", on_leaving: "take_rest", reason: "",
    };
}

export class PbLoansBoard extends Component {
    static template = "pb_loans.PbLoansBoard";
    static components = { PbFilterLayout };
    static props = ["*"];

    get stepsLabel() { return _t("Where every loan is"); }
    get searchLabel() { return _t("Find a person, a reference or a reason…"); }

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.state = useState({
            loaded: false, allowed: true, why: "",
            canSetUp: false, kpis: {}, total: 0, kinds: [], leaving: [],
            setup: { schemes: [], missing: 0 }, notes: [],
            nextMonth: "",
            rows: [], listTotal: 0, listLoaded: false, listError: false,
            loadingMore: false, stepCounts: {},
            // the drawer
            loan: null, loanBusy: false, act: null,
            // new loan
            creating: false, draft: blankDraft(""), people: [], searching: false,
            preview: null, busy: false,
            // set up
            setupOpen: false,
        });
        this.kit = useFilterKit({
            model: "pb.loans",
            noun: _t("loans"),
            onChange: () => this.loadPage(),
        });
        this._previewSeq = 0;
        useExternalListener(window, "keydown", (ev) => this.onKey(ev));
        onWillStart(async () => { await this.load(); });
    }

    icon(name, size = 16) { return pbfIcon(name, size); }

    // ------------------------------------------------------------ loading
    async load() {
        try {
            const d = await this.orm.call("pb.loans", "get_board", []);
            Object.assign(this.state, {
                allowed: d.allowed !== false,
                why: d.why || "",
                canSetUp: !!d.can_set_up,
                kpis: d.kpis || {},
                total: d.total || 0,
                kinds: d.kinds || [],
                leaving: d.leaving || [],
                setup: d.setup || { schemes: [], missing: 0 },
                notes: d.notes || [],
                nextMonth: d.next_month || "",
            });
        } catch (e) {
            console.warn("pb_loans: the board could not be read", e);
            this.state.allowed = false;
            this.state.why = _t("The loans could not be read just now.");
        } finally {
            this.state.loaded = true;
        }
    }

    async loadPage({ more = false } = {}) {
        if (this.kit.refusal) {
            this.state.listLoaded = true;
            return;
        }
        const q = this.kit.query;
        const offset = more ? this.state.rows.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call("pb.loans", "get_loans_page", [], {
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
            console.error("pb_loans: the loans could not load", e);
            if (!more) {
                this.state.listError = true;
                this.state.listLoaded = true;
            }
            this.notif.add(_t("The loans could not load. Check your connection, then press Try again."),
                           { type: "warning" });
        } finally {
            this.state.loadingMore = false;
        }
    }
    loadMore() { if (!this.state.loadingMore) { this.loadPage({ more: true }); } }
    retry() {
        this.state.listError = false;
        this.state.listLoaded = false;
        this.kit.refresh();
    }
    get hasMore() { return this.state.rows.length < this.state.listTotal; }
    get nextPage() { return Math.min(PAGE, this.state.listTotal - this.state.rows.length); }
    fmtInt(n) { return Number(n || 0).toLocaleString(); }
    async refresh() { await Promise.all([this.load(), this.kit.refresh()]); }

    // --------------------------------------------------------- the quiet board
    get stepDefs() {
        return [
            { key: "draft", title: _t("Being prepared") },
            { key: "waiting", title: _t("Waiting for approval") },
            { key: "running", title: _t("Running") },
            { key: "paused", title: _t("Paused") },
            { key: "closed", title: _t("Closed") },
        ];
    }
    _loansLabel(n) { return n === 1 ? _t("1 loan") : _t("%s loans", this.fmtInt(n)); }
    get steps() {
        const counts = this.state.stepCounts || {};
        return this.stepDefs.map((st, i) => {
            const count = counts[st.key] || 0;
            let flag = "";
            if (st.key === "waiting" && count) {
                flag = count === 1 ? _t("1 waiting for a sign-off") : _t("%s waiting for a sign-off", count);
            }
            return {
                ...st, n: String(i + 1).padStart(2, "0"), count,
                countLabel: this._loansLabel(count), sub: "", flag, flagTone: "",
                on: this.kit.loaded && this.kit.isOn("where", st.key),
            };
        });
    }
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
        const out = [
            { key: "waiting", n: k.waiting || 0, label: _t("waiting for approval"), tone: tone(k.waiting, "amber"), run: pick("waiting") },
            { key: "running", n: k.running || 0, label: _t("being repaid"), tone: "", run: pick("running") },
            { key: "paused", n: k.paused || 0, label: _t("paused"), tone: tone(k.paused, "amber"), run: pick("paused") },
            { key: "closed", n: k.closed_mtd || 0, label: _t("repaid in full this month"), tone: tone(k.closed_mtd, "green"), run: pick("closed") },
        ];
        if (k.left_label) {
            out.push({ key: "left", n: k.left_label, label: _t("left to repay"), tone: "", run: null, zero: false });
        }
        return out;
    }
    get glanceOn() {
        if (!this.kit.loaded) { return ""; }
        for (const [key, f] of Object.entries(GLANCE_FILTERS)) {
            if (this.kit.isExactly(f)) { return key; }
        }
        return "";
    }

    // ------------------------------------------------------------ the drawer
    async openLoan(row) {
        this.state.act = null;
        this.state.loanBusy = true;
        if (!this.state.loan || this.state.loan.id !== row.id) {
            this.state.loan = { ...row, loading: true };
        }
        try {
            this.state.loan = await this.orm.call("pb.loans", "get_loan", [row.id]);
        } catch (e) {
            this.notif.add(this._msg(e, _t("This loan could not be opened.")), { type: "danger" });
            this.state.loan = null;
        } finally {
            this.state.loanBusy = false;
        }
    }
    closeLoan() { this.state.loan = null; this.state.act = null; }

    /** Open the small form under the buttons for a move that needs words. */
    startAct(verb) {
        const loan = this.state.loan;
        const amount = verb === "record" ? "" : "";
        this.state.act = { verb, reason: "", amount, reference: "" };
        if (verb === "settle" && loan) { this.state.act.amount = loan.available_label; }
    }
    cancelAct() { this.state.act = null; }
    onAct(field, ev) { this.state.act[field] = ev.target.value; }

    get actTitle() {
        const verb = this.state.act && this.state.act.verb;
        return {
            pause: _t("Pause the repayments"),
            resume: _t("Start the repayments again"),
            record: _t("Record a repayment made outside payroll"),
            settle: _t("Settle now"),
            cancel: _t("Cancel this loan"),
            refuse: _t("Do not approve"),
        }[verb] || "";
    }
    get actHelp() {
        const verb = this.state.act && this.state.act.verb;
        const loan = this.state.loan || {};
        return {
            pause: _t("No instalment is taken until it is resumed. The plan moves on by a month for each month missed."),
            resume: _t("The next regular pay run takes an instalment again."),
            record: _t("Cash or a bank transfer the person paid back. It reduces what is left to repay straight away."),
            settle: _t("Records everything still owed (%s) as paid back outside payroll, and closes the loan.", loan.available_label || ""),
            cancel: _t("Nothing more is taken from pay. What was already paid back stays recorded."),
            refuse: _t("The loan is turned down and nothing is taken from pay."),
        }[verb] || "";
    }
    get actButton() {
        const verb = this.state.act && this.state.act.verb;
        return {
            pause: _t("Pause"), resume: _t("Resume"), record: _t("Record it"),
            settle: _t("Settle now"), cancel: _t("Cancel the loan"), refuse: _t("Do not approve"),
        }[verb] || _t("Confirm");
    }

    async doAct() {
        const act = this.state.act;
        if (!act) { return; }
        if (["pause", "cancel", "record", "settle"].includes(act.verb) && !act.reason.trim()) {
            this.notif.add(_t("Say why, in a few words."), { type: "warning" });
            return;
        }
        let amount = null;
        if (act.verb === "record") {
            amount = parseFloat(String(act.amount).replace(/[^0-9.\-]/g, ""));
            if (!(amount > 0)) {
                this.notif.add(_t("Type the amount that was paid back."), { type: "warning" });
                return;
            }
        }
        await this.move(act.verb, { reason: act.reason, amount, reference: act.reference });
    }

    async move(verb, { reason = null, amount = null, reference = null } = {}) {
        const loan = this.state.loan;
        if (!loan) { return; }
        this.state.loanBusy = true;
        try {
            const res = await this.orm.call("pb.loans", "move", [loan.id, verb], {
                reason, amount, reference,
            });
            this.state.act = null;
            this.notif.add(res.msg || _t("Done."), { type: "success" });
            if (res.deleted) {
                this.state.loan = null;
            } else {
                await this.openLoan({ id: loan.id });
            }
            await this.refresh();
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be done.")), { type: "danger" });
        } finally {
            this.state.loanBusy = false;
        }
    }

    // ----------------------------------------------------------- new loan
    openCreate() {
        this.state.draft = blankDraft(this.state.nextMonth || "");
        this.state.people = [];
        this.state.preview = null;
        this.state.creating = true;
    }
    closeCreate() { this.state.creating = false; }
    onDraft(field, ev) {
        let value = ev.target.value;
        if (field === "first_month" && value && value.length === 7) { value = value + "-01"; }
        this.state.draft[field] = value;
        this.updatePreview();
    }
    setDraft(field, value) {
        this.state.draft[field] = value;
        this.updatePreview();
    }
    get draftMonth() {
        const m = this.state.draft.first_month || "";
        return m ? m.slice(0, 7) : "";
    }
    async onPersonSearch(ev) {
        const term = ev.target.value;
        this.state.draft.employee = term;
        this.state.draft.employee_id = 0;
        if (!term || term.length < 2) { this.state.people = []; return; }
        this.state.searching = true;
        try {
            this.state.people = await this.orm.call("pb.loans", "employee_options", [term]);
        } catch {
            this.state.people = [];
        } finally {
            this.state.searching = false;
        }
    }
    pickPerson(person) {
        Object.assign(this.state.draft, {
            employee_id: person.id, employee: person.name, currency_id: person.currency_id,
            currency: person.currency, leaving: person.leaving,
        });
        this.state.people = [];
        this.updatePreview();
    }
    async updatePreview() {
        const d = this.state.draft;
        const seq = ++this._previewSeq;
        if (!parseFloat(d.amount)) { this.state.preview = null; return; }
        try {
            const p = await this.orm.call("pb.loans", "plan_preview", [{
                amount: d.amount, plan_mode: d.plan_mode, plan_amount: d.plan_amount,
                plan_months: d.plan_months, first_month: d.first_month,
                currency_id: d.currency_id,
            }]);
            if (seq === this._previewSeq) { this.state.preview = p; }
        } catch {
            if (seq === this._previewSeq) { this.state.preview = null; }
        }
    }
    async confirmCreate(send) {
        const d = this.state.draft;
        if (!d.employee_id) { this.notif.add(_t("Pick who the loan is for."), { type: "warning" }); return; }
        if (!(parseFloat(d.amount) > 0)) { this.notif.add(_t("A loan needs an amount above zero."), { type: "warning" }); return; }
        if (!(this.state.preview && this.state.preview.ok)) {
            this.notif.add(_t("Say how much comes off each month, or over how many months."), { type: "warning" });
            return;
        }
        if (!d.reason.trim()) { this.notif.add(_t("Say what the loan is for, in a few words."), { type: "warning" }); return; }
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.loans", "create_loan", [{
                employee_id: d.employee_id, kind: d.kind, amount: d.amount,
                currency_id: d.currency_id, first_month: d.first_month,
                plan_mode: d.plan_mode, plan_amount: d.plan_amount, plan_months: d.plan_months,
                on_leaving: d.on_leaving, reason: d.reason,
            }], { send: !!send });
            this.state.creating = false;
            await this.refresh();
            this.notif.add(send
                ? (res.state === "running" ? _t("Loan approved. The next regular pay run takes the first instalment.")
                                           : _t("Loan sent for approval."))
                : _t("Loan saved. Send it for approval when you are ready."),
                { type: "success" });
            await this.openLoan({ id: res.id });
        } catch (e) {
            this.notif.add(this._msg(e, _t("The loan could not be saved.")), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------ set up
    openSetup() { this.state.setupOpen = true; }
    closeSetup() { this.state.setupOpen = false; }
    async pickItem(scheme, ev) {
        const ruleId = parseInt(ev.target.value || "0", 10) || 0;
        try {
            await this.orm.call("pb.loans", "set_loan_item", [scheme.id, ruleId]);
            this.notif.add(ruleId ? _t("Saved. Loan repayments go into that pay item from the next calculation.")
                                  : _t("Saved. This scheme takes no loan repayments."), { type: "success" });
            await this.load();
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be saved.")), { type: "danger" });
            await this.load();
        }
    }

    // ------------------------------------------------------------ plumbing
    onKey(ev) {
        if (ev.key !== "Escape") { return; }
        if (this.state.act) { this.state.act = null; return; }
        if (this.state.creating) { this.state.creating = false; return; }
        if (this.state.setupOpen) { this.state.setupOpen = false; return; }
        if (this.state.loan) { this.closeLoan(); }
    }
    barStyle(pct) { return `width: ${Math.max(0, Math.min(100, pct || 0))}%`; }
    _msg(e, fallback) {
        if (e && e.message && e.message.data && e.message.data.message) { return e.message.data.message; }
        if (e && e.data && e.data.message) { return e.data.message; }
        return fallback;
    }
}

registry.category("actions").add("pb_loans_board", PbLoansBoard);
