/** @odoo-module **/
/**
 * `pb_goals_board` — the Goals lens on the People hub.
 *
 * ONE BOARD, TWO READERS, AND THE SERVER DECIDES WHICH. A manager opening this
 * sees their own team; the HR team sees the company. That is not a switch on
 * the screen and it is not two lenses — it is the record rules doing what
 * record rules are for, with one honest sentence at the top saying whose
 * sheets are on the board. A screen that asks somebody to choose a scope they
 * do not have is a screen with a dead end in it.
 *
 * NOTHING HERE RECOMPUTES A NUMBER. The server works out every figure, every
 * ratio and the order the rows come in; a second opinion written in JavaScript
 * would only ever disagree with the one that counts.
 *
 * PROBLEM FIRST (R113). The rows arrive ranked by what somebody has to DO
 * about them — sent back, never written, waiting on a manager, waiting on HR,
 * then the ones that are finished — and never by the spelling of the status,
 * which is alphabetical order pretending to be lifecycle order (R50).
 *
 * EVERY COLLECTION IN THE INITIAL STATE IS A COLLECTION (R195): a panel is
 * rendered ONCE over the initial state before the `await` that fetches its
 * data has resolved, so a `{}` where the template reads `.length` throws
 * "Cannot read properties of undefined", which the theme shows as a generic
 * "something went wrong" dialog with nothing useful in the console.
 *
 * Every icon comes from the shared `ic()` registry in pb_import_kit — the set
 * is CLOSED and an unknown name renders a plain circle with no error, so a
 * name used here is a name that is in that file.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

/** The chip colour for each status. Problem first, and never by spelling. */
const STATE_TONE = {
    returned: "bad",
    draft: "wait",
    submitted: "wait",
    manager_ok: "wait",
    refused: "bad",
    locked: "ok",
};

const STATE_ICON = {
    returned: "undo",
    draft: "pencil",
    submitted: "clock",
    manager_ok: "clock",
    refused: "xCircle",
    locked: "lock",
    closed: "archive",
};

/**
 * THE FIVE TABS, NAMED (B2).
 *
 * A CHAIN OF TABS NAMES EVERY ONE OF THEM AND HAS NO `t-else` AT THE END
 * (R194). A catch-all branch claims every tab nobody has written yet, and the
 * symptom is two panels rendering at once on a screen that otherwise looks
 * perfectly normal.
 *
 * The order is the order of the year: who has written theirs, are we talking
 * about them, are the reviews written up, what has been asked to change, and
 * what it all came out at.
 */
const TABS = [
    { key: "sheets", label: _t("Goal sheets"), icon: "target" },
    { key: "checkins", label: _t("Monthly conversations"), icon: "calendar" },
    { key: "reviews", label: _t("Reviews"), icon: "award" },
    { key: "changes", label: _t("Changes asked for"), icon: "repeat" },
    { key: "scores", label: _t("Scores"), icon: "trendingUp" },
];

const CHECKIN_TONE = { planned: "wait", done: "ok", missed: "bad" };
const CHANGE_TONE = {
    draft: "wait",
    submitted: "wait",
    manager_ok: "wait",
    approved: "ok",
    refused: "bad",
};

export class PbGoalsBoard extends Component {
    static template = "pb_goals.PbGoalsBoard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.dialog = useService("dialog");

