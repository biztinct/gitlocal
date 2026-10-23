/** @odoo-module **/
/**
 * Learning › PATHS (LEARNING L3) — learning paths.
 *
 * HERO MOMENT: every path card draws its STATION LINE (the shared quiet-board
 * QuietSteps): the stations are the steps plus "Finished", the count on each
 * is how many people are at that step right now, and a rose "N late" flag
 * shows where people are stuck. Pressing a station opens the path page on
 * the people at that step. Every enrolled person is at exactly one station,
 * so the counts add up to the people on the path.
 *
 * The path page: the big station line, filter chips (Not started · Under way
 * · Late · Finished), search, and one row per person with a dot rail (done
 * tick, now ring, waiting grey), "Open their courses" and "Remove from path".
 *
 * Two drawers: "New path" / "Edit path" (name, purpose, one sentence, the
 * steps — add a course, drag or move up/down, a gate per step — day-one
 * audience, days, trial period) and "Enrol people" (picked people, a
 * department, a job or everybody; why; by when).
 *
 * Reads `pb.training.paths_board` / `path_page` / `path_lists` (gated like the
 * board: a reader outside the training team gets `allowed: false` and a
 * sentence). Writes go through the board's one verb, `pb.training.act`.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { openHub } from "@pb_hub/js/hub_nav";
import { LEARNING_HUB_XMLID } from "@pb_learning_hub/js/learning_hub";

/** The context key the Paths lens reads its arrival filter from. */
export const PATH_STATE_KEY = "pb_training_path_state";
/** The context key the Assigned lens reads a search from ("Open their courses"). */
export const TRAINING_TERM_KEY = "pb_training_term";

const STATE_ORDER = ["not_started", "in_progress", "overdue", "done"];

function blankPath() {
    return { id: 0, name: "", purpose: "role", blurb: "", due_days: 90,
             counts_for_probation: false, day_one: false,
             department_ids: [], job_ids: [], steps: [] };
}

function blankEnrol() {
    return { mode: "people", picked: [], department_id: 0, job_id: 0,
             reason: "adhoc", due_date: "" };
}

