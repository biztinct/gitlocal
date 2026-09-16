/** @odoo-module **/
/**
 * `pb_training_board` — the Training lens on the Learn hub.
 *
 * THE QUESTION THIS BOARD ANSWERS is "who still has to do what", so the order
 * is PROBLEM FIRST and the server decides it (R113): a course fourteen people
 * were put on and nobody has opened comes above a course everybody finished in
 * March. Nothing here re-sorts and nothing here recomputes a number — a second
 * opinion written in JavaScript would only ever disagree with the one that
 * counts.
 *
 * THE DRAWER IS THE SCREEN. A course row is a summary; the work — who is on
 * it, who has not started, who failed the test, putting three more people on —
 * happens in the drawer beside it, because every one of those is a question
 * about ONE course and a board that answered them all at once would be a
 * spreadsheet.
 *
 * Every scrim is a DIRECT CHILD of the root div and holds exactly one
 * `.pbim-modal` (R114/R115): the scrim is what centres and dims, the modal is
 * its child, and neither is nested under anything else.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

/** Fold accents in the browser too, so the picker filters as you type. */
function fold(text) {
    return (text || "").normalize("NFKD").replace(/[̀-ͯ]/g, "")
        .replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase();
}

export class PbTrainingBoard extends Component {
    static template = "pb_training.PbTrainingBoard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");

        this.state = useState({
            loaded: false,
            allowed: true,
            canWrite: false,
            canAdmin: false,
            courses: [],
            kpis: {},
            completionMail: false,
            search: "",
            busy: false,

            // the drawer
            open: null,             // the course payload, or null
            openId: 0,

            // the people picker
            picker: false,
            pickerTerm: "",
            pickerRows: [],
            picked: [],
            pickerBusy: false,

            // ---------------------------------------------------- E2
            // WHICH QUESTION THE BOARD IS ANSWERING. Courses is "what is in
            // the library"; Assignments is "who still owes what". They are
            // different questions with different orders and different
            // tiles, so they are tabs rather than one list with a filter on
            // it.
            tab: "courses",
            aLoaded: false,
            aBusy: false,
            aRows: [],
            aKpis: {},
            aFacets: {},
            aDelays: [],
            aSchedules: [],
            aRules: [],
            aReasons: [],
            aStates: [],
            aSwitches: {},
            aFilters: { reason: "", state: "", department_id: 0, term: "",
                        include_done: false },

            // the "Assign a course" dialog
            assign: false,
            assignCourse: 0,
            assignReason: "adhoc",
            assignDue: "",
            assignProbation: false,
            assignTerm: "",
            assignRows: [],
            assignPicked: [],
            assignBusy: false,
            groups: { departments: [], jobs: [] },
            expandKind: "department",
            expandValue: 0,
        });

        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------- reading
    async load() {
        this.state.busy = true;
        try {
            const d = await this.orm.call("pb.training", "get_board", []);
            Object.assign(this.state, {
                allowed: d.allowed !== false,
                canWrite: !!d.can_write,
                canAdmin: !!d.can_admin,
                courses: d.courses || [],
                kpis: d.kpis || {},
                completionMail: !!d.completion_mail,
                loaded: true,
            });
        } catch (e) {
            this.state.loaded = true;
            this.state.allowed = false;
            console.warn("pb_training: the training board could not be read", e);
        } finally {
            this.state.busy = false;
        }
    }

    get rows() {
        const needle = fold(this.state.search);
        if (!needle) { return this.state.courses; }
        return this.state.courses.filter((c) => fold(c.name).includes(needle));
    }

    /** The one sentence under the heading — what this board is looking at. */
    get headline() {
        const k = this.state.kpis || {};
        const courses = k.courses || 0;
        if (!courses) { return ""; }
        const bits = [
            courses === 1 ? _t("1 course") : _t("%s courses", courses),
            (k.members || 0) === 1 ? _t("1 person on it")
                : _t("%s people on them", k.members || 0),
        ];
        if (k.not_started) {
            bits.push((k.not_started === 1)
                ? _t("1 has not started")
                : _t("%s have not started", k.not_started));
        }
        return bits.join(" · ");
    }

    /** A pass rate nobody can answer yet is a dash, never a zero. */
    get passRate() {
        const rate = (this.state.kpis || {}).pass_rate;
        return (rate === null || rate === undefined) ? "—" : `${rate}%`;
    }

    // -------------------------------------------------------------- doors
    async act(verb, payload = {}, { reload = true } = {}) {
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.training", "act",
                                            [verb, payload]);
            if (res && res.type) {
                await this.action.doAction(res);
                return res;
            }
            if (res && res.message) {
                this.notif.add(res.message, { type: "success" });
            }
            if (reload) {
                await this.load();
                if (this.state.openId) { await this.openCourse(this.state.openId); }
            }
            return res;
        } catch (e) {
            const message = (e && e.data && e.data.message)
                || _t("That did not work.");
            this.notif.add(message, { type: "danger" });
            return null;
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------- drawer
    async openCourse(channelId) {
        this.state.busy = true;
        try {
            const course = await this.orm.call("pb.training", "get_course",
                                               [channelId]);
            this.state.open = course;
            this.state.openId = channelId;
        } catch (e) {
            const message = (e && e.data && e.data.message)
                || _t("That course could not be opened.");
            this.notif.add(message, { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    closeDrawer() {
        this.state.open = null;
        this.state.openId = 0;
        this.closePicker();
    }

    /**
     * "See it as a learner" — the employee's own page, in a new tab.
     *
     * AN ADMINISTRATOR WHO IS NOT ON THE COURSE SEES THE REFUSAL, and that is
     * correct rather than a defect: the page is built round a membership and
     * pretending otherwise would make the preview a different screen from the
     * one the employee gets. The tooltip says so before the click.
     */
    seeAsLearner(channelId) {
        window.open(`/my/training/${channelId}`, "_blank", "noopener");
    }

    // ------------------------------------------------------- people picker
    async openPicker() {
        this.state.picker = true;
        this.state.picked = [];
        this.state.pickerTerm = "";
        await this.searchPeople();
    }

    closePicker() {
        this.state.picker = false;
        this.state.pickerRows = [];
        this.state.picked = [];
    }

    async searchPeople() {
        this.state.pickerBusy = true;
        try {
            this.state.pickerRows = await this.orm.call(
                "pb.training", "search_people",
                [this.state.pickerTerm, this.state.openId]);
        } catch (e) {
            console.warn("pb_training: the people search failed", e);
            this.state.pickerRows = [];
        } finally {
            this.state.pickerBusy = false;
        }
    }

    onPickerTerm(ev) {
        this.state.pickerTerm = ev.target.value;
        clearTimeout(this._pickerTimer);
        this._pickerTimer = setTimeout(() => this.searchPeople(), 220);
    }

    togglePick(id) {
        const at = this.state.picked.indexOf(id);
        if (at === -1) { this.state.picked.push(id); }
        else { this.state.picked.splice(at, 1); }
    }

    isPicked(id) { return this.state.picked.includes(id); }

    get pickedWord() {
        const n = this.state.picked.length;
        if (!n) { return _t("Nobody picked yet"); }
        return n === 1 ? _t("1 person picked")
            : _t("%s people picked", n);
    }

    async confirmEnrol() {
        if (!this.state.picked.length) { return; }
        const res = await this.act("enrol", {
            channel_id: this.state.openId,
            employee_ids: this.state.picked.slice(),
        });
        if (res) { this.closePicker(); }
    }

    async removePerson(partnerId) {
        await this.act("unenrol", {
            channel_id: this.state.openId,
            partner_ids: [partnerId],
        });
    }

    // ------------------------------------------------------------- wording
    /** What a member's row says about their test. */
    testWord(row) {
        if (row.test === "passed") { return _t("Passed"); }
        if (row.test === "failed") { return _t("Not passed"); }
        return "";
    }

    statusWord(row) {
        if (row.status === "completed") { return _t("Finished"); }
        if (!row.percent) { return _t("Not started"); }
        return _t("Under way");
    }

    // =====================================================================
    //  E2 — the Assignments tab
    // =====================================================================
    async setTab(tab) {
        this.state.tab = tab;
        if (tab !== "courses" && !this.state.aLoaded) {
            await this.loadAssignments();
        }
    }

    /**
     * "Read the board again" means THIS board, whichever tab is showing.
     *
     * It used to call `load()`, which reads the courses and nothing else — so
     * pressing it on the Assignments tab (or Schedules, or Day one) re-read
     * a list that was not on the screen and left the one that was exactly as
     * stale as it had been. Found live after a schedule's next date was
     * corrected underneath an open board.
     */
    async refresh() {
        await this.load();
        if (this.state.aLoaded) { await this.loadAssignments(); }
    }

    async loadAssignments() {
        this.state.aBusy = true;
        try {
            const d = await this.orm.call("pb.training", "get_assignments",
                                          [this.assignFilters()]);
            Object.assign(this.state, {
                aRows: d.rows || [],
                aKpis: d.kpis || {},
                aFacets: d.facets || {},
                aDelays: d.delays || [],
                aSchedules: d.schedules || [],
                aRules: d.rules || [],
                aReasons: d.reasons || [],
                aStates: d.states || [],
                aSwitches: d.switches || {},
                aLoaded: true,
            });
        } catch (e) {
            this.state.aLoaded = true;
            console.warn("pb_training: the assignments could not be read", e);
            this.notif.add(
                (e && e.data && e.data.message)
                || _t("The assignments could not be read."),
                { type: "danger" });
        } finally {
            this.state.aBusy = false;
        }
    }

    /** Only the filters that are actually set — an empty one is not a filter. */
    assignFilters() {
        const f = this.state.aFilters;
        const out = {};
        if (f.reason) { out.reason = f.reason; }
        if (f.state) { out.state = f.state; }
        if (f.department_id) { out.department_id = f.department_id; }
        if (f.term) { out.term = f.term; }
        if (f.include_done) { out.include_done = true; }
        return out;
    }

    async setFilter(key, value) {
        // A CHIP THAT IS ALREADY ON IS A CHIP THAT TURNS OFF. Otherwise the
        // only way back to everything is a reload, which is a dead end.
        this.state.aFilters[key] =
            this.state.aFilters[key] === value ? "" : value;
        await this.loadAssignments();
    }

    onAssignTerm(ev) {
        this.state.aFilters.term = ev.target.value;
        clearTimeout(this._aTimer);
        this._aTimer = setTimeout(() => this.loadAssignments(), 250);
    }

    async toggleDone() {
        this.state.aFilters.include_done = !this.state.aFilters.include_done;
        await this.loadAssignments();
    }

    get aHeadline() {
        const k = this.state.aKpis || {};
        if (!k.total) { return ""; }
        const bits = [
            k.total === 1 ? _t("1 assignment") : _t("%s assignments", k.total),
        ];
        if (k.overdue) {
            bits.push(k.overdue === 1 ? _t("1 is past its date")
                : _t("%s are past their date", k.overdue));
        }
        return bits.join(" · ");
    }

    stateWord(key) {
        const row = (this.state.aStates || []).find((s) => s.key === key);
        return row ? row.label : key;
    }

    /** The chip class for a state — problem first, so late is loud. */
    stateClass(key) {
        if (key === "overdue") { return "pbtn-chip--bad"; }
        if (key === "excused") { return "pbtn-chip--wait"; }
        if (key === "done") { return "pbtn-chip--ok"; }
        if (key === "in_progress") { return "pbtn-chip--go"; }
        return "";
    }

    // ---------------------------------------------------- the assign dialog
    async openAssign(channelId = 0) {
        this.state.assign = true;
        this.state.assignCourse = channelId || (this.state.courses[0] || {}).id
            || 0;
        this.state.assignReason = "adhoc";
        this.state.assignProbation = false;
        this.state.assignTerm = "";
        this.state.assignPicked = [];
        this.state.assignDue = this.defaultDue();
        try {
            this.state.groups = await this.orm.call("pb.training",
                                                    "departments", []);
        } catch (e) {
            console.warn("pb_training: the group lists could not be read", e);
            this.state.groups = { departments: [], jobs: [] };
        }
        await this.searchAssignPeople();
    }

    /** Today plus whatever the company has set, as a yyyy-mm-dd string. */
    defaultDue() {
        const days = (this.state.aSwitches || {}).default_due_days || 14;
        const when = new Date();
        when.setDate(when.getDate() + days);
        return when.toISOString().slice(0, 10);
    }

    closeAssign() {
        this.state.assign = false;
        this.state.assignRows = [];
        this.state.assignPicked = [];
    }

    async searchAssignPeople() {
        this.state.assignBusy = true;
        try {
            this.state.assignRows = await this.orm.call(
                "pb.training", "search_people",
                [this.state.assignTerm, this.state.assignCourse]);
        } catch (e) {
            console.warn("pb_training: the people search failed", e);
            this.state.assignRows = [];
        } finally {
            this.state.assignBusy = false;
        }
    }

    onAssignTermInput(ev) {
        this.state.assignTerm = ev.target.value;
        clearTimeout(this._assignTimer);
        this._assignTimer = setTimeout(() => this.searchAssignPeople(), 220);
    }

    toggleAssignPick(id) {
        const at = this.state.assignPicked.indexOf(id);
        if (at === -1) { this.state.assignPicked.push(id); }
        else { this.state.assignPicked.splice(at, 1); }
    }

    isAssignPicked(id) { return this.state.assignPicked.includes(id); }

    get assignPickedWord() {
        const n = this.state.assignPicked.length;
        if (!n) { return _t("Nobody picked yet"); }
        return n === 1 ? _t("1 person picked") : _t("%s people picked", n);
    }

    /** Bulk ergonomics: a whole department, a whole job, everybody here. */
    async expand() {
        this.state.assignBusy = true;
        try {
            const res = await this.orm.call("pb.training", "expand_people",
                                            [this.state.expandKind,
                                             this.state.expandValue]);
            const ids = (res.people || []).map((p) => p.id);
            for (const id of ids) {
                if (!this.state.assignPicked.includes(id)) {
                    this.state.assignPicked.push(id);
                }
            }
            // The picked people have to be VISIBLE or the count is a claim
            // nobody can check.
            this.state.assignTerm = "";
            this.state.assignRows = (res.people || []).map((p) => ({
                id: p.id, name: p.name, partner_id: 0, email: "",
                on_it: false,
            }));
            this.notif.add(res.message, { type: "success" });
        } catch (e) {
            this.notif.add((e && e.data && e.data.message)
                || _t("That group could not be opened up."),
                           { type: "danger" });
        } finally {
            this.state.assignBusy = false;
        }
    }

    async confirmAssign() {
        if (!this.state.assignPicked.length || !this.state.assignCourse) {
            return;
        }
        const res = await this.actA("assign", {
            channel_id: this.state.assignCourse,
            employee_ids: this.state.assignPicked.slice(),
            reason: this.state.assignReason,
            due_date: this.state.assignDue || false,
            counts_for_probation: this.state.assignProbation,
        });
        if (res) { this.closeAssign(); }
    }

    /** The same dispatcher as `act`, but it refreshes the Assignments tab. */
    async actA(verb, payload = {}) {
        this.state.aBusy = true;
        try {
            const res = await this.orm.call("pb.training", "act",
                                            [verb, payload]);
            if (res && res.type) {
                await this.action.doAction(res);
                return res;
            }
            if (res && res.message) {
                this.notif.add(res.message, { type: "success" });
            }
            await this.loadAssignments();
            await this.load();
            return res;
        } catch (e) {
            this.notif.add((e && e.data && e.data.message)
                || _t("That did not work."), { type: "danger" });
            return null;
        } finally {
            this.state.aBusy = false;
        }
    }

    async dropAssignment(id) {
        await this.actA("drop", { assignment_id: id });
    }

    async openAssignment(id) {
        await this.actA("open_assignment", { assignment_id: id });
    }

    async openDelay(id) {
        await this.actA("open_delay", { delay_id: id });
    }

    async runReminders() {
        await this.actA("run_reminders", {});
    }
}

registry.category("actions").add("pb_training_board", PbTrainingBoard);
