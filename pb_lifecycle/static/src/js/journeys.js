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
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";
import { useFilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

const PAGE = 60;
// What each figure on the numbers line means as a filter: the same filters as
// the built-in views, so pressing a figure lights the matching tab.
const GLANCE_FILTERS = {
    active: { status: ["active"] },
    overdue: { late: ["yes"] },
};

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
    static components = { HubBackChip, PbFilterLayout };
    static props = ["*"];

    // A literal inside a template expression is never extracted for
    // translation, so the panel's placeholder comes through _t here.
    get searchLabel() { return _t("Search by name, team, job or checklist…"); }

    setup() {
        // NAV P2: Journeys opens on its own (from Settings › HR, or an old
        // Lifecycle link), so it draws the return door it was handed.
        this.back = this.props.embedded ? null : hubBack(this.props);
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");

        this.state = useState({
            loaded: false,
            allowed: true,
            canWrite: false,
            canAdmin: false,
            kpis: {},
            total: 0,
            types: [],
            templates: [],
            states: [],

            // the board, one page at a time for the filter panel's state
            rows: [],
            listTotal: 0,
            listLoaded: false,
            listError: false,
            loadingMore: false,
            stepCounts: {},

            // the open journey
            drawer: null,
            drawerBusy: false,

            // dialogs — one at a time, and each one is plain state
            start: null,
            prompt: null,
            picker: null,
            addStep: null,
        });

        // The shared filter panel (pb_filter_kit, FILTER W1): it owns the
        // filters, the counts and the views; this screen loads one page of
        // journeys for kit.query. A reader without lifecycle access is
        // refused by the server and the panel stays out of the way.
        this.kit = useFilterKit({
            model: "pb.journeys",
            noun: _t("journeys"),
            onChange: () => this.loadPage(),
        });
        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------------ read
    /** The head: access, the numbers line, the start dialog's lists. */
    async load() {
        try {
            const d = await this.orm.call("pb.journeys", "get_board", []);
            Object.assign(this.state, {
                allowed: d.allowed,
                canWrite: d.can_write,
                canAdmin: d.can_admin,
                kpis: d.kpis || {},
                total: d.total || 0,
                types: d.types || [],
                templates: d.templates || [],
                states: d.states || [],
                loaded: true,
            });
        } catch (e) {
            // Reported, never swallowed into a decoration (W40).
            console.warn("pb_journeys: could not read the board", e);
            this.state.loaded = true;
            this.state.allowed = false;
        }
    }

    /** One page of journeys for the panel's current filters. */
    async loadPage({ more = false } = {}) {
        if (this.kit.refusal) {
            this.state.listLoaded = true;
            return;
        }
        const q = this.kit.query;
        const offset = more ? this.state.rows.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call("pb.journeys", "get_journeys_page", [], {
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
            console.error("pb_journeys: the board could not load", e);
            if (!more) {
                this.state.listError = true;
                this.state.listLoaded = true;
            }
            this.notif.add(_t("The journeys could not load. Check your connection, then press Try again."),
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

    /** Read the board again in place: the numbers, the page, the counts, and
     * the open journey. The filters stay as they are. */
    async refresh() {
        await Promise.all([this.load(), this.kit.refresh()]);
        if (this.state.drawer) { await this.openCase(this.state.drawer.case.id); }
    }

    // ----------------------------------------------------- the quiet board
    //
    // One slim line of numbers instead of a row of tiles, and the three steps
    // a journey moves through. A journey is at EXACTLY ONE step (the server's
    // `_step_domains`), so the step counts add up. The figures and the steps
    // set the filter panel; pressing a lit one again clears it.
    get glance() {
        const k = this.state.kpis || {};
        const tone = (v, t) => (v ? t : "");
        const pick = (id) => () => this.kit.toggleFilters(GLANCE_FILTERS[id]);
        return [
            { key: "active", n: k.active || 0, label: _t("Running now"), tone: "",
              run: pick("active") },
            { key: "overdue", n: k.overdue || 0, label: _t("Steps overdue"), tone: tone(k.overdue, "rose"),
              run: pick("overdue") },
            { key: "due", n: k.due_week || 0, label: _t("Due in 7 days"), tone: "", run: null },
            { key: "red", n: k.red_flags || 0, label: _t("Need attention"), tone: tone(k.red_flags, "rose"), run: null },
            { key: "letters", n: k.letters_month || 0, label: _t("Letters this month"), tone: "", run: null },
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

    get stepDefs() {
        return [
            { key: "start", title: _t("Not started"), sub: _t("Set up, not running yet") },
            { key: "running", title: _t("Under way"), sub: _t("Steps still to do") },
            { key: "wrap", title: _t("Nothing left to do"), sub: _t("Every step settled, ready to close") },
        ];
    }

    /** Counted by the server for the panel's state (each step against every
     * OTHER filter, the panel's own rule), with how many of each run late. */
    get steps() {
        const counts = this.state.stepCounts || {};
        return this.stepDefs.map((st, i) => {
            const c = counts[st.key] || {};
            const count = c.n || 0;
            const late = c.late || 0;
            return {
                ...st,
                n: String(i + 1).padStart(2, "0"),
                count,
                countLabel: count === 1 ? _t("1 journey") : _t("%s journeys", this.fmtInt(count)),
                flag: !late ? "" : late === 1 ? _t("1 with steps overdue") : _t("%s with steps overdue", late),
                flagTone: "rose",
                on: this.kit.loaded && this.kit.isOn("step", st.key),
            };
        });
    }

    /** A step pressed: list that step. Pressed again: back to the start view
     * when it was the only filter, otherwise only that step comes off. */
    pickStep(key) {
        const kit = this.kit;
        if (kit.isOn("step", key) && !kit.isExactly({ step: [key] })) {
            kit.toggle("step", key);
            return;
        }
        kit.toggleFilters({ step: [key] });
    }

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
            await Promise.all([this.load(), this.kit.refresh()]);
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
