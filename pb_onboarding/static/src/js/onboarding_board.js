/** @odoo-module **/
/**
 * `pb_onboarding_board` — the New joiners lens on the Lifecycle hub.
 *
 * The Journeys board answers "what is running". This one answers the question
 * an HR coordinator actually asks on a Monday morning: WHO IS ARRIVING, and is
 * anything about their arrival not ready. So a row is a PERSON, not a case:
 * their day, their progress, their buddy, their HR partner, their welcome
 * session, how complete their record is, and how they said it was going.
 *
 * The shape is `pb_people`'s and `pb_journeys`': an `AbstractModel` facade
 * behind every read, `props.embedded` dropping the H1 when the hub is already
 * saying "Lifecycle › New joiners" above it (W17), and the kit's `.pbim-*`
 * primitives for every surface so this screen re-tints with the rest of the
 * product and cannot drift into a second palette.
 *
 * WHAT THIS FILE DELIBERATELY DOES NOT DO: decide who may change anything.
 * `pb.onboarding._require_write()` is the boundary; `state.canWrite` only
 * decides whether a control is OFFERED, because an offer the server would
 * refuse is worse than no offer (W29).
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { useFilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

/** The verdict a candidate buddy wears, as a kit tone. */
const LEVEL_CLS = { pass: "ok", warn: "warn", fail: "err" };

/** How a joiner's last answer reads as a dot. */
const SCORE_CLS = { 1: "err", 2: "err", 3: "warn", 4: "ok", 5: "ok" };

const PAGE = 60;

export class PbOnboardingBoard extends Component {
    static template = "pb_onboarding.PbOnboardingBoard";
    static components = { PbFilterLayout };
    static props = ["*"];

    // A literal inside a template expression is never extracted for
    // translation, so the panel's placeholder comes through _t here.
    get searchLabel() { return _t("Search by name, team, buddy or HR contact…"); }

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");

        this.state = useState({
            loaded: false,
            allowed: true,
            canWrite: false,
            kpis: {},
            total: 0,

            // the board, one page at a time for the filter panel's state
            rows: [],
            listTotal: 0,
            listLoaded: false,
            listError: false,
            loadingMore: false,
            stepCounts: {},

            // the open joiner
            drawer: null,
            drawerBusy: false,

            // dialogs — one at a time, each one plain state
            buddy: null,
            temp: null,
        });

        // The shared filter panel (pb_filter_kit, FILTER W1): it owns the
        // filters, the counts and the views; this screen loads one page of
        // joiners for kit.query. A reader without lifecycle access is refused
        // by the server too, and the panel stays out of the way.
        this.kit = useFilterKit({
            model: "pb.onboarding",
            noun: _t("new joiners"),
            onChange: () => this.loadPage(),
        });
        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------------ read
    /** The head: access and the numbers line. */
    async load() {
        try {
            const d = await this.orm.call("pb.onboarding", "get_board", []);
            Object.assign(this.state, {
                allowed: d.allowed,
                canWrite: d.can_write,
                kpis: d.kpis || {},
                total: d.total || 0,
                loaded: true,
            });
        } catch (e) {
            // Reported, never swallowed into a decoration (W40).
            console.warn("pb_onboarding: could not read the board", e);
            this.state.loaded = true;
            this.state.allowed = false;
        }
    }

