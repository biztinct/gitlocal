/** @odoo-module **/
/**
 * `pb_contractlife_board` — the Contracts lens on the Lifecycle hub.
 *
 * Journeys answers "what is running", New joiners "who is arriving", Exits
 * "who is leaving", Probation "who is still being decided about". This one
 * answers the question nobody asks until it is too late: WHOSE AGREEMENT RUNS
 * OUT, AND HAS ANYBODY DECIDED.
 *
 * THE COUNTDOWN IS THE HERO. Every row carries the number of days left and the
 * words for it ("in 42 days", "ends tomorrow"), and the board is sorted by it,
 * so the page reads top to bottom as an order of work rather than as a table
 * somebody has to sort.
 *
 * THE DECISION DRAWER IS THE OTHER HALF. Three buttons, and above each one the
 * server's own list of exactly what pressing it does to somebody's employment,
 * their contract and their inbox. That list comes from `decision_preview` on
 * the server, because a second opinion written in JavaScript would only ever
 * disagree with the one that counts.
 *
 * NO WAGE ON THIS BOARD, ON PURPOSE. A screen that lists what everybody earns
 * is a screen nobody can leave open. The number appears once, inside the
 * confirm summary, at the moment somebody is about to agree to it.
 *
 * WHAT THIS FILE DELIBERATELY DOES NOT DO: decide who may change anything.
 * `pb.contractlife._require_write()`, `pb.contract.review._require_manager()`
 * and the approval chain are the boundary; `state.canWrite` only decides
 * whether a control is OFFERED, because an offer the server would refuse is
 * worse than no offer.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

/** The three choices, in the order a person weighs them. */
const CHOICES = ["convert", "extend", "terminate"];

const CHOICE_TITLE = {
    convert: _t("Make it permanent"),
    extend: _t("Extend it"),
    terminate: _t("Let it end"),
};

const CHOICE_BLURB = {
    convert: _t("Their colleagues are asked, and if that goes well a contract with no end date is prepared."),
    extend: _t("Write down why, their manager agrees it, and a new contract on the same terms is prepared."),
    terminate: _t("The contract runs to its date and stops. Their leaving checklist opens."),
};

const CHOICE_ICON = { convert: "award", extend: "rotate", terminate: "powerOff" };

export class PbContractLifeBoard extends Component {
    static template = "pb_contract_lifecycle.PbContractLifeBoard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.choices = CHOICES;

        this.state = useState({
            loaded: false,
            allowed: true,
            canWrite: false,
            autoOn: false,
            wouldRaise: 0,
            leadDays: 60,
            defaultMonths: 12,
            kpis: {},
            rows: [],
            kinds: [],
            departments: [],
            months: [],
            states: [],
            capped: false,

            // filters
            q: "",
            kind: "all",
            dept: "all",
            month: "all",
            reviewState: "all",
            attentionOnly: false,

            // the open contract
            drawer: null,
            drawerBusy: false,

            // one dialog at a time, each one plain state
            deciding: null,
            typing: null,
        });

        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------------ read
    async load() {
        try {
            const d = await this.orm.call("pb.contractlife", "get_board", []);
            Object.assign(this.state, {
                allowed: d.allowed,
                canWrite: d.can_write,
                autoOn: !!d.auto_on,
                wouldRaise: d.would_raise || 0,
                leadDays: d.lead_days || 60,
                defaultMonths: d.default_months || 12,
                kpis: d.kpis || {},
                rows: d.rows || [],
                kinds: d.kinds || [],
                departments: d.departments || [],
                months: d.months || [],
                states: d.states || [],
                capped: !!d.capped,
                loaded: true,
            });
        } catch (e) {
            // Reported, never swallowed into a decoration.
            console.warn("pb_contract_lifecycle: could not read the board", e);
            this.state.loaded = true;
            this.state.allowed = false;
        }
    }

