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
    onWillUnmount, onWillUpdateProps,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { user } from "@web/core/user";
import { hubBack, HubBackChip, openHub } from "@pb_hub/js/hub_nav";
import {
    makeFormat, MONTHS, monthLong, monthShort,
    useTranslator as useFormatTranslator,
} from "@pb_decision_room/js/decision_format";
import {
    drawHorizon, drawRing, drawDemand, drawBridge, drawRoom,
    tweenSeries, easeOut,
} from "@pb_decision_room/js/decision_charts";
import {
    compute, defaultState, normalizeState, normalizeGoals, defaultGoals,
    evaluateGoals, series, stressBand, story, warnings, bridge, marginal,
    balanceShifts, payStory, teamsInDecember, headroom, candidates,
    stressOutcome, briefModel, changes, describeChange, experimentSize,
    GOAL_DEFS, GOAL_ORDER, cloneState, SHIFTS,
    computeBlocks, rateFor, actualSeries, actualPeople, actualVerdict,
    closedMonths,
    useTranslator as useEngineTranslator,
} from "@pb_decision_room/js/decision_engine";

/**
 * THE ENGINE AND THE FORMATTER SPEAK VIETNAMESE THROUGH HERE.
 *
 * Neither file may import anything — `node tools/decision_engine_check.mjs`
 * loads them off disk exactly as they ship — so they are handed the platform's
 * translator instead. This runs while the asset bundle is being evaluated,
 * long before any component renders, and every `_t("…")` inside those two
 * files is still found by the string extractor exactly as if it had been
 * imported there.
 */
useEngineTranslator(_t);
useFormatTranslator(_t);

