/** @odoo-module **/
/**
 * The Decision Room.
 *
 * One canvas where the person who owns the year sets a revenue target, moves a
 * handful of levers, and watches the business answer: the dark stage with one
 * huge number and the year drawn as a line, a compass of goals, twelve month
 * cards, one sentence explaining what just happened, three cards showing the
 * ripple from people to work to money, and a dock of saved plans.
 *
 * WHAT THIS FILE DELIBERATELY DOES NOT DO:
 *
 *   * it never computes money. `decision_engine.js` does, and it is a plain
 *     module with no imports so `node tools/decision_engine_check.mjs` can hold
 *     it to twenty numbered facts without a browser;
 *   * it never decides who may do anything. `pb.decision.room._can_read()` and
 *     `_can_manage()` are the boundary; `state.canManage` only decides whether
 *     a control is OFFERED, because an offer the server would refuse is worse
 *     than no offer;
 *   * it never writes to an employee, a contract or a payslip. There is no such
 *     call in this file, and the sentence saying so is on the screen.
 *
 * The heavy results — three computed years and a stress band, each twelve rows
 * of twenty numbers — are held on the INSTANCE and not in `useState`. A
 * reactive proxy over that much array is a measurable cost on every read, and
 * nothing in it is edited in place: it is replaced wholesale by `_recompute()`,
 * which bumps one counter the render does read.
 */