    async refresh() {
        this.state.loaded = false;
        await this.load();
        if (this.state.drawer) {
            await this.openContract(this.state.drawer.row.id);
        }
    }

    // --------------------------------------------------------------- filters
    get visibleRows() {
        const q = (this.state.q || "").trim().toLowerCase();
        return this.state.rows.filter((r) => {
            if (this.state.kind !== "all" && r.kind_label !== this.state.kind) {
                return false;
            }
            if (this.state.dept !== "all" && r.dept !== this.state.dept) {
                return false;
            }
            if (this.state.month !== "all" && r.end_month !== this.state.month) {
                return false;
            }
            if (this.state.reviewState !== "all"
                && r.review_label !== this.state.reviewState) {
                return false;
            }
            if (this.state.attentionOnly && !this.needsAttention(r)) {
                return false;
            }
            if (!q) { return true; }
            return (r.employee + " " + (r.job || "") + " " + (r.dept || "")
                + " " + (r.contract_name || "")).toLowerCase().includes(q);
        });
    }

    /** "Somebody has to do something about this one" — the one filter that matters. */
    needsAttention(row) {
        return !!(row.urgent || row.needs_decision
            || row.review_state === "lapsed"
            || (row.non_permanent && row.days === null));
    }

    get hasFilters() {
        return this.state.q || this.state.kind !== "all"
            || this.state.dept !== "all" || this.state.month !== "all"
            || this.state.reviewState !== "all" || this.state.attentionOnly;
    }

    clearFilters() {
        Object.assign(this.state, {
            q: "", kind: "all", dept: "all", month: "all", reviewState: "all",
            attentionOnly: false,
        });
    }

    onSearch(ev) { this.state.q = ev.target.value; }
    setKind(id) { this.state.kind = this.state.kind === id ? "all" : id; }
    setDept(id) { this.state.dept = this.state.dept === id ? "all" : id; }
    setMonth(id) { this.state.month = this.state.month === id ? "all" : id; }
    setReviewState(id) {
        this.state.reviewState = this.state.reviewState === id ? "all" : id;
    }
    toggleAttention() { this.state.attentionOnly = !this.state.attentionOnly; }

    // ------------------------------------------------------------ formatting
    day(value) {
        if (!value) { return "—"; }
        try {
            const d = new Date(value + "T00:00:00");
            return d.toLocaleDateString(undefined,
                { day: "numeric", month: "short", year: "numeric" });
        } catch (e) { return value; }
    }

    monthLabel(value) {
        if (!value) { return "—"; }
        try {
            const d = new Date(value + "-01T00:00:00");
            return d.toLocaleDateString(undefined,
                { month: "long", year: "numeric" });
        } catch (e) { return value; }
    }

    choiceTitle(kind) { return CHOICE_TITLE[kind] || kind; }
    choiceBlurb(kind) { return CHOICE_BLURB[kind] || ""; }
    choiceIcon(kind) { return CHOICE_ICON[kind] || "check"; }

    /** The countdown chip's tone. A colour AND a word, never a colour alone. */
    countdownCls(row) {
        if (row.days === null) { return "muted"; }
        if (row.days < 0) { return "err"; }
        if (row.urgent) { return "err"; }
        if (row.days <= this.state.leadDays) { return "warn"; }
        return "ok";
    }

    // --------------------------------------------------------------- plumbing
    fail(e) {
        const msg = (e && e.data && e.data.message) || (e && e.message)
            || _t("That did not work. Try again in a moment.");
        this.notif.add(msg, { type: "danger" });
    }

    async call(method, args, okMessage) {
        try {
            const res = await this.orm.call("pb.contractlife", method, args);
            if (okMessage) { this.notif.add(okMessage, { type: "success" }); }
            return res === undefined ? true : res;
        } catch (e) {
            this.fail(e);
            return false;
        }
    }

