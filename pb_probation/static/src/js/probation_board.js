/** @odoo-module **/
/**
 * `pb_probation_board` — the Probation lens on the Lifecycle hub.
 *
 * The Journeys board answers "what is running", New joiners answers "who is
 * arriving" and Exits answers "who is leaving". This one answers the question
 * an HR coordinator asks on the first Monday of a month: WHOSE TRIAL PERIOD
 * ENDS SOON, and is anything in the way of deciding.
 *
 * THE STAGE RAIL IS THE HERO. Four dots on every card — colleagues chosen,
 * answers in, conversation had, decision made — so twenty people can be read
 * as one column each rather than twenty sentences. Everything else on the row
 * is either a number with a unit on it or a door to a screen that exists.
 *
 * THE VERDICT WIZARD IS THE OTHER HALF. Three steps, and the last one is not a
 * confirmation dialog: it is a plain-English list of exactly what pressing the
 * button will do to somebody's record, their contract and their inbox. The
 * server produces that list (`verdict_preview`), because a second opinion
 * written in JavaScript would only ever disagree with the one that counts.
 *
 * WHAT THIS FILE DELIBERATELY DOES NOT DO: decide who may change anything.
 * `pb.probation._require_write()` and `pb.probation.review._require_manager()`
 * are the boundary; `state.canWrite` only decides whether a control is OFFERED,
 * because an offer the server would refuse is worse than no offer (W29).
 */
