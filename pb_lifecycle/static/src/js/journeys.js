/** @odoo-module **/
/**
 * `pb_journeys` — the Journeys cockpit.
 *
 * One board of every journey running in the companies you work in, and one
 * drawer that opens the whole of a single one: the steps in the order they come
 * due, who owns each, what is late, the check-ins beside them and the letters
 * that came out of it.
 *
 * The shape is `pb_people`'s, deliberately: an `AbstractModel` facade behind
 * every read, `props.embedded` dropping the H1 when the hub is already saying
 * "Lifecycle › Journeys" above it (W17), and the kit's `.pbim-*` primitives for
 * every surface so this screen re-tints with the rest of the product and cannot
 * drift into a second palette.
 *
 * WHAT THIS FILE DELIBERATELY DOES NOT DO: decide who may change a journey. The
 * facade's `_require_write()` is the boundary; `state.canWrite` only decides
 * whether a control is OFFERED, because an offer the server would refuse is
 * worse than no offer (W29).
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const STATE_CLS = {
    done: "ok", pending: "info", in_progress: "warn", blocked: "err",
    skipped: "muted",
};

const CASE_STATE_CLS = {
    active: "info", on_hold: "warn", draft: "muted", done: "ok",
    cancelled: "muted",
};

/** The icon a journey type wears, everywhere it appears. */
const TYPE_IC = {
    onboarding: "sunrise",
    offboarding: "logIn",
    probation: "shieldCheck",
    pip: "trendingUp",
    conversion: "arrowLeftRight",
    other: "briefcase",
};

export class PbJourneys extends Component {
    static template = "pb_lifecycle.PbJourneys";
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
            kpis: {},
            rows: [],
            types: [],
            templates: [],
            states: [],
            typeCounts: {},
            capped: false,

            // filters
            q: "",
            type: "all",
            lifeState: "all",
            lateOnly: false,

            // the open journey
            drawer: null,
            drawerBusy: false,