    // ------------------------------------------------------------- the drawer
    async openContract(contractId) {
        this.state.drawerBusy = true;
        try {
            this.state.drawer = await this.orm.call(
                "pb.contractlife", "get_contract", [contractId]);
        } catch (e) {
            this.fail(e);
            this.state.drawer = null;
        } finally {
            this.state.drawerBusy = false;
        }
    }

    closeDrawer() { this.state.drawer = null; }

    async raiseDecision(row) {
        const res = await this.call("raise_decision", [row.id],
            _t("Raised. Their manager and the HR team have been asked to choose."));
        if (res) { await this.refresh(); }
    }

    // =====================================================================
    //  THE DECISION DIALOG
    // =====================================================================
    /** Open the dialog on one choice, with the server's own consequence list. */
    async askDecide(choice) {
        const d = this.state.drawer;
        if (!d || !d.review_id) { return; }
        this.state.deciding = {
            reviewId: d.review_id,
            who: d.row.employee,
            choice,
            reason: "",
            months: this.state.defaultMonths,
            preview: (d.previews && d.previews[choice]) || null,
            terms: d.terms || {},
            busy: false,
        };
        // Re-asked with the month count for an extension, because the dates in
        // the consequence copy depend on it.
        if (choice === "extend") { await this.refreshPreview(); }
    }

    async refreshPreview() {
        const v = this.state.deciding;
        if (!v) { return; }
        v.busy = true;
        try {
            v.preview = await this.orm.call(
                "pb.contractlife", "decision_preview",
                [v.reviewId, v.choice, v.months]);
        } catch (e) {
            this.fail(e);
        } finally {
            if (this.state.deciding) { this.state.deciding.busy = false; }
        }
    }

    cancelDecide() { this.state.deciding = null; }
    onReason(ev) { this.state.deciding.reason = ev.target.value; }

    onMonths(ev) {
        const n = parseInt(ev.target.value, 10);
        this.state.deciding.months = isNaN(n) ? 1 : Math.max(1, Math.min(n, 60));
        clearTimeout(this._monthTimer);
        this._monthTimer = setTimeout(() => this.refreshPreview(), 300);
    }

    get decideBlocked() {
        const v = this.state.deciding;
        if (!v) { return true; }
        if (v.preview && v.preview.blocked && v.preview.blocked.length) {
            return true;
        }
        if (v.choice === "extend" && !(v.reason || "").trim()) { return true; }
        return false;
    }

    /** The sentence under the reason box — ONE expression (R34). */
    get reasonHint() {
        const v = this.state.deciding;
        if (!v || v.choice !== "extend") { return ""; }
        return (v.reason || "").trim()
            ? _t("Good. Their manager reads this before agreeing.")
            : _t("Write down why before you can ask. In a year somebody will read this before agreeing the next one.");
    }

    async confirmDecide() {
        const v = this.state.deciding;
        if (!v || v.busy || this.decideBlocked) { return; }
        v.busy = true;
        let res = false;
        if (v.choice === "terminate") {
            res = await this.call("decide_terminate", [v.reviewId, false]);
            if (res) {
                this.notif.add(
                    _t("Recorded. Their leaving checklist is open, dated the last day of the contract."),
                    { type: "success" });
            }
        } else if (v.choice === "extend") {
            res = await this.call("request_extension",
                [v.reviewId, v.reason, v.months]);
            if (res) {
                this.notif.add(
                    _t("Asked. Their manager has until %s to agree it.",
                       res.approve_by || ""),
                    { type: "success" });
            }
        } else {
            res = await this.call("request_conversion", [v.reviewId]);
            if (res) {
                this.notif.add(
                    _t("The evaluation is open and their manager has been asked to name three to five colleagues."),
                    { type: "success" });
            }
        }
        if (res) {
            this.state.deciding = null;
            await this.refresh();
        } else if (this.state.deciding) {
            this.state.deciding.busy = false;
        }
    }