        this.state = useState({
            loaded: false,
            allowed: true,
            busy: false,
            why: "",
            isHr: false,
            scope: "",
            headline: "",
            today: "",
            cycles: [],
            cycleId: 0,
            rows: [],
            stats: [],
            bar: [],
            facets: { departments: [], managers: [] },
            states: [],
            remindersOn: true,
            myPage: false,
            filters: { state: "", department_id: 0, manager_id: 0, q: "",
                       mine: false },
            // The drawer. Every nested object carries the keys the template
            // reads, because the drawer is rendered before its payload lands.
            open: false,
            sheet: { goals: [], history: [], ok: false },
            weights: {},
            weightTotal: 0,
            weightsOk: false,
            weightWord: "",
            backNote: "",
            backOpen: false,
            bulk: null,

            // ============================================== B2: the year
            // EVERY COLLECTION IN THE INITIAL STATE IS A COLLECTION AND
            // EVERY NESTED OBJECT CARRIES THE KEYS THE TEMPLATE READS
            // (R195). A tab is rendered ONCE over this state before the
            // `await` that fetches its data has resolved, so a `{}` where
            // the template reads `.length` throws "Cannot read properties
            // of undefined" — which the theme shows as the generic
            // "something went wrong" dialog with nothing in the console.
            tab: "sheets",
            year: { rows: [], stats: [], headline: "", tab: "" },
            yearBusy: false,
            // The drawer's new sections.
            checkins: [],
            reviews: [],
            changes: [],
            audit: [],
            scores: { goals: [], sentence: "", scored: false, band: "" },
            applicability: { note: "", mid_year: true, year_end: true },
            scoreOptions: [],
            mayScore: false,
            mayCheckin: false,
            mayChange: false,
            sheetClosed: false,
            // The three little forms the drawer opens.
            checkinOpen: 0,
            checkinNote: "",
            checkinBlockers: "",
            reviewOpen: 0,
            reviewNote: "",
            changeOpen: false,
            changeKind: "edit",
            changeGoalId: 0,
            changeTitle: "",
            changeDescription: "",
            changeDate: "",
            changeKrs: "",
            changeReason: "",
            marks: {},
            closing: null,
            closeAnyway: false,
        });