import { Component, useState, onWillStart, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

/** The four stops the rail shows, in order. */
const STAGES = ["peers", "answers", "talk", "decision"];

/** What each stop is called.
 *
 * SHORT ENOUGH TO FIT. These four sit in a four-column grid on a card that can
 * be 340px wide, and a label that ellipses ("CONVERSATI…") is a label that has
 * stopped being a label. "Meeting" is the same thing said in seven characters;
 * the prose everywhere else in this module still calls it the conversation,
 * because there it has room to.
 */
const STAGE_LABEL = {
    peers: _t("Colleagues"),
    answers: _t("Answers"),
    talk: _t("Meeting"),
    decision: _t("Decision"),
};

/** Which review states have passed which stop. */
const STAGE_DONE = {
    peers: ["feedback", "consolidation", "one_on_one", "verdict", "closed"],
    answers: ["consolidation", "one_on_one", "verdict", "closed"],
    talk: ["verdict", "closed"],
    decision: ["closed"],
};

/** Which review state is sitting ON each stop. */
const STAGE_CURRENT = {
    peers: ["", "scheduled", "nomination"],
    answers: ["feedback"],
    talk: ["consolidation", "one_on_one"],
    decision: ["verdict"],
};

export class PbProbationBoard extends Component {
    static template = "pb_probation.PbProbationBoard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.stages = STAGES;

        this.state = useState({
            loaded: false,
            allowed: true,
            canWrite: false,
            autoOn: false,
            kpis: {},
            rows: [],
            countries: [],
            departments: [],
            states: [],
            capped: false,
            minNominees: 3,
            maxNominees: 5,

            // filters
            q: "",
            country: "all",
            dept: "all",
            reviewState: "all",
            attentionOnly: false,

            // the open person
            drawer: null,
            drawerBusy: false,

            // dialogs — one at a time, each one plain state
            nominating: null,
            verdicting: null,
            talking: null,
        });

        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    /** The consolidated report, as HTML rather than as its own source code.
     *
     * `t-out` escapes a PLAIN STRING and renders a `markup()` value raw — and
     * an Html field crossing JSON-RPC arrives as a plain string, so without
     * this the reader gets `<h4>How they were rated</h4>` on the screen
     * instead of a heading. Marking it safe is correct here and nowhere else:
     * every value inside it was `escape()`d by `_build_report()` on the way
     * in, so the only markup in the string is markup this codebase wrote.
     */
    report(html) { return markup(html || ""); }

    // ------------------------------------------------------------------ read
    async load() {
        try {
            const d = await this.orm.call("pb.probation", "get_board", []);
            Object.assign(this.state, {
                allowed: d.allowed,
                canWrite: d.can_write,
                autoOn: !!d.auto_on,
                kpis: d.kpis || {},
                rows: d.rows || [],
                countries: d.countries || [],
                departments: d.departments || [],
                states: d.states || [],
                capped: !!d.capped,
                minNominees: d.min_nominees || 3,
                maxNominees: d.max_nominees || 5,
                loaded: true,
            });
        } catch (e) {
            // Reported, never swallowed into a decoration (W40).
            console.warn("pb_probation: could not read the board", e);
            this.state.loaded = true;
            this.state.allowed = false;
        }
    }

    async refresh() {
        this.state.loaded = false;
        await this.load();
        if (this.state.drawer) {
            await this.openPerson(this.state.drawer.row.id);
        }
    }

    // --------------------------------------------------------------- filters
    get visibleRows() {
        const q = (this.state.q || "").trim().toLowerCase();
        return this.state.rows.filter((r) => {
            if (this.state.country !== "all" && r.country !== this.state.country) {
                return false;
            }
            if (this.state.dept !== "all" && r.dept !== this.state.dept) {
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
            return (r.employee + " " + (r.job || "") + " " + (r.dept || ""))
                .toLowerCase().includes(q);
        });
    }

    /** "Somebody has to do something about this one" — the one filter that matters. */
    needsAttention(row) {
        return !!(row.urgent
            || row.feedback_late
            || row.red_flags
            || !row.training_ok
            || row.review_state === "verdict"
            || (!row.review_state && row.days !== null && row.days <= 21));
    }

    get hasFilters() {
        return this.state.q || this.state.country !== "all"
            || this.state.dept !== "all" || this.state.reviewState !== "all"
            || this.state.attentionOnly;
    }

    clearFilters() {
        Object.assign(this.state, {
            q: "", country: "all", dept: "all", reviewState: "all",
            attentionOnly: false,
        });
    }

    onSearch(ev) { this.state.q = ev.target.value; }
    setCountry(id) { this.state.country = this.state.country === id ? "all" : id; }
    setDept(id) { this.state.dept = this.state.dept === id ? "all" : id; }
    setReviewState(id) {
        this.state.reviewState = this.state.reviewState === id ? "all" : id;
    }
    toggleAttention() { this.state.attentionOnly = !this.state.attentionOnly; }

    // ------------------------------------------------------------ the rail
    stageLabel(stage) { return STAGE_LABEL[stage] || stage; }

    stageCls(row, stage) {
        const st = row.review_state || "";
        if ((STAGE_DONE[stage] || []).includes(st)) { return "done"; }
        if ((STAGE_CURRENT[stage] || []).includes(st)) { return "now"; }
        return "todo";
    }

    /** The small number under a stop — "3 of 5", "2 chosen". */
    stageNote(row, stage) {
        if (stage === "peers") {
            return row.nominees ? row.nominees + " " + _t("chosen") : "";
        }
        if (stage === "answers") {
            return row.feedback_total
                ? row.feedback_in + " " + _t("of") + " " + row.feedback_total
                : "";
        }
        if (stage === "decision" && row.verdict_label) {
            return row.verdict_label;
        }
        return "";
    }

    // ------------------------------------------------------------ formatting
    day(value) {
        if (!value) { return "—"; }
        try {
            const d = new Date(value + "T00:00:00");
            return d.toLocaleDateString(undefined,
                { day: "numeric", month: "short" });
        } catch (e) { return value; }
    }

    /** The training chip, as a word and a tone. */
    trainingChip(row) {
        if (!row.training_total) {
            return { cls: "muted", text: _t("No course needed") };
        }
        if (row.training_ok) {
            return { cls: "ok", text: _t("Course finished") };
        }
        const n = row.training_pending.length;
        return {
            cls: "err",
            text: n === 1
                ? _t("1 course item outstanding")
                : n + " " + _t("course items outstanding"),
        };
    }

    // --------------------------------------------------------------- plumbing
    fail(e) {
        const msg = (e && e.data && e.data.message) || (e && e.message)
            || _t("That did not work. Try again in a moment.");
        this.notif.add(msg, { type: "danger" });
    }

    async call(method, args, okMessage) {
        try {
            const res = await this.orm.call("pb.probation", method, args);
            if (okMessage) { this.notif.add(okMessage, { type: "success" }); }
            return res === undefined ? true : res;
        } catch (e) {
            this.fail(e);
            return false;
        }
    }

    // ------------------------------------------------------------- the drawer
    async openPerson(employeeId) {
        this.state.drawerBusy = true;
        try {
            this.state.drawer = await this.orm.call(
                "pb.probation", "get_person", [employeeId]);
        } catch (e) {
            this.fail(e);
            this.state.drawer = null;
        } finally {
            this.state.drawerBusy = false;
        }
    }

    closeDrawer() { this.state.drawer = null; }

    // =====================================================================
    //  CHOOSING THE COLLEAGUES
    // =====================================================================
    async askNominate(row) {
        this.state.nominating = {
            employeeId: row.id,
            who: row.employee,
            term: "",
            options: [],
            chosen: [],
            busy: true,
        };
        await this.loadNominees();
    }

    async loadNominees() {
        const n = this.state.nominating;
        if (!n) { return; }
        n.busy = true;
        try {
            const options = await this.orm.call(
                "pb.probation", "nominee_options",
                [n.employeeId, n.term || false]);
            n.options = options || [];
        } catch (e) {
            this.fail(e);
            n.options = [];
        } finally {
            if (this.state.nominating) { this.state.nominating.busy = false; }
        }
    }

    onNomineeSearch(ev) {
        this.state.nominating.term = ev.target.value;
        clearTimeout(this._nomineeTimer);
        this._nomineeTimer = setTimeout(() => this.loadNominees(), 260);
    }

    isChosen(id) {
        const n = this.state.nominating;
        return !!(n && n.chosen.some((c) => c.id === id));
    }

    toggleNominee(option) {
        const n = this.state.nominating;
        if (!n) { return; }
        const at = n.chosen.findIndex((c) => c.id === option.id);
        if (at >= 0) {
            n.chosen.splice(at, 1);
            return;
        }
        if (n.chosen.length >= this.state.maxNominees) {
            this.notif.add(
                _t("That is already %s colleagues. Past five, people assume somebody else will answer and nobody does.",
                   this.state.maxNominees),
                { type: "warning" });
            return;
        }
        n.chosen.push({ id: option.id, name: option.name });
    }

    /** The sentence under the picker — ONE expression (R34). */
    get nomineeHint() {
        const n = this.state.nominating;
        if (!n) { return ""; }
        const short = this.state.minNominees - n.chosen.length;
        if (short > 0) {
            return short === 1
                ? _t("One more colleague and you can send the questions.")
                : _t("%s more colleagues and you can send the questions.", short);
        }
        return _t("%s chosen — ready to send.", n.chosen.length);
    }

    get canSendNominees() {
        const n = this.state.nominating;
        return !!(n && n.chosen.length >= this.state.minNominees
            && n.chosen.length <= this.state.maxNominees && !n.busy);
    }

    cancelNominate() { this.state.nominating = null; }

    async sendNominees() {
        const n = this.state.nominating;
        if (!n || !this.canSendNominees) { return; }
        n.busy = true;
        const res = await this.call("confirm_nominees",
                                    [n.employeeId, n.chosen.map((c) => c.id)]);
        if (res) {
            this.state.nominating = null;
            this.notif.add(
                _t("Sent. Everybody has a private link that closes on %s.",
                   res.deadline || ""),
                { type: "success" });
            await this.refresh();
        } else if (this.state.nominating) {
            this.state.nominating.busy = false;
        }
    }

    // =====================================================================
    //  THE DEADLINE, THE CONVERSATION
    // =====================================================================
    async startReview(row) {
        if (await this.call("start_review", [row.id],
                            _t("The review is open and their manager has been asked for colleagues."))) {
            await this.refresh();
        }
    }

    async extendDeadline(row) {
        const res = await this.call("extend_deadline", [row.review_id]);
        if (res) {
            this.notif.add(
                _t("Everybody has until %s. This can only be done once.",
                   res.deadline || ""),
                { type: "success" });
            await this.refresh();
        }
    }

    async consolidate(row) {
        if (await this.call("consolidate", [row.review_id],
                            _t("Put together. Their manager has been sent the report."))) {
            await this.refresh();
        }
    }

    askTalk(row) {
        this.state.talking = {
            reviewId: row.review_id, who: row.employee, notes: "", busy: false,
        };
    }

    onTalkNotes(ev) { this.state.talking.notes = ev.target.value; }
    cancelTalk() { this.state.talking = null; }

    async saveTalk() {
        const t = this.state.talking;
        if (!t || t.busy) { return; }
        t.busy = true;
        const ok = await this.call("finish_one_on_one",
                                   [t.reviewId, t.notes || false]);
        if (ok) {
            this.state.talking = null;
            this.notif.add(_t("Noted. The decision is next."), { type: "success" });
            await this.refresh();
        } else if (this.state.talking) {
            this.state.talking.busy = false;
        }
    }

    // =====================================================================
    //  THE VERDICT WIZARD
    // =====================================================================
    async askVerdict(row) {
        this.state.verdicting = {
            reviewId: row.review_id,
            employeeId: row.id,
            who: row.employee,
            step: 1,
            report: "",
            avg: 0,
            strengths: "",
            improvements: "",
            verdict: "",
            months: 1,
            preview: null,
            busy: true,
        };
        try {
            const person = await this.orm.call(
                "pb.probation", "get_person", [row.id]);
            const v = this.state.verdicting;
            if (v) {
                v.report = person.report || "";
                v.avg = person.avg_rating || 0;
                v.strengths = person.strengths || "";
                v.improvements = person.improvements || "";
            }
        } catch (e) {
            this.fail(e);
        } finally {
            if (this.state.verdicting) { this.state.verdicting.busy = false; }
        }
    }

    cancelVerdict() { this.state.verdicting = null; }
    onStrengths(ev) { this.state.verdicting.strengths = ev.target.value; }
    onImprovements(ev) { this.state.verdicting.improvements = ev.target.value; }
    onMonths(ev) {
        const n = parseInt(ev.target.value, 10);
        this.state.verdicting.months = isNaN(n) ? 1 : Math.max(1, Math.min(n, 12));
    }

    verdictStep(step) {
        const v = this.state.verdicting;
        if (!v) { return; }
        v.step = step;
        if (step !== 3) { v.preview = null; }
    }

    async pickVerdict(verdict) {
        const v = this.state.verdicting;
        if (!v) { return; }
        v.verdict = verdict;
        v.busy = true;
        v.preview = null;
        try {
            v.preview = await this.orm.call(
                "pb.probation", "verdict_preview",
                [v.reviewId, verdict, v.months]);
            v.step = 3;
        } catch (e) {
            this.fail(e);
        } finally {
            if (this.state.verdicting) { this.state.verdicting.busy = false; }
        }
    }

    get verdictBlocked() {
        const v = this.state.verdicting;
        return !!(v && v.preview && v.preview.blocked
            && v.preview.blocked.length);
    }

    async saveVerdict() {
        const v = this.state.verdicting;
        if (!v || v.busy || !v.verdict || this.verdictBlocked) { return; }
        v.busy = true;
        const res = await this.call(
            "save_verdict",
            [v.reviewId, v.verdict, v.strengths || false,
             v.improvements || false, v.months]);
        if (res) {
            const done = {
                pass: _t("Confirmed. The letter is prepared, filed and on its way to them."),
                extend: _t("Extended. The new date is on their record and a second review is scheduled."),
                fail: _t("Recorded. Nothing about their leaving has been started — that is a separate button."),
            }[v.verdict];
            this.state.verdicting = null;
            this.notif.add(done, { type: "success" });
            await this.refresh();
        } else if (this.state.verdicting) {
            this.state.verdicting.busy = false;
        }
    }

    // =====================================================================
    //  THE EXIT, THE TRAINING, THE DOORS
    // =====================================================================
    async startExit(row) {
        const act = await this.call("start_exit", [row.review_id]);
        if (act) {
            this.notif.add(_t("The leaving checklist is open."),
                           { type: "success" });
            this.action.doAction(act);
        }
    }

    async settleTraining(item, done) {
        if (await this.call("settle_training", [item.id, done])) {
            await this.refresh();
        }
    }

    async runAutomation() {
        const res = await this.call("run_automation", []);
        if (res) {
            const n = (c, one, many) => c + " " + (c === 1 ? one : many);
            this.notif.add(
                _t("%(reviews)s opened, %(reminders)s sent, %(done)s put together.",
                   { reviews: n(res.reviews || 0, _t("review"), _t("reviews")),
                     reminders: n(res.reminders || 0, _t("reminder"), _t("reminders")),
                     done: n(res.consolidated || 0, _t("report"), _t("reports")) }),
                { type: "success" });
            await this.refresh();
        }
    }

    async openReview(row) {
        if (!row.review_id) { return; }
        const act = await this.call("open_review_action", [row.review_id]);
        if (act) { this.action.doAction(act); }
    }

    async openLetter(letterId) {
        const act = await this.call("open_letter_action", [letterId]);
        if (act) { this.action.doAction(act); }
    }

    async openEmployee(row) {
        const act = await this.call("open_employee_action", [row.id]);
        if (act) { this.action.doAction(act); }
    }

    openPolicies() {
        this.action.doAction("pb_probation.action_pb_probation_policy");
    }

    openCourses() {
        this.action.doAction("pb_probation.action_pb_training_track");
    }

    openReviews() {
        this.action.doAction("pb_probation.action_pb_probation_review");
    }
}

registry.category("actions").add("pb_probation_board", PbProbationBoard);
