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

/** The verdict a candidate buddy wears, as a kit tone. */
const LEVEL_CLS = { pass: "ok", warn: "warn", fail: "err" };

/** How a joiner's last answer reads as a dot. */
const SCORE_CLS = { 1: "err", 2: "err", 3: "warn", 4: "ok", 5: "ok" };

export class PbOnboardingBoard extends Component {
    static template = "pb_onboarding.PbOnboardingBoard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");

        this.state = useState({
            loaded: false,
            allowed: true,
            canWrite: false,
            kpis: {},
            rows: [],
            countries: [],
            departments: [],
            months: [],
            capped: false,

            // filters
            q: "",
            country: "all",
            dept: "all",
            month: "all",
            needsOnly: false,
            focus: "",      // the figure on the numbers line now filtering
            step: "",       // the step now filtering

            // the open joiner
            drawer: null,
            drawerBusy: false,

            // dialogs — one at a time, each one plain state
            buddy: null,
            temp: null,
        });

        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------------ read
    async load() {
        try {
            const d = await this.orm.call("pb.onboarding", "get_board", []);
            Object.assign(this.state, {
                allowed: d.allowed,
                canWrite: d.can_write,
                kpis: d.kpis || {},
                rows: d.rows || [],
                countries: d.countries || [],
                departments: d.departments || [],
                months: d.months || [],
                capped: !!d.capped,
                loaded: true,
            });
        } catch (e) {
            // Reported, never swallowed into a decoration (W40).
            console.warn("pb_onboarding: could not read the board", e);
            this.state.loaded = true;
            this.state.allowed = false;
        }
    }

    async refresh() {
        this.state.loaded = false;
        await this.load();
        if (this.state.drawer) {
            await this.openJoiner(this.state.drawer.joiner.id);
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
            if (this.state.month !== "all" && r.month !== this.state.month) {
                return false;
            }
            if (this.state.needsOnly
                && !(r.overdue || !r.buddy || !r.hrbp || r.pulse_red)) {
                return false;
            }
            if (this.state.focus && !this.matchesFocus(r, this.state.focus)) {
                return false;
            }
            if (this.state.step && this.stepOf(r) !== this.state.step) {
                return false;
            }
            if (!q) { return true; }
            return (r.employee + " " + (r.job || "") + " " + (r.dept || "")
                + " " + (r.buddy || "") + " " + (r.hrbp || ""))
                .toLowerCase().includes(q);
        });
    }

    get hasFilters() {
        return this.state.q || this.state.country !== "all"
            || this.state.dept !== "all" || this.state.month !== "all"
            || this.state.needsOnly || this.state.focus || this.state.step;
    }

    clearFilters() {
        Object.assign(this.state, {
            q: "", country: "all", dept: "all", month: "all", needsOnly: false,
            focus: "", step: "",
        });
    }

    // ----------------------------------------------------- the quiet board
    //
    // One slim line of numbers instead of a row of tiles, and the three steps
    // a joiner moves through. A joiner is at EXACTLY ONE step (stepOf), so
    // the step counts add up to the board. Pressing a lit figure or step
    // again clears it.
    matchesFocus(r, key) {
        const days = r.doj ? r.days : null;
        if (key === "joining") { return days !== null && days >= 0 && days <= 7; }
        if (key === "started") { return days !== null && days <= 0; }
        if (key === "nobuddy") { return !r.buddy; }
        if (key === "overdue") { return !!r.overdue; }
        if (key === "red") { return !!r.pulse_red; }
        return true;
    }

    toggleFocus(key) { this.state.focus = this.state.focus === key ? "" : key; }

    get glance() {
        const k = this.state.kpis || {};
        const tone = (v, t) => (v ? t : "");
        return [
            { key: "joining", n: k.joining || 0, label: _t("Joining this week"), tone: "",
              run: () => this.toggleFocus("joining") },
            { key: "started", n: k.started || 0, label: _t("Already started"), tone: tone(k.started, "green"),
              run: () => this.toggleFocus("started") },
            { key: "nobuddy", n: k.no_buddy || 0, label: _t("Still without a buddy"), tone: tone(k.no_buddy, "amber"),
              run: () => this.toggleFocus("nobuddy") },
            { key: "overdue", n: k.overdue || 0, label: _t("Steps overdue"), tone: tone(k.overdue, "rose"),
              run: () => this.toggleFocus("overdue") },
            { key: "red", n: k.red || 0, label: _t("Said they are struggling"), tone: tone(k.red, "rose"),
              run: () => this.toggleFocus("red") },
        ];
    }

    /** Before the first day → settling in → checklist finished. */
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

    get steps() {
        const rows = this.state.rows;
        return this.stepDefs.map((st, i) => {
            const at = rows.filter((r) => this.stepOf(r) === st.key);
            const late = at.filter((r) => r.overdue).length;
            return {
                ...st,
                n: String(i + 1).padStart(2, "0"),
                count: at.length,
                countLabel: at.length === 1 ? _t("1 new joiner") : _t("%s new joiners", at.length),
                flag: !late ? "" : late === 1 ? _t("1 with steps overdue") : _t("%s with steps overdue", late),
                flagTone: "rose",
                on: this.state.step === st.key,
            };
        });
    }

    pickStep(key) { this.state.step = this.state.step === key ? "" : key; }

    stepMeta(r) {
        const defs = this.stepDefs;
        const index = defs.findIndex((st) => st.key === this.stepOf(r));
        return {
            label: _t("Step %s of %s", index + 1, defs.length),
            title: defs[index].title,
            marks: defs.map((st, j) => (j < index ? "done" : j === index ? "here" : "")),
        };
    }

    get showingLine() {
        const all = this.state.rows.length;
        if (!this.hasFilters) {
            return { all: true, text: !all ? _t("Showing no new joiners yet")
                : all === 1 ? _t("Showing all 1 new joiner · press a step or a number to narrow it")
                    : _t("Showing all %s new joiners · press a step or a number to narrow it", all) };
        }
        const shown = this.visibleRows.length;
        const st = this.stepDefs.find((x) => x.key === this.state.step);
        return { all: false, text: st
            ? _t("Showing %s of %s new joiners at %s", shown, all, st.title)
            : _t("Showing %s of %s new joiners", shown, all) };
    }

    onSearch(ev) { this.state.q = ev.target.value; }
    setCountry(id) { this.state.country = this.state.country === id ? "all" : id; }
    setDept(id) { this.state.dept = this.state.dept === id ? "all" : id; }
    setMonth(id) { this.state.month = this.state.month === id ? "all" : id; }
    toggleNeeds() { this.state.needsOnly = !this.state.needsOnly; }

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