            // dialogs — one at a time, and each one is plain state
            start: null,
            prompt: null,
            picker: null,
            addStep: null,
        });

        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------------ read
    async load() {
        try {
            const d = await this.orm.call("pb.journeys", "get_board", []);
            Object.assign(this.state, {
                allowed: d.allowed,
                canWrite: d.can_write,
                canAdmin: d.can_admin,
                kpis: d.kpis || {},
                rows: d.rows || [],
                types: d.types || [],
                templates: d.templates || [],
                states: d.states || [],
                typeCounts: d.type_counts || {},
                capped: !!d.capped,
                loaded: true,
            });
        } catch (e) {
            // Reported, never swallowed into a decoration (W40).
            console.warn("pb_journeys: could not read the board", e);
            this.state.loaded = true;
            this.state.allowed = false;
        }
    }

    async refresh() {
        this.state.loaded = false;
        await this.load();
        if (this.state.drawer) { await this.openCase(this.state.drawer.case.id); }
    }

    // --------------------------------------------------------------- filters
    get visibleRows() {
        const q = (this.state.q || "").trim().toLowerCase();
        return this.state.rows.filter((r) => {
            if (this.state.type !== "all" && r.type !== this.state.type) {
                return false;
            }
            if (this.state.lifeState !== "all"
                && r.state !== this.state.lifeState) {
                return false;
            }
            if (this.state.lateOnly && !r.late && !r.overdue) { return false; }
            if (!q) { return true; }
            return (r.employee + " " + r.type_label + " " + (r.dept || "")
                + " " + (r.job || "")).toLowerCase().includes(q);
        });
    }

    get hasFilters() {
        return this.state.q || this.state.type !== "all"
            || this.state.lifeState !== "all" || this.state.lateOnly;
    }

    clearFilters() {
        Object.assign(this.state,
            { q: "", type: "all", lifeState: "all", lateOnly: false });
    }

    setType(id) { this.state.type = this.state.type === id ? "all" : id; }
    setState(id) { this.state.lifeState = this.state.lifeState === id ? "all" : id; }
    toggleLate() { this.state.lateOnly = !this.state.lateOnly; }
    onSearch(ev) { this.state.q = ev.target.value; }

    // ------------------------------------------------------------ formatting
    typeIcon(type) { return ic(TYPE_IC[type] || "briefcase", 15); }
    stateCls(s) { return STATE_CLS[s] || "muted"; }
    caseStateCls(s) { return CASE_STATE_CLS[s] || "muted"; }

    day(value) {
        if (!value) { return "—"; }
        try {
            const d = new Date(value + "T00:00:00");
            return d.toLocaleDateString(undefined,
                { day: "numeric", month: "short" });
        } catch (e) { return value; }
    }

    /** "3 days late" / "in 2 days" / "today" — the words, not the arithmetic. */
    relative(value) {
        if (!value) { return ""; }
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const d = new Date(value + "T00:00:00");
        const days = Math.round((d - today) / 86400000);
        if (days === 0) { return _t("today"); }
        if (days === 1) { return _t("tomorrow"); }
        if (days === -1) { return _t("1 day late"); }
        if (days < 0) { return _t("%s days late", -days); }
        return _t("in %s days", days);
    }

    // ------------------------------------------------------------- the drawer
    async openCase(caseId) {
        this.state.drawerBusy = true;
        try {
            this.state.drawer = await this.orm.call(
                "pb.journeys", "get_case", [caseId]);
        } catch (e) {
            this.fail(e);
            this.state.drawer = null;
        } finally {
            this.state.drawerBusy = false;
        }
    }

    closeDrawer() { this.state.drawer = null; }

    get openTasks() {
        if (!this.state.drawer) { return []; }
        return this.state.drawer.tasks.filter(
            (t) => ["pending", "in_progress", "blocked"].includes(t.state));
    }

    get settledTasks() {
        if (!this.state.drawer) { return []; }
        return this.state.drawer.tasks.filter(
            (t) => ["done", "skipped"].includes(t.state));
    }

    // --------------------------------------------------------------- actions
    fail(e) {
        const msg = (e && e.data && e.data.message) || (e && e.message)
            || _t("That did not work. Try again in a moment.");
        this.notif.add(msg, { type: "danger" });
    }

    async call(method, args, okMessage) {
        try {
            await this.orm.call("pb.journeys", method, args);
            if (okMessage) { this.notif.add(okMessage, { type: "success" }); }
            return true;
        } catch (e) {
            this.fail(e);
            return false;
        }
    }

    async taskDone(taskId) {
        if (await this.call("task_done", [taskId], _t("Marked done."))) {
            await this.refresh();
        }
    }

    taskSkipAsk(task) {
        this.state.prompt = {
            title: _t("Skip this step"),
            label: _t("Why is it being skipped? Everyone reading the journey later will see this."),
            placeholder: _t("e.g. the laptop was already issued"),
            value: "",
            kind: "skip",
            taskId: task.id,
        };
    }

    async promptOk() {
        const p = this.state.prompt;
        if (!p) { return; }
        this.state.prompt = null;
        if (p.kind === "skip") {
            if (await this.call("task_skip", [p.taskId, p.value],
                                _t("Step skipped."))) {
                await this.refresh();
            }
        }
    }

    promptCancel() { this.state.prompt = null; }
    onPromptInput(ev) { this.state.prompt.value = ev.target.value; }

    // ---- give a step to somebody else ----
    reassignAsk(task) {
        this.state.picker = { taskId: task.id, term: "", results: [] };
        this.pickerSearch();
    }

    async pickerSearch() {
        const p = this.state.picker;
        if (!p) { return; }
        try {
            p.results = await this.orm.call(
                "pb.journeys", "search_users", [p.term || ""]);
        } catch (e) {
            p.results = [];
        }
    }

    onPickerInput(ev) {
        this.state.picker.term = ev.target.value;
        this.pickerSearch();
    }

    async pickUser(userId) {
        const p = this.state.picker;
        this.state.picker = null;
        if (await this.call("task_reassign", [p.taskId, userId],
                            _t("Step handed over."))) {
            await this.refresh();
        }
    }

    // ---- add a step nobody thought of ----
    addStepAsk() {
        this.state.addStep = { name: "", description: "", due: "", blocking: false };
    }

    async addStepSave() {
        const a = this.state.addStep;
        if (!a || !a.name.trim()) {
            this.notif.add(_t("Give the step a name first."), { type: "warning" });
            return;
        }
        this.state.addStep = null;
        if (await this.call("add_task",
                            [this.state.drawer.case.id,
                             { name: a.name, description: a.description,
                               due_date: a.due || false,
                               blocking_ff: a.blocking }],
                            _t("Step added."))) {
            await this.refresh();
        }
    }

    async caseAction(verb, okMessage) {
        if (!this.state.drawer) { return; }
        if (await this.call("case_action",
                            [this.state.drawer.case.id, verb], okMessage)) {
            await this.refresh();
        }
    }

    async copyLink(link) {
        try {
            await navigator.clipboard.writeText(link);
            this.notif.add(_t("Link copied — paste it into an email."),
                           { type: "success" });
        } catch (e) {
            this.notif.add(link, { type: "info", sticky: true });
        }
    }

    // ---------------------------------------------------- start a journey
    startAsk() {
        this.state.start = {
            term: "", results: [], empId: 0, empName: "",
            caseType: "onboarding", templateId: 0, anchor: "", busy: false,
        };
        this.startSearch();
    }

    async startSearch() {
        const s = this.state.start;
        if (!s) { return; }
        try {
            s.results = await this.orm.call(
                "pb.journeys", "search_employees", [s.term || ""]);
        } catch (e) {
            s.results = [];
        }
    }

    onStartInput(ev) {
        this.state.start.term = ev.target.value;
        this.state.start.empId = 0;
        this.startSearch();
    }

    pickEmployee(emp) {
        this.state.start.empId = emp.id;
        this.state.start.empName = emp.name;
        this.state.start.term = emp.name;
        this.state.start.results = [];
    }

    onStartType(ev) {
        this.state.start.caseType = ev.target.value;
        this.state.start.templateId = 0;
    }

    onStartTemplate(ev) {
        this.state.start.templateId = Number(ev.target.value) || 0;
    }

    onStartAnchor(ev) { this.state.start.anchor = ev.target.value; }

    /** The checklists that fit the chosen type — the rest would only mislead. */
    get startTemplates() {
        const s = this.state.start;
        if (!s) { return []; }
        return this.state.templates.filter((t) => t.case_type === s.caseType);
    }

    get anchorLabel() {
        const s = this.state.start;
        const map = {
            onboarding: _t("Joining date"),
            offboarding: _t("Last working day"),
            probation: _t("Probation end"),
            pip: _t("Review date"),
            conversion: _t("Change takes effect"),
            other: _t("Key date"),
        };
        return (s && map[s.caseType]) || _t("Key date");
    }

    async startSubmit() {
        const s = this.state.start;
        if (!s.empId) {
            this.notif.add(_t("Choose the person first."), { type: "warning" });
            return;
        }
        s.busy = true;
        try {
            const res = await this.orm.call("pb.journeys", "open_case", [
                s.empId, s.caseType, s.templateId || false, s.anchor || false,
            ]);
            this.state.start = null;
            this.notif.add(
                res.steps
                    ? _t("Journey started — %s step(s) are on the list.",
                         res.steps)
                    : _t("Journey started. There is no checklist for this type"
                         + " yet, so add the steps you need."),
                { type: "success" });
            await this.load();
            await this.openCase(res.case_id);
        } catch (e) {
            this.fail(e);
        } finally {
            if (this.state.start) { this.state.start.busy = false; }
        }
    }

    startCancel() { this.state.start = null; }

    // ------------------------------------------------------------ the doors
    openTemplates() {
        this.action.doAction("pb_lifecycle.action_journey_template");
    }

    openLetters() {
        this.action.doAction("pb_lifecycle.action_hr_letter");
    }
}

registry.category("actions").add("pb_journeys", PbJourneys);