export class PbPathsLens extends Component {
    static template = "pb_training.PbPathsLens";
    static props = {
        embedded: { type: Boolean, optional: true },
        startState: { type: String, optional: true },
        "*": true,
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.state = useState({
            loaded: false,
            failed: false,
            data: { paths: [], kpis: {} },
            onlyLate: this.props.startState === "overdue",
            page: null,
            pageBusy: false,
            pf: { state: "", step: "", q: "" },
            lists: null,
            drawer: "",
            form: blankPath(),
            courseTerm: "",
            dragFrom: -1,
            enrol: blankEnrol(),
            enrolPath: null,
            peopleTerm: "",
            people: [],
            saving: false,
            acting: 0,
        });
        onWillStart(() => this.load());
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------- reading
    async load() {
        this.state.failed = false;
        try {
            this.state.data = await this.orm.call("pb.training", "paths_board", []);
        } catch (e) {
            console.warn("pb_training: the learning paths could not be read", e);
            this.state.failed = true;
        } finally {
            this.state.loaded = true;
        }
    }

    async retry() {
        this.state.loaded = false;
        await this.load();
    }

    get data() { return this.state.data || {}; }
    get allowed() { return this.data.allowed !== false; }
    get kpis() { return this.data.kpis || {}; }

    get cards() {
        const all = this.data.paths || [];
        return this.state.onlyLate ? all.filter((c) => c.overdue > 0) : all;
    }

    showEveryPath() { this.state.onlyLate = false; }

    async ensureLists() {
        if (!this.state.lists) {
            try {
                this.state.lists = await this.orm.call("pb.training", "path_lists", []);
            } catch (e) {
                console.warn("pb_training: the path lists could not be read", e);
                this.state.lists = { courses: [], departments: [], jobs: [], purposes: [], reasons: [] };
            }
        }
        return this.state.lists;
    }

    get lists() { return this.state.lists || { courses: [], departments: [], jobs: [], purposes: [], reasons: [] }; }

    // ------------------------------------------------------------- one path
    /**
     * The station handler for one card. Built HERE, at render time: an arrow
     * written in the template that names the loop variable is called later
     * inside QuietSteps' own `t-call` context, where the loop variable is
     * gone (found in the local walk).
     */
    stationPicker(pathId) { return (key) => this.openPath(pathId, key); }

    async openPath(pathId, step = "") {
        this.state.pf = { state: this.state.onlyLate ? "overdue" : "", step: step || "", q: "" };
        this.state.page = { id: pathId, loading: true };
        await this.loadPage(pathId);
    }

    async loadPage(pathId) {
        const id = pathId || (this.state.page && this.state.page.id);
        if (!id) { return; }
        this.state.pageBusy = true;
        try {
            this.state.page = await this.orm.call("pb.training", "path_page", [id, { ...this.state.pf }]);
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That path could not be read just now."), { type: "danger" });
            this.state.page = null;
        } finally {
            this.state.pageBusy = false;
        }
    }

    closePage() {
        this.state.page = null;
        this.load();
    }

    get page() { return this.state.page; }

    pickStation(key) {
        this.state.pf.step = this.state.pf.step === key ? "" : key;
        this.loadPage();
    }

    setStateFilter(key) {
        this.state.pf.state = this.state.pf.state === key ? "" : key;
        this.loadPage();
    }

    onPageSearch(ev) {
        this.state.pf.q = ev.target.value;
        clearTimeout(this._pageTimer);
        this._pageTimer = setTimeout(() => this.loadPage(), 250);
    }

    clearPageFilters() {
        this.state.pf = { state: "", step: "", q: "" };
        this.loadPage();
    }

    get anyPageFilter() {
        const f = this.state.pf;
        return !!(f.state || f.step || f.q);
    }

    stateLabel(key) {
        return { not_started: _t("Not started"), in_progress: _t("Under way"),
                 overdue: _t("Late"), done: _t("Finished") }[key] || key;
    }

    get stateChips() {
        const counts = (this.page && this.page.counts) || {};
        return STATE_ORDER.map((key) => ({ key, label: this.stateLabel(key), n: counts[key] || 0 }));
    }

    stateClass(key) {
        return { overdue: "is-bad", done: "is-ok", in_progress: "is-go" }[key] || "";
    }

    railStyle(row) { return `--pbpt-cols: ${Math.max((row.rail || []).length, 1)};`; }

    railTitle(dot) {
        const word = { done: _t("Finished"), now: _t("On it now"), next: _t("Open"), waits: _t("Waiting") }[dot.state] || "";
        return `${dot.name} — ${word}`;
    }

    get shownWords() {
        const p = this.page || {};
        const n = p.total || 0;
        if (p.truncated) { return _t("Showing the first 200 of %s people — narrow it with a filter", n); }
        return n === 1 ? _t("1 person shown") : _t("%s people shown", n);
    }

    /** "Open their courses": the Assigned lens, searched on their name. */
    openCourses(row) {
        openHub(this.action, {
            xmlid: LEARNING_HUB_XMLID,
            lens: "assigned",
            context: { [TRAINING_TERM_KEY]: row.employee },
        });
    }

    async act(verb, payload, key = -1) {
        this.state.acting = key;
        try {
            const res = await this.orm.call("pb.training", "act", [verb, payload]);
            if (res && res.message) {
                this.notif.add(res.message, { type: res.type || "success" });
            }
            return res || {};
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
            return null;
        } finally {
            this.state.acting = 0;
        }
    }

    async unenrol(row) {
        const res = await this.act("unenrol_path", { enrolment_id: row.enrolment_id }, row.enrolment_id);
        if (res) { await this.loadPage(); }
    }

    async archive(card) {
        const res = await this.act("archive_path", { path_id: card.id }, card.id);
        if (res) {
            this.state.page = null;
            await this.load();
        }
    }

    async restore(row) {
        const res = await this.act("archive_path", { path_id: row.id }, row.id);
        if (res) { await this.load(); }
    }

    // ------------------------------------------------------------- the path drawer
    async newPath() {
        await this.ensureLists();
        Object.assign(this.state, { drawer: "path", form: blankPath(), courseTerm: "" });
    }

    async editPath(card) {
        await this.ensureLists();
        const v = JSON.parse(JSON.stringify(card.values || {}));
        Object.assign(this.state, { drawer: "path", form: Object.assign(blankPath(), v), courseTerm: "" });
    }

    closeDrawer() { this.state.drawer = ""; }

    setField(field, ev, kind = "text") {
        let value = ev.target.value;
        if (kind === "int") { value = Number(value) || 0; }
        if (kind === "bool") { value = !!ev.target.checked; }
        this.state.form[field] = value;
    }

    course(id) { return (this.lists.courses || []).find((c) => c.id === id) || { id, name: "", published: true }; }

    get courseMatches() {
        const taken = new Set(this.state.form.steps.map((s) => s.channel_id));
        const fold = (t) => (t || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase();
        const needle = fold(this.state.courseTerm);
        return (this.lists.courses || [])
            .filter((c) => !taken.has(c.id) && (!needle || fold(c.name).includes(needle)))
            .slice(0, 12);
    }

    onCourseTerm(ev) { this.state.courseTerm = ev.target.value; }

    addStep(c) {
        this.state.form.steps.push({ channel_id: c.id, gate: false, due_days: 0 });
        this.state.courseTerm = "";
    }

    removeStep(i) { this.state.form.steps.splice(i, 1); }

    moveStep(i, delta) {
        const steps = this.state.form.steps;
        const j = i + delta;
        if (j < 0 || j >= steps.length) { return; }
        const [row] = steps.splice(i, 1);
        steps.splice(j, 0, row);
    }

    toggleGate(i) { this.state.form.steps[i].gate = !this.state.form.steps[i].gate; }

    setStepDays(i, ev) { this.state.form.steps[i].due_days = Math.max(Number(ev.target.value) || 0, 0); }

    // drag to reorder (the keyboard has the up / down buttons)
    onDragStart(i, ev) {
        this.state.dragFrom = i;
        if (ev.dataTransfer) { ev.dataTransfer.effectAllowed = "move"; ev.dataTransfer.setData("text/plain", String(i)); }
    }

    onDragOver(ev) { ev.preventDefault(); }

    onDrop(i, ev) {
        ev.preventDefault();
        const from = this.state.dragFrom;
        this.state.dragFrom = -1;
        if (from < 0 || from === i) { return; }
        const steps = this.state.form.steps;
        const [row] = steps.splice(from, 1);
        steps.splice(i, 0, row);
    }

    addTo(field, ev) {
        const id = Number(ev.target.value) || 0;
        if (id && !this.state.form[field].includes(id)) { this.state.form[field].push(id); }
        ev.target.value = "0";
    }

    removeFrom(field, id) {
        this.state.form[field] = this.state.form[field].filter((x) => x !== id);
    }

    nameOf(listKey, id) {
        const row = (this.lists[listKey] || []).find((x) => x.id === id);
        return row ? row.name : "";
    }

    get pathHint() {
        const f = this.state.form;
        if (!f.name.trim()) { return _t("Start with a name people will recognise."); }
        if (!f.steps.length) { return _t("Add at least one course."); }
        return "";
    }

    get canSavePath() { return !this.pathHint && !this.state.saving; }

    async savePath() {
        if (!this.canSavePath) { return; }
        this.state.saving = true;
        try {
            const res = await this.orm.call("pb.training", "act", ["save_path", this.state.form]);
            this.notif.add((res && res.message) || _t("Saved."), { type: "success" });
            this.state.drawer = "";
            await this.load();
            if (this.state.page) { await this.loadPage(); }
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    // ------------------------------------------------------------- the enrol drawer
    async openEnrol(card) {
        await this.ensureLists();
        Object.assign(this.state, { drawer: "enrol", enrol: blankEnrol(), enrolPath: card, peopleTerm: "", people: [] });
        await this.searchPeople();
    }

    setEnrol(field, ev, kind = "text") {
        let value = ev.target.value;
        if (kind === "int") { value = Number(value) || 0; }
        this.state.enrol[field] = value;
    }

    setMode(mode) { this.state.enrol.mode = mode; }

    async searchPeople() {
        try {
            this.state.people = await this.orm.call("pb.training", "search_people", [this.state.peopleTerm]);
        } catch (e) {
            console.warn("pb_training: the people search failed", e);
            this.state.people = [];
        }
    }

    onPeopleTerm(ev) {
        this.state.peopleTerm = ev.target.value;
        clearTimeout(this._peopleTimer);
        this._peopleTimer = setTimeout(() => this.searchPeople(), 220);
    }

    isPicked(emp) { return this.state.enrol.picked.some((p) => p.id === emp.id); }

    togglePerson(emp) {
        const list = this.state.enrol.picked;
        const at = list.findIndex((p) => p.id === emp.id);
        if (at >= 0) { list.splice(at, 1); } else { list.push({ id: emp.id, name: emp.name }); }
    }

    get canEnrol() {
        const e = this.state.enrol;
        if (this.state.saving) { return false; }
        if (e.mode === "people") { return e.picked.length > 0; }
        if (e.mode === "department") { return !!e.department_id; }
        if (e.mode === "job") { return !!e.job_id; }
        return e.mode === "everyone";
    }

    get dueHint() {
        const p = this.state.enrolPath;
        const days = (p && p.values && p.values.due_days) || 90;
        return _t("Leave it empty and the whole path is due %s days from today.", days);
    }

    async saveEnrol() {
        if (!this.canEnrol) { return; }
        const e = this.state.enrol;
        const payload = { path_id: this.state.enrolPath.id, reason: e.reason, due_date: e.due_date || false };
        if (e.mode === "people") { payload.employee_ids = e.picked.map((p) => p.id); }
        if (e.mode === "department") { payload.department_id = e.department_id; }
        if (e.mode === "job") { payload.job_id = e.job_id; }
        if (e.mode === "everyone") { payload.everyone = true; }
        this.state.saving = true;
        try {
            const res = await this.orm.call("pb.training", "act", ["enrol_path", payload]);
            this.notif.add((res && res.message) || _t("Done."), { type: (res && res.type) || "success" });
            this.state.drawer = "";
            await this.load();
            if (this.state.page) { await this.loadPage(); }
        } catch (err) {
            this.notif.add((err && err.data && err.data.message) || _t("That did not work."), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }
}