/** Has this person asked their computer to stop moving things? */
function prefersReducedMotion() {
    try {
        return !!(window.matchMedia
            && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    } catch {
        return false;
    }
}

const UNDO_DEPTH = 40;
const TWEEN_MS = 350;
/** How long a chart takes to travel from its old shape to its new one. */
const CHART_MS = 300;
/** Below this width the control room becomes a sheet you pull up. */
const PHONE = 720;
/** Where the scope a person last planned is remembered, per database. */
const SCOPE_KEY = "pbdr.scope.v1";
/** The five things a plan can be about, in the words a reader sees. */
const SCOPE_WORDS = () => ({
    group: _t("Whole group"),
    country: _t("Country"),
    company: _t("Company"),
    division: _t("Division"),
    scheme: _t("Payroll scheme"),
});

/**
 * A money box a person can actually type into.
 *
 * It SHOWS the compact form the rest of the room speaks — ₫2,200B — and
 * accepts every spelling of the same amount: 2200000000000, "2,200 B",
 * "2.2 t", "1.5m", with or without the currency symbol. Arrow keys step by
 * the unit on screen, so up on ₫2,200B is ₫2,201B and not a fraction of a
 * dong. Text that is not a number at all leaves the old value exactly where
 * it was and shakes once, because silently zeroing a revenue target is the
 * worst thing a box like this can do.
 */
export class DrMoneyInput extends Component {
    static template = "pb_decision_room.DrMoneyInput";
    static props = {
        value: Number,
        api: Object,                 // {format, parse, step, symbol}
        label: String,
        onCommit: Function,
        inputId: { type: String, optional: true },
        min: { type: Number, optional: true },
        tone: { type: String, optional: true },
    };

    setup() {
        this.box = useRef("box");
        this.state = useState({
            text: this.props.api.format(this.props.value),
            editing: false,
            shake: false,
        });
        onWillUpdateProps((next) => {
            if (!this.state.editing) {
                this.state.text = next.api.format(next.value);
            }
        });
        // `t-att-value` writes the ATTRIBUTE, and a browser stops mirroring
        // that into the field the moment somebody types in it. Without this
        // the box would keep whatever nonsense was typed after a refusal,
        // while the plan quietly held the old number — the one state a money
        // box must never be in.
        onPatched(() => this._sync());
    }

    _sync() {
        const el = this.box.el;
        if (el && !this.state.editing && el.value !== this.state.text) {
            el.value = this.state.text;
        }
    }

    _show(text) {
        this.state.text = text;
        if (this.box.el) { this.box.el.value = text; }
    }

    onFocus() { this.state.editing = true; }

    onInput(event) { this.state.text = event.target.value; }

    /** Enter and blur mean the same thing: "I have finished typing." */
    onKeydown(event) {
        if (event.key === "Enter") { event.preventDefault(); this.commit(); }
        else if (event.key === "Escape") { this.cancel(); }
        else if (event.key === "ArrowUp" || event.key === "ArrowDown") {
            event.preventDefault();
            this.nudge(event.key === "ArrowUp" ? 1 : -1);
        }
    }

    nudge(direction) {
        const current = this.props.api.parse(this.state.text);
        const from = current === null ? this.props.value : current;
        const step = this.props.api.step(from) || 1;
        const next = Math.max(this.props.min === undefined ? -Infinity
            : this.props.min, from + direction * step);
        this._show(this.props.api.format(next));
        this.props.onCommit(next);
    }

    cancel() {
        this.state.editing = false;
        this._show(this.props.api.format(this.props.value));
    }

    commit() {
        const value = this.props.api.parse(this.state.text);
        this.state.editing = false;
        if (value === null
            || (this.props.min !== undefined && value < this.props.min)) {
            this._show(this.props.api.format(this.props.value));
            this.state.shake = true;
            setTimeout(() => { this.state.shake = false; }, 460);
            return;
        }
        this._show(this.props.api.format(value));
        this.props.onCommit(value);
    }
}

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
    static components = { HubBackChip, DrMoneyInput };
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
        this.demandRef = useRef("demand");
        this.bridgeRef = useRef("bridge");
        this.roomRef = useRef("room");

        /** Stable identities, built ONCE: a money box handed a freshly made
         *  function on every paint re-renders on every paint (W21). */
        /** How the engine's search functions compute one trial year. Bound
         *  ONCE: a fresh arrow on every call is a fresh identity, and these
         *  are passed into memoised getters. */
        this._runner = (trial) => this._run(trial).group;

        this.moneyApi = {
            format: (v) => this.fmt.money(v),
            parse: (text) => this.fmt.parse(text),
            step: (v) => this.fmt.step(v),
            symbol: () => this.fmt.symbol,
        };

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
            // The operating system's own answer, asked once. Somebody who has
            // told their computer they do not want movement has told THIS
            // screen too, and should not have to say it again.
            motion: !prefersReducedMotion(),
            teamKey: "",
            roleKey: "",
            moveMonth: 1,

            // the detail workspace
            detail: "coverage",
            roomTeam: "",
            roomRole: "",

            // trying a possibility
            preview: false,
            finding: false,
            searchNote: "",

            // the phone: the control room becomes a sheet you pull up
            phone: false,
            sheet: false,
            refreshing: false,

            // dialogs, one at a time
            saveOpen: false,
            saveName: "",
            saveConflict: false,
            saveError: "",
            goalsOpen: false,
            assumptionsOpen: false,
            assumeDraft: {},
            assumeError: "",
            assumeBusy: false,
            briefBusy: false,

            // a company with nobody on record can still sketch one
            sketchOpen: false,
            sketchName: "",
            sketchPeople: 10,
            sketchPay: 0,

            // ---- GROUP P4 ------------------------------------------------
            // what this plan is a plan FOR, and the picker that changes it
            scope: { kind: "company", ref: "", label: "", mixed: false,
                     currencies: [], company_ids: [] },
            scopeOpen: false,
            scopeBusy: false,
            scopeNote: "",
            openNodes: {},
            // a group read in each entity's own money instead of the board's
            ownMoney: false,
            year: new Date().getFullYear(),
            // the decision
            decideOpen: false,
            decideFor: 0,
            decideApprove: true,
            decideNote: "",
            decideBusy: false,
            versionsOpen: false,
            versionsFor: 0,
            versions: [],
            exactBusy: 0,
            exactNote: "",
            // Where this scope's statutory numbers come from. Reactive,
            // because the dialog redraws the moment the switch is pressed.
            assumeMeta: {},
            // THE HOME DECISION (asked for in the handover): approvals reach
            // the reader as a CHIP on the Decision Room lens they already
            // have, not as a second Home lens. A rail the IA programme spent
            // five cycles cutting from thirty-eight items to eight does not
            // get a ninth whose content is empty on most days — and a chip
            // that vanishes when there is nothing to decide is the honest
            // shape for something that is usually nothing.
            awaiting: { count: 0, plans: [] },

            toast: "",
            busy: false,
        });

        // Not reactive on purpose (see the file header).
        this.baseline = { asof: "", headcount: 0, full_time: 0,
                          split_people: 0, teams: [], source: "" };
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
        this._preview = null;       // {state, goals, scene, historyLength}
        this._paths = [];           // the three ways the finder found
        this._room = null;          // the headroom scan, memoised
        this._roomKey = "";
        this._chartFrom = {};       // where each chart is travelling FROM
        this._chartSig = {};        // and what it last travelled to
        this._chartFrame = {};
        this._media = null;
        this._onVisibility = null;
        this.assumptionsForm = [];
        this.assumptionsGroups = [];
        // ---- GROUP P4, held off the reactive state for the same reason the
        // computed years are: they are replaced wholesale, never edited.
        this.blocks = [];
        this.rates = { target: {}, rows: {}, unknown: [], known: true };
        this.actuals = { available: false, months: [] };
        this.scopeTree = null;
        this.rulesets = [];
        this._calcBlocks = null;
        this._exactTimer = null;

        // The reader's language decides how money is SAID, not only which
        // words surround it: ₫2.200 tỷ and ₫2,200B are the same amount
        // written by two different finance departments.
        this.lang = user.lang || "";
        this.fmt = makeFormat({}, this.lang);

        onWillStart(async () => { await this.load(); });
        onMounted(() => {
            this._resize = new ResizeObserver(() => this.paint());
            if (this.horizonRef.el) { this._resize.observe(this.horizonRef.el); }
            this._watchWidth();
            this.paint();
            this._focusArrival();
            // A play-through nobody is watching is a timer nobody wanted:
            // leave the tab and the year stops where it is.
            this._onVisibility = () => {
                if (document.visibilityState === "hidden") { this.stopPlay(); }
            };
            document.addEventListener("visibilitychange", this._onVisibility);
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
            if (this._media && this._media.removeEventListener) {
                this._media.removeEventListener("change", this._onWidth);
            }
            if (this._onVisibility) {
                document.removeEventListener("visibilitychange",
                                             this._onVisibility);
            }
            cancelAnimationFrame(this._heroFrame);
            for (const key of Object.keys(this._chartFrame)) {
                cancelAnimationFrame(this._chartFrame[key]);
            }
            clearTimeout(this._toastTimer);
            clearTimeout(this._pulseTimer);
            window.removeEventListener("keydown", this.onKey, true);
        });
    }

    ic(name, size = 16) { return ic(name, size); }

    // ===================================================================
    // reading
    // ===================================================================
    /**
     * The scope this room opens on.
     *
     * Three places, in order, and every one of them is somebody saying
     * something: the URL (a link a colleague sent, and the thing that makes a
     * scope shareable at all), then what this person was last looking at, then
     * their own company. A hash that names a scope nobody can reach falls back
     * silently on the server and the chip says so.
     */
    _startScope() {
        const fromHash = this._scopeFromHash();
        if (fromHash) { return fromHash; }
        try {
            const raw = window.localStorage.getItem(SCOPE_KEY);
            const saved = raw ? JSON.parse(raw) : null;
            if (saved && saved.kind) {
                return { kind: saved.kind, ref: String(saved.ref || "") };
            }
        } catch { /* a private window has no storage; that is not an error */ }
        return { kind: "company", ref: "" };
    }

    _scopeFromHash() {
        try {
            const hash = new URLSearchParams(
                String(window.location.hash || "").replace(/^#/, ""));
            const kind = hash.get("dr_scope");
            if (!kind) { return null; }
            return { kind, ref: String(hash.get("dr_ref") || "") };
        } catch {
            return null;
        }
    }

    _rememberScope(scope) {
        try {
            window.localStorage.setItem(SCOPE_KEY, JSON.stringify(
                { kind: scope.kind, ref: scope.ref }));
        } catch { /* nothing to do about it, and nothing to say */ }
        try {
            const hash = new URLSearchParams(
                String(window.location.hash || "").replace(/^#/, ""));
            hash.set("dr_scope", scope.kind);
            hash.set("dr_ref", String(scope.ref || ""));
            window.history.replaceState(null, "", "#" + hash.toString());
        } catch { /* a hash we cannot write is not worth a dialog */ }
    }

    async load(refresh = false, scope = null) {
        try {
            const asked = scope || this._startScope();
            const data = await this.orm.call(
                "pb.decision.room", "get_room", [],
                { refresh, scope: asked, year: this.state.year });
            this.state.allowed = !!data.allowed;
            this.state.canManage = !!data.can_manage;
            this.state.company = data.company || {};
            this.state.plans = data.plans || [];
            this.state.awaiting = data.awaiting || { count: 0, plans: [] };
            this.state.limits = data.limits || { max_plans: 20 };
            this.state.error = "";
            this.baseline = data.baseline
                || { asof: "", headcount: 0, full_time: 0, split_people: 0,
                     teams: [], blocks: [],
                     source: "" };
            this.blocks = this.baseline.blocks || [];
            this.assumptions = data.assumptions || {};
            this.assumptionsForm = data.assumptions_form || [];
            this.assumptionsGroups = data.assumptions_groups || [];
            this.state.assumeMeta = data.assumptions_scope || {};
            this.rates = data.rates
                || { target: {}, rows: {}, unknown: [], known: true };
            this.actuals = data.actuals || { available: false, months: [] };
            this.state.scope = data.scope || this.state.scope;
            this.state.scopeNote = (data.scope || {}).lost || "";
            this.state.year = data.year || this.state.year;
            this._rememberScope(this.state.scope);
            // The money the STAGE speaks. For a group that is the board's own
            // currency; for anything else it is the company's.
            this.fmt = makeFormat(
                (this.state.scope || {}).currency
                || (data.company || {}).currency || {}, this.lang);

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
            this.state.roomTeam = this.state.teamKey;
            this.state.roomRole = "";
            this.state.detail = (this.planState.target || 0) > 0
                ? "coverage" : "people";
            this.state.moveMonth = this.planState.start;
            this.state.month = Math.min(11, Math.max(0, new Date().getMonth()));
            this._history = [];
            this._preview = null;
            this.state.preview = false;
            this._clearPaths();
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

    // ===================================================================
    // GROUP P4 — the scope chip and its picker
    // ===================================================================
    get scopeWord() {
        return SCOPE_WORDS()[this.state.scope.kind] || "";
    }

    /** What the chip reads: "Retail scheme · Vietnam", in the words a
     *  person uses. Never the scope's code name. */
    get scopeChip() {
        const scope = this.state.scope || {};
        const parts = [scope.label || _t("This company")];
        if (scope.kind !== "group" && scope.group_name) {
            parts.push(scope.group_name);
        }
        return parts.join(" · ");
    }

    get scopeIcon() {
        return { group: "globe", country: "mapPin", company: "building",
                 division: "layers", scheme: "route" }[
            this.state.scope.kind] || "building";
    }

    get isGroupScope() {
        return (this.state.scope.company_ids || []).length > 1;
    }

    get scopeCurrencies() {
        return (this.state.scope.currencies || []).join(" · ");
    }

    async openScope() {
        this.stopPlay();
        if (this.state.scopeOpen) { this.state.scopeOpen = false; return; }
        this._openDialog("scopeOpen");
        if (this.scopeTree) { return; }
        this.state.scopeBusy = true;
        try {
            this.scopeTree = await this.orm.call(
                "pb.decision.room", "get_scopes", []);
            // Everything above the scope a person is standing in is open, so
            // the tree arrives showing where they are rather than making them
            // hunt for it.
            for (const node of (this.scopeTree.nodes || [])) {
                this.state.openNodes[this._nodeKey(node)] = true;
                for (const child of (node.children || [])) {
                    this.state.openNodes[this._nodeKey(child)] = true;
                }
            }
        } catch (e) {
            this.scopeTree = { has_group: false, nodes: [],
                               note: this._reason(e) };
        } finally {
            this.state.scopeBusy = false;
            this.state.rev++;
        }
    }

    closeScope() { this.state.scopeOpen = false; }

    _nodeKey(node) { return `${node.kind}:${node.ref}`; }

    /** The tree, flattened to rows the template can draw with one loop. */
    get scopeRows() {
        void this.state.rev;
        const rows = [];
        const words = SCOPE_WORDS();
        const walk = (node, depth) => {
            const key = this._nodeKey(node);
            const open = !!this.state.openNodes[key];
            const kids = node.children || [];
            rows.push({
                key, depth, node, open,
                hasKids: kids.length > 0,
                // OWL renders a bare `undefined` identifier as an attribute,
                // so the "no aria-expanded here" case is FALSE, which OWL
                // drops, and never the word itself.
                expanded: kids.length ? (open ? "true" : "false") : false,
                // A tree read aloud has to say how deep it is, or every row
                // sounds like a top-level one.
                level: depth + 1,
                chevron: open ? "chevronDown" : "chevron",
                word: words[node.kind] || "",
                label: node.label,
                people: node.people || 0,
                current: node.kind === this.state.scope.kind
                    && String(node.ref) === String(this.state.scope.ref),
            });
            if (open) { for (const child of kids) { walk(child, depth + 1); } }
        };
        for (const node of ((this.scopeTree && this.scopeTree.nodes) || [])) {
            walk(node, 0);
        }
        return rows;
    }

    get scopeTreeNote() {
        return (this.scopeTree && this.scopeTree.note) || "";
    }

    toggleNode(row) {
        this.state.openNodes[row.key] = !this.state.openNodes[row.key];
        this.state.rev++;
    }

    onScopeKey(row, event) {
        const key = event.key;
        if (key === "ArrowRight" && row.hasKids && !row.open) {
            event.preventDefault();
            this.toggleNode(row);
        } else if (key === "ArrowLeft" && row.hasKids && row.open) {
            event.preventDefault();
            this.toggleNode(row);
        } else if (key === "ArrowDown" || key === "ArrowUp") {
            event.preventDefault();
            const all = [...document.querySelectorAll(".dr-scope-row")];
            const at = all.indexOf(event.currentTarget);
            const next = all[at + (key === "ArrowDown" ? 1 : -1)];
            if (next) { next.focus(); }
        }
    }

    async pickScope(row) {
        this.state.scopeOpen = false;
        await this.changeScope({ kind: row.node.kind, ref: row.node.ref });
    }

    /** Change what the room is about. Everything reloads together. */
    async changeScope(scope) {
        this.state.loaded = false;
        this.state.busy = true;
        try {
            await this.load(false, scope);
            this._toast(_t("Now planning %s.", this.state.scope.label || ""));
        } finally {
            this.state.busy = false;
            this.state.loaded = true;
        }
    }

    _focusArrival() {
        const focus = (this.props.arrival && this.props.arrival.focus) || "";
        if (focus === "group") {
            // A door whose words say "the group" must open ON the group, not
            // on wherever this person happened to be last.
            this.changeScope({ kind: "group", ref: "" });
            return;
        }
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

    /**
     * The year, for a scope that may span several companies.
     *
     * With one company this IS `compute()` — the same function, the same
     * arguments, the same numbers, which is exactly what the identity test
     * holds it to. With several, every company is computed with its own rules
     * in its own money and only the reading is converted (group ledger rule 7).
     */
    _run(state) {
        return computeBlocks(this.baseline, state, this.rates);
    }

    _recompute() {
        const base = this.baseline;
        const a = this.assumptions;
        const baseRun = this._run(this._baseState());
        const basePlan = baseRun.group;
        const planRun = this._run(this.planState);
        const plan = planRun.group;
        this._calcBlocks = planRun;
        const refState = this.comparison.state
            ? normalizeState(this.comparison.state, base, a)
            : normalizeState(this._baseState(), base, a);
        const ref = this.comparison.state
            ? this._run(refState).group : basePlan;
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
            band: stressBand(base, a, this.planState, 10, this._runner),
            checks: evaluateGoals(plan, this.goals, this.fmt),
            story: story(plan, ref, normalizeState(this.planState, base, a),
                         refState, this.comparison.name, base, this.fmt),
            warnings: warnings(plan, ref,
                               normalizeState(this.planState, base, a),
                               this.fmt),
        };
        // The headroom scan is a hundred computed years; it is memoised on the
        // instance and thrown away the moment anything it depended on moves.
        this._roomKey = "";
        this.state.rev++;
    }

    get calc() {
        void this.state.rev;
        return this._calc;
    }

    // ===================================================================
    // GROUP P4 — a group on the stage
    // ===================================================================
    get blockRuns() {
        void this.state.rev;
        return (this._calcBlocks && this._calcBlocks.blocks) || [];
    }

    /** One thin line per company, already in the board's money. A company
     *  whose rate is missing has no line — it is named under the chart. */
    get entityLines() {
        if (!this.isGroupScope || this.state.diff) { return []; }
        const key = this.metric === "people" ? "people" : "profit";
        if (this.metric === "coverage") { return []; }
        return this.blockRuns.filter((b) => b.known).map((block) => {
            let running = 0;
            return {
                label: block.company,
                values: block.plan.rows.map((row, m) => {
                    const rate = rateFor(this.rates, block.code, m);
                    running += (row[key] || 0) * (rate.known ? rate.rate : 0);
                    return running;
                }),
            };
        });
    }

    /** The per-company table under the stage: each line in its own money,
     *  and the same line in the board's money beside it. */
    get companyRows() {
        void this.state.rev;
        if (!this.isGroupScope) { return []; }
        return this.blockRuns.map((block) => {
            const own = makeFormat(block.currency || {}, this.lang);
            const rate = rateFor(this.rates, block.code, 11);
            const year = block.plan.year;
            return {
                key: block.company_id,
                company: block.company,
                code: block.code,
                heads: this.fmt.int(year.headcount),
                ownCost: own.money(year.people),
                ownProfit: own.money(year.profit),
                cost: rate.known ? this.fmt.money(year.people * rate.rate)
                    : _t("not converted"),
                profit: rate.known ? this.fmt.money(year.profit * rate.rate)
                    : _t("not converted"),
                known: rate.known,
                share: Math.round((block.share || 0) * 100),
            };
        });
    }

    /** The sentence under a converted total: which rate, and when from. */
    get rateBadge() {
        if (!this.isGroupScope) { return ""; }
        const codes = Object.keys(this.rates.rows || {});
        const target = (this.rates.target || {}).code || "";
        const parts = [];
        for (const code of codes) {
            if (code === target) { continue; }
            const cell = rateFor(this.rates, code, 11);
            if (!cell.known) { continue; }
            // GR22: a sentence that must READ as a sentence is built as ONE
            // string here, not out of adjacent template nodes.
            parts.push(_t("1 %(src)s = %(rate)s %(dst)s%(when)s",
                          { src: code, rate: this._rateText(cell.rate),
                            dst: target,
                            when: cell.date ? " \u00b7 " + cell.date : "" }));
        }
        return parts.join("   ");
    }

    get notConverted() {
        if (!this.isGroupScope) { return []; }
        return (this.rates.unknown || []).map((row) => {
            const hit = (this._calcBlocks && this._calcBlocks.unknown || [])
                .find((u) => u.code === row.code);
            return {
                code: row.code,
                note: row.note,
                company: hit ? hit.company : "",
            };
        });
    }

    get groupMoneyNote() {
        if (!this.isGroupScope) { return ""; }
        return _t("Every company is worked out in its own money and added up "
                  + "in %(money)s. The revenue target is shared out by how "
                  + "much of the group's pay bill sits in each one.",
                  { money: (this.rates.target || {}).code
                      || this.fmt.code || "" });
    }

    toggleOwnMoney() { this.state.ownMoney = !this.state.ownMoney; }

    // ===================================================================
    // GROUP P4 — what actually happened, over the plan
    // ===================================================================
    get hasActuals() {
        return !!(this.actuals && this.actuals.available
                  && (this.actuals.months || []).length);
    }

    /** The solid line: only for money metrics, only for closed months. */
    get actualLine() {
        if (!this.hasActuals || this.state.diff) { return null; }
        if (this.metric !== "people") { return null; }
        return actualSeries(this.actuals, this.rates, true);
    }

    get actualVerdictText() {
        if (!this.calc) { return ""; }
        if (!this.hasActuals) {
            return (this.actuals && this.actuals.note) || "";
        }
        return actualVerdict(this.calc.plan, this.actuals, this.rates,
                             this.fmt);
    }


    /** The tile: the last closed month, plan against answer. */
    get actualTile() {
        if (!this.hasActuals || !this.calc) { return null; }
        const { monthly, people, full, any } =
            closedMonths(this.calc.plan, this.actuals, this.rates);
        const last = full >= 0 ? full : any;
        if (last < 0) { return null; }
        const row = this.calc.plan.rows[last];
        const gap = monthly[last] - row.people;
        return {
            label: _t("Plan against what happened · %s", monthLong(last)),
            value: this.fmt.money(monthly[last]),
            planned: this.fmt.money(row.people),
            delta: this.fmt.signedMoney(gap),
            bad: gap > 0,
            people: people[last] === null ? "" : this.fmt.int(people[last]),
        };
    }

    /** A rate a person can read: 20,000 and 0.00005 are both rates. */
    _rateText(rate) {
        const n = Number(rate) || 0;
        if (n >= 1000) { return this.fmt.int(Math.round(n)); }
        if (n >= 1) {
            return String(Number(n.toFixed(4)));
        }
        return String(Number(n.toPrecision(4)));
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

    get canUndo() { return this._history.length > 0 || this.state.preview; }

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

    /**
     * A slider a keyboard can actually drive.
     *
     * The browser already moves a range by one step per arrow press, which is
     * 0.5% on the salary lever — eighty presses to cross it. Shift makes each
     * press worth ten, which is how every other serious slider behaves, and
     * how somebody who never touches a mouse gets across the room.
     */
    onLeverKey(lev, event) {
        const down = event.key === "ArrowLeft" || event.key === "ArrowDown";
        const up = event.key === "ArrowRight" || event.key === "ArrowUp";
        if (!event.shiftKey || (!down && !up)) { return; }
        event.preventDefault();
        const step = (Number(lev.step) || 1) * 10;
        const next = Math.max(lev.min, Math.min(lev.max,
            (Number(this.planState[lev.key]) || 0) + (up ? step : -step)));
        if (Math.abs((this.planState[lev.key] || 0) - next) < 1e-9) { return; }
        this._apply({ [lev.key]: next }, _t("Your working plan"));
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

    /** The revenue target, typed the way people write money. */
    setTarget(value) {
        const target = Math.max(0, Number(value) || 0);
        if (Math.abs(target - (this.planState.target || 0)) >= 1e-9) {
            this._apply({ target }, _t("Your working plan"));
            if (target > 0 && this.state.detail === "people") {
                this.state.detail = "coverage";
            }
        }
        this.onTargetCommit();
    }

    /** The target is remembered for everyone, when we may. */
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
        // Undo, while a possibility is being tried, means "back to my plan" —
        // it is the same act, and two different ways to leave a preview is one
        // too many.
        if (this._preview) { this.backToPlan(); return; }
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
        // GROUP P4 — a month that has actually been run gets its own tile, so
        // "the plan said" and "it came to" sit next to each other rather than
        // in two different places on the page.
        const actual = this.actualTile;
        if (actual) {
            tiles.push({
                label: actual.label.toUpperCase(),
                value: actual.value,
                delta: actual.delta,
                bad: actual.bad,
            });
        }
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
        this._markMonth();
    }

    /** Space on the timeline plays the year — the shape every player has. */
    onTimelineKey(event) {
        if (event.key !== " " && event.key !== "Spacebar") { return; }
        event.preventDefault();
        this.togglePlay();
    }

    pickMonth(index) {
        this.stopPlay();
        this.state.month = index;
        this._markMonth();
    }

    /**
     * The month you just chose says so — once, and quietly.
     *
     * On a phone the twelve month cards are a strip you scroll, so the one
     * being explored can be off screen entirely; it is brought to the middle.
     * On a desktop grid nothing scrolls, because scrolling a grid that fits
     * would drag the whole page for no reason.
     */
    _markMonth() {
        clearTimeout(this._pulseTimer);
        this._pulseTimer = setTimeout(() => {
            const strip = document.querySelector(".dr-months");
            const card = strip && strip.querySelector(".dr-month.is-on");
            if (!strip || !card) { return; }
            if (strip.scrollWidth > strip.clientWidth + 4) {
                strip.scrollTo({
                    left: Math.max(0, card.offsetLeft
                        - (strip.clientWidth - card.offsetWidth) / 2),
                    behavior: this.state.motion ? "smooth" : "auto",
                });
            }
            if (!this.state.motion) { return; }
            card.classList.remove("dr-pulse");
            void card.offsetWidth;      // restart the animation
            card.classList.add("dr-pulse");
        }, 20);
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
            name: monthShort(i),
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
     * The six goal cards.
     *
     * The money goals used to be typed "in billions", with the unit written
     * beside the box and the multiplication done on the way in — which worked
     * and read like a form. They are now the same compact money box as the
     * revenue target: you type ₫2,200B, or 2200000000000, or 2.2t, and it is
     * the same amount.
     */
    get goalCards() {
        const checks = this.calc ? this.calc.checks : [];
        return GOAL_ORDER.map((key) => {
            const def = GOAL_DEFS[key];
            const check = checks.find((c) => c.key === key);
            const money = def.unit === "money";
            return {
                key, label: def.label(), money,
                bound: def.sense === "min" ? _t("At least") : _t("At most"),
                unit: money ? ""
                    : (def.unit === "people" ? _t("people") : def.unit),
                step: def.step,
                min: def.min,
                on: this.goals[key].on,
                target: this.goals[key].target,
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
        this.state.scopeOpen = false;
        this.state.decideOpen = false;
        this.state.versionsOpen = false;
        if (name) { this.state[name] = true; }
    }

    openGoals() { this.stopPlay(); this._openDialog("goalsOpen"); }
    closeGoals() { this.state.goalsOpen = false; }

    toggleGoal(key, event) {
        this._push();
        this._goalsTouched = true;
        this._clearPaths();
        this.goals = normalizeGoals(
            { ...this.goals, [key]: { ...this.goals[key],
                                      on: !!event.target.checked } },
            this.calc.basePlan, this.hasTarget);
        this._recompute();
    }

    setGoalTarget(key, event) {
        const raw = event.target.value;
        if (raw === "" || !Number.isFinite(Number(raw))) { return; }
        this.setGoalValue(key, Number(raw));
    }

    setGoalValue(key, value) {
        if (!Number.isFinite(Number(value))) { return; }
        this._goalsTouched = true;
        this._clearPaths();
        this.goals = normalizeGoals(
            { ...this.goals, [key]: { ...this.goals[key],
                                      target: Number(value) } },
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
        const words = SCOPE_WORDS();
        const mine = this.fmt.code || "";
        for (const plan of this.state.plans) {
            const s = plan.summary || {};
            // A plan saved in another currency cannot be lined up beside this
            // one, and the honest thing is to say which money it is in and
            // refuse the comparison rather than print two numbers that look
            // like the same kind of number and are not.
            const sameMoney = !plan.currency || !mine
                || plan.currency === mine;
            rows.push({
                id: plan.id, name: plan.name, tag: "saved",
                who: plan.user,
                heads: this.fmt.int(s.heads || 0),
                cost: sameMoney ? this.fmt.money(s.cost || 0)
                    : this._otherMoney(s.cost || 0, plan.currency),
                served: this.hasTarget && s.coverage !== undefined
                    ? this.fmt.pct((s.coverage || 0) * 100) : "—",
                profit: sameMoney ? this.fmt.money(s.profit || 0)
                    : this._otherMoney(s.profit || 0, plan.currency),
                delta: sameMoney
                    ? this.fmt.signedMoney((s.profit || 0) - refProfit) : "—",
                bad: sameMoney && (s.profit || 0) < refProfit - 1,
                mine: !!plan.mine,
                reference: !!plan.is_reference,
                // ---- GROUP P4 -------------------------------------------
                scope: plan.scope_label || "",
                scopeWord: words[plan.scope_kind] || "",
                sameMoney,
                currency: plan.currency || "",
                status: plan.status || "draft",
                statusLabel: this._statusWord(plan.status),
                versions: plan.versions || 0,
                exact: plan.exact || {},
                exactText: this._exactText(plan),
                canPropose: (plan.mine || this.state.canManage)
                    && plan.status !== "approved",
                canDecide: this.state.canManage && plan.status === "proposed",
                approved: plan.status === "approved",
                decidedBy: plan.decided_by || "",
                note: plan.decision_note || "",
                busy: this.state.exactBusy === plan.id,
            });
        }
        return rows;
    }

    /** A figure in a money this stage does not speak, said in that money. */
    _otherMoney(value, code) {
        const own = makeFormat({ code, symbol: code, position: "after",
                                 decimals: 0 }, this.lang);
        return own.money(value);
    }

    _statusWord(status) {
        return {
            draft: _t("Draft"),
            proposed: _t("Waiting for approval"),
            approved: _t("Approved"),
            rejected: _t("Sent back"),
        }[status || "draft"] || "";
    }

    _exactText(plan) {
        const result = plan.exact || {};
        if (!result || !Object.keys(result).length) { return ""; }
        if (!result.ok) { return result.note || ""; }
        const estimate = (plan.summary || {}).cost || 0;
        const gap = estimate ? (result.year - estimate) / estimate * 100 : 0;
        // A percentage CHANGE, not percentage points: "the estimate was 2.1%
        // low" is the sentence, and "pp" is the wrong unit for it.
        const sign = gap >= 0 ? "+" : "\u2212";
        return _t("Exact cost %(exact)s · the estimate was %(estimate)s "
                  + "(%(gap)s)",
                  { exact: this.fmt.money(result.year),
                    estimate: this.fmt.money(estimate),
                    gap: sign + this.fmt.pct(Math.abs(gap)) });
    }

    // ===================================================================
    // GROUP P4 — proposing, approving, versions and the exact cost
    // ===================================================================
    _planById(id) {
        return this.state.plans.find((p) => p.id === id) || null;
    }

    _replacePlan(plan) {
        const at = this.state.plans.findIndex((p) => p.id === plan.id);
        if (at >= 0) { this.state.plans[at] = plan; }
        else { this.state.plans = [plan, ...this.state.plans]; }
        this.state.rev++;
    }

    async proposePlan(row) {
        if (this.state.busy) { return; }
        this.state.busy = true;
        try {
            const plan = await this.orm.call(
                "pb.decision.room", "propose_plan", [row.id]);
            this._replacePlan(plan);
            this._toast(_t("“%s” is with your approver. They will find it on "
                           + "their home page.", row.name));
        } catch (e) {
            this._toast(this._reason(e));
        } finally {
            this.state.busy = false;
        }
    }

    openDecide(row, approve) {
        this.stopPlay();
        this.state.decideFor = row.id;
        this.state.decideApprove = !!approve;
        this.state.decideNote = "";
        this._openDialog("decideOpen");
    }

    closeDecide() { this.state.decideOpen = false; }

    onDecideNote(event) { this.state.decideNote = event.target.value; }

    get decidePlan() { return this._planById(this.state.decideFor); }

    get decideTitle() {
        const plan = this.decidePlan;
        const name = plan ? plan.name : "";
        return this.state.decideApprove
            ? _t("Approve “%s”?", name) : _t("Send “%s” back?", name);
    }

    get decideCopy() {
        return this.state.decideApprove
            ? _t("Approving keeps a version of this plan exactly as it stands, "
                 + "so what you agreed to survives every edit made afterwards. "
                 + "Nothing about payroll changes.")
            : _t("The plan goes back to its author as a draft, with whatever "
                 + "you write below.");
    }

    /** An approval taken over a missing rate says so in its own record.
     *
     *  Read from the PLAN's own summary and not from the scope on screen: a
     *  person may be standing on a group view while approving a plan that was
     *  saved for one company, and the sentence has to be about the thing being
     *  approved. */
    get decideWarning() {
        const plan = this.decidePlan;
        const missing = ((plan && plan.summary) || {}).unconverted || [];
        if (!this.state.decideApprove || !missing.length) { return ""; }
        return _t("%s of this group's money could not be converted when this "
                  + "plan was saved, so the total in it is a partial one. The "
                  + "version keeps that note.", missing.join(", "));
    }

    async confirmDecide() {
        const row = this.decidePlan;
        if (!row) { this.state.decideOpen = false; return; }
        this.state.decideBusy = true;
        try {
            const plan = await this.orm.call(
                "pb.decision.room", "decide_plan",
                [row.id, this.state.decideApprove, this.state.decideNote]);
            this._replacePlan(plan);
            this.state.decideOpen = false;
            this._toast(this.state.decideApprove
                ? _t("“%s” is approved.", row.name)
                : _t("“%s” went back to %s.", row.name, row.who || ""));
        } catch (e) {
            this._toast(this._reason(e));
        } finally {
            this.state.decideBusy = false;
        }
    }

    async keepEditing(row) {
        this.state.busy = true;
        try {
            const plan = await this.orm.call(
                "pb.decision.room", "copy_plan", [row.id]);
            this._replacePlan(plan);
            this._toast(_t("“%s” is a fresh draft that starts where the "
                           + "approved plan ends.", plan.name));
        } catch (e) {
            this._toast(this._reason(e));
        } finally {
            this.state.busy = false;
        }
    }

    async openVersions(row) {
        this.stopPlay();
        this.state.versionsFor = row.id;
        this.state.versions = [];
        this._openDialog("versionsOpen");
        try {
            this.state.versions = await this.orm.call(
                "pb.decision.room", "plan_versions", [row.id]);
        } catch (e) {
            this._toast(this._reason(e));
        }
    }

    closeVersions() { this.state.versionsOpen = false; }

    get versionRows() {
        const words = SCOPE_WORDS();
        return (this.state.versions || []).map((version) => {
            const snapshot = version.snapshot || {};
            const summary = snapshot.summary || {};
            const scope = snapshot.scope || {};
            return {
                id: version.id,
                title: _t("Version %(n)s · %(label)s",
                          { n: version.number,
                            label: version.label || _t("kept") }),
                who: version.by,
                when: (version.at || "").slice(0, 16).replace("T", " "),
                scope: [words[scope.kind] || "", scope.label || ""]
                    .filter(Boolean).join(" · "),
                cost: this.fmt.money(summary.cost || 0),
                profit: this.fmt.money(summary.profit || 0),
                heads: this.fmt.int(summary.heads || 0),
                unconverted: (snapshot.unconverted || []).join(", "),
            };
        });
    }

    async startExact(row) {
        this.state.exactBusy = row.id;
        this.state.exactNote = _t("Working it out…");
        try {
            await this.orm.call("pb.decision.room", "start_exact", [row.id]);
            this._pollExact(row.id, 0);
        } catch (e) {
            this.state.exactBusy = 0;
            this._toast(this._reason(e));
        }
    }

    /** Ask again, backing off, until the job says it is finished.
     *  Bounded: a job that never answers stops asking and says so. */
    _pollExact(planId, tries) {
        clearTimeout(this._exactTimer);
        if (tries > 90) {
            this.state.exactBusy = 0;
            this.state.exactNote = "";
            this._toast(_t("The exact cost is taking longer than expected. "
                           + "It will appear on the plan when it finishes."));
            return;
        }
        this._exactTimer = setTimeout(async () => {
            let job = {};
            try {
                job = await this.orm.call(
                    "pb.decision.room", "exact_status", [planId]);
            } catch {
                this.state.exactBusy = 0;
                return;
            }
            if (job.state === "done" || job.state === "failed") {
                this.state.exactBusy = 0;
                this.state.exactNote = "";
                const plan = this._planById(planId);
                if (plan) {
                    plan.exact = job.result || {};
                    this.state.rev++;
                }
                this._toast(job.state === "done"
                    ? _t("Exact cost worked out in %s seconds.",
                         Math.round(job.seconds || 0))
                    : (job.message || _t("The exact cost could not be worked "
                                         + "out. Try again.")));
                return;
            }
            this.state.exactNote = job.state === "queued"
                ? _t("Waiting to start…")
                : _t("Working it out… %s%%", job.progress || 0);
            this._pollExact(planId, tries + 1);
        }, tries < 5 ? 800 : 2000);
    }

    get comparisonOptions() {
        const mine = this.fmt.code || "";
        return [
            { value: "baseline", label: _t("The company as it is today") },
            ...this.state.plans.map((p) => ({
                value: String(p.id),
                label: p.name,
                // A plan in another money is offered but not selectable: the
                // reason is on the option itself rather than in a toast after
                // somebody has already clicked.
                disabled: !!(p.currency && mine && p.currency !== mine),
                suffix: (p.currency && mine && p.currency !== mine)
                    ? _t(" — in %s, cannot be compared", p.currency) : "",
            })),
        ];
    }

    /** The chip: how many decisions are waiting on this reader right now.
     *
     *  Plans and PAY are counted together, because a person opening this room
     *  is asking one question — what needs me — and answering it in two
     *  places is how one of the two goes unread for a week. The pay half is
     *  a soft probe: a database without the Pay area simply contributes zero.
     */
    get awaitingText() {
        const state = this.state.awaiting || {};
        const plans = state.count || 0;
        const pay = state.pay_count || 0;
        const parts = [];
        if (plans) {
            parts.push(plans === 1
                ? _t("1 plan is waiting for your decision.")
                : _t("%s plans are waiting for your decision.", plans));
        }
        if (pay && state.pay_sentence) { parts.push(state.pay_sentence); }
        return parts.join(" ");
    }

    goToPlans() {
        const dock = document.querySelector(".dr-dock");
        if (!dock) { return; }
        dock.scrollIntoView({
            behavior: this.state.motion ? "smooth" : "auto", block: "start" });
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
        if (this.state.preview) { this._toast(this.previewNote); return; }
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
        if (this.state.preview) { this._toast(this.previewNote); return; }
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
                scope: { kind: this.state.scope.kind,
                         ref: this.state.scope.ref },
                state: cloneState(this.planState),
                goals: JSON.parse(JSON.stringify(this.goals)),
                summary: {
                    profit: c.plan.year.profit,
                    cost: c.plan.year.people,
                    revenue: c.plan.year.revenue,
                    coverage: c.plan.year.coverage,
                    heads: c.plan.year.headcount,
                    margin: c.plan.year.margin,
                    // The money this plan's numbers are IN. Without it the
                    // dock lines up a dong figure beside a dollar one and
                    // calls the difference a decision.
                    currency: this.fmt.code || "",
                    scope_label: this.state.scope.label || "",
                    unconverted: this.notConverted.map((r) => r.code),
                },
            }]);
            const data = await this.orm.call(
                "pb.decision.room", "get_room", [],
                { scope: { kind: this.state.scope.kind,
                           ref: this.state.scope.ref },
                  year: this.state.year });
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

    /**
     * The server's own sentence, or ours — never the platform's.
     *
     * GR17: the platform's RPC error object carries "Odoo Server Error" in its
     * `message`, and the real sentence is at `error.data.message`. So
     * `error.message` is NOT a rung on this ladder: falling back to it prints
     * the one word this product may never say, in a red box, on the screen the
     * reader is looking at.
     */
    _reason(error) {
        const data = (error && error.data)
            || (error && error.message && error.message.data);
        const said = data
            && (data.message || (data.arguments && data.arguments[0]));
        return String(said || "").trim()
            || _t("That did not go through. Try again, and tell your "
                  + "administrator if it keeps happening.");
    }

    // ===================================================================
    // assumptions (read only in this release)
    // ===================================================================
    openAssumptions() {
        this.state.assumeDraft = {};
        this.state.assumeError = "";
        this._openDialog("assumptionsOpen");
    }

    closeAssumptions() {
        this.state.assumptionsOpen = false;
        this.state.assumeDraft = {};
        this.state.assumeError = "";
    }

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
            [_t("Shifts and when the work arrives"),
             _t("%(evening)s of the people who earn revenue work evenings and "
                + "%(night)s work nights, paid %(eu)s and %(nu)s above base "
                + "pay. The work itself arrives %(dd)s during the day, "
                + "%(de)s in the evening and %(dn)s at night — a shift can "
                + "only serve the work that arrives on it.",
                { evening: f.pct(this.planState.evening || 0, 0),
                  night: f.pct(this.planState.night || 0, 0),
                  eu: f.pct(a.evening_uplift_pct || 0, 0),
                  nu: f.pct(a.night_uplift_pct || 0, 0),
                  dd: f.pct(a.demand_day_pct || 0, 0),
                  de: f.pct(a.demand_evening_pct || 0, 0),
                  dn: f.pct(a.demand_night_pct || 0, 0) })],
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
    // the detail workspace
    // ===================================================================
    get detailTabs() {
        return [
            { key: "coverage", icon: "sun", label: _t("Work & shifts") },
            { key: "money", icon: "trendingUp", label: _t("Why profit changed") },
            { key: "people", icon: "users", label: _t("People & pay") },
            { key: "room", icon: "arrowLeftRight", label: _t("Room to hire") },
        ].map((t) => ({ ...t, active: t.key === this.state.detail }));
    }

    setDetail(key) {
        if (this.state.detail === key) { return; }
        this.state.detail = key;
        // A tab you come back to draws itself again from the beginning: the
        // waterfall grows out of the comparison, the other two arrive whole.
        if (key === "money") {
            delete this._chartFrom.bridge;
            delete this._chartSig.bridge;
        }
        this.state.rev++;
    }

    /** Clicking an impact card opens its tab and walks the page down to it. */
    focusDetail(key) {
        this.setDetail(key);
        setTimeout(() => {
            const el = document.querySelector(".dr-work");
            if (!el) { return; }
            el.scrollIntoView({
                behavior: this.state.motion ? "smooth" : "auto",
                block: "start",
            });
        }, 40);
    }

    /** Arrow keys walk a tab strip; that is what `role="tablist"` promises. */
    onTabKey(event) {
        const keys = this.detailTabs.map((t) => t.key);
        const at = keys.indexOf(this.state.detail);
        let next = -1;
        if (event.key === "ArrowRight") { next = (at + 1) % keys.length; }
        else if (event.key === "ArrowLeft") {
            next = (at - 1 + keys.length) % keys.length;
        } else if (event.key === "Home") { next = 0; }
        else if (event.key === "End") { next = keys.length - 1; }
        if (next < 0) { return; }
        event.preventDefault();
        this.setDetail(keys[next]);
        setTimeout(() => {
            const el = document.querySelector(
                `.dr-tabstrip [data-detail="${keys[next]}"]`);
            if (el) { el.focus(); }
        }, 0);
    }

    // ------------------------------------------------- 1 · work & shifts
    /**
     * Hours, said short: 1.2m h / 840k h / 620 h — and, for a Vietnamese
     * reader, 1,2 triệu giờ / 840 nghìn giờ / 620 giờ. The unit is a
     * translated term and the number keeps this language's own marks.
     */
    _hours(value) {
        const v = Math.abs(Number(value) || 0);
        if (v >= 1e6) {
            return _t("%(n)sm h", { n: this.fmt.fixed(v / 1e6, 2) });
        }
        if (v >= 1e3) {
            return _t("%(n)sk h", { n: this.fmt.int(v / 1e3) });
        }
        return _t("%(n)s h", { n: this.fmt.int(v) });
    }

    get shiftMeta() {
        return {
            day: { name: _t("Day"), icon: "sun", band: _t("06:00 – 14:00") },
            evening: { name: _t("Evening"), icon: "sunset",
                       band: _t("14:00 – 22:00") },
            night: { name: _t("Night"), icon: "moon",
                     band: _t("22:00 – 06:00") },
        };
    }

    get shiftTiles() {
        const c = this.calc;
        if (!c) { return []; }
        const row = c.plan.rows[this.state.month];
        const refRow = c.ref.rows[this.state.month];
        const meta = this.shiftMeta;
        return (row.shifts || []).map((shift, i) => {
            const before = refRow.shifts[i];
            const served = this.hasTarget && shift.demand > 0
                ? Math.min(100, shift.served / shift.demand * 100) : null;
            const wasServed = this.hasTarget && before.demand > 0
                ? Math.min(100, before.served / before.demand * 100) : null;
            const gap = this.hasTarget
                ? Math.max(0, shift.demand - shift.served) : 0;
            const spare = this.hasTarget && gap <= 1
                && shift.available > shift.demand * 1.15;
            return {
                key: shift.key,
                name: meta[shift.key].name,
                icon: meta[shift.key].icon,
                band: meta[shift.key].band,
                premium: shift.uplift > 0
                    ? _t("+%s on top of base pay",
                         this.fmt.pct(shift.uplift * 100, 0))
                    : _t("base rate"),
                heads: this.fmt.int(shift.heads),
                share: this.fmt.pct(shift.share * 100, 0),
                servedPct: served === null ? 0 : served,
                wasPct: wasServed === null ? 0 : wasServed,
                servedText: served === null ? "—" : this.fmt.pct(served),
                hoursText: this._hours(
                    this.hasTarget ? shift.served : shift.available),
                thin: served !== null && served < 95,
                status: !this.hasTarget
                    ? _t("%s of the hours this team can work",
                         this.fmt.pct(shift.share * 100, 0))
                    : (gap > 1
                        ? _t("%s of work goes unserved on this shift",
                             this._hours(gap))
                        : (spare
                            ? _t("Every hour covered · spare capacity here")
                            : _t("Every hour of this shift is covered"))),
                bad: gap > 1,
            };
        });
    }

    get eveningLever() {
        return this._lever(
            "evening", _t("People on the evening shift"),
            _t("A share of the people who earn revenue."), 0, 50, 1, "%");
    }

    get nightLever() {
        return this._lever(
            "night", _t("People on the night shift"),
            _t("A share of the people who earn revenue."), 0, 40, 1, "%");
    }

    get shiftBalance() {
        const a = this.assumptions;
        return _t("The work arrives %(day)s day, %(evening)s evening, "
                  + "%(night)s night.",
                  { day: this.fmt.pct(a.demand_day_pct || 0, 0),
                    evening: this.fmt.pct(a.demand_evening_pct || 0, 0),
                    night: this.fmt.pct(a.demand_night_pct || 0, 0) });
    }

    matchShiftsToDemand() {
        const next = balanceShifts(this.baseline, this.assumptions,
                                   this.planState);
        this._apply({ evening: next.evening, night: next.night },
                    _t("Your working plan"));
        this._toast(_t("Shifts matched to the work: %(evening)s on evenings, "
                       + "%(night)s on nights.",
                       { evening: this.fmt.pct(next.evening, 0),
                         night: this.fmt.pct(next.night, 0) }));
    }

    // -------------------------------------------- 2 · why profit changed
    get bridgeRows() {
        const c = this.calc;
        if (!c) { return []; }
        return bridge(c.plan, c.ref).steps.map((step) => ({
            label: step.label,
            reason: step.reason,
            value: this.fmt.signedMoney(step.value),
            good: step.value >= 0,
            zero: Math.abs(step.value) < 1,
        }));
    }

    get bridgeTotal() {
        const c = this.calc;
        if (!c) { return ""; }
        return this.fmt.signedMoney(c.plan.year.profit - c.ref.year.profit);
    }

    // ------------------------------------------------- 3 · people & pay
    get teamRows() {
        const c = this.calc;
        if (!c) { return []; }
        const rows = teamsInDecember(c.plan, c.ref);
        const max = Math.max(1, ...rows.map(
            (t) => Math.max(t.heads, t.refHeads))) * 1.08;
        return rows.map((t) => ({
            key: t.key,
            name: t.name,
            heads: this.fmt.int(t.heads),
            pay: this.fmt.money(t.payMonth),
            delta: Math.abs(t.heads - t.refHeads) >= 0.5
                ? this.fmt.people(t.heads - t.refHeads) : "",
            planW: (t.heads / max * 100).toFixed(1),
            refW: (t.refHeads / max * 100).toFixed(1),
            title: _t("%(name)s: %(heads)s people, comparison %(was)s",
                      { name: t.name, heads: this.fmt.int(t.heads),
                        was: this.fmt.int(t.refHeads) }),
        }));
    }

    get payRows() {
        const c = this.calc;
        if (!c) { return { strip: [], employee: [], employer: [] }; }
        const p = payStory(c.plan);
        const take = p.gross > 0 ? p.takehome / p.gross * 100 : 100;
        return {
            strip: [
                { key: "take", flex: take,
                  label: _t("Take-home %s", this.fmt.pct(take)) },
                { key: "ded", flex: Math.max(0, 100 - take),
                  label: (100 - take) >= 12 ? _t("Deductions") : "" },
            ],
            employee: [
                { label: _t("Gross pay to employees"),
                  value: this.fmt.money(p.gross), strong: false },
                { label: _t("− Employee contributions and income tax"),
                  value: this.fmt.money(p.withholding), strong: false },
                { label: _t("= What reaches employees"),
                  value: this.fmt.money(p.takehome), strong: true },
            ],
            employer: [
                { label: _t("Employer contributions, paid on top"),
                  value: this.fmt.money(p.contributions), strong: false },
                { label: _t("Overtime and shift premiums"),
                  value: this.fmt.money(p.overtime + p.premiums),
                  strong: false },
                { label: _t("Recruiting, severance and better hours"),
                  value: this.fmt.money(p.recruit + p.severance + p.learning),
                  strong: false },
                { label: _t("Total workforce cost to the business"),
                  value: this.fmt.money(p.total), strong: true },
            ],
        };
    }

    // ------------------------------------------------ 4 · room to hire
    get roomTeamObj() {
        return this.teams.find((t) => t.key === this.state.roomTeam)
            || this.teams[0] || null;
    }

    get roomRoles() { return this.roomTeamObj ? this.roomTeamObj.roles : []; }

    setRoomTeam(event) {
        this.state.roomTeam = event.target.value;
        this.state.roomRole = "";
        this._roomKey = "";
        this.state.rev++;
    }

    setRoomRole(event) {
        this.state.roomRole = event.target.value;
        this._roomKey = "";
        this.state.rev++;
    }

    /** The scan, computed at most once per (plan, team, role). */
    get roomScan() {
        void this.state.rev;
        const key = `${this.state.rev}|${this.state.roomTeam}`
            + `|${this.state.roomRole}`;
        if (this._roomKey === key && this._room) { return this._room; }
        if (!this.calc || !this.roomTeamObj) { return null; }
        const started = performance.now();
        this._room = headroom(
            this.baseline, this.assumptions, this.planState, this.goals,
            this.roomTeamObj.key, this.fmt, this.state.roomRole || null,
            this._runner);
        this._room.ms = Math.round(performance.now() - started);
        this._roomKey = key;
        return this._room;
    }

    get roomResult() {
        const scan = this.roomScan;
        const team = this.roomTeamObj;
        if (!scan || !team) {
            return { title: _t("Pick a team to explore."), copy: "",
                     tries: [] };
        }
        if (!scan.enabled) {
            return {
                title: _t("Choose a goal to see your room to hire."),
                copy: _t("Switch on margin, profit, cost, demand served, team "
                         + "size or overtime and this becomes an answer."),
                tries: [],
            };
        }
        const where = this.state.roomRole && scan.role
            ? _t("%(role)s in %(team)s",
                 { role: scan.role.name, team: team.name })
            : team.name;
        if (!scan.intervals.length) {
            return {
                title: _t("No additional hiring meets every goal."),
                copy: _t("Every extra person in %s breaks at least one of "
                         + "your goals. Ease a goal, or look at hours and "
                         + "productive time instead.", where),
                tries: [],
            };
        }
        const ranges = scan.intervals.map(
            ([lo, hi]) => (lo === hi ? String(lo) : `${lo}–${hi}`)).join(
            _t(" or "));
        const edges = [...new Set(scan.intervals.flatMap(([lo, hi]) => [lo, hi]))]
            .filter((n) => n > 0).slice(0, 4);
        return {
            title: _t("%(range)s more people in %(where)s",
                      { range: ranges, where }),
            copy: _t("Every one of those keeps all your goals. Demand, pay, "
                     + "shifts, overtime and the hiring month all stay exactly "
                     + "where you left them."),
            tries: edges.map((n) => ({
                n, label: _t("Try %s more", this.fmt.int(n)),
            })),
        };
    }

    get roomFootnote() {
        const scan = this.roomScan;
        if (!scan) { return ""; }
        const stepped = scan.step > 1
            ? _t(" in steps of %s people", scan.step) : "";
        const notEarning = scan.team && !scan.revenue
            ? _t(" This team does not earn revenue in this model, so adding "
                 + "people here changes cost only.") : "";
        return _t("Walked from 0 to %(max)s more people%(step)s, holding every "
                  + "other decision fixed.%(note)s",
                  { max: scan.max, step: stepped, note: notEarning });
    }

    tryRoom(n) {
        const team = this.roomTeamObj;
        if (!team) { return; }
        const role = this.state.roomRole || null;
        const where = role
            ? (this.roomRoles.find((r) => r.key === role) || {}).name
            : team.name;
        this.beginPreview({
            ...this.planState,
            moves: [...(this.planState.moves || []),
                    { team: team.key, role, n, month: this.planState.start }],
        }, _t("%(n)s more in %(where)s · preview",
              { n: this.fmt.int(n), where }));
    }

    // ===================================================================
    // the goal finder
    // ===================================================================
    _clearPaths() {
        this._paths = [];
        this.state.searchNote = "";
    }

    get hasPaths() { void this.state.rev; return this._paths.length > 0; }

    /**
     * When the three directions turn out to be the same one.
     *
     * It happens, and it is the truth rather than a failure: if the team
     * already serves every hour of the work, then hiring, overtime and
     * training all only add cost, and the best plan on every lane is the one
     * already on screen. Showing that as three identical cards makes the room
     * look broken. One card, saying what actually happened, does not.
     */
    get pathsAreOne() {
        void this.state.rev;
        if (this._paths.length < 2) { return false; }
        const first = JSON.stringify(this._paths[0].state);
        return this._paths.every((p) => JSON.stringify(p.state) === first);
    }

    get pathsVerdict() {
        const cards = this.pathCards;
        if (!cards.length) { return null; }
        const one = cards[0];
        return {
            ...one,
            title: one.met
                ? _t("Your plan already meets these goals.")
                : _t("Nothing reaches these goals from here."),
            copy: one.met
                ? _t("Every direction the search tried came back to the plan "
                     + "you already have. Raise a goal and look again — there "
                     + "is room to think bigger.")
                : _t("%(gaps)s. Adding people, hours or productive time only "
                     + "moves the plan further away, so the search came back "
                     + "to where you started. Ease a goal, change the revenue "
                     + "target, or look at what the work itself is worth.",
                     { gaps: one.gapText }),
        };
    }

    get anyGoalOn() {
        return GOAL_ORDER.some((k) => this.goals && this.goals[k]
                               && this.goals[k].on);
    }

    get pathCards() {
        void this.state.rev;
        const c = this.calc;
        if (!c) { return []; }
        const names = {
            hire: { eyebrow: _t("HIRING & HOURS"), title: _t("Build the team"),
                    icon: "users",
                    keeps: _t("Productive time stays as you assumed it.") },
            develop: { eyebrow: _t("SKILLS & HOURS"),
                       title: _t("Develop the team"), icon: "sparkles",
                       keeps: _t("Hiring stays exactly as you planned it.") },
            balanced: { eyebrow: _t("MOST FLEXIBLE"), title: _t("Blend the two"),
                        icon: "gitBranch",
                        keeps: _t("Hiring and productive time can both move.") },
        };
        return this._paths.map((path, index) => {
            const meta = names[path.lane];
            const added = (path.state.moves || [])
                .reduce((total, m) => total + m.n, 0);
            const team = this._paths.team;
            return {
                index,
                lane: path.lane,
                eyebrow: meta.eyebrow,
                title: meta.title,
                icon: meta.icon,
                met: path.met,
                status: path.met
                    ? _t("Meets every goal you switched on")
                    : _t("%(n)s goal%(s)s still missed",
                         { n: path.failed, s: path.failed === 1 ? "" : "s" }),
                profit: this.fmt.money(path.result.year.profit),
                delta: this.fmt.signedMoney(
                    path.result.year.profit - c.plan.year.profit),
                better: path.result.year.profit >= c.plan.year.profit,
                specs: [
                    { label: _t("People to add"),
                      value: added
                          ? _t("%(n)s in %(team)s",
                               { n: this.fmt.int(added),
                                 team: team ? team.name : "" })
                          : _t("none") },
                    { label: _t("Productive time"),
                      value: this.fmt.pct(path.state.productivity, 0) },
                    { label: _t("Overtime per person"),
                      value: _t("%s h a month",
                                Math.round(path.state.ot)) },
                    { label: _t("Workforce cost"),
                      value: this.fmt.money(path.result.year.people) },
                    { label: _t("Operating margin"),
                      value: this.fmt.pct(path.result.year.margin * 100) },
                    { label: _t("Demand served"),
                      value: this.hasTarget
                          ? this.fmt.pct(path.result.year.coverage * 100)
                          : "—" },
                ],
                gapText: path.checks.filter((x) => !x.met)
                    .map((x) => `${x.short}: ${this._gapText(x)}`)
                    .join(" · "),
                copy: path.met
                    ? _t("Every goal you switched on is met. %s", meta.keeps)
                    : _t("%(gaps)s. %(keeps)s",
                         { gaps: path.checks.filter((x) => !x.met)
                             .map((x) => `${x.short}: ${this._gapText(x)}`)
                             .join(" · "),
                           keeps: meta.keeps }),
            };
        });
    }

    async findPaths() {
        // A second press while the first search is still running would throw
        // eighty more computed years at a browser that is already busy, and
        // the slower of the two would win. One search at a time.
        if (this.state.finding) { return; }
        if (!this.anyGoalOn) {
            this._toast(_t("Switch on at least one goal first — the search "
                           + "needs something to aim at."));
            return;
        }
        this.state.finding = true;
        // A frame, so the button actually paints "Exploring…" before the
        // browser is handed eighty computed years to get through.
        await new Promise((resolve) => setTimeout(resolve, 40));
        try {
            const found = candidates(this.baseline, this.assumptions,
                                     this.planState, this.goals, this.fmt,
                                     this._runner);
            this._paths = found.lanes;
            this._paths.team = found.team;
            this.state.searchNote = found.lanes.length
                ? _t("Checked %s combinations, keeping your demand, pay, "
                     + "shifts and hiring month exactly as they are.",
                     this.fmt.int(found.count))
                : _t("Nothing to search: switch on a goal first.");
        } catch (e) {
            console.warn("pb_decision_room: the search failed", e);
            this._paths = [];
            this.state.searchNote = _t("The search could not finish. %s",
                                       this._reason(e));
        } finally {
            this.state.finding = false;
            this.state.rev++;
        }
    }

    tryPath(index) {
        const path = this._paths[index];
        if (!path) { return; }
        const title = { hire: _t("Build the team"),
                        develop: _t("Develop the team"),
                        balanced: _t("Blend the two") }[path.lane];
        this.state.goalsOpen = false;
        this.beginPreview(path.state, _t("%s · preview", title));
    }

    // ===================================================================
    // trying a possibility, and coming back
    // ===================================================================
    beginPreview(nextState, sceneName) {
        if (!this._preview) {
            this._preview = {
                state: cloneState(this.planState),
                goals: JSON.parse(JSON.stringify(this.goals || {})),
                scene: this.state.sceneName,
                touched: this._goalsTouched,
                historyLength: this._history.length,
                // Kept so the banner can say "against your previous plan"
                // without recomputing a whole year on every paint.
                profit: this.calc ? this.calc.plan.year.profit : 0,
            };
        }
        this.state.preview = true;
        this._apply(nextState, sceneName, false);
        setTimeout(() => {
            const el = document.querySelector(".dr-preview");
            if (!el) { return; }
            el.scrollIntoView({
                behavior: this.state.motion ? "smooth" : "auto",
                block: "center",
            });
        }, 40);
    }

    get previewBanner() {
        const c = this.calc;
        if (!this.state.preview || !this._preview || !c) { return null; }
        const checks = c.checks;
        const met = checks.filter((x) => x.met).length;
        return {
            title: this.state.sceneName,
            copy: _t("%(delta)s of yearly profit against your previous plan. "
                     + "%(met)s of %(all)s goals met. Your previous plan is "
                     + "kept until you choose.",
                     { delta: this.fmt.signedMoney(
                         c.plan.year.profit - this._preview.profit),
                       met, all: checks.length }),
        };
    }

    /** Keep it: the plan you had becomes the thing Ctrl+Z brings back. */
    keepPreview() {
        if (!this._preview) { return; }
        const kept = this._preview;
        this._history.length = kept.historyLength;
        this._history.push({
            state: kept.state, goals: kept.goals, scene: kept.scene,
            touched: kept.touched,
        });
        if (this._history.length > UNDO_DEPTH) { this._history.shift(); }
        this._preview = null;
        this.state.preview = false;
        this.state.sceneName = String(this.state.sceneName)
            .replace(" · preview", "");
        this._recompute();
        this._toast(_t("Kept. You can still undo it."));
    }

    /** Back out: everything — levers, goals, name, history — as it was. */
    backToPlan() {
        if (!this._preview) { return; }
        const kept = this._preview;
        this._history.length = kept.historyLength;
        this.planState = normalizeState(kept.state, this.baseline,
                                        this.assumptions);
        this.goals = kept.goals;
        this._goalsTouched = kept.touched;
        this.state.sceneName = kept.scene;
        this._preview = null;
        this.state.preview = false;
        this._recompute();
        this._toast(_t("Your previous plan is back, exactly as it was."));
    }

    get previewNote() {
        return _t("Finish trying this possibility first — keep it, or go "
                  + "back to your plan.");
    }

    // ===================================================================
    // the reality check
    // ===================================================================
    get stressOptions() {
        return [
            { value: -10, head: _t("−10%"), label: _t("Softer demand") },
            { value: 0, head: _t("As planned"), label: _t("Your forecast") },
            { value: 10, head: _t("+10%"), label: _t("Stronger demand") },
        ].map((o) => ({ ...o,
                        active: Math.abs(this.planState.stress - o.value) < 1e-9 }));
    }

    setStress(value) {
        if (Math.abs((this.planState.stress || 0) - value) < 1e-9) { return; }
        this._apply({ stress: value }, _t("Your working plan"));
    }

    get stressText() {
        const c = this.calc;
        if (!c) { return ""; }
        return stressOutcome(this.baseline, this.assumptions, this.planState,
                             c.plan, this.fmt, this._runner);
    }

    // ===================================================================
    // one small experiment
    // ===================================================================
    /**
     * How many people this team's experiment is worth asking about.
     *
     * Phase 2 always asked about five, which is a real question in a
     * forty-person team and a rounding error in a four-thousand-person one:
     * at that size the card read "would add ₫0" and the whole idea looked
     * broken. It is one per cent of the team now, never fewer than five.
     */
    get experimentN() {
        const team = this.team;
        return experimentSize(team ? team.heads : 0);
    }

    get experiment() {
        const c = this.calc;
        const team = this.team;
        if (!c || !team) { return null; }
        const n = this.experimentN;
        const step = marginal(this.baseline, this.assumptions, this.planState,
                              c.plan, team.key, n, this._runner);
        if (!step) { return null; }
        const good = step.dProfit >= 0;
        const people = this.fmt.int(n);
        return {
            n,
            button: _t("Preview %s more people", people),
            title: good
                ? _t("%(n)s more people in %(team)s would add %(money)s of "
                     + "profit.",
                     { n: people, team: team.name,
                       money: this.fmt.money(step.dProfit) })
                : _t("%(n)s more people in %(team)s would cost %(money)s of "
                     + "profit.",
                     { n: people, team: team.name,
                       money: this.fmt.money(-step.dProfit) }),
            copy: this.hasTarget && Math.abs(step.dCoverage) >= 0.05
                ? _t("Demand served moves %(cov)s for %(cost)s more workforce "
                     + "cost across the year.",
                     { cov: this.fmt.pp(step.dCoverage),
                       cost: this.fmt.money(step.dCost) })
                : _t("At this size %(n)s people barely move what you can "
                     + "deliver. Workforce cost rises %(cost)s across the "
                     + "year.",
                     { n: people, cost: this.fmt.money(step.dCost) }),
            good,
        };
    }

    previewExperiment() {
        const team = this.team;
        if (!team) { return; }
        const n = this.experimentN;
        this.beginPreview({
            ...this.planState,
            moves: [...(this.planState.moves || []),
                    { team: team.key, role: null, n,
                      month: this.planState.start }],
        }, _t("%(n)s more in %(team)s · preview",
              { n: this.fmt.int(n), team: team.name }));
    }

    // ===================================================================
    // the assumptions, now editable
    // ===================================================================
    get assumptionFields() {
        const groups = {};
        for (const field of this.assumptionsForm) {
            (groups[field.group] = groups[field.group] || []).push({
                ...field,
                value: field.key === "revenue_team_ids"
                    ? (this.state.assumeDraft.revenue_team_ids
                       || this.assumptions.revenue_team_ids || [])
                    : (this.state.assumeDraft[field.key] !== undefined
                        ? this.state.assumeDraft[field.key]
                        : (this.assumptions[field.key] || 0)),
                text: this._assumeText(field),
            });
        }
        return this.assumptionsGroups
            .filter((name) => groups[name])
            .map((name) => ({ name, fields: groups[name] }));
    }

    _assumeValue(field) {
        if (this.state.assumeDraft[field.key] !== undefined) {
            return this.state.assumeDraft[field.key];
        }
        return this.assumptions[field.key] || 0;
    }

    _assumeText(field) {
        if (field.kind === "teams") {
            const chosen = this.state.assumeDraft.revenue_team_ids
                || this.assumptions.revenue_team_ids || [];
            return _t("%s teams", chosen.length);
        }
        const value = this._assumeValue(field);
        switch (field.kind) {
            case "money": return this.fmt.money(value);
            case "pct": return this.fmt.pct(value, 1);
            case "months": return Number(value) === 1
                ? _t("1 month") : _t("%s months", value);
            case "rate": return _t("%s× normal", Number(value).toFixed(2));
            case "int": return this.fmt.int(value);
            default: return String(value);
        }
    }

    get assumeTeamChips() {
        const chosen = new Set(this.state.assumeDraft.revenue_team_ids
            || this.assumptions.revenue_team_ids || []);
        return (this.baseline.teams || [])
            .filter((t) => t.department_id)
            .map((t) => ({
                id: t.department_id, name: t.name, on: chosen.has(t.department_id),
            }));
    }

    toggleRevenueTeam(id) {
        const chosen = new Set(this.state.assumeDraft.revenue_team_ids
            || this.assumptions.revenue_team_ids || []);
        if (chosen.has(id)) { chosen.delete(id); } else { chosen.add(id); }
        this.state.assumeDraft = {
            ...this.state.assumeDraft, revenue_team_ids: [...chosen],
        };
        this.state.assumeError = "";
    }

    setAssumption(key, value) {
        this.state.assumeDraft = { ...this.state.assumeDraft, [key]: value };
        this.state.assumeError = this.demandShareError;
    }

    onAssumption(key, event) {
        const raw = event.target.value;
        if (raw === "" || !Number.isFinite(Number(raw))) { return; }
        this.setAssumption(key, Number(raw));
    }

    /** The one rule the dialog can break on its own, said inline. */
    get demandShareError() {
        const total = ["demand_day_pct", "demand_evening_pct",
                       "demand_night_pct"]
            .reduce((sum, key) => sum + Number(
                this.state.assumeDraft[key] !== undefined
                    ? this.state.assumeDraft[key]
                    : (this.assumptions[key] || 0)), 0);
        if (Math.abs(total - 100) <= 0.01) { return ""; }
        return _t("Day, evening and night have to add up to 100%% of the "
                  + "work. They add up to %s%% right now.",
                  Math.round(total * 10) / 10);
    }

    get assumeDirty() {
        return Object.keys(this.state.assumeDraft).length > 0;
    }

    async saveAssumptions() {
        if (this.demandShareError) {
            this.state.assumeError = this.demandShareError;
            return;
        }
        this.state.assumeBusy = true;
        try {
            const fresh = await this.orm.call(
                "pb.decision.room", "save_assumptions",
                [{ ...this.state.assumeDraft,
                   scope: { kind: this.state.scope.kind,
                            ref: this.state.scope.ref } }]);
            this.assumptions = fresh;
            this.state.assumeMeta = fresh.scope || this.state.assumeMeta;
            this.state.assumeDraft = {};
            this.state.assumeError = "";
            // Which teams earn revenue is part of the BASELINE, so the roster
            // has to come back with it.
            await this.load(true);
            this.state.assumptionsOpen = true;
            this._toast(_t("Assumptions saved for %s. Every plan now uses "
                           + "them.", this.state.scope.label || ""));
        } catch (e) {
            this.state.assumeError = this._reason(e);
        } finally {
            this.state.assumeBusy = false;
        }
    }

    openAssumptionsRecord() {
        const id = this.assumptions.id;
        if (!id) { return; }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "pb.decision.assumptions",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // ---- GROUP P4: whose rules these are, and how to change that --------
    /** "Rules for Vietnam", or "Rules for this scheme (instead of Vietnam)".
     *  The scope's own name is printed BESIDE this, so it is never repeated
     *  inside it — a heading that says the same thing twice reads as a bug. */
    get rulesTitle() {
        const meta = this.state.assumeMeta || {};
        const country = meta.country_name || "";
        if (!meta.use_country_rules) {
            return meta.scope_kind === "scheme"
                ? _t("Rules for this payroll scheme%s",
                     country ? _t(" (instead of %s)", country) : "")
                : _t("Your own numbers%s",
                     country ? _t(" (instead of %s)", country) : "");
        }
        return country || _t("Rules for this company");
    }

    get rulesNote() {
        const meta = this.state.assumeMeta || {};
        if (!meta.use_country_rules) {
            return _t("These numbers were typed here and are not touched by "
                      + "an upgrade. Put them back on the country's rules "
                      + "below if you would rather follow those.");
        }
        return meta.note || "";
    }

    get capNote() { return (this.assumptions || {}).cap_note || ""; }

    get canOverrideRules() {
        return !!(this.state.canManage
                  && (this.state.assumeMeta || {}).can_override);
    }

    get followsCountry() {
        return !!(this.state.assumeMeta || {}).use_country_rules;
    }

    async toggleCountryRules() {
        if (!this.state.canManage) { return; }
        this.state.assumeBusy = true;
        try {
            const fresh = await this.orm.call(
                "pb.decision.room", "save_assumptions",
                [{ use_country_rules: !this.followsCountry,
                   scope: { kind: this.state.scope.kind,
                            ref: this.state.scope.ref } }]);
            this.assumptions = fresh;
            this.state.assumeMeta = fresh.scope || this.state.assumeMeta;
            await this.load(true);
            this.state.assumptionsOpen = true;
            this._toast(this.followsCountry
                ? _t("Back on the rules for %s.",
                     (this.state.assumeMeta || {}).country_name || "")
                : _t("These numbers are now this scope's own."));
        } catch (e) {
            this.state.assumeError = this._reason(e);
        } finally {
            this.state.assumeBusy = false;
        }
    }

    async resetToCountryRules() {
        if (!this.state.canManage) { return; }
        this.state.assumeBusy = true;
        try {
            const fresh = await this.orm.call(
                "pb.decision.room", "reset_assumptions",
                [{ kind: this.state.scope.kind, ref: this.state.scope.ref }]);
            this.assumptions = fresh;
            this.state.assumeMeta = fresh.scope || this.state.assumeMeta;
            await this.load(true);
            this.state.assumptionsOpen = true;
            this._toast(_t("Back on the rules for %s.",
                           (this.state.assumeMeta || {}).country_name || ""));
        } catch (e) {
            this.state.assumeError = this._reason(e);
        } finally {
            this.state.assumeBusy = false;
        }
    }

    get assumptionsWho() {
        if (this.state.canManage) {
            return _t("You can change these numbers. Everyone planning %s "
                      + "will see the change.", this.state.scope.label || "");
        }
        const who = this.assumptions.changed_by;
        const when = (this.assumptions.changed_on || "").slice(0, 10);
        const last = who && when
            ? _t("Last changed by %(who)s on %(when)s. ", { who, when }) : "";
        return _t("%sThese numbers are looked after by your HR or finance "
                  + "lead. Ask them if one of them looks wrong.", last);
    }

    // ===================================================================
    // the printable brief
    // ===================================================================
    async exportBrief() {
        const c = this.calc;
        if (!c || this.state.briefBusy) { return; }
        // The tab is opened BEFORE the round trip: a window opened later, from
        // a promise, is a pop-up as far as every browser is concerned.
        const tab = window.open("", "_blank");
        this.state.briefBusy = true;
        try {
            const model = briefModel({
                plan: c.plan, ref: c.ref, baseline: this.baseline,
                assumptions: this.assumptions, state: this.planState,
                refState: c.refState, goals: this.goals, format: this.fmt,
                planName: String(this.state.sceneName),
                comparisonName: String(this.comparison.name),
                assumptionLines: this.assumptionLines,
            });
            const html = await this.orm.call(
                "pb.decision.room", "render_brief", [model]);
            if (!tab || tab.closed) {
                this._toast(_t("Your browser blocked the new tab. Allow "
                               + "pop-ups for this site and try again."));
                return;
            }
            tab.document.open();
            tab.document.write(html);
            tab.document.close();
            this._toast(_t("Decision brief opened in a new tab — use Print to "
                           + "save it as a PDF."));
        } catch (e) {
            if (tab && !tab.closed) { tab.close(); }
            console.warn("pb_decision_room: the brief failed", e);
            this._toast(_t("The brief could not be built. %s",
                           this._reason(e)));
        } finally {
            this.state.briefBusy = false;
        }
    }

    // ===================================================================
    // the phone
    // ===================================================================
    /**
     * A phone is not a small desktop.
     *
     * On a 390 px screen the levers cannot sit above the stage: you would
     * scroll past nine controls before seeing a single number, which is the
     * opposite of what this room is for. So the stage comes first and the
     * control room becomes a SHEET — one thumb-reach bar at the bottom lifts
     * it, the levers scroll inside it, and the hero number is mirrored in its
     * header so a lever's effect is visible while your thumb is still on it.
     *
     * The markup is the same markup: the sheet is the control room, moved.
     * Two copies of nine levers would be two places for them to drift apart.
     */
    _watchWidth() {
        if (!window.matchMedia) { return; }
        this._media = window.matchMedia(`(max-width: ${PHONE}px)`);
        this._onWidth = () => {
            this.state.phone = this._media.matches;
            if (!this.state.phone) { this.state.sheet = false; }
        };
        this._onWidth();
        if (this._media.addEventListener) {
            this._media.addEventListener("change", this._onWidth);
        }
    }

    openSheet() {
        this.state.sheet = true;
    }

    closeSheet() {
        this.state.sheet = false;
    }

    get sheetLabel() {
        return String(this.state.sceneName || "");
    }

    // ===================================================================
    // the roster, and how old it is
    // ===================================================================
    /**
     * "as of 14:02" — the wall-clock time this roster was actually read.
     *
     * The baseline is cached for ten minutes, so a number on this screen can
     * legitimately be a few minutes behind a hire made this morning. Saying
     * WHEN it was read, and offering to read it again, is the difference
     * between a stale number and a dated one.
     */
    get asofText() {
        const stamp = this.baseline.asof_at || "";
        if (!stamp) { return this.baseline.asof || ""; }
        const when = new Date(stamp.replace(" ", "T") + "Z");
        if (isNaN(when.getTime())) { return this.baseline.asof || ""; }
        const hh = String(when.getHours()).padStart(2, "0");
        const mm = String(when.getMinutes()).padStart(2, "0");
        return `${hh}:${mm}`;
    }

    /**
     * GROUP P5 — the full-time figure, said ONLY when it differs.
     *
     * On a company where every person works a whole month at one employment
     * the two numbers are the same, and printing "4,533 people · 4,533.0
     * full-time" would be noise dressed as precision. It appears the moment
     * somebody's month is split, which is exactly when it means something.
     */
    get fullTimeText() {
        const heads = Number(this.baseline.headcount || 0);
        const full = Number(this.baseline.full_time || 0);
        if (!full || Math.abs(full - heads) < 0.05) { return ""; }
        return _t("%(figure)s full-time", { figure: full.toLocaleString() });
    }

    /** "Two people are paid in two places this month." Said only when true. */
    get splitNote() {
        const n = Number(this.baseline.split_people || 0);
        if (!n) { return ""; }
        return n === 1
            ? _t("1 person is paid in two places this month.")
            : _t("%(count)s people are paid in two places this month.",
                 { count: n });
    }

    /** Read the roster again, and keep the plan exactly where it is. */
    async refreshRoster() {
        if (this.state.refreshing) { return; }
        this.state.refreshing = true;
        const kept = {
            state: cloneState(this.planState),
            goals: JSON.parse(JSON.stringify(this.goals || {})),
            scene: this.state.sceneName,
            touched: this._goalsTouched,
            comparison: this.comparison,
            month: this.state.month,
            metric: this.state.metric,
            detail: this.state.detail,
        };
        try {
            await this.load(true);
            this.planState = normalizeState(kept.state, this.baseline,
                                            this.assumptions);
            this.goals = kept.goals;
            this._goalsTouched = kept.touched;
            this.state.sceneName = kept.scene;
            this.comparison = kept.comparison;
            this.state.month = kept.month;
            this.state.metric = kept.metric;
            this.state.detail = kept.detail;
            this.state.assumptionsOpen = true;
            this._recompute();
            this._toast(_t("Roster read again. Your plan is untouched."));
        } catch (e) {
            this._toast(_t("The roster could not be read again. %s",
                           this._reason(e)));
        } finally {
            this.state.refreshing = false;
        }
    }

    // ===================================================================
    // painting
    // ===================================================================
    /**
     * One chart, travelling from the shape it had to the shape it has.
     *
     * A chart that snaps asks the reader to compare two pictures from memory.
     * Three rules keep it from becoming decoration: it only starts when the
     * numbers actually changed (a resize redraws, it does not re-animate), it
     * ends EXACTLY on the target, and with "Motion off" — or the operating
     * system's own reduced-motion setting — there is no travel at all.
     */
    _travel(key, next, draw) {
        const signature = JSON.stringify(next);
        if (this._chartSig[key] === signature) {
            if (!this._chartFrame[key]) { draw(next); }
            return;
        }
        const from = this._chartFrom[key];
        this._chartSig[key] = signature;
        cancelAnimationFrame(this._chartFrame[key]);
        this._chartFrame[key] = 0;
        if (!this.state.motion || !from) {
            this._chartFrom[key] = next;
            draw(next);
            return;
        }
        const started = performance.now();
        const tick = (now) => {
            const k = Math.min(1, (now - started) / CHART_MS);
            const eased = easeOut(k);
            const mixed = {};
            for (const name of Object.keys(next)) {
                mixed[name] = Array.isArray(next[name])
                    ? tweenSeries(from[name], next[name], eased, true)
                    : next[name];
            }
            draw(mixed);
            if (k < 1) {
                this._chartFrame[key] = requestAnimationFrame(tick);
            } else {
                this._chartFrame[key] = 0;
                this._chartFrom[key] = next;
            }
        };
        this._chartFrame[key] = requestAnimationFrame(tick);
    }

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
            months: this.months,
            goodUp: this.metricDef.goodUp,
            // GROUP P4 — the companies inside a group, and what the closed
            // pay runs actually produced.
            entities: this.entityLines,
            actual: this.actualLine,
            fmt: (v) => (coverage ? `${Math.round(v)}%` : this.fmt.money(v)),
        });
        drawRing(this.ringRef.el, {
            value: c.plan.year.coverage,
            ref: c.ref.year.coverage,
            goodAt: this.goals.coverage.on
                ? this.goals.coverage.target / 100 : 0.95,
        });
        this._paintDetail(c);
        this._tweenHero();
    }

    /** Only the tab on screen is drawn: the others have no box to size to. */
    _paintDetail(c) {
        if (this.state.detail === "coverage" && this.demandRef.el) {
            this._travel("demand", {
                demand: c.plan.rows.map((r) => r.hoursDemand),
                capacity: c.plan.rows.map((r) => r.hoursAvailable),
                served: c.plan.rows.map((r) => r.hoursServed),
                month: this.state.month,
            }, (o) => drawDemand(this.demandRef.el, {
                ...o,
                months: this.months,
                fmt: (v) => this._hours(v),
            }));
        }
        if (this.state.detail === "money" && this.bridgeRef.el) {
            const b = bridge(c.plan, c.ref);
            // The bars GROW FROM THE RUNNING LEVEL: the first frame is the
            // comparison with seven steps of nothing, and the waterfall
            // builds itself in front of you.
            if (this._chartFrom.bridge === undefined) {
                this._chartFrom.bridge = {
                    values: b.steps.map(() => 0), end: b.start,
                };
            }
            this._travel("bridge", {
                values: b.steps.map((x) => x.value), end: b.end,
            }, (o) => drawBridge(this.bridgeRef.el, {
                start: b.start,
                end: o.end,
                steps: b.steps.map((x, i) => ({ ...x, value: o.values[i] })),
                startName: String(this.comparison.name),
                endName: _t("Your plan"),
                fmt: (v) => this.fmt.money(v),
                signed: (v) => this.fmt.signedMoney(v),
            }));
        }
        if (this.state.detail === "room" && this.roomRef.el) {
            const scan = this.roomScan;
            if (scan && scan.points.length > 1) {
                this._travel("room", {
                    profit: scan.points.map((pt) => pt.profit),
                }, (o) => drawRoom(this.roomRef.el, {
                    points: scan.points.map((pt, i) => ({
                        ...pt, profit: o.profit[i],
                    })),
                    label: (n) => _t("+%s people", this.fmt.int(n)),
                    fmt: (v) => this.fmt.money(v),
                }));
            }
        }
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
            if (this.state.saveOpen || this.state.goalsOpen
                || this.state.sketchOpen || this.state.assumptionsOpen
                || this.state.scopeOpen || this.state.decideOpen
                || this.state.versionsOpen) {
                this.state.saveOpen = false;
                this.state.goalsOpen = false;
                this.state.sketchOpen = false;
                this.state.scopeOpen = false;
                this.state.decideOpen = false;
                this.state.versionsOpen = false;
                if (this.state.assumptionsOpen) { this.closeAssumptions(); }
                return;
            }
            // Nothing else was open, so Escape means the sheet.
            this.state.sheet = false;
            return;
        }
        if (!(event.metaKey || event.ctrlKey) || event.altKey) { return; }
        const key = String(event.key || "").toLowerCase();
        const tag = (event.target.tagName || "").toLowerCase();
        if (key === "z" && !event.shiftKey) {
            if (tag === "input" || tag === "textarea") { return; }
            event.preventDefault();
            this.undo();
            return;
        }
        // Ctrl+S is "save this", everywhere in the world. Here it opens the
        // name dialog rather than saving over yesterday's plan silently.
        if (key === "s" && !event.shiftKey) {
            event.preventDefault();
            this.openSave();
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
        return MONTHS.map((_name, i) => ({ value: i + 1,
                                           label: monthLong(i) }));
    }

    /** The twelve short month names, in the reader's own language. */
    get months() { return MONTHS.map((_name, i) => monthShort(i)); }

    get emptyTitle() { return _t("The Decision Room is not open to you."); }

    get emptyNote() {
        return _t("Planning the year is done by the people who hold the "
                  + "Decision Room role. Ask your HR or finance lead to add "
                  + "you, and this screen fills itself in.");
    }
}

registry.category("actions").add("pb_decision_room", PbDecisionRoom);
