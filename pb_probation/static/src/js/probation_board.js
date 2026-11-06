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
import { useFilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

/** Cards per page; "Show N more" loads the next one. */
const PAGE = 60;

/** The five stops the rail shows, in order — the SAME five steps as the
 *  numbered strip above the cards (flowStepOf), so a card and the strip can
 *  never disagree about where a person is (owner, 2026-09-30). */
const STAGES = ["peers", "answers", "talk", "review", "outcome"];

/** What each stop is called.
 *
 * SHORT ENOUGH TO FIT. Five stops share a card that can be 340px wide, and a
 * label that ellipses is a label that has stopped being a label, so each is
 * one short word for the step's full name in the strip above.
 */
const STAGE_LABEL = {
    peers: _t("Peers"),
    answers: _t("Answers"),
    talk: _t("Meeting"),
    review: _t("Sign-off"),
    outcome: _t("Outcome"),
};

// One arrival opens one drawer (NAV P3c), keyed on the hub's arrival object.
const _openedFor = new WeakSet();

export class PbProbationBoard extends Component {
    static template = "pb_probation.PbProbationBoard";
    static components = { PbFilterLayout };
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
            total: 0,               // everybody in a trial period
            glanceFilters: {},      // what each figure means as a filter
            minNominees: 3,
            maxNominees: 5,

            // the page the filter panel produced (FILTER wave 2)
            rows: [],
            rowsTotal: 0,
            listLoaded: false,
            loadingMore: false,
            stepCounts: {},

            // the open person
            drawer: null,
            drawerBusy: false, reviewNote: "", reviewBusy: false,

            // dialogs — one at a time, each one plain state
            nominating: null,
            verdicting: null,
            talking: null,
        });

        // The shared filter panel (pb_filter_kit): it owns the filters, the
        // counts and the views; this board loads one page of cards for
        // kit.query, counted and filtered on the server (no 300-row cap).
        this.kit = useFilterKit({
            model: "pb.probation",
            noun: _t("people"),
            onChange: () => this.loadPage(),
        });

        onWillStart(async () => {
            await this.load();
            // NAV P3c — a door may open the board ON one person
            // (`pb_focus: "person:<employee id>"`, Home › TEAM). Once per
            // arrival: tabbing away and back does not pop the drawer again.
            const arrival = this.props.arrival;
            const m = /^person:(\d+)$/.exec(String((arrival && arrival.focus) || ""));
            if (m && this.state.allowed && !_openedFor.has(arrival)) {
                _openedFor.add(arrival);
                await this.openPerson(Number(m[1]));
            }
        });
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
    /** The numbers line, the switch notice and the flags — counted over
     *  everybody in a trial period, whatever is filtered. */
    async load() {
        try {
            const d = await this.orm.call("pb.probation", "get_board_head", []);
            Object.assign(this.state, {
                allowed: d.allowed,
                canWrite: d.can_write,
                autoOn: !!d.auto_on,
                kpis: d.kpis || {},
                total: d.total || 0,
                glanceFilters: d.glance_filters || {},
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

    /** One page of cards (and, on the first, the step counts) for the
     *  panel's current filters. A reply for an older filter state is dropped. */
    async loadPage({ more = false } = {}) {
        const q = this.kit.query;
        const offset = more ? this.state.rows.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call("pb.probation", "get_board_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.rows = more ? [...this.state.rows, ...d.rows] : d.rows;
            this.state.rowsTotal = d.total;
            if (!more) { this.state.stepCounts = d.steps || {}; }
            this.state.listLoaded = true;
        } catch (e) {
            console.warn("pb_probation: could not load the cards", e);
            if (this.kit.isCurrent(q.seq)) {
                this.notif.add(_t("The trial periods could not be loaded. Try again in a moment."),
                               { type: "warning" });
                this.state.listLoaded = true;
            }
        } finally {
            this.state.loadingMore = false;
        }
    }

    loadMore() {
        if (!this.state.loadingMore) { this.loadPage({ more: true }); }
    }

    get hasMore() { return this.state.rows.length < this.state.rowsTotal; }

    get nextPage() { return Math.min(PAGE, this.state.rowsTotal - this.state.rows.length); }

    fmtInt(n) { return Number(n || 0).toLocaleString("en-US"); }

    async refresh() {
        await Promise.all([this.load(), this.kit.refresh()]);
        if (this.state.drawer) {
            await this.openPerson(this.state.drawer.row.id);
        }
    }

    /** Back to everybody in a trial period (the first view). */
    showAll() { this.kit.toggleFilters({}); }

    /** Why the list is empty, in one translatable sentence (R34). */
    get emptyText() {
        if (this.kit.chips.length) {
            return this.state.total === 1
                ? _t("There is 1 person in a trial period, but they do not fit every filter you have set. Remove a filter above, or start again from everybody.")
                : _t("There are %s people in a trial period, but none of them fits every filter you have set. Remove a filter above, or start again from everybody.",
                     this.fmtInt(this.state.total));
        }
        if (this.kit.search) {
            return _t("Nobody matches “%s”. Check the spelling, or search by job or team.", this.kit.search);
        }
        return _t("Nothing could be listed just now. Show everybody to start again.");
    }

    // ----------------------------------------------------- the quiet board
    //
    // One slim line of numbers instead of a row of tiles, and the five
    // numbered steps of a review. A person is at EXACTLY ONE step, so the
    // step counts add up to what the panel lists. A figure that filters
    // ticks exactly its filters in the panel (and lights the view tab with
    // the same filters); pressing it again shows everyone.
    glanceRun(key) {
        const f = this.state.glanceFilters[key];
        return f ? () => this.kit.toggleFilters(f) : null;
    }

    /** Which figure is lit: the one whose filters are exactly what is on. */
    get glanceOn() {
        if (!this.kit.loaded) { return ""; }
        for (const [key, f] of Object.entries(this.state.glanceFilters || {})) {
            if (this.kit.isExactly(f)) { return key; }
        }
        return "";
    }

    get glance() {
        const k = this.state.kpis || {};
        const tone = (v, t) => (v ? t : "");
        return [
            { key: "all", n: k.in_probation || 0, label: _t("In a trial period"), tone: "", run: null },
            { key: "running", n: k.running || 0, label: _t("Reviews running"), tone: "",
              run: this.glanceRun("running") },
            { key: "verdicts", n: k.verdicts || 0, label: _t("Waiting on a decision"), tone: tone(k.verdicts, "amber"),
              run: this.glanceRun("verdicts") },
            { key: "late", n: k.overdue_feedback || 0, label: _t("Answers overdue"), tone: tone(k.overdue_feedback, "rose"),
              run: this.glanceRun("late") },
            { key: "urgent", n: k.urgent || 0, label: _t("Ending within a week"), tone: tone(k.urgent, "rose"),
              run: this.glanceRun("urgent") },
        ];
    }

    /** Waiting on the HR lead or the CEO to sign the recommendation off. */
    atSignOff(r) {
        return r.review_state === "verdict" && ["hr", "ceo"].includes(r.review_gate);
    }

    /**
     * The review step a person is at. Not started / scheduled / choosing
     * colleagues → peers; answers running → answers; putting the answers
     * together, the 1:1 and the manager's own recommendation → talk; the
     * HR lead or CEO sign-off → review; a closed review → outcome.
     */
    flowStepOf(r) {
        const st = r.review_state || "";
        if (st === "closed" || r.review_gate === "approved") { return "outcome"; }
        if (this.atSignOff(r)) { return "review"; }
        if (["consolidation", "one_on_one", "verdict"].includes(st)) { return "talk"; }
        if (st === "feedback") { return "answers"; }
        return "peers";
    }

    get stepDefs() {
        return [
            { key: "peers", title: _t("Choose peers"), sub: _t("Not started, or colleagues being chosen") },
            { key: "answers", title: _t("Gather perspectives"), sub: _t("Colleagues are answering") },
            { key: "talk", title: _t("Manager conversation"), sub: _t("The 1:1 and the manager's recommendation") },
            { key: "review", title: _t("HR & leadership review"), sub: _t("The recommendation is being signed off") },
            { key: "outcome", title: _t("Share the outcome"), sub: _t("Decided and recorded") },
        ];
    }

    /** The five steps, counted on the server for the panel's filters
     *  (everything except the step itself), so they follow the filters. */
    get steps() {
        const counts = this.state.stepCounts || {};
        return this.stepDefs.map((st, i) => {
            const c = counts[st.key] || {};
            const at = { length: c.n || 0 };
            // everybody at the sign-off step is waiting for a sign-off
            const waiting = st.key === "review" ? c.n || 0 : 0;
            const late = c.late || 0;
            let flag = "";
            let flagTone = "";
            if (waiting) {
                flag = waiting === 1 ? _t("1 waiting for a sign-off") : _t("%s waiting for a sign-off", waiting);
            } else if (late) {
                flag = late === 1 ? _t("1 with answers overdue") : _t("%s with answers overdue", late);
                flagTone = "rose";
            }
            return {
                ...st,
                n: String(i + 1).padStart(2, "0"),
                count: at.length,
                countLabel: at.length === 1 ? _t("1 person") : _t("%s people", at.length),
                flag,
                flagTone,
                on: this.stepIsOn(st.key),
            };
        });
    }

    stepIsOn(key) {
        const v = this.kit.values("stage");
        return v.length === 1 && String(v[0]) === key;
    }

    /** A step narrows the panel's list to that step, keeping every other
     *  filter; pressing the lit step again lifts it. */
    pickStep(key) {
        if (this.stepIsOn(key)) { this.kit.clear("stage"); } else { this.kit.only("stage", key); }
    }

    // ------------------------------------------------------------ the rail
    stageLabel(stage) { return STAGE_LABEL[stage] || stage; }

    stageCls(row, stage) {
        const here = STAGES.indexOf(this.flowStepOf(row));
        const at = STAGES.indexOf(stage);
        if (at < here) { return "done"; }
        if (at === here) {
            // a decided review has finished its last stop too
            return stage === "outcome" && row.review_state === "closed" ? "done" : "now";
        }
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
        if (stage === "outcome" && row.verdict_label) {
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

    async reviewRecommendation(decision) {
        if (this.state.reviewBusy) return;
        this.state.reviewBusy = true;
        const result = await this.call("review_recommendation", [this.state.drawer.row.review_id, decision, this.state.reviewNote]);
        this.state.reviewBusy = false;
        if (result) { this.notif.add(result.note, {type:"success"}); this.state.reviewNote = ""; await this.refresh(); }
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
        const person = await this.orm.call("pb.probation", "get_person", [row.id]);
        this.state.minNominees = person.sop?.peer_min || 3;
        this.state.maxNominees = person.sop?.peer_max || 4;
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
                _t("This policy allows up to %s colleagues.",
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
            avg: 0, scale: 4, ratings: {quality:"",culture:"",adaptability:"",initiative:"",leadership:""}, leadership: false, improvementPlan: "",
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
                v.scale = person.sop?.scale || 5;
                v.ratings = person.sop?.ratings || v.ratings;
                v.leadership = person.sop?.leadership || false;
                v.improvementPlan = person.sop?.improvement_plan || "";
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
        const saved = await this.call("save_manager_evaluation", [v.reviewId, {...v.ratings}, v.leadership, v.improvementPlan]);
        if (!saved) { v.busy = false; return; }
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
            this.notif.add(res.note || done, { type: "success" });
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