    /** One page of joiners for the panel's current filters. */
    async loadPage({ more = false } = {}) {
        if (this.kit.refusal) {
            this.state.listLoaded = true;
            return;
        }
        const q = this.kit.query;
        const offset = more ? this.state.rows.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call("pb.onboarding", "get_joiners_page", [], {
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
            console.error("pb_onboarding: the new joiners could not load", e);
            if (!more) {
                this.state.listError = true;
                this.state.listLoaded = true;
            }
            this.notif.add(_t("The new joiners could not load. Check your connection, then press Try again."),
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
     * the open joiner. The filters stay as they are. */
    async refresh() {
        await Promise.all([this.load(), this.kit.refresh()]);
        if (this.state.drawer) {
            await this.openJoiner(this.state.drawer.joiner.id);
        }
    }

    // ----------------------------------------------------- the quiet board
    //
    // One slim line of numbers instead of a row of tiles, and the three steps
    // a joiner moves through. A joiner is at EXACTLY ONE step (the server's
    // `_step_domains`), so the step counts add up. The figures and the steps
    // set the filter panel; pressing a lit one again clears it.
    glanceFilters() {
        // "Joining this week" is the view's own filters (the next 7 days), so
        // pressing the figure lights that tab.
        const view = this.kit.views.find((v) => v.key === "week");
        const week = view ? view.filters : { first_day: { preset: "next_7" } };
        return {
            joining: week,
            started: { step: ["settling", "done"] },
            nobuddy: { buddy: [false] },
            overdue: { overdue: ["yes"] },
            red: { pulse: ["red"] },
        };
    }

    get glance() {
        const k = this.state.kpis || {};
        const tone = (v, t) => (v ? t : "");
        const f = this.glanceFilters();
        const pick = (id) => () => this.kit.toggleFilters(f[id]);
        return [
            { key: "joining", n: k.joining || 0, label: _t("Joining this week"), tone: "",
              run: pick("joining") },
            { key: "started", n: k.started || 0, label: _t("Already started"), tone: tone(k.started, "green"),
              run: pick("started") },
            { key: "nobuddy", n: k.no_buddy || 0, label: _t("Still without a buddy"), tone: tone(k.no_buddy, "amber"),
              run: pick("nobuddy") },
            { key: "overdue", n: k.overdue || 0, label: _t("Steps overdue"), tone: tone(k.overdue, "rose"),
              run: pick("overdue") },
            { key: "red", n: k.red || 0, label: _t("Said they are struggling"), tone: tone(k.red, "rose"),
              run: pick("red") },
        ];
    }
    /** Which figure is lit: the one whose filters are exactly what is on. */
    get glanceOn() {
        if (!this.kit.loaded) { return ""; }
        for (const [key, f] of Object.entries(this.glanceFilters())) {
            if (this.kit.isExactly(f)) { return key; }
        }
        return "";
    }

    /** Where ONE card is, for its own "Step 2 of 3" line: before the first
     * day → settling in → checklist finished (the same rule the server's
     * `_step_domains` filters by). */
    stepOf(r) {
        const arrived = !!r.doj && r.days !== null && r.days <= 0;
        if (!arrived) { return "ready"; }
        return (r.progress || 0) >= 100 ? "done" : "settling";
    }

    get stepDefs() {
        return [
            { key: "ready", title: _t("Getting ready"), sub: _t("Before their first day") },
            { key: "settling", title: _t("Settling in"), sub: _t("Started, checklist still open") },
            { key: "done", title: _t("Checklist done"), sub: _t("Everything on the checklist is settled") },
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
                countLabel: count === 1 ? _t("1 new joiner") : _t("%s new joiners", this.fmtInt(count)),
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

    stepMeta(r) {
        const defs = this.stepDefs;
        const index = defs.findIndex((st) => st.key === this.stepOf(r));
        return {
            label: _t("Step %s of %s", index + 1, defs.length),
            title: defs[index].title,
            marks: defs.map((st, j) => (j < index ? "done" : j === index ? "here" : "")),
        };
    }

    // ------------------------------------------------------------ formatting
    scoreCls(score) { return SCORE_CLS[Number(score)] || "muted"; }
    levelCls(level) { return LEVEL_CLS[level] || "muted"; }

    day(value) {
        if (!value) { return "—"; }
        try {
            const d = new Date(value + "T00:00:00");
            return d.toLocaleDateString(undefined,
                { day: "numeric", month: "short" });
        } catch (e) { return value; }
    }

    monthLabel(value) {
        if (!value) { return ""; }
        try {
            const d = new Date(value + "-01T00:00:00");
            return d.toLocaleDateString(undefined,
                { month: "short", year: "numeric" });
        } catch (e) { return value; }
    }

    // ------------------------------------------------------------- the drawer
    async openJoiner(caseId) {
        this.state.drawerBusy = true;
        try {
            this.state.drawer = await this.orm.call(
                "pb.onboarding", "get_joiner", [caseId]);
        } catch (e) {
            this.fail(e);
            this.state.drawer = null;
        } finally {
            this.state.drawerBusy = false;
        }
    }

    closeDrawer() { this.state.drawer = null; }

    get drawerOpenTasks() {
        if (!this.state.drawer) { return []; }
        return this.state.drawer.tasks.filter(
            (t) => ["pending", "in_progress", "blocked"].includes(t.state));
    }

    get drawerDoneTasks() {
        if (!this.state.drawer) { return []; }
        return this.state.drawer.tasks.filter(
            (t) => ["done", "skipped"].includes(t.state));
    }

    // --------------------------------------------------------------- plumbing
    fail(e) {
        const msg = (e && e.data && e.data.message) || (e && e.message)
            || _t("That did not work. Try again in a moment.");
        this.notif.add(msg, { type: "danger" });
    }

    async call(method, args, okMessage) {
        try {
            const res = await this.orm.call("pb.onboarding", method, args);
            if (okMessage) { this.notif.add(okMessage, { type: "success" }); }
            return res === undefined ? true : res;
        } catch (e) {
            this.fail(e);
            return false;
        }
    }

    // ------------------------------------------------------ choose a buddy
    async buddyAsk(row) {
        this.state.buddy = {
            employeeId: row.employee_id,
            caseId: row.id,
            who: row.employee,
            term: "",
            results: [],
            busy: false,
        };
        await this.buddySearch();
    }

    async buddySearch() {
        const b = this.state.buddy;
        if (!b) { return; }
        try {
            b.results = await this.orm.call(
                "pb.onboarding", "buddy_candidates",
                [b.employeeId, b.term || ""]);
        } catch (e) {
            b.results = [];
        }
    }

    onBuddyInput(ev) {
        this.state.buddy.term = ev.target.value;
        this.buddySearch();
    }

    async buddyPick(candidate) {
        const b = this.state.buddy;
        if (!b || b.busy) { return; }
        // A `fail` candidate is SHOWN with its reason but cannot be chosen —
        // the server refuses independently, so this only spares the round trip
        // and lets the message be about the person rather than about a rule.
        if (candidate.level === "fail") {
            this.notif.add(
                _t("%s cannot be a buddy — see the reason on their card.",
                   candidate.name),
                { type: "warning" });
            return;
        }
        b.busy = true;
        const res = await this.call(
            "buddy_choose", [b.employeeId, candidate.id, b.caseId]);
        if (res) {
            this.state.buddy = null;
            this.notif.add(
                _t("%(who)s is now the buddy — %(n)s catch-up(s) are in the diary.",
                   { who: res.buddy || candidate.name, n: res.connects || 0 }),
                { type: "success" });
            await this.refresh();
        } else if (this.state.buddy) {
            this.state.buddy.busy = false;
        }
    }

    buddyCancel() { this.state.buddy = null; }

    // ------------------------------------------------ hand a buddy over
    async tempAsk(row) {
        this.state.temp = {
            employeeId: row.employee_id,
            who: row.employee,
            term: "",
            results: [],
            pickId: 0,
            pickName: "",
            from: "",
            to: "",
        };
        await this.tempSearch();
    }

    async tempSearch() {
        const t = this.state.temp;
        if (!t) { return; }
        try {
            t.results = await this.orm.call(
                "pb.onboarding", "buddy_candidates",
                [t.employeeId, t.term || ""]);
        } catch (e) {
            t.results = [];
        }
    }

    onTempInput(ev) {
        this.state.temp.term = ev.target.value;
        this.state.temp.pickId = 0;
        this.tempSearch();
    }

    tempPick(candidate) {
        this.state.temp.pickId = candidate.id;
        this.state.temp.pickName = candidate.name;
        this.state.temp.results = [];
        this.state.temp.term = candidate.name;
    }

    onTempFrom(ev) { this.state.temp.from = ev.target.value; }
    onTempTo(ev) { this.state.temp.to = ev.target.value; }

    async tempSave() {
        const t = this.state.temp;
        if (!t) { return; }
        if (!t.pickId) {
            this.notif.add(_t("Choose who is standing in first."),
                           { type: "warning" });
            return;
        }
        const res = await this.call("buddy_temp",
            [t.employeeId, t.pickId, t.from || false, t.to || false]);
        if (res) {
            this.state.temp = null;
            this.notif.add(
                _t("%(who)s is covering — %(n)s catch-up(s) moved across.",
                   { who: res.temp || "", n: res.moved || 0 }),
                { type: "success" });
            await this.refresh();
        }
    }

    tempCancel() { this.state.temp = null; }

    // ------------------------------------------------------------- the doing
    async runStep(task) {
        if (await this.call("run_step_now", [task.id],
                            _t("Sent — and the step is ticked."))) {
            await this.refresh();
        }
    }

    async backfillHrbp() {
        const res = await this.call("backfill_hrbp", []);
        if (res) {
            this.notif.add(
                res.touched
                    ? _t("%s person(s) now have an HR partner.", res.touched)
                    : _t("Everybody the rules cover already has one."),
                { type: "success" });
            await this.refresh();
        }
    }

    async runAutomation() {
        const res = await this.call("run_automation", []);
        if (res) {
            this.notif.add(
                _t("%(steps)s step(s) ran, %(sent)s check(s) sent.",
                   { steps: res.auto_steps || 0, sent: res.pulses_sent || 0 }),
                { type: "success" });
            await this.refresh();
        }
    }

    // ------------------------------------------------------------ the doors
    openRules() {
        this.action.doAction("pb_onboarding.action_pb_hrbp_rule");
    }

    openBatches() {
        this.action.doAction("pb_onboarding.action_pb_orientation_batch");
    }
}

registry.category("actions").add("pb_onboarding_board", PbOnboardingBoard);