        onWillStart(async () => {
            await this.load();
        });
    }

    ic(name, size = 16) { return ic(name, size); }

    tone(key) { return STATE_TONE[key] || "wait"; }
    stateIcon(key) { return STATE_ICON[key] || "circle"; }
    checkinTone(key) { return CHECKIN_TONE[key] || "wait"; }
    changeTone(key) { return CHANGE_TONE[key] || "wait"; }

    get tabs() { return TABS; }

    get cycle() {
        return this.state.cycles.find((c) => c.id === this.state.cycleId)
            || null;
    }

    /**
     * The drawer's one-line subtitle.
     *
     * BUILT HERE AND NOT IN THE TEMPLATE. `[a, b, c].filter(Boolean)` is
     * ordinary JavaScript and dies inside an OWL template with *"undefined is
     * not a function"* — the compiled expression runs in a restricted scope
     * that does not carry `Boolean`, and the whole component then fails to
     * render with the real cause two levels down an OwlError's `cause`. The
     * drawer simply never opened. Anything a template needs that is not a
     * property or a method of the component belongs in the component.
     */
    get drawerSub() {
        const s = this.state.sheet;
        return [s.job, s.department, s.cycle].filter((v) => !!v).join(" · ");
    }

    get anyFilter() {
        const f = this.state.filters;
        return !!(f.state || f.department_id || f.manager_id || f.q || f.mine);
    }

    // =================================================================
    //  reading
    // =================================================================
    async load() {
        this.state.busy = true;
        try {
            const f = this.state.filters;
            const payload = { cycle_id: this.state.cycleId };
            if (f.state) { payload.state = f.state; }
            if (f.department_id) { payload.department_id = f.department_id; }
            if (f.manager_id) { payload.manager_id = f.manager_id; }
            if (f.q) { payload.q = f.q; }
            if (f.mine) { payload.mine = true; }
            const d = await this.orm.call("pb.goals", "get_board", [payload]);
            if (d.allowed === false) {
                Object.assign(this.state, {
                    loaded: true, allowed: false, why: d.why || "" });
                return;
            }
            Object.assign(this.state, {
                loaded: true,
                allowed: true,
                isHr: !!d.is_hr,
                scope: d.scope || "",
                headline: d.headline || "",
                today: d.today || "",
                cycles: d.cycles || [],
                cycleId: d.cycle_id || 0,
                rows: d.rows || [],
                stats: d.stats || [],
                bar: d.bar || [],
                facets: d.facets || { departments: [], managers: [] },
                states: d.states || [],
                remindersOn: d.reminders_on !== false,
                myPage: !!d.my_page,
            });
        } catch (e) {
            this.state.loaded = true;
            this.state.allowed = false;
            this.state.why = _t("The goals board could not be read.");
            console.warn("pb_goals: the board could not be read", e);
        } finally {
            this.state.busy = false;
        }
    }

    async pickCycle(id) {
        this.state.cycleId = Number(id) || 0;
        await this.reload();
    }

    /**
     * "READ IT AGAIN" MUST READ WHAT IS ON THE SCREEN (R188).
     *
     * The board grew four more payloads in B2, and a refresh that only ever
     * re-read the goal sheets would leave whichever of the other four was
     * showing exactly as stale as it was — found live on another module's
     * board when a date was corrected underneath an open screen and the
     * button would not pick it up.
     */
    async reload() {
        await this.load();
        if (this.state.tab !== "sheets") {
            await this.loadYear();
        }
    }

    async setTab(key) {
        if (this.state.tab === key) { return; }
        this.state.tab = key;
        if (key === "sheets") { return; }
        // A TAB IS DRAWN BEFORE ITS OWN PAYLOAD ARRIVES (R195): OWL
        // re-renders the moment `state.tab` changes, which is before the
        // await below has resolved. The panel is therefore rendered once
        // over the PREVIOUS tab's rows — harmless, because every row shape
        // the templates read is guarded — and then again over its own.
        this.state.year = { rows: [], stats: [], headline: "", tab: key };
        await this.loadYear();
    }

    async loadYear() {
        this.state.yearBusy = true;
        try {
            const d = await this.orm.call("pb.goals", "get_year", [
                this.state.cycleId, this.state.tab,
                { state: this.state.filters.state || "" },
            ]);
            if (d.allowed === false) {
                this.state.year = { rows: [], stats: [],
                                    headline: d.why || "", tab: this.state.tab };
                return;
            }
            this.state.year = {
                rows: d.rows || [],
                stats: d.stats || [],
                headline: d.headline || "",
                tab: d.tab || this.state.tab,
            };
        } catch (e) {
            this.state.year = { rows: [], stats: [], tab: this.state.tab,
                                headline: _t("That could not be read.") };
            console.warn("pb_goals: the year could not be read", e);
        } finally {
            this.state.yearBusy = false;
        }
    }

    /** A chip that is already on is a chip that turns off — otherwise the
     *  only way back to everything is a page reload, which is a dead end. */
    async setFilter(key, value) {
        const current = this.state.filters[key];
        const blank = key === "state" ? "" : 0;
        this.state.filters[key] =
            String(current) === String(value) ? blank : value;
        await this.load();
    }

    async toggleMine() {
        this.state.filters.mine = !this.state.filters.mine;
        await this.load();
    }

    onSearch(ev) {
        this.state.filters.q = ev.target.value || "";
        clearTimeout(this._timer);
        this._timer = setTimeout(() => this.load(), 260);
    }

    async clearFilters() {
        this.state.filters = { state: "", department_id: 0, manager_id: 0,
                               q: "", mine: false };
        await this.load();
    }

    // =================================================================
    //  the drawer
    // =================================================================
    async openSheet(id) {
        this.state.busy = true;
        try {
            const d = await this.orm.call("pb.goals", "get_set", [id]);
            if (!d.ok) {
                this.notif.add(d.why || _t("That one could not be opened."),
                               { type: "warning" });
                return;
            }
            this.state.sheet = Object.assign(
                { goals: [], history: [] }, d);
            this.state.weights = {};
            for (const goal of d.goals || []) {
                this.state.weights[goal.id] = goal.weight;
            }
            this.state.weightTotal = d.weight_total || 0;
            this.state.weightsOk = !!d.weights_ok;
            this.state.weightWord = "";
            this.state.backNote = "";
            this.state.backOpen = false;
            // ---------------------------------------------- B2's sections
            this.state.checkins = d.checkins || [];
            this.state.reviews = d.reviews || [];
            this.state.changes = d.changes || [];
            this.state.audit = d.audit || [];
            this.state.scores = Object.assign(
                { goals: [], sentence: "", scored: false, band: "" },
                d.scores || {});
            this.state.applicability = Object.assign(
                { note: "", mid_year: true, year_end: true },
                d.applicability || {});
            this.state.scoreOptions = d.score_options || [];
            this.state.mayScore = !!d.may_score;
            this.state.mayCheckin = !!d.may_checkin;
            this.state.mayChange = !!d.may_change;
            this.state.sheetClosed = !!d.closed;
            this.state.marks = {};
            for (const goal of this.state.scores.goals || []) {
                for (const kr of goal.krs || []) {
                    this.state.marks[kr.id] = kr.score || "";
                }
            }
            this.state.checkinOpen = 0;
            this.state.checkinNote = "";
            this.state.checkinBlockers = "";
            this.state.reviewOpen = 0;
            this.state.reviewNote = "";
            this.state.changeOpen = false;
            this.state.changeReason = "";
            this.state.open = true;
        } catch (e) {
            this.notif.add(_t("That one could not be opened."),
                           { type: "danger" });
            console.warn("pb_goals: the drawer could not be read", e);
        } finally {
            this.state.busy = false;
        }
    }

    closeDrawer() {
        this.state.open = false;
    }

    /** The running total moves as the manager types, so nobody has to add up
     *  four numbers in their head to find out why the button is off. */
    onWeight(goalId, ev) {
        const value = Math.max(0, Math.min(100, Number(ev.target.value) || 0));
        this.state.weights[goalId] = value;
        let total = 0;
        for (const key of Object.keys(this.state.weights)) {
            total += Number(this.state.weights[key]) || 0;
        }
        this.state.weightTotal = Math.round(total * 10) / 10;
        this.state.weightsOk = Math.abs(total - 100) < 0.01;
    }

    async saveWeights() {
        this.state.busy = true;
        try {
            const d = await this.orm.call(
                "pb.goals", "set_weights",
                [this.state.sheet.id, this.state.weights]);
            this.state.weightTotal = d.weight_total;
            this.state.weightsOk = !!d.weights_ok;
            this.state.weightWord = d.sentence || "";
            this.notif.add(d.sentence || _t("Saved."),
                           { type: d.weights_ok ? "success" : "warning" });
            await this.load();
        } catch (e) {
            this.notif.add(this.constructor.reason(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    static reason(e) {
        return (e && e.data && e.data.message)
            || (e && e.message) || _t("That did not work.");
    }

    async sendBack() {
        const note = (this.state.backNote || "").trim();
        if (!note) {
            this.notif.add(
                _t("Write what you would like changed — a sheet that comes "
                   + "back with no note is a sheet somebody has to guess "
                   + "about."), { type: "warning" });
            return;
        }
        this.state.busy = true;
        try {
            const d = await this.orm.call(
                "pb.goals", "send_back", [this.state.sheet.id, note]);
            this.notif.add(d.sentence || _t("Sent back."),
                           { type: "success" });
            this.state.open = false;
            await this.load();
        } catch (e) {
            this.notif.add(this.constructor.reason(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // =================================================================
    //  the doors
    // =================================================================
    async openRecord(id) {
        const action = await this.orm.call("pb.goals", "open_set", [id]);
        await this.action.doAction(action);
    }

    async openCycles() {
        const action = await this.orm.call("pb.goals", "open_cycles", []);
        await this.action.doAction(action);
    }

    async openTemplates() {
        const action = await this.orm.call("pb.goals", "open_templates", []);
        await this.action.doAction(action);
    }

    // =================================================================
    //  opening a year for everybody
    // =================================================================
    /** IT SAYS HOW MANY BEFORE IT MAKES ANY (R54). A button that writes to
     *  four thousand people has to be a button somebody presses twice. */
    async askBulk() {
        if (!this.state.cycleId) { return; }
        this.state.busy = true;
        try {
            const d = await this.orm.call(
                "pb.goals", "preview_open_for_everyone",
                [this.state.cycleId]);
            this.state.bulk = d;
        } catch (e) {
            this.notif.add(this.constructor.reason(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    closeBulk() { this.state.bulk = null; }

    async doBulk() {
        this.state.busy = true;
        try {
            const d = await this.orm.call(
                "pb.goals", "open_for_everyone", [this.state.cycleId]);
            this.notif.add(d.sentence || _t("Done."), { type: "success" });
            this.state.bulk = null;
            await this.load();
        } catch (e) {
            this.notif.add(this.constructor.reason(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    /**
     * A figure a person reads, with the thousands in it.
     *
     * A Vietnamese revenue target is ten digits long, and ten digits with no
     * separators is a number nobody reads — they count the noughts. Trailing
     * zeroes after the point are dropped so "40" stays "40".
     */
    num(value) {
        const n = Number(value || 0);
        if (!isFinite(n)) { return "0"; }
        return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
    }

    /** One key result's figures, as the one string the drawer prints. */
    krWords(kr) {
        const parts = [this.num(kr.current)];
        if (kr.target) { parts.push("/ " + this.num(kr.target)); }
        if (kr.measure) { parts.push(kr.measure); }
        return parts.join(" ");
    }

    /** The widest bar in a table is 100%; everything else is relative to it. */
    share(value, top) {
        if (!top) { return 0; }
        return Math.round((Number(value || 0) / Number(top)) * 100);
    }

    // =================================================================
    //  B2 — the monthly conversation
    // =================================================================
    openCheckinForm(id) {
        this.state.checkinOpen = this.state.checkinOpen === id ? 0 : id;
        this.state.checkinNote = "";
        this.state.checkinBlockers = "";
    }

    async writeUpCheckin() {
        const note = (this.state.checkinNote || "").trim();
        if (!note) {
            this.notif.add(
                _t("Write a line about what moved this month — a check-in "
                   + "with nothing on it cannot be read next March."),
                { type: "warning" });
            return;
        }
        this.state.busy = true;
        try {
            const d = await this.orm.call(
                "pb.goals", "write_up_checkin",
                [this.state.checkinOpen, note, this.state.checkinBlockers]);
            this.notif.add(d.sentence || _t("Written up."),
                           { type: "success" });
            this.state.checkinOpen = 0;
            await this.openSheet(this.state.sheet.id);
            await this.reload();
        } catch (e) {
            this.notif.add(this.constructor.reason(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // =================================================================
    //  B2 — the two reviews
    // =================================================================
    openReviewForm(id) {
        this.state.reviewOpen = this.state.reviewOpen === id ? 0 : id;
        this.state.reviewNote = "";
    }

    async writeUpReview() {
        const note = (this.state.reviewNote || "").trim();
        if (!note) {
            this.notif.add(
                _t("Write up what was said. This is the one row somebody "
                   + "will want to read next year."), { type: "warning" });
            return;
        }
        this.state.busy = true;
        try {
            const d = await this.orm.call(
                "pb.goals", "write_up_review",
                [this.state.reviewOpen, note]);
            this.notif.add(d.sentence || _t("Written up."),
                           { type: "success" });
            this.state.reviewOpen = 0;
            await this.openSheet(this.state.sheet.id);
            await this.reload();
        } catch (e) {
            this.notif.add(this.constructor.reason(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // =================================================================
    //  B2 — scoring
    // =================================================================
    onMark(krId, ev) {
        this.state.marks[krId] = ev.target.value || "";
    }

    /** How many marks are still missing, so the button can say so. */
    get marksLeft() {
        let left = 0;
        for (const key of Object.keys(this.state.marks)) {
            if (!this.state.marks[key]) { left += 1; }
        }
        return left;
    }

    async saveMarks() {
        this.state.busy = true;
        try {
            const d = await this.orm.call(
                "pb.goals", "score_key_results",
                [this.state.sheet.id, this.state.marks]);
            this.notif.add(d.sentence || _t("Saved."),
                           { type: d.scored ? "success" : "info" });
            await this.openSheet(this.state.sheet.id);
            await this.reload();
        } catch (e) {
            this.notif.add(this.constructor.reason(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async markGoalDone(goalId, done) {
        this.state.busy = true;
        try {
            const d = await this.orm.call(
                "pb.goals", "mark_goal_done", [goalId, done]);
            this.notif.add(d.sentence || _t("Saved."), { type: "success" });
            await this.openSheet(this.state.sheet.id);
        } catch (e) {
            this.notif.add(this.constructor.reason(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // =================================================================
    //  B2 — asking to change agreed goals
    // =================================================================
    openChangeForm(kind, goalId) {
        this.state.changeOpen = true;
        this.state.changeKind = kind || "edit";
        this.state.changeGoalId = Number(goalId) || 0;
        const goal = (this.state.sheet.goals || []).find(
            (g) => g.id === this.state.changeGoalId);
        this.state.changeTitle = goal ? goal.title : "";
        this.state.changeDescription = goal ? goal.description : "";
        this.state.changeDate = goal ? goal.to : "";
        this.state.changeKrs = "";
        this.state.changeReason = "";
    }

    closeChangeForm() { this.state.changeOpen = false; }

    async askChange() {
        const reason = (this.state.changeReason || "").trim();
        if (!reason) {
            this.notif.add(
                _t("Say why. A request to change agreed goals with no reason "
                   + "on it is a request nobody can decide."),
                { type: "warning" });
            return;
        }
        this.state.busy = true;
        try {
            const values = {
                title: this.state.changeTitle,
                description: this.state.changeDescription,
                date_end: this.state.changeDate || false,
                kr_titles: (this.state.changeKrs || "").split("\n"),
            };
            const d = await this.orm.call("pb.goals", "ask_for_change", [
                this.state.sheet.id, this.state.changeKind, values, reason,
                this.state.changeGoalId || null,
            ]);
            this.notif.add(d.sentence || _t("Asked."), { type: "success" });
            this.state.changeOpen = false;
            await this.openSheet(this.state.sheet.id);
            await this.reload();
        } catch (e) {
            this.notif.add(this.constructor.reason(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async decideChange(changeId, action) {
        this.state.busy = true;
        try {
            const d = await this.orm.call(
                "pb.goals", "decide_change", [changeId, action, ""]);
            this.notif.add(d.sentence || _t("Done."), { type: "success" });
            if (this.state.open && this.state.sheet.id) {
                await this.openSheet(this.state.sheet.id);
            }
            await this.reload();
        } catch (e) {
            this.notif.add(this.constructor.reason(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // =================================================================
    //  B2 — closing the year
    // =================================================================
    /** IT SAYS HOW MANY AND WHAT IS MISSING BEFORE IT DOES ANYTHING (R54). */
    async askClose() {
        if (!this.state.cycleId) { return; }
        this.state.busy = true;
        try {
            const d = await this.orm.call(
                "pb.goals", "preview_close", [this.state.cycleId]);
            this.state.closing = d;
            this.state.closeAnyway = false;
        } catch (e) {
            this.notif.add(this.constructor.reason(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    closeClosing() { this.state.closing = null; }

    toggleCloseAnyway() {
        this.state.closeAnyway = !this.state.closeAnyway;
    }

    async doClose() {
        this.state.busy = true;
        try {
            const d = await this.orm.call("pb.goals", "close_cycle", [
                this.state.cycleId, this.state.closeAnyway]);
            this.notif.add(d.sentence || _t("The year is closed."),
                           { type: "success" });
            this.state.closing = null;
            await this.reload();
        } catch (e) {
            this.notif.add(this.constructor.reason(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // =================================================================
    //  B2 — the doors
    // =================================================================
    async openCheckinRecord(id) {
        const action = await this.orm.call("pb.goals", "open_checkin", [id]);
        await this.action.doAction(action);
    }

    async openChangeRecord(id) {
        const action = await this.orm.call("pb.goals", "open_change", [id]);
        await this.action.doAction(action);
    }

    async openNumbers() {
        const action = await this.orm.call("pb.goals", "open_numbers", []);
        await this.action.doAction(action);
    }
}

registry.category("actions").add("pb_goals_board", PbGoalsBoard);