    // =====================================================================
    //  THE EXTENSION, FROM THE MANAGER'S SIDE
    // =====================================================================
    async approveExtension() {
        const d = this.state.drawer;
        if (!d || !d.extension) { return; }
        const ok = await this.call("approve_extension", [d.extension.id, false]);
        if (ok) {
            this.notif.add(
                _t("Agreed. A new contract has been prepared on the same terms, starting the day after this one ends."),
                { type: "success" });
            await this.refresh();
        }
    }

    async refuseExtension() {
        const d = this.state.drawer;
        if (!d || !d.extension) { return; }
        const ok = await this.call("refuse_extension", [d.extension.id, false]);
        if (ok) {
            this.notif.add(
                _t("Turned down. Nothing was created and the choice is back on this contract."),
                { type: "success" });
            await this.refresh();
        }
    }

    // =====================================================================
    //  TYPING SOMEBODY BY HAND
    // =====================================================================
    askType(row) {
        this.state.typing = {
            employeeId: row.employee_id,
            who: row.employee,
            kind: row.kind || "employee",
            options: (this.state.drawer && this.state.drawer.kinds) || [],
            busy: false,
        };
    }

    cancelType() { this.state.typing = null; }
    pickType(kind) { this.state.typing.kind = kind; }

    async saveType() {
        const t = this.state.typing;
        if (!t || t.busy) { return; }
        t.busy = true;
        const res = await this.call("set_employment_type", [t.employeeId, t.kind]);
        if (res) {
            this.state.typing = null;
            this.notif.add(_t("Recorded as %s.", res.label || ""),
                           { type: "success" });
            await this.refresh();
        } else if (this.state.typing) {
            this.state.typing.busy = false;
        }
    }

    // =====================================================================
    //  THE NIGHTLY WORK, BY HAND
    // =====================================================================
    async runAutomation() {
        const res = await this.call("run_automation", []);
        if (res) {
            const n = (c, one, many) => c + " " + (c === 1 ? one : many);
            this.notif.add(
                _t("%(raised)s raised, %(nudges)s nudged, %(lapsed)s marked as ended undecided.",
                   { raised: n(res.decisions || 0, _t("decision"), _t("decisions")),
                     nudges: n(res.nudges || 0, _t("reminder"), _t("reminders")),
                     lapsed: n(res.lapsed || 0, _t("contract"), _t("contracts")) }),
                { type: "success" });
            await this.refresh();
        }
    }

    // ------------------------------------------------------------- the doors
    async openContractRecord(row) {
        const act = await this.call("open_contract_action", [row.id]);
        if (act) { this.action.doAction(act); }
    }

    async openNewContract(contractId) {
        const act = await this.call("open_contract_action", [contractId]);
        if (act) { this.action.doAction(act); }
    }

    async openEmployee(row) {
        if (!row.employee_id) { return; }
        const act = await this.call("open_employee_action", [row.employee_id]);
        if (act) { this.action.doAction(act); }
    }

    async openReview(reviewId) {
        if (!reviewId) { return; }
        const act = await this.call("open_review_action", [reviewId]);
        if (act) { this.action.doAction(act); }
    }

    async openEvaluation(evaluationId) {
        if (!evaluationId) { return; }
        const act = await this.call("open_evaluation_action", [evaluationId]);
        if (act) { this.action.doAction(act); }
    }

    async openLetter(letterId) {
        const act = await this.call("open_letter_action", [letterId]);
        if (act) { this.action.doAction(act); }
    }

    async openCase(caseId) {
        const act = await this.call("open_case_action", [caseId]);
        if (act) { this.action.doAction(act); }
    }

    openDecisions() {
        this.action.doAction("pb_contract_lifecycle.action_pb_contract_review");
    }

    openExtensions() {
        this.action.doAction("pb_contract_lifecycle.action_pb_contract_extension");
    }
}

registry.category("actions").add("pb_contractlife_board", PbContractLifeBoard);