import {
    Component, useState, useRef, onWillStart, onMounted, onPatched,
    onWillUnmount,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { hubBack, HubBackChip, openHub } from "@pb_hub/js/hub_nav";
import { makeFormat, MONTHS, monthLong } from "@pb_decision_room/js/decision_format";
import { drawHorizon, drawRing } from "@pb_decision_room/js/decision_charts";
import {
    compute, defaultState, normalizeState, normalizeGoals, defaultGoals,
    evaluateGoals, series, stressBand, story, warnings,
    GOAL_DEFS, GOAL_ORDER, cloneState,
} from "@pb_decision_room/js/decision_engine";

const UNDO_DEPTH = 40;
const TWEEN_MS = 350;

/** The three metrics the stage can show. */
const METRICS = {
    profit: {
        key: "profit", tab: _t("Profit"),
        title: _t("OPERATING PROFIT FOR THE YEAR"), goodUp: true,
    },
    people: {
        key: "people", tab: _t("People cost"),
        title: _t("WORKFORCE COST FOR THE YEAR"), goodUp: false,
    },
    coverage: {
        key: "coverage", tab: _t("Demand served"),
        title: _t("DEMAND SERVED THIS YEAR"), goodUp: true,
    },
};

export class PbDecisionRoom extends Component {
    static template = "pb_decision_room.PbDecisionRoom";
    static components = { HubBackChip };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.actionService = useService("action");
        this.onKey = this.onKey.bind(this);

        /** The scene name of the untouched company. Compared by IDENTITY, so
         *  it is built once — `_t()` returns a new lazy string every call and
         *  `_t("Today") === _t("Today")` is false. */
        this.TODAY = _t("Today");

        this.horizonRef = useRef("horizon");
        this.ringRef = useRef("ring");
        this.heroRef = useRef("hero");

        this.state = useState({
            loaded: false,
            allowed: true,
            canManage: false,
            error: "",
            rev: 0,                 // bumped by _recompute()

            company: {},
            limits: { max_plans: 20 },
            plans: [],

            // what is on screen
            sceneName: this.TODAY,
            month: 0,
            metric: "profit",
            diff: false,
            motion: true,
            teamKey: "",
            roleKey: "",
            moveMonth: 1,

            // dialogs, one at a time
            saveOpen: false,
            saveName: "",
            saveConflict: false,
            saveError: "",
            goalsOpen: false,
            assumptionsOpen: false,

            // a company with nobody on record can still sketch one
            sketchOpen: false,
            sketchName: "",
            sketchPeople: 10,
            sketchPay: 0,

            toast: "",
            busy: false,
        });

        // Not reactive on purpose (see the file header).
        this.baseline = { asof: "", headcount: 0, teams: [], source: "" };
        this.assumptions = {};
        this.planState = {};
        this.goals = {};
        this.comparison = { kind: "baseline", id: 0, name: this.TODAY,
                            state: null };
        this._history = [];
        this._goalsTouched = false;
        this._calc = null;
        this._playing = null;
        this._heroFrom = null;
        this._heroFrame = 0;
        this._heroMetric = "";
        this._resize = null;
        this._toastTimer = null;
        this._rippleAt = 0;

        this.fmt = makeFormat({});
        this.months = MONTHS;

        onWillStart(async () => { await this.load(); });
        onMounted(() => {
            this._resize = new ResizeObserver(() => this.paint());
            if (this.horizonRef.el) { this._resize.observe(this.horizonRef.el); }
            this.paint();
            this._focusArrival();
            // CAPTURE, deliberately. The platform's own hotkey service listens
            // on `window` and stops propagation for the keys it claims —
            // Escape among them — so a bubble-phase listener here never fires
            // and the dialogs cannot be closed with the keyboard at all. This
            // one only reads; it never calls preventDefault on Escape, so the
            // platform still gets its turn.
            window.addEventListener("keydown", this.onKey, true);
        });
        onPatched(() => this.paint());
        onWillUnmount(() => {
            this.stopPlay();
            if (this._resize) { this._resize.disconnect(); }
            cancelAnimationFrame(this._heroFrame);
            clearTimeout(this._toastTimer);
            window.removeEventListener("keydown", this.onKey, true);
        });
    }

    ic(name, size = 16) { return ic(name, size); }

    // ===================================================================
    // reading
    // ===================================================================
    async load(refresh = false) {
        try {
            const data = await this.orm.call(
                "pb.decision.room", "get_room", [], { refresh });
            this.state.allowed = !!data.allowed;
            this.state.canManage = !!data.can_manage;
            this.state.company = data.company || {};
            this.state.plans = data.plans || [];
            this.state.limits = data.limits || { max_plans: 20 };
            this.state.error = "";
            this.baseline = data.baseline
                || { asof: "", headcount: 0, teams: [], source: "" };
            this.assumptions = data.assumptions || {};
            this.fmt = makeFormat((data.company || {}).currency || {});

            this.planState = defaultState(this.baseline, this.assumptions);
            this.goals = null;                     // built after the first sum
            this._goalsTouched = false;
            this.comparison = { kind: "baseline", id: 0,
                                name: this.TODAY, state: null };
            const reference = (data.plans || []).find((p) => p.is_reference);
            if (reference) {
                this.comparison = {
                    kind: "plan", id: reference.id, name: reference.name,
                    state: reference.state || {},
                };
            }
            const firstTeam = (this.baseline.teams || [])[0];
            this.state.teamKey = firstTeam ? firstTeam.key : "";
            this.state.roleKey = "";
            this.state.moveMonth = this.planState.start;
            this.state.month = Math.min(11, Math.max(0, new Date().getMonth()));
            this._history = [];
            this._recompute();
        } catch (e) {
            console.warn("pb_decision_room: the room could not load", e);
            this.state.error = (e && e.message) || String(e);
        } finally {
            this.state.loaded = true;
        }
    }

    async retry() {
        this.state.loaded = false;
        this.state.error = "";
        await this.load(true);
    }

    _focusArrival() {
        const focus = (this.props.arrival && this.props.arrival.focus) || "";
        if (focus !== "plans") { return; }
        // One frame later: the dock is in the first render, but the canvas is
        // still being laid out at mount and scrolling to it now lands nowhere.
        setTimeout(() => {
            const dock = document.querySelector(".dr-dock");
            if (!dock) { return; }
            dock.scrollIntoView({
                behavior: this.state.motion ? "smooth" : "auto",
                block: "start",
            });
        }, 120);
    }

    // ===================================================================
    // the numbers
    // ===================================================================
    /**
     * The company exactly as it is today — but earning the revenue the owner
     * has typed.
     *
     * This is the one modelling judgement in the cockpit and it matters. The
     * revenue target is a statement about the BUSINESS, not a workforce lever:
     * comparing a plan that earns ₫2,200B against a "today" that earns nothing
     * would credit every workforce decision with the whole year's revenue, and
     * the first number the owner sees would be nonsense. So "Today" keeps the
     * target and the growth, and changes nothing about the people.
     */
    _baseState() {
        return {
            ...defaultState(this.baseline, this.assumptions),
            target: this.planState.target || 0,
            growth: this.planState.growth || 0,
        };
    }

    _recompute() {
        const base = this.baseline;
        const a = this.assumptions;
        const basePlan = compute(base, a, this._baseState());
        const plan = compute(base, a, this.planState);
        const refState = this.comparison.state
            ? normalizeState(this.comparison.state, base, a)
            : normalizeState(this._baseState(), base, a);
        const ref = this.comparison.state ? compute(base, a, refState) : basePlan;
        // Until somebody sets a goal of their own, the goals ARE the defaults —
        // recomputed every time, so typing a revenue target switches on the
        // three goals that only mean something once there is revenue.
        if (!this._goalsTouched || !this.goals) {
            this.goals = defaultGoals(basePlan, this.planState.target > 0);
        }
        this.goals = normalizeGoals(this.goals, basePlan,
                                    this.planState.target > 0);
        this._calc = {
            basePlan, plan, ref, refState,
            band: stressBand(base, a, this.planState),
            checks: evaluateGoals(plan, this.goals, this.fmt),
            story: story(plan, ref, normalizeState(this.planState, base, a),
                         refState, this.comparison.name, base, this.fmt),
            warnings: warnings(plan, ref,
                               normalizeState(this.planState, base, a),
                               this.fmt),
        };
        this.state.rev++;
    }

    get calc() {
        void this.state.rev;
        return this._calc;
    }

    get hasRoster() { return (this.baseline.teams || []).length > 0; }
    get hasTarget() { return (this.planState.target || 0) > 0; }
    get teams() { return this.baseline.teams || []; }

    get team() {
        return this.teams.find((t) => t.key === this.state.teamKey)
            || this.teams[0] || null;
    }

    get roles() { return this.team ? this.team.roles : []; }

    get role() {
        return this.roles.find((r) => r.key === this.state.roleKey) || null;
    }

    // ===================================================================
    // the levers
    // ===================================================================
    /** How many people this lever is currently adding or removing. */
    get peopleValue() {
        const key = this.state.roleKey || null;
        const hit = (this.planState.moves || []).find(
            (m) => m.team === this.state.teamKey && (m.role || null) === key
                && m.month === this.state.moveMonth);
        return hit ? hit.n : 0;
    }

    get peopleRange() {
        const heads = this.role ? this.role.heads
            : (this.team ? this.team.heads : 0);
        return { min: -Math.round(heads * 0.2), max: Math.round(heads * 0.5),
                 heads };
    }

    /** One descriptor per slider, so the template renders them all one way. */
    _lever(key, label, note, min, max, step, unit) {
        const refState = this.calc ? this.calc.refState : this.planState;
        return {
            key, label, note, min, max, step, unit,
            value: this.planState[key],
            was: refState[key],
            fill: ((this.planState[key] - min) / (max - min || 1) * 100)
                .toFixed(1),
            tick: ((refState[key] - min) / (max - min || 1) * 100).toFixed(1),
            same: Math.abs(this.planState[key] - refState[key]) < 1e-9,
        };
    }

    get otLever() {
        return this._lever(
            "ot", _t("Overtime per person"),
            _t("Extra hours a month, paid at the overtime rate."),
            0, 40, 1, _t("h / month"));
    }

    get raiseLever() {
        return this._lever(
            "raise", _t("Salary increase"),
            _t("Applies to everyone from the month you choose."),
            0, 30, 0.5, "%");
    }

    get growthLever() {
        return this._lever(
            "growth", _t("More work by December"),
            _t("How much more work arrives at the end of the year."),
            -20, 50, 1, "%");
    }

    get productivityLever() {
        return this._lever(
            "productivity", _t("Productive time"),
            _t("An assumed improvement in how much gets done in an hour."),
            0, 25, 1, "%");
    }

    get absenceLever() {
        return this._lever(
            "absence", _t("Unavailable paid time"),
            _t("Leave, absence and everything else that is paid but not "
               + "delivered."),
            0, 30, 1, "%");
    }

    get bonusValue() { return this.planState.bonusMonths; }

    // ===================================================================
    // changing something
    // ===================================================================
    _push() {
        this._history.push({
            state: cloneState(this.planState),
            goals: JSON.parse(JSON.stringify(this.goals || {})),
            scene: this.state.sceneName,
            touched: this._goalsTouched,
        });
        if (this._history.length > UNDO_DEPTH) { this._history.shift(); }
    }

    get canUndo() { return this._history.length > 0; }

    /** Every lever change lands here, so undo and the ripple are never missed. */
    _apply(patch, sceneName, record = true) {
        if (record) { this._push(); }
        this.planState = normalizeState(
            { ...this.planState, ...patch }, this.baseline, this.assumptions);
        if (sceneName) { this.state.sceneName = sceneName; }
        this._ripple();
        this._recompute();
    }

    onLever(key, event) {
        const raw = event.target.value;
        if (raw === "" || !Number.isFinite(Number(raw))) { return; }
        const value = Number(raw);
        if (Math.abs((this.planState[key] || 0) - value) < 1e-9) { return; }
        this._apply({ [key]: value }, _t("Your working plan"));
    }

    onBonus(event) {
        this._apply({ bonusMonths: Number(event.target.value) || 0 },
                    _t("Your working plan"));
    }

    setAttrition(event) {
        this._apply({ attritionOn: !!event.target.checked });
    }

    setBackfill(event) {
        this._apply({ backfill: !!event.target.checked });
    }

    onMonthSelect(key, event) {
        this._apply({ [key]: Number(event.target.value) || 1 });
    }

    setTeam(event) {
        this.state.teamKey = event.target.value;
        this.state.roleKey = "";
        this.state.rev++;
    }

    setRole(event) {
        this.state.roleKey = event.target.value;
        this.state.rev++;
    }

    setMoveMonth(event) {
        this.state.moveMonth = Number(event.target.value) || 1;
        this._apply({ start: Number(event.target.value) || 1 });
    }

    /** Add or remove people in the team (and role) on screen. */
    onPeople(event) {
        const raw = event.target.value;
        if (raw === "" || !Number.isFinite(Number(raw))) { return; }
        const n = Math.round(Number(raw));
        const key = this.state.roleKey || null;
        const moves = (this.planState.moves || []).filter(
            (m) => !(m.team === this.state.teamKey && (m.role || null) === key
                     && m.month === this.state.moveMonth));
        if (n) {
            moves.push({ team: this.state.teamKey, role: key, n,
                         month: this.state.moveMonth });
        }
        this._apply({ moves }, _t("Your working plan"));
    }

    onTarget(event) {
        const raw = String(event.target.value || "").replace(/[^\d.-]/g, "");
        const value = Math.max(0, Number(raw) || 0);
        if (Math.abs(value - (this.planState.target || 0)) < 1e-9) { return; }
        this._apply({ target: value }, _t("Your working plan"));
    }

    /** On blur the target is remembered for everyone, when we may. */
    async onTargetCommit() {
        if (!this.state.canManage) { return; }
        const target = this.planState.target || 0;
        const growth = this.planState.growth || 0;
        if (Math.abs(target - (this.assumptions.revenue_target || 0)) < 1e-9
            && Math.abs(growth - (this.assumptions.demand_growth_pct || 0)) < 1e-9) {
            return;
        }
        try {
            this.assumptions = await this.orm.call(
                "pb.decision.room", "save_assumptions",
                [{ revenue_target: target, demand_growth_pct: growth }]);
            this._toast(_t("Revenue target saved for everyone at %s.",
                           this.state.company.name || ""));
        } catch (e) {
            console.warn("pb_decision_room: the target could not be saved", e);
            this._toast(_t("The target could not be saved. It is still in "
                           + "your plan on this screen."));
        }
    }

    // -------------------------------------------------------- the presets
    get presets() {
        const earner = this.teams.find((t) => t.revenue && t.heads > 0)
            || this.teams[0];
        const bump = earner ? Math.max(1, Math.round(earner.heads * 0.05)) : 0;
        const nextMonth = Math.min(12, new Date().getMonth() + 2);
        return [
            {
                id: "grow", label: _t("Grow thoughtfully"),
                note: earner
                    ? _t("%(n)s more people in %(team)s from %(month)s",
                         { n: bump, team: earner.name,
                           month: monthLong(nextMonth - 1) })
                    : _t("Add people where the work is"),
                patch: earner
                    ? { moves: [{ team: earner.key, role: null, n: bump,
                                  month: nextMonth }],
                        raise: 0, ot: this.planState.ot }
                    : {},
            },
            {
                id: "pay", label: _t("Invest in people"),
                note: _t("A 5% increase from January, and 5% more "
                         + "productive time"),
                patch: { raise: 5, raiseMonth: 1, productivity: 5, moves: [] },
            },
            {
                id: "hours", label: _t("Ease overtime"),
                note: _t("No overtime, and 8% more productive time"),
                patch: { ot: 0, productivity: 8, moves: [] },
            },
        ];
    }

    applyPreset(preset) {
        this._apply(preset.patch, preset.label);
        this._toast(_t("“%s” is on the canvas. Change any lever to make it "
                       + "yours.", preset.label));
    }

    // ------------------------------------------------------ undo / reset
    undo() {
        if (!this._history.length) { return; }
        const previous = this._history.pop();
        this.planState = previous.state;
        this.goals = previous.goals;
        this._goalsTouched = previous.touched;
        this.state.sceneName = previous.scene;
        this._recompute();
    }

    reset() {
        this.stopPlay();
        this._push();
        // The revenue target survives a reset: it is what the business plans to
        // earn, not something the room made up, and nobody wants to retype it
        // because they changed their mind about hiring.
        this.planState = normalizeState(this._baseState(), this.baseline,
                                        this.assumptions);
        this.state.sceneName = this.TODAY;
        this._recompute();
        this._toast(_t("Back to the company as it is today."));
    }

    // ===================================================================
    // the stage
    // ===================================================================
    /**
     * What the stage is actually showing.
     *
     * Without a revenue target there is no revenue, so profit and demand
     * served would both be a straight lie dressed as a number. The stage is
     * LOCKED to people cost until a target is typed — which is also why the
     * target is the first control on the left.
     */
    get metric() {
        return this.hasTarget ? this.state.metric : "people";
    }

    get metricDef() { return METRICS[this.metric] || METRICS.profit; }

    get metricTabs() {
        const keys = this.hasTarget
            ? ["profit", "people", "coverage"] : ["people"];
        return keys.map((k) => ({ ...METRICS[k], active: k === this.metric }));
    }

    get heroValue() {
        const c = this.calc;
        if (!c) { return 0; }
        if (this.metric === "coverage") { return c.plan.year.coverage * 100; }
        return c.plan.year[this.metric === "people" ? "people" : "profit"];
    }

    get heroRefValue() {
        const c = this.calc;
        if (!c) { return 0; }
        if (this.metric === "coverage") { return c.ref.year.coverage * 100; }
        return c.ref.year[this.metric === "people" ? "people" : "profit"];
    }

    heroText(value) {
        return this.metric === "coverage"
            ? this.fmt.pct(value) : this.fmt.money(value);
    }

    get heroDelta() {
        const d = this.heroValue - this.heroRefValue;
        const good = this.metricDef.goodUp ? d >= 0 : d <= 0;
        const text = this.metric === "coverage"
            ? this.fmt.pp(d) : this.fmt.signedMoney(d);
        return { text: _t("%(delta)s vs %(name)s",
                          { delta: text, name: this.comparison.name }),
                 good, zero: Math.abs(d) < (this.metric === "coverage"
                                            ? 0.05 : 1) };
    }

    get heroSentence() {
        const c = this.calc;
        if (!c) { return ""; }
        const before = this.heroText(this.heroRefValue);
        const after = this.heroText(this.heroValue);
        const tail = this.metric === "profit"
            ? _t("Margin %(margin)s on %(revenue)s of revenue.",
                 { margin: this.fmt.pct(c.plan.year.margin * 100),
                   revenue: this.fmt.money(c.plan.year.revenue) })
            : this.metric === "people"
                ? _t("%s on payroll in December.",
                     this.fmt.int(c.plan.year.headcount))
                : _t("%s of demand goes unserved this year.",
                     this.fmt.money(c.plan.year.unserved));
        return _t("%(name)s %(before)s → your plan %(after)s. %(tail)s",
                  { name: this.comparison.name, before, after, tail });
    }

    get stageTiles() {
        const c = this.calc;
        if (!c) { return []; }
        const row = c.plan.rows[this.state.month];
        const refRow = c.ref.rows[this.state.month];
        const stamp = monthLong(this.state.month).toUpperCase();
        const tiles = [
            {
                label: _t("PEOPLE ON PAYROLL · %s", stamp),
                value: this.fmt.int(row.heads),
                delta: this.fmt.people(row.heads - refRow.heads),
                bad: false,
            },
            {
                label: _t("WORKFORCE COST · %s", stamp),
                value: this.fmt.money(row.people),
                delta: this.fmt.signedMoney(row.people - refRow.people),
                bad: row.people - refRow.people > 1,
            },
        ];
        tiles.push(this.hasTarget
            ? {
                label: _t("DEMAND SERVED · %s", stamp),
                value: this.fmt.pct(row.coverage * 100),
                delta: this.fmt.pp((row.coverage - refRow.coverage) * 100),
                bad: row.coverage < refRow.coverage - 0.0005,
            }
            : {
                label: _t("TAKE-HOME PAY · %s", stamp),
                value: this.fmt.money(row.takehome),
                delta: this.fmt.signedMoney(row.takehome - refRow.takehome),
                bad: false,
            });
        return tiles;
    }

    get monthCallout() {
        const c = this.calc;
        if (!c) { return { title: "", lines: [] }; }
        const row = c.plan.rows[this.state.month];
        const refRow = c.ref.rows[this.state.month];
        const value = this.state.diff
            ? (this.metric === "coverage"
                ? this.fmt.pp((row.coverage - refRow.coverage) * 100)
                : this.fmt.signedMoney(
                    series(c.plan, this.metric)[this.state.month]
                    - series(c.ref, this.metric)[this.state.month]))
            : (this.metric === "coverage"
                ? this.fmt.pct(row.coverage * 100)
                : this.fmt.money(
                    series(c.plan, this.metric)[this.state.month]));
        const lines = [
            _t("%s people", this.fmt.int(row.heads)),
        ];
        if (this.hasTarget) {
            lines.push(_t("%s of the work served",
                          this.fmt.pct(row.coverage * 100)));
        }
        if (row.recruit + row.severance > 0) {
            lines.push(_t("Joining and leaving costs land this month"));
        }
        if (row.bonus > 0) { lines.push(_t("The yearly bonus is paid")); }
        return { title: monthLong(this.state.month), value, lines };
    }

    get chartContext() {
        const what = this.metric === "coverage"
            ? _t("demand served each month")
            : this.metric === "people"
                ? _t("workforce cost, adding up through the year")
                : _t("profit, adding up through the year");
        return this.state.diff ? _t("The difference in %s", what) : what;
    }

    get goalPaceNote() {
        if (this.state.diff) { return ""; }
        if (this.metric === "profit" && this.goals.profit.on) {
            return _t("Dotted line: an even pace to your profit goal");
        }
        if (this.metric === "people" && this.goals.cost.on) {
            return _t("Dotted line: an even share of your cost limit");
        }
        if (this.metric === "coverage" && this.goals.coverage.on) {
            return _t("Dotted line: your demand-served goal");
        }
        return "";
    }

    setMetric(key) {
        if (this.state.metric === key) { return; }
        this.state.metric = key;
        this.state.rev++;
    }

    setMonth(event) {
        this.stopPlay();
        this.state.month = Number(event.target.value) || 0;
    }

    pickMonth(index) {
        this.stopPlay();
        this.state.month = index;
    }

    toggleDiff() { this.state.diff = !this.state.diff; }

    toggleMotion() {
        this.state.motion = !this.state.motion;
        if (!this.state.motion) { this.stopPlay(); }
    }

    get playing() { return !!this._playing; }

    togglePlay() {
        if (this._playing) { this.stopPlay(); return; }
        if (this.state.month >= 11) { this.state.month = 0; }
        this._playing = setInterval(() => {
            if (this.state.month >= 11) { this.stopPlay(); return; }
            this.state.month += 1;
        }, 1000);
        this.state.rev++;
    }

    stopPlay() {
        if (this._playing) { clearInterval(this._playing); }
        this._playing = null;
        this.state.rev++;
    }

    // ===================================================================
    // the year lens, the caption and the ripple
    // ===================================================================
    get monthCards() {
        const c = this.calc;
        if (!c) { return []; }
        const threshold = this.goals.coverage.on
            ? this.goals.coverage.target / 100 : 0.95;
        return c.plan.rows.map((row, i) => ({
            index: i,
            name: MONTHS[i],
            value: this.hasTarget ? this.fmt.money(row.profit)
                : this.fmt.money(row.people),
            watch: (this.hasTarget && row.coverage + 1e-8 < threshold)
                || row.profit < 0,
            active: i === this.state.month,
            title: this.hasTarget
                ? _t("%(month)s: %(profit)s profit, %(served)s of demand served",
                     { month: monthLong(i), profit: this.fmt.exact(row.profit),
                       served: this.fmt.pct(row.coverage * 100) })
                : _t("%(month)s: %(cost)s of workforce cost",
                     { month: monthLong(i), cost: this.fmt.exact(row.people) }),
        }));
    }

    get yearNote() {
        const c = this.calc;
        if (!c) { return ""; }
        const worst = c.plan.rows[c.plan.year.worstMonth];
        const measure = this.hasTarget ? _t("lowest-profit") : _t("costliest");
        const peak = this.hasTarget ? worst
            : c.plan.rows[c.plan.year.peakMonth];
        const value = this.hasTarget
            ? this.fmt.money(peak.profit) : this.fmt.money(peak.people);
        const extra = peak.bonus > 0
            ? _t(" The yearly bonus is paid this month.")
            : (peak.recruit + peak.severance > 0
                ? _t(" Joining and leaving costs land here.") : "");
        return _t("%(month)s is your %(measure)s month at %(value)s.%(extra)s",
                  { month: monthLong(peak.index), measure, value, extra });
    }

    get storyLine() { return this.calc ? this.calc.story : { title: "", copy: "" }; }
    get warningLines() { return this.calc ? this.calc.warnings : []; }

    /** One square is about this many people, so the grid never exceeds 200. */
    get dotScale() {
        const heads = this.calc ? this.calc.plan.year.headcount : 0;
        return Math.max(1, Math.ceil(heads / 180));
    }

    get peopleDots() {
        const c = this.calc;
        if (!c) { return []; }
        const scale = this.dotScale;
        const dec = c.plan.rows[11].heads;
        const ref = c.ref.rows[11].heads;
        const kept = Math.round(Math.min(dec, ref) / scale);
        const added = Math.round(Math.max(0, dec - ref) / scale);
        const gone = Math.round(Math.max(0, ref - dec) / scale);
        const dots = [];
        for (let i = 0; i < kept; i++) { dots.push({ id: `k${i}`, cls: "" }); }
        for (let i = 0; i < gone; i++) { dots.push({ id: `g${i}`, cls: "gone" }); }
        for (let i = 0; i < added; i++) { dots.push({ id: `a${i}`, cls: "added" }); }
        return dots.slice(0, 200);
    }

    get profitBars() {
        const c = this.calc;
        if (!c) { return []; }
        const key = this.hasTarget ? "profit" : "people";
        const max = Math.max(
            ...c.plan.rows.map((r) => Math.abs(r[key])),
            ...c.ref.rows.map((r) => Math.abs(r[key])), 1);
        return c.plan.rows.map((row, i) => ({
            id: i,
            refH: Math.abs(c.ref.rows[i][key]) / max * 100,
            planH: Math.abs(row[key]) / max * 100,
            neg: row[key] < 0,
            title: _t("%(month)s: %(now)s (was %(was)s)",
                      { month: monthLong(i),
                        now: this.fmt.exact(row[key]),
                        was: this.fmt.exact(c.ref.rows[i][key]) }),
        }));
    }

    get peopleCopy() {
        const c = this.calc;
        if (!c) { return ""; }
        const dec = c.plan.rows[11].heads;
        const ref = c.ref.rows[11].heads;
        const delta = dec - ref;
        if (delta > 0.5) {
            return _t("%(n)s people arrive during the year, paid in full from "
                      + "their first day and about half as productive while "
                      + "they learn. Recruiting them costs %(cost)s, once.",
                      { n: this.fmt.int(delta),
                        cost: this.fmt.money(c.plan.year.recruit) });
        }
        if (delta < -0.5) {
            return _t("%s fewer roles than the comparison. Nothing here "
                      + "changes anybody's job — it is a picture, not a "
                      + "decision.", this.fmt.int(-delta));
        }
        if (this.planState.raise || this.planState.productivity) {
            return _t("The same team, better paid or better supported. The "
                      + "cost moves; the headcount does not.");
        }
        return _t("The same team as the comparison. Any change is coming from "
                  + "hours, pay or the work itself.");
    }

    get coverageCopy() {
        const c = this.calc;
        if (!c) { return ""; }
        if (!this.hasTarget) {
            return _t("Type a revenue target on the left and this card starts "
                      + "showing how much of the work your team can actually "
                      + "deliver.");
        }
        const d = (c.plan.year.coverage - c.ref.year.coverage) * 100;
        const tail = c.plan.year.unserved > 0
            ? _t("%s of demand is left on the table.",
                 this.fmt.money(c.plan.year.unserved))
            : _t("Every hour of the work you planned for is covered.");
        return _t("%(delta)s against %(name)s. %(tail)s",
                  { delta: this.fmt.pp(d), name: this.comparison.name, tail });
    }

    get moneyCopy() {
        const c = this.calc;
        if (!c) { return ""; }
        if (!this.hasTarget) {
            return _t("%(cost)s of workforce cost for the year, %(perhead)s "
                      + "for each person on average. Add a revenue target and "
                      + "profit appears.",
                      { cost: this.fmt.money(c.plan.year.people),
                        perhead: this.fmt.money(c.plan.year.costPerHead) });
        }
        return _t("%(rev)s of revenue − %(people)s of workforce − %(other)s of "
                  + "other costs = %(profit)s of operating profit. Margin "
                  + "%(margin)s.",
                  { rev: this.fmt.money(c.plan.year.revenue),
                    people: this.fmt.money(c.plan.year.people),
                    other: this.fmt.money(c.plan.year.other),
                    profit: this.fmt.money(c.plan.year.profit),
                    margin: this.fmt.pct(c.plan.year.margin * 100) });
    }

    get profitChangeText() {
        const c = this.calc;
        if (!c) { return ""; }
        const key = this.hasTarget ? "profit" : "people";
        return this.fmt.signedMoney(c.plan.year[key] - c.ref.year[key]);
    }

    get coverageRingValue() {
        const c = this.calc;
        return c ? this.fmt.pct(c.plan.year.coverage * 100) : "";
    }

    _ripple() {
        if (!this.state.motion) { return; }
        this._rippleAt = Date.now();
        const journey = document.querySelector(".dr-journey");
        if (!journey) { return; }
        journey.classList.remove("dr-ripple");
        void journey.offsetWidth;
        journey.classList.add("dr-ripple");
    }

    // ===================================================================
    // the goal compass
    // ===================================================================
    get goalPills() {
        const checks = this.calc ? this.calc.checks : [];
        return checks.map((c) => ({
            key: c.key, short: c.short, met: c.met,
            actual: c.actualText,
            note: _t("%(bound)s %(target)s · %(gap)s",
                     { bound: c.sense === "min" ? _t("At least") : _t("At most"),
                       target: c.targetText, gap: this._gapText(c) }),
            progress: Math.max(0, Math.min(100,
                c.sense === "min"
                    ? (c.target !== 0 ? c.actual / c.target * 100 : 100)
                    : (c.actual !== 0 ? c.target / c.actual * 100 : 100))),
        }));
    }

    _gapText(check) {
        const def = GOAL_DEFS[check.key];
        const size = def.unit === "%"
            ? this.fmt.pp(Math.abs(check.gap))
            : def.unit === "people"
                ? this.fmt.people(Math.abs(check.gap))
                : def.unit === "h/mo"
                    ? _t("%s hours", Math.round(Math.abs(check.gap)))
                    : this.fmt.money(Math.abs(check.gap));
        if (check.met) {
            return check.sense === "min"
                ? _t("%s to spare", size) : _t("%s of room left", size);
        }
        return check.sense === "min"
            ? _t("%s short", size) : _t("%s over", size);
    }

    get goalSummary() {
        const checks = this.calc ? this.calc.checks : [];
        if (!checks.length) { return _t("What would make this a good year?"); }
        const met = checks.filter((c) => c.met).length;
        return met === checks.length
            ? _t("%(met)s of %(all)s goals met. Room to think bigger.",
                 { met, all: checks.length })
            : _t("%(met)s of %(all)s goals met. Let us close the gaps.",
                 { met, all: checks.length });
    }

    /**
     * The unit a MONEY goal is typed in.
     *
     * Nobody types ₫327,361,352,250 into a box, and nobody reads it back. So
     * the money goals are entered in the same unit the whole screen speaks —
     * billions here, millions on a smaller company — and multiplied back on
     * the way in. The scale is chosen ONCE from the size of the company's
     * workforce bill, not from the value in the box, so it cannot change under
     * somebody's fingers while they are typing.
     */
    _moneyScale() {
        const size = this.calc
            ? Math.abs(this.calc.basePlan.year.people) : 0;
        const whole = (this.fmt.decimals || 0) === 0;
        if (size >= 1e9) { return { by: 1e9, suffix: whole ? "B" : "bn" }; }
        if (size >= 1e6) { return { by: 1e6, suffix: whole ? "M" : "m" }; }
        if (size >= 1e3) { return { by: 1e3, suffix: "k" }; }
        return { by: 1, suffix: "" };
    }

    get goalCards() {
        const checks = this.calc ? this.calc.checks : [];
        const scale = this._moneyScale();
        return GOAL_ORDER.map((key) => {
            const def = GOAL_DEFS[key];
            const check = checks.find((c) => c.key === key);
            const money = def.unit === "money";
            return {
                key, label: def.label, money,
                bound: def.sense === "min" ? _t("At least") : _t("At most"),
                unit: money ? `${scale.suffix} ${this.fmt.symbol}`.trim()
                    : (def.unit === "people" ? _t("people") : def.unit),
                step: money ? 0.01 : def.step,
                on: this.goals[key].on,
                target: money
                    ? Math.round(this.goals[key].target / scale.by * 100) / 100
                    : this.goals[key].target,
                status: check
                    ? _t("Now %(now)s · %(gap)s",
                         { now: check.actualText, gap: this._gapText(check) })
                    : _t("Switched off. Turn it on to hold the plan to it."),
                missed: !!check && !check.met,
            };
        });
    }

    /** One dialog at a time — opening one closes whatever else was open. */
    _openDialog(name) {
        this.state.saveOpen = false;
        this.state.goalsOpen = false;
        this.state.assumptionsOpen = false;
        this.state.sketchOpen = false;
        if (name) { this.state[name] = true; }
    }

    openGoals() { this.stopPlay(); this._openDialog("goalsOpen"); }
    closeGoals() { this.state.goalsOpen = false; }

    toggleGoal(key, event) {
        this._push();
        this._goalsTouched = true;
        this.goals = normalizeGoals(
            { ...this.goals, [key]: { ...this.goals[key],
                                      on: !!event.target.checked } },
            this.calc.basePlan, this.hasTarget);
        this._recompute();
    }

    setGoalTarget(key, event) {
        const raw = event.target.value;
        if (raw === "" || !Number.isFinite(Number(raw))) { return; }
        this._goalsTouched = true;
        const scale = GOAL_DEFS[key].unit === "money"
            ? this._moneyScale().by : 1;
        this.goals = normalizeGoals(
            { ...this.goals, [key]: { ...this.goals[key],
                                      target: Number(raw) * scale } },
            this.calc.basePlan, this.hasTarget);
        this._recompute();
    }

    // ===================================================================
    // the dock
    // ===================================================================
    get dockRows() {
        const c = this.calc;
        if (!c) { return []; }
        const refProfit = c.ref.year.profit;
        const rows = [{
            id: 0, name: this.comparison.name, tag: "comparison",
            heads: this.fmt.int(c.ref.year.headcount),
            cost: this.fmt.money(c.ref.year.people),
            served: this.hasTarget
                ? this.fmt.pct(c.ref.year.coverage * 100) : "—",
            profit: this.fmt.money(c.ref.year.profit),
            delta: "—", bad: false, mine: false,
        }, {
            id: -1, name: this.state.sceneName, tag: "current",
            heads: this.fmt.int(c.plan.year.headcount),
            cost: this.fmt.money(c.plan.year.people),
            served: this.hasTarget
                ? this.fmt.pct(c.plan.year.coverage * 100) : "—",
            profit: this.fmt.money(c.plan.year.profit),
            delta: this.fmt.signedMoney(c.plan.year.profit - refProfit),
            bad: c.plan.year.profit < refProfit - 1, mine: false,
        }];
        for (const plan of this.state.plans) {
            const s = plan.summary || {};
            rows.push({
                id: plan.id, name: plan.name, tag: "saved",
                who: plan.user,
                heads: this.fmt.int(s.heads || 0),
                cost: this.fmt.money(s.cost || 0),
                served: this.hasTarget && s.coverage !== undefined
                    ? this.fmt.pct((s.coverage || 0) * 100) : "—",
                profit: this.fmt.money(s.profit || 0),
                delta: this.fmt.signedMoney((s.profit || 0) - refProfit),
                bad: (s.profit || 0) < refProfit - 1,
                mine: !!plan.mine,
                reference: !!plan.is_reference,
            });
        }
        return rows;
    }

    get comparisonOptions() {
        return [
            { value: "baseline", label: _t("The company as it is today") },
            ...this.state.plans.map((p) => ({ value: String(p.id),
                                              label: p.name })),
        ];
    }

    get comparisonValue() {
        return this.comparison.kind === "plan"
            ? String(this.comparison.id) : "baseline";
    }

    onComparison(event) {
        const value = event.target.value;
        if (value === "baseline") {
            this.comparison = { kind: "baseline", id: 0, name: this.TODAY,
                                state: null };
        } else {
            const plan = this.state.plans.find((p) => String(p.id) === value);
            if (!plan) { return; }
            this.comparison = { kind: "plan", id: plan.id, name: plan.name,
                                state: plan.state || {} };
        }
        this._recompute();
        this._toast(_t("Everything is now measured against “%s”.",
                       this.comparison.name));
    }

    compareWith(row) {
        const plan = this.state.plans.find((p) => p.id === row.id);
        if (!plan) { return; }
        this.comparison = { kind: "plan", id: plan.id, name: plan.name,
                            state: plan.state || {} };
        this._recompute();
        this._toast(_t("Everything is now measured against “%s”.", plan.name));
    }

    openPlan(row) {
        const plan = this.state.plans.find((p) => p.id === row.id);
        if (!plan) { return; }
        this._push();
        this.planState = normalizeState(plan.state || {}, this.baseline,
                                        this.assumptions);
        this.goals = normalizeGoals(plan.goals || {}, this.calc.basePlan,
                                    this.planState.target > 0);
        this._goalsTouched = true;
        this.state.sceneName = plan.name;
        this._ripple();
        this._recompute();
        this._toast(_t("“%s” is on the canvas.", plan.name));
    }

    async removePlan(row) {
        if (this.state.busy) { return; }
        this.state.busy = true;
        try {
            await this.orm.call("pb.decision.room", "delete_plan", [row.id]);
            this.state.plans = this.state.plans.filter((p) => p.id !== row.id);
            if (this.comparison.kind === "plan"
                && this.comparison.id === row.id) {
                this.comparison = { kind: "baseline", id: 0,
                                    name: this.TODAY, state: null };
            }
            this._recompute();
            this._toast(_t("“%s” removed.", row.name));
        } catch (e) {
            this._toast(this._reason(e));
        } finally {
            this.state.busy = false;
        }
    }

    async useAsComparison() {
        this.comparison = {
            kind: "plan", id: 0, name: this.state.sceneName,
            state: cloneState(this.planState),
        };
        this._recompute();
        this._toast(_t("This plan is now the comparison. Every number is "
                       + "measured against it."));
    }

    // -------------------------------------------------------------- saving
    openSave() {
        this.state.saveName = this.state.sceneName === this.TODAY
            ? "" : String(this.state.sceneName);
        this.state.saveConflict = false;
        this.state.saveError = "";
        this._openDialog("saveOpen");
    }

    closeSave() { this.state.saveOpen = false; }

    onSaveName(event) {
        this.state.saveName = event.target.value;
        this.state.saveConflict = false;
        this.state.saveError = "";
    }

    async confirmSave(replace = false) {
        const name = (this.state.saveName || "").trim();
        if (!name) {
            this.state.saveError = _t("Give the plan a name first.");
            return;
        }
        if (!replace
            && this.state.plans.some((p) => p.name === name)) {
            this.state.saveConflict = true;
            return;
        }
        if (!replace
            && this.state.plans.length >= (this.state.limits.max_plans || 20)) {
            this.state.saveError = _t(
                "%s plans are saved for this company. Remove one first.",
                this.state.limits.max_plans || 20);
            return;
        }
        const c = this.calc;
        this.state.busy = true;
        try {
            await this.orm.call("pb.decision.room", "save_plan", [{
                name,
                replace,
                state: cloneState(this.planState),
                goals: JSON.parse(JSON.stringify(this.goals)),
                summary: {
                    profit: c.plan.year.profit,
                    cost: c.plan.year.people,
                    revenue: c.plan.year.revenue,
                    coverage: c.plan.year.coverage,
                    heads: c.plan.year.headcount,
                    margin: c.plan.year.margin,
                },
            }]);
            const data = await this.orm.call("pb.decision.room", "get_room", []);
            this.state.plans = data.plans || [];
            this.state.sceneName = name;
            this.state.saveOpen = false;
            this._recompute();
            this._toast(_t("“%(name)s” saved for everyone at %(company)s.",
                           { name, company: this.state.company.name || "" }));
        } catch (e) {
            this.state.saveError = this._reason(e);
        } finally {
            this.state.busy = false;
        }
    }

    _reason(error) {
        const data = error && error.data;
        return (data && (data.message || data.arguments && data.arguments[0]))
            || (error && error.message) || String(error);
    }

    // ===================================================================
    // assumptions (read only in this release)
    // ===================================================================
    openAssumptions() { this._openDialog("assumptionsOpen"); }
    closeAssumptions() { this.state.assumptionsOpen = false; }

    get assumptionLines() {
        const a = this.assumptions;
        const f = this.fmt;
        const teams = (this.baseline.teams || []).length;
        const lines = [
            [_t("Who this is about"),
             _t("%(people)s people in %(teams)s teams, as they stood on "
                + "%(date)s. Pay is the monthly salary on each open contract.",
                { people: f.int(this.baseline.headcount), teams,
                  date: this.baseline.asof })],
            [_t("What the business pays on top"),
             _t("Employer contributions %(rate)s of pay%(cap)s. Allowances add "
                + "%(allow)s of base pay.",
                { rate: f.pct(a.employer_rate_pct || 0),
                  cap: a.contribution_cap
                      ? _t(", capped at %s a month",
                           f.exact(a.contribution_cap)) : "",
                  allow: f.pct(a.allowance_pct || 0) })],
            [_t("What the employee has taken off"),
             _t("Employee contributions %(rate)s of pay, then income tax. "
                + "Neither is an extra cost to the business — they only change "
                + "what reaches the employee.",
                { rate: f.pct(a.employee_rate_pct || 0) })],
            [_t("Extra hours"),
             _t("Overtime is paid at %(mult)s times the normal hourly rate, "
                + "worked out over %(days)s paid days a month.",
                { mult: (a.ot_multiplier || 1.5).toFixed(2).replace(/0$/, ""),
                  days: a.work_days || 22 })],
            [_t("Joining and leaving"),
             _t("Recruiting someone costs %(hire)s of their pay, once, in the "
                + "month they arrive. They are paid in full from day one and "
                + "deliver about %(ramp)s in that first month. Ending a role "
                + "costs %(sev)s.",
                { hire: this._months(a.recruit_cost_months || 1),
                  ramp: f.pct(a.ramp_first_month_pct || 50, 0),
                  sev: this._months(a.severance_months || 1.5) })],
            [_t("The yearly bonus"),
             a.bonus_month_index
                 ? _t("%(months)s of pay, in %(month)s.",
                      { months: this._months(this.planState.bonusMonths),
                        month: monthLong((a.bonus_month_index || 1) - 1) })
                 : _t("No yearly bonus is assumed.")],
            [_t("Everything that is not people"),
             _t("%(fixed)s a month, plus %(pct)s of whatever you sell.",
                { fixed: f.exact(a.other_fixed_monthly || 0),
                  pct: f.pct(a.other_pct_revenue || 0) })],
            [_t("The shape of the year"),
             _t("Work is not spread evenly: the curve is quiet after the new "
                + "year and busiest in October and November. Your revenue "
                + "target is spread along it.")],
            [_t("What this leaves out"),
             _t("Individual people, working-capital timing, roster legality "
                + "and tax filings. This is a planning sketch, not a payroll "
                + "calculation — and nothing here changes payroll.")],
        ];
        return lines.map(([title, copy]) => ({ title, copy }));
    }

    /** "1 month" / "1.5 months" — never "1 months". */
    _months(value) {
        const n = Number(value) || 0;
        const text = Number.isInteger(n) ? String(n) : String(n);
        return n === 1 ? _t("%s month", text) : _t("%s months", text);
    }

    get whoCanChange() {
        return this.state.canManage
            ? _t("You can change these numbers.")
            : _t("These numbers are looked after by your HR or finance lead. "
                 + "Ask them if one of them looks wrong.");
    }

    get contributionLines() {
        const a = this.assumptions;
        const f = this.fmt;
        return [
            { label: _t("Employer contributions"),
              value: f.pct(a.employer_rate_pct || 0) },
            { label: _t("Employee contributions"),
              value: f.pct(a.employee_rate_pct || 0) },
            { label: _t("Contributions capped at"),
              value: a.contribution_cap
                  ? f.exact(a.contribution_cap) : _t("no cap") },
            { label: _t("Allowances"), value: f.pct(a.allowance_pct || 0) },
            { label: _t("Overtime rate"),
              value: _t("%s× normal", a.ot_multiplier || 1.5) },
            { label: _t("Paid working days"),
              value: _t("%s a month", a.work_days || 22) },
        ];
    }

    // ===================================================================
    // a company with nobody on record
    // ===================================================================
    openSketch() { this._openDialog("sketchOpen"); }
    closeSketch() { this.state.sketchOpen = false; }

    addSketchTeam() {
        const name = (this.state.sketchName || "").trim();
        const heads = Math.max(1, Math.round(this.state.sketchPeople || 0));
        const pay = Math.max(0, Number(this.state.sketchPay) || 0);
        if (!name || !pay) {
            this._toast(_t("Give the team a name and a monthly pay first."));
            return;
        }
        const key = `sketch_${(this.baseline.teams || []).length + 1}`;
        this.baseline = {
            ...this.baseline,
            headcount: (this.baseline.headcount || 0) + heads,
            teams: [...(this.baseline.teams || []), {
                key, name, department_id: 0, revenue: true, heads,
                pay_month_avg: pay,
                roles: [{ key: `${key}_r`, name: _t("Everyone"), job_id: 0,
                          heads, pay_month_avg: pay, level: 1 }],
            }],
        };
        this.state.teamKey = key;
        this.state.sketchOpen = false;
        this.state.sketchName = "";
        this._recompute();
        this._toast(_t("“%s” added to this sketch. It is not saved to anybody's "
                       + "record.", name));
    }

    onSketch(field, event) { this.state[field] = event.target.value; }

    // ===================================================================
    // painting
    // ===================================================================
    paint() {
        const c = this.calc;
        if (!c) { return; }
        const metric = this.metric;
        const coverage = metric === "coverage";
        const goal = this._goalPace(c);
        drawHorizon(this.horizonRef.el, {
            plan: series(c.plan, metric),
            ref: series(c.ref, metric),
            lo: series(c.band.lo, metric),
            hi: series(c.band.hi, metric),
            goal,
            month: this.state.month,
            diff: this.state.diff,
            coverage,
            goodUp: this.metricDef.goodUp,
            fmt: (v) => (coverage ? `${Math.round(v)}%` : this.fmt.money(v)),
        });
        drawRing(this.ringRef.el, {
            value: c.plan.year.coverage,
            ref: c.ref.year.coverage,
            goodAt: this.goals.coverage.on
                ? this.goals.coverage.target / 100 : 0.95,
        });
        this._tweenHero();
    }

    _goalPace(c) {
        if (this.state.diff) { return null; }
        if (this.metric === "profit" && this.goals.profit.on) {
            return c.plan.rows.map(
                (_row, i) => this.goals.profit.target * (i + 1) / 12);
        }
        if (this.metric === "people" && this.goals.cost.on) {
            return c.plan.rows.map(
                (_row, i) => this.goals.cost.target * (i + 1) / 12);
        }
        if (this.metric === "coverage" && this.goals.coverage.on) {
            return c.plan.rows.map(() => this.goals.coverage.target);
        }
        return null;
    }

    _tweenHero() {
        const el = this.heroRef.el;
        if (!el) { return; }
        const to = this.heroValue;
        cancelAnimationFrame(this._heroFrame);
        const from = (this._heroMetric === this.metric
                      && this._heroFrom !== null) ? this._heroFrom : to;
        this._heroMetric = this.metric;
        this._heroFrom = to;
        if (!this.state.motion || Math.abs(to - from) < 1e-9) {
            el.textContent = this.heroText(to);
            return;
        }
        const started = performance.now();
        const tick = (now) => {
            const k = Math.min(1, (now - started) / TWEEN_MS);
            const eased = 1 - Math.pow(1 - k, 3);
            el.textContent = this.heroText(from + (to - from) * eased);
            if (k < 1) { this._heroFrame = requestAnimationFrame(tick); }
        };
        this._heroFrame = requestAnimationFrame(tick);
    }

    // ===================================================================
    // chrome
    // ===================================================================
    onKey(event) {
        if (event.key === "Escape") {
            this.state.saveOpen = false;
            this.state.goalsOpen = false;
            this.state.assumptionsOpen = false;
            this.state.sketchOpen = false;
            return;
        }
        if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z"
            && !event.shiftKey) {
            const tag = (event.target.tagName || "").toLowerCase();
            if (tag === "input" || tag === "textarea") { return; }
            event.preventDefault();
            this.undo();
        }
    }

    _toast(message) {
        this.state.toast = message;
        clearTimeout(this._toastTimer);
        this._toastTimer = setTimeout(() => { this.state.toast = ""; }, 4200);
    }

    get inHub() { return !!this.props.inPlan || !!this.props.embedded; }

    /**
     * The way back.
     *
     * Whoever opened the room says how to leave it — but a DEEP LINK says
     * nothing, and somebody who typed the address or followed a bookmark would
     * otherwise be standing in a full-screen room with no door. So a standalone
     * room always offers People, which is where the room lives.
     */
    get back() {
        const given = hubBack(this.props);
        if (given || this.inHub) { return given; }
        return {
            label: _t("People"), tag: "",
            xmlid: "pb_people_hub.action_pb_people_hub",
            lens: "plan", lensKey: "pb_lens", context: {},
        };
    }

    openPeople() {
        openHub(this.actionService, {
            xmlid: "pb_people_hub.action_pb_people_hub", lens: "plan",
        });
    }

    get monthOptions() {
        return MONTHS.map((name, i) => ({ value: i + 1, label: monthLong(i) }));
    }

    get emptyTitle() { return _t("The Decision Room is not open to you."); }

    get emptyNote() {
        return _t("Planning the year is done by the people who hold the "
                  + "Decision Room role. Ask your HR or finance lead to add "
                  + "you, and this screen fills itself in.");
    }
}

registry.category("actions").add("pb_decision_room", PbDecisionRoom);
