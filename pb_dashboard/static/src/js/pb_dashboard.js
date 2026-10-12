/** @odoo-module **/
/* =============================================================================
   HOME — the Payobook Home (HOME P2, docs/handovers/home/P2_HANDOVER.md)
   -----------------------------------------------------------------------------
   One screen that says where this month's payroll stands, in one sentence,
   with the one thing to do next — and a 12-month chart that is also the month
   picker. Build target: docs/design/home-dashboard-prototype.html (ported to
   OWL, not redesigned). Rules: docs/handovers/home/HOME_LEDGER.md.

   THE SERVER OWNS FACTS, THIS FILE OWNS WORDS (H-R3). `get_home_data()` sends
   keys, numbers and dates; every sentence on the screen is built here through
   `_t()`, and the three word tables below (NEEDS, STEPS, UPCOMING) are pinned
   key-for-key against the server by tests/test_home_front.py (test 3).

   NO COCKPIT DEPENDENCY. pb_dashboard declares `pb_import_kit` (icons and
   tokens) and nothing from the hub family: the doors below write the hub
   navigation protocol's `pb_back` payload by hand (`backDoor()`), the same
   shape `@pb_hub/js/hub_nav` writes, pinned key-for-key by pb_home_hub's
   tests. Importing the hub kit would make the first screen of every tenant
   depend on the hub family.

   The chart is hand-drawn SVG: geometry here (`get chart()`), drawing in the
   template. No chart library (program doc).
   ========================================================================== */

import { Component, useState, onWillStart, onMounted, onPatched,
         onWillUnmount, onWillUpdateProps, useRef,
         useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const { DateTime, Settings } = luxon;

/* =============================================================================
   THE ACTIVATION CHECKLIST — LEARNOS Phase 3
   -----------------------------------------------------------------------------
   Five steps from an empty database to a real pay run. While a tenant has no
   pay run this is the whole of Home under the greeting line.

   THE SERVER OWNS `done`, THIS TABLE OWNS THE WORDS. Every tick is a count
   taken in `pb.dashboard._activation` — never a browser flag, never "you
   pressed this button once". The payload carries `[{key, done}]` in order, and
   the two learning steps are simply absent from it on a database without
   pb_learn, so nothing here has to guess.

   `run` is what each button does, and three of the five hand off to the
   scenario engine. That engine belongs to pb_learn, so it is looked up as an
   OPTIONAL service — `useService` throws when a service is missing, and this
   code runs on databases where it is guaranteed to be missing.
   ========================================================================== */
const ACTIVATION = {
    meet: {
        icon: "compass",
        title: _t("Meet Payobook"),
        desc: _t("A 2-minute tour. I drive, you watch."),
        cta: _t("Watch the tour"),
        // LEARNOS Phase 6. What the button says when the walkthrough is
        // half-taken. Only the two learning rows can be half-taken: the other
        // three are database facts, which are true or not.
        resume: _t("Pick up where you left off"),
        run: (self) => self.scenario(SC_WELCOME, "watch"),
    },
    employee: {
        icon: "user-plus",
        title: _t("Add your first employee"),
        desc: _t("A name, a contract, a salary. That is all it takes."),
        cta: _t("Add employee"),
        run: (self) => self.open(ACT_EMPLOYEES),
    },
    import: {
        icon: "upload",
        title: _t("Bring in your payroll Excel"),
        desc: _t("Already have a sheet? Bring everyone in at once."),
        cta: _t("Import data"),
        run: (self) => self.open(ACT_IMPORT),
    },
    practice: {
        icon: "play",
        title: _t("Run a practice payroll"),
        desc: _t("On a made-up company. Nothing here is real."),
        cta: _t("Try it"),
        resume: _t("Pick up where you left off"),
        run: (self) => self.scenario(SC_PAYRUN, "try"),
    },
    real: {
        icon: "zap",
        title: _t("Run your first real payroll"),
        desc: _t("Your own data, with the guide beside you. You press every button."),
        cta: _t("Start"),
        // Do-mode walks the REAL wizard and never presses anything itself.
        // With no guide on this database the honest fallback is the wizard,
        // which is where the step ends up either way.
        run: (self) => self.scenario(SC_PAYRUN, "do", ACT_PAYRUN),
    },
};

// Both leaves carry an EMPTY action_xmlid and are opened by TAG
// (pb_sidebar/data/pb_sidebar_data.xml); these are the client actions behind
// those tags.
const ACT_EMPLOYEES = "pb_people.action_pb_people";
const ACT_IMPORT = "pb_import.action_pb_import";
const ACT_PAYRUN = "pb_payrun_wizard.action_pb_payrun_wizard";

/* The learning module's scenario engine, named as STRINGS: pb_dashboard
   imports nothing from pb_learn, so the only thing that can go stale here is
   a key, and a stale key degrades to a notification. */
const SCENARIO_SERVICE = "learn.scenario";
const SC_WELCOME = "sc_welcome";
const SC_PAYRUN = "sc_payrun";

/* =============================================================================
   DOORS — every chip, step, row and figure opens the screen it talks about.
   By XMLID, never by bare tag (W98: a tag-only action leaves the breadcrumb
   reading "Unnamed"). Each carries the Home back chip except the Approvals
   lens, which IS Home.
   ========================================================================== */
const HOME_XMLID = "pb_home_hub.action_pb_home_hub";
const PAY_HUB = "pb_payhub.action_pb_pay_hub";
const INSIGHTS_HUB = "pb_insights_hub.action_pb_insights_hub";
const LIFECYCLE_HUB = "pb_lifecycle.action_pb_lifecycle_hub";

/** Payroll stage -> Pay Run hub lens (the same table as pb_home_hub's
 *  STAGE_LENS, copied because pb_home_hub depends on THIS module). */
const STAGE_LENS = { 1: "run", 2: "runs", 3: "payslips", 4: "deliver", 5: "runs" };

const DOORS = {
    approvals: { xmlid: HOME_XMLID, lens: "approvals", back: false },
    exits: { xmlid: LIFECYCLE_HUB, lens: "exits" },
    hiring: { xmlid: LIFECYCLE_HUB, lens: "hiring" },
    contracts: { xmlid: "pb_people_hub.action_pb_people_contracts" },
    // Mission Control reads its lens from `pb_shell_lens` (hub_nav.js).
    holidays: { xmlid: "pb_mission.action_pb_workforce", lens: "holidays",
                lensKey: "pb_shell_lens" },
    calendar: { xmlid: "pb_comp_ben.action_pb_payroll_calendar" },
};

/* =============================================================================
   THE WORD TABLES. Keys are the server's (home_data.py NEEDS_ORDER,
   STEP_KEYS, the upcoming kinds); test 3 pins both directions.
   ========================================================================== */

/** "Needs you" chips: singular / plural label, tone, door. */
const NEEDS = {
    runs_to_approve: {
        one: () => _t("pay run to approve"),
        many: () => _t("pay runs to approve"),
        door: "run",
    },
    leave_to_approve: {
        one: () => _t("leave request to approve"),
        many: () => _t("leave requests to approve"),
        door: "approvals",
    },
    other_to_approve: {
        one: () => _t("other approval"),
        many: () => _t("other approvals"),
        door: "approvals",
    },
    settlements_to_check: {
        one: () => _t("final settlement to check"),
        many: () => _t("final settlements to check"),
        door: "exits",
    },
    renewals_to_start: {
        one: () => _t("contract renewal to start"),
        many: () => _t("contract renewals to start"),
        door: "contracts",
    },
    writeups_overdue: {
        one: () => _t("interview write-up overdue"),
        many: () => _t("interview write-ups overdue"),
        // Late, not merely waiting: the one rose chip (H-R5).
        rose: true,
        door: "hiring",
    },
};

/** The five steps: the journey label (hero) and the row title (steps card). */
const STEPS = {
    setup: {
        journey: () => _t("Set up"),
        title: () => _t("Set up the month"),
    },
    prepare: {
        journey: () => _t("Prepare"),
        title: () => _t("Prepare payslips"),
    },
    approve: {
        journey: () => _t("Approve"),
        title: () => _t("Approve"),
    },
    pay: {
        journey: () => _t("Pay"),
        title: () => _t("Pay"),
    },
    deliver: {
        journey: () => _t("Deliver payslips"),
        title: () => _t("Deliver payslips"),
    },
};

/** "Coming up" rows: title, sub line and door per kind. */
const UPCOMING = {
    cutoff: {
        title: (it, self) => _t("Last day for %(month)s changes",
                                { month: self.monthName(self.period.key) }),
        sub: () => _t("New joiners, salary changes, overtime"),
        door: "calendar",
    },
    payday: {
        title: () => _t("Payday"),
        sub: (it) => {
            const n = (it.extra || {}).banks;
            if (!n) { return ""; }
            return n === 1 ? _t("1 bank") : _t("%(n)s banks", { n });
        },
        door: "deliver",
    },
    contracts_end: {
        title: (it) => (it.n === 1 ? _t("1 contract ends")
                        : _t("%(n)s contracts end", { n: it.n })),
        sub: () => "",
        door: "contracts",
    },
    holiday: {
        title: () => _t("Next public holiday"),
        sub: (it) => (it.extra || {}).name || "",
        door: "holidays",
    },
    interviews: {
        title: (it) => (it.n === 1 ? _t("1 interview")
                        : _t("%(n)s interviews", { n: it.n })),
        sub: () => _t("this week"),
        door: "hiring",
    },
};

/** The chart's segmented control. Money measures drop out on a database
 *  without the stored run totals (H4). */
const MEASURES = [
    { key: "net", money: true, label: () => _t("Net pay") },
    { key: "gross", money: true, label: () => _t("Gross pay") },
    { key: "ded", money: true, label: () => _t("Deductions") },
    { key: "er", money: true, label: () => _t("Employer cost") },
    { key: "people", money: false, label: () => _t("People") },
];

/* ============================================================== helpers */

/** The reader's locale, as the web client set it for dates and numbers. */
function locale() {
    return (Settings && Settings.defaultLocale) || undefined;
}

function reducedMotion() {
    return !!(window.matchMedia
              && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
}

/** A whole number with the reader's thousands separator. */
function int(v) {
    return Math.round(Number(v) || 0).toLocaleString(locale());
}

/**
 * Compact money: `53.1 bn đ`, `11.8 M đ`, `850 K đ` — thresholds 1e9 / 1e6 /
 * 1e3, ONE space between the number and the unit, the unit after the number
 * (H-R7). Full figures (tooltips) use `toLocaleString` instead.
 */
function compact(v) {
    const n = Number(v) || 0;
    const a = Math.abs(n);
    if (a >= 1e9) { return { num: (n / 1e9).toFixed(1), unit: _t("bn") }; }
    if (a >= 1e6) { return { num: (n / 1e6).toFixed(1), unit: _t("M") }; }
    if (a >= 1e3) { return { num: Math.round(n / 1e3).toLocaleString(locale()), unit: _t("K") }; }
    return { num: Math.round(n).toLocaleString(locale()), unit: "" };
}

/** A "nice" axis step: 1, 2, 5 or 10 × a power of ten. */
function niceStep(raw) {
    if (!(raw > 0)) { return 1; }
    const p = Math.pow(10, Math.floor(Math.log10(raw)));
    const r = raw / p;
    return (r <= 1 ? 1 : r <= 2 ? 2 : r <= 5 ? 5 : 10) * p;
}

/** A column with a 4 px rounded top and a square base (the prototype's). */
function roundedTop(x, y, w, h, r) {
    r = Math.max(0, Math.min(r, w / 2, h));
    const f = (n) => Math.round(n * 10) / 10;
    return `M${f(x)},${f(y + h)} L${f(x)},${f(y + r)} Q${f(x)},${f(y)} ${f(x + r)},${f(y)} `
         + `L${f(x + w - r)},${f(y)} Q${f(x + w)},${f(y)} ${f(x + w)},${f(y + r)} `
         + `L${f(x + w)},${f(y + h)} Z`;
}

/**
 * A 12-point sparkline: `{line, area, dot}` or null when fewer than two
 * months have a value. `hi` is the index to ring (else the last value).
 */
export function sparkPath(values, W, H, hi) {
    const pad = 5;
    const live = [];
    values.forEach((v, i) => { if (v !== null && v !== undefined) { live.push([i, Number(v)]); } });
    if (live.length < 2 || !(W > 0)) { return null; }
    const vs = live.map((p) => p[1]);
    const min = Math.min(...vs);
    const span = (Math.max(...vs) - min) || 1;
    const step = (W - pad * 2) / Math.max(1, values.length - 1);
    const pt = (i, v) => [pad + i * step, H - pad - ((v - min) / span) * (H - pad * 2)];
    const pts = live.map(([i, v]) => pt(i, v));
    const line = pts.map((p, k) => `${k ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
    const last = pts[pts.length - 1];
    const area = `${line} L${last[0].toFixed(1)},${H} L${pts[0][0].toFixed(1)},${H} Z`;
    const ringed = (hi !== null && hi !== undefined && values[hi] !== null
                    && values[hi] !== undefined) ? pt(hi, Number(values[hi])) : last;
    return { line, area, dot: { x: ringed[0], y: ringed[1] } };
}

/**
 * A translated sentence with inline parts. `template` keeps its `%(name)s`
 * placeholders (one msgid a translator can reorder); each value is a plain
 * string or `{text, kind: "b"|"link", go}`. Returns the segments in order.
 */
function segs(template, vars) {
    const out = [];
    const src = String(template);
    const re = /%\((\w+)\)s/g;
    let last = 0;
    let m;
    while ((m = re.exec(src))) {
        if (m.index > last) { out.push({ text: src.slice(last, m.index) }); }
        const v = vars[m[1]];
        out.push(v && typeof v === "object" ? v : { text: v === undefined || v === null ? "" : String(v) });
        last = re.lastIndex;
    }
    if (last < src.length) { out.push({ text: src.slice(last) }); }
    return out;
}

/* ===================================================== the count-up figure */
/**
 * One number that travels to its new value (520 ms, cubic ease-out) when the
 * month changes. Its own component so a running count re-renders this span
 * and nothing else. Never animates the first paint, never under reduced
 * motion.
 */
export class PbdCount extends Component {
    static template = "pb_dashboard.Count";
    static props = {
        value: { optional: true },
        format: Function,
    };

    setup() {
        this.state = useState({ v: this.props.value });
        this._target = this.props.value;
        onWillUpdateProps((next) => this.travel(next.value));
        onWillUnmount(() => cancelAnimationFrame(this._raf));
    }

    travel(to) {
        if (to === this._target) { return; }
        this._target = to;
        cancelAnimationFrame(this._raf);
        const from = this.state.v;
        if (from === null || from === undefined || to === null || to === undefined
                || reducedMotion() || typeof requestAnimationFrame !== "function") {
            this.state.v = to;
            return;
        }
        const t0 = performance.now();
        const tick = (now) => {
            const k = Math.min(1, (now - t0) / 520);
            const e = 1 - Math.pow(1 - k, 3);
            this.state.v = k >= 1 ? to : from + (to - from) * e;
            if (k < 1) { this._raf = requestAnimationFrame(tick); }
        };
        this._raf = requestAnimationFrame(tick);
    }

    get parts() {
        const v = this.state.v;
        return (v === null || v === undefined) ? { n: "—", u: "" } : this.props.format(v);
    }
}

/* ============================================================== the board */
export class PbDashboard extends Component {
    static template = "pb_dashboard.PbDashboard";
    static components = { PbdCount };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.chartRef = useRef("chart");
        this.heroSparkRef = useRef("heroSpark");
        this.stackRef = useRef("stack");
        this.stepsRef = useRef("steps");
        this.state = useState({
            d: null,
            loaded: false,
            failed: false,
            loading: false,
            updated: "",
            sel: -1,               // the chosen month (index into months)
            measure: "net",
            tip: -1,               // the column the tooltip is about
            width: 0,              // chart host width (ResizeObserver)
            heroW: 0,              // hero sparkline host width
            stackW: 0,             // stacked bar width — labels need 90 px
            progReady: false,      // the hero progress bar grows once
        });

        // THE DEEP LINK, read once: `pb_focus: "month:2026-06"` or
        // `"month:current"` — from the Home hub's arrival (a `wantsArrival`
        // lens) or from the standalone action's own context (H8).
        const arrival = this.props.arrival || {};
        const ctx = (this.props.action && this.props.action.context) || {};
        this.focus = String(arrival.focus || ctx.pb_focus || "");

        this.fmtInt = (v) => ({ n: int(v), u: "" });
        this.fmtMoney = (v) => this.moneyParts(v);

        // NOT awaited: the first frame is the kit skeleton, and the board
        // paints when the payload lands — never a blank page while it loads.
        onWillStart(() => { this.load(); });
        onMounted(() => this.observe());
        onPatched(() => this.observe());
        onWillUnmount(() => {
            if (this._ro) { this._ro.disconnect(); }
            cancelAnimationFrame(this._rafProg);
        });

        // Capture phase: the platform's hotkey service claims Escape on
        // `window` and stops it, so a bubble-phase listener never fires
        // (WF4). Claimed ONLY while the chart has focus and is off its home
        // month, so every other Escape still gets its turn.
        useExternalListener(window, "keydown", (ev) => this.onWindowKey(ev),
                            { capture: true });
    }

    // ------------------------------------------------------------- loading
    /** The one data call. Errors land on a Retry block, never a blank page. */
    async load() {
        this.state.loading = true;
        try {
            const d = await this.orm.call("pb.dashboard", "get_home_data", []);
            this.state.d = d;
            this.state.failed = false;
            this.state.updated = DateTime.now().toFormat("t");
            this.state.sel = this.focusIndex(this.focus);
            if (!this.measures.some((m) => m.key === this.state.measure)) {
                this.state.measure = "people";
            }
            this.state.loaded = true;
            this.growProgress();
        } catch (e) {
            console.warn("pb_dashboard: Home could not load", e);
            this.state.failed = true;
        } finally {
            this.state.loading = false;
        }
    }

    retry() { return this.load(); }

    /** The hero's progress bar grows from nothing once, after the first
     *  frame with data has painted at width 0 (two frames). */
    growProgress() {
        if (this.state.progReady) { return; }
        if (typeof requestAnimationFrame !== "function" || reducedMotion()) {
            this.state.progReady = true;
            return;
        }
        this._rafProg = requestAnimationFrame(() => {
            this._rafProg = requestAnimationFrame(() => { this.state.progReady = true; });
        });
    }

    /** Watch the three widths the drawing depends on. Re-run after every
     *  patch: the elements appear only once the payload has landed. */
    observe() {
        if (!window.ResizeObserver) {
            this.measureAll();
            return;
        }
        if (!this._ro) {
            this._seen = {};
            this._ro = new ResizeObserver(() => this.measureAll());
        }
        for (const [name, ref] of [["chart", this.chartRef], ["hero", this.heroSparkRef],
                                   ["stack", this.stackRef]]) {
            const el = ref.el;
            if (el && this._seen[name] !== el) {
                if (this._seen[name]) { this._ro.unobserve(this._seen[name]); }
                this._seen[name] = el;
                this._ro.observe(el);
            }
        }
    }

    measureAll() {
        const w = (ref) => (ref.el ? Math.round(ref.el.clientWidth) : 0);
        const chart = w(this.chartRef);
        const hero = w(this.heroSparkRef);
        const stack = w(this.stackRef);
        if (chart && chart !== this.state.width) { this.state.width = chart; }
        if (hero && hero !== this.state.heroW) { this.state.heroW = hero; }
        if (stack !== this.state.stackW) { this.state.stackW = stack; }
    }

    // ---------------------------------------------------------- formatting
    icon(name, size = 18) {
        // The activation table names icons in Lucide's own spelling
        // ("user-plus"); the kit's registry keys are camelCase.
        const key = String(name).replace(/-([a-z])/g, (_m, c) => c.toUpperCase());
        return ic(key, size);
    }

    ic(name, size = 16) { return ic(name, size); }

    get currency() { return (this.state.d && this.state.d.currency) || {}; }

    /** `{n, u}` for a figure that prints its unit small: `53.1` + `bn đ`;
     *  a currency printed before the number keeps it there (`$1.2` + `M`). */
    moneyParts(v) {
        const c = compact(v);
        const sym = this.currency.symbol || "";
        if (this.currency.position === "after") {
            return { n: c.num, u: [c.unit, sym].filter(Boolean).join(" ") };
        }
        return { n: sym + c.num, u: c.unit };
    }

    /** Compact money on one line: `53.1 bn đ`, `$1.2 M`. */
    money(v) {
        const p = this.moneyParts(v);
        return p.u ? p.n + " " + p.u : p.n;
    }

    /** The full figure, for tooltips: thousands separators in the reader's
     *  locale (`toLocaleString`), symbol on the currency's own side. */
    fullMoney(v) {
        const num = Math.round(Number(v) || 0).toLocaleString(locale());
        const sym = this.currency.symbol || "";
        return this.currency.position === "after" ? `${num} ${sym}`.trim() : sym + num;
    }

    int(v) { return int(v); }

    date(iso) { return iso ? DateTime.fromISO(iso) : null; }

    get today() {
        const t = this.state.d && this.state.d.today;
        return t ? DateTime.fromISO(t) : DateTime.now().startOf("day");
    }

    /** "Tue 20 Oct" this year, "20 Oct 2025" otherwise. */
    shortDate(iso) {
        const d = this.date(iso);
        if (!d || !d.isValid) { return ""; }
        return d.year === this.today.year ? d.toFormat("ccc d LLL") : d.toFormat("d LLL yyyy");
    }

    daysUntil(iso) {
        const d = this.date(iso);
        return d && d.isValid ? Math.round(d.startOf("day").diff(this.today, "days").days) : null;
    }

    monthName(key) { return DateTime.fromISO(`${key}-01`).toFormat("LLLL"); }

    monthLabel(key) { return DateTime.fromISO(`${key}-01`).toFormat("LLLL yyyy"); }

    monthShort(key) { return DateTime.fromISO(`${key}-01`).toFormat("LLL"); }

    peopleWord(n) {
        return n === 1 ? _t("1 person") : _t("%(n)s people", { n: int(n) });
    }

    // Local browser time — the server's clock is not the reader's.
    greeting() {
        const h = new Date().getHours();
        if (h < 12) return _t("Good morning");
        if (h < 18) return _t("Good afternoon");
        return _t("Good evening");
    }

    get todayLong() { return DateTime.now().toFormat("cccc d LLLL yyyy"); }

    get updatedLine() {
        return this.state.updated ? _t("Updated %(time)s", { time: this.state.updated }) : "";
    }

    // ------------------------------------------------------------ the data
    get d() { return this.state.d || {}; }

    get period() { return this.d.period || {}; }

    get months() { return this.d.months || []; }

    get latestIndex() { return this.months.findIndex((m) => m.latest); }

    get progressIndex() { return this.months.findIndex((m) => m.inprogress); }

    /** Where Escape lands: the latest completed month, else the newest. */
    get homeIndex() {
        const i = this.latestIndex;
        return i >= 0 ? i : this.months.length - 1;
    }

    get noRuns() { return !this.months.some((m) => m.runs > 0); }

    get hasMoney() {
        return this.months.some((m) => m.net !== null && m.net !== undefined);
    }

    get measures() {
        return MEASURES.filter((m) => !m.money || this.hasMoney);
    }

    focusIndex(focus) {
        const months = this.months;
        if (focus.startsWith("month:")) {
            const want = focus.slice(6);
            if (want === "current" && this.progressIndex >= 0) { return this.progressIndex; }
            const at = months.findIndex((m) => m.key === want);
            if (at >= 0) { return at; }
        }
        if (this.noRuns && this.progressIndex >= 0) { return this.progressIndex; }
        return this.homeIndex;
    }

    // ------------------------------------------------------- activation
    /** The five steps, in payload order, each carrying its words. The SERVER
     *  decides which steps exist and which are done; a key this table does
     *  not know is dropped rather than rendered blank. */
    get activation() {
        const a = (this.state.d && this.state.d.activation) || null;
        if (!a || !a.show) return null;
        const items = (a.items || [])
            .filter((it) => ACTIVATION[it.key])
            .map((it) => {
                const copy = ACTIVATION[it.key];
                // A step the learner STARTED says so. The server sends
                // `state` for the two learning rows and nothing for the
                // three database facts.
                const resuming = it.state === "in_progress" && !!copy.resume;
                return Object.assign({}, copy, {
                    key: it.key,
                    done: !!it.done,
                    resuming,
                    cta: resuming ? copy.resume : copy.cta,
                });
            });
        if (!items.length) return null;
        // The first step still to do is the one being ASKED for: one solid
        // button, never three.
        const next = items.findIndex((it) => !it.done);
        return { items, next, doneCount: items.filter((it) => it.done).length };
    }

    /** One handler for all five buttons. The step carries what it does. */
    runStep(item) {
        if (item && typeof item.run === "function") item.run(this);
    }

    // --------------------------------------------------------------- hero
    /** A run as people call it: its division label, else its name. */
    runName(run) {
        return (run && (run.division || run.name)) || "";
    }

    get hero() {
        const p = this.period;
        const month = this.monthName(p.key);
        const out = {
            eyebrow: _t("%(month)s payroll", { month: this.monthLabel(p.key) }),
            h1: [],
            say: [],
            tracked: p.stage !== null && p.stage !== undefined,
        };
        if (!out.tracked) {
            out.h1 = [_t("Pay runs are not tracked on this database")];
            return out;
        }
        const days = p.payday ? this.daysUntil(p.payday) : null;
        if (days !== null && days >= 0) {
            const first = days === 0 ? _t("Payday is today")
                : days === 1 ? _t("1 day to payday")
                : _t("%(days)s days to payday", { days });
            const n = p.awaiting_me || 0;
            const second = n === 1 ? _t("%(n)s pay run needs your approval", { n })
                : n > 1 ? _t("%(n)s pay runs need your approval", { n })
                : _t("nothing is waiting on you");
            out.h1 = [first, second];
        } else {
            out.h1 = [_t("%(month)s payroll is at step %(stage)s of 5",
                         { month, stage: p.stage })];
        }

        // The headline already names the step when no payday is known; the
        // sentence then starts with what is happening, never says it twice.
        const say = out.h1.length > 1 ? segs(_t("%(month)s is at %(step)s."), {
            month,
            step: { kind: "link", text: _t("step %(n)s of 5", { n: p.stage }),
                    go: () => this.toSteps() },
        }) : [];
        const aw = p.awaiting_run;
        const now = p.now_run;
        if (aw) {
            const vars = {
                who: aw.submitted_by,
                run: { kind: "link", text: this.runName(aw), go: () => this.openRun(aw.id) },
                people: this.peopleWord(aw.people || 0),
                net: aw.net !== null && aw.net !== undefined ? this.money(aw.net) : "",
            };
            let tpl;
            if (!aw.submitted_by) {
                tpl = _t("The %(run)s run (%(people)s) is waiting for your approval");
            } else if (vars.net) {
                tpl = _t("%(who)s has submitted the %(run)s run (%(people)s, %(net)s) for your approval");
            } else {
                tpl = _t("%(who)s has submitted the %(run)s run (%(people)s) for your approval");
            }
            say.push({ text: say.length ? " " : "" }, ...segs(tpl, vars));
            if (now && now.id !== aw.id) {
                say.push(...segs(_t(", and the %(run)s run is being prepared"), {
                    run: { kind: "link", text: this.runName(now), go: () => this.openRun(now.id) },
                }));
            }
            say.push({ text: "." });
        } else if (now) {
            say.push({ text: say.length ? " " : "" }, ...segs(_t("The %(run)s run is being prepared."), {
                run: { kind: "link", text: this.runName(now), go: () => this.openRun(now.id) },
            }));
        } else if (p.stage === 1) {
            say.push({ text: say.length ? " " : "" }, { text: _t("No pay run has started yet.") });
        }
        out.say = say;
        return out;
    }

    /** The hero's ONE solid button names the act. */
    get primary() {
        const p = this.period;
        const aw = p.awaiting_run;
        const now = p.now_run;
        if (aw) {
            return { label: _t("Review %(run)s", { run: this.runName(aw) }), icon: "fileCheck",
                     go: () => this.openRun(aw.id) };
        }
        if (now) {
            return { label: _t("Continue preparing %(run)s", { run: this.runName(now) }),
                     icon: "play", go: () => this.openRun(now.id) };
        }
        if (p.stage !== null && p.stage !== undefined && p.stage <= 1) {
            return { label: _t("Start %(month)s payroll", { month: this.monthName(p.key) }),
                     icon: "zap", go: () => this.openPay("run") };
        }
        return { label: _t("Open pay runs"), icon: "layoutGrid", runs: true,
                 go: () => this.openPay("runs") };
    }

    /** The five journey nodes, from the server's steps. */
    get journey() {
        const steps = this.d.steps || [];
        return steps.filter((st) => STEPS[st.key]).map((s, i) => {
            let sub = "";
            if (s.state === "done") {
                sub = s.when ? _t("Done %(date)s", { date: this.shortDate(s.when) }) : _t("Done");
            } else if (s.state === "wait") {
                sub = _t("Waiting on you");
            } else if (s.state === "now") {
                if (s.key === "approve") {
                    sub = s.who && s.who.name ? _t("Waiting on %(who)s", { who: s.who.name })
                        : _t("Waiting for approval");
                } else {
                    sub = _t("Under way");
                }
            } else if (s.key === "pay" && s.when) {
                sub = this.shortDate(s.when);
            } else if (s.key === "deliver") {
                sub = _t("Email, EN + VI");
            }
            return {
                key: s.key, state: s.state, num: i + 1, label: STEPS[s.key].journey(), sub,
                go: () => this.openStep(s, i + 1),
            };
        });
    }

    /** The cut-off, when it is still ahead (P1: `upcoming` drops a past one). */
    get cutoffItem() {
        return (this.d.upcoming || []).find((u) => u.kind === "cutoff") || null;
    }

    get heroFig() {
        const p = this.period;
        const prepared = p.prepared || 0;
        const expected = p.expected || 0;
        const facts = [];
        if (p.net_so_far !== null && p.net_so_far !== undefined) {
            facts.push(segs(_t("%(net)s net pay so far"),
                            { net: { kind: "b", text: this.money(p.net_so_far) } }));
        }
        const n = p.run_count || 0;
        facts.push(segs(n === 1 ? _t("%(n)s pay run") : _t("%(n)s pay runs"),
                        { n: { kind: "b", text: int(n) } }));
        const cut = this.cutoffItem;
        if (cut) {
            facts.push(segs(_t("cut-off %(date)s"),
                            { date: { kind: "b", text: this.shortDate(cut.date) } }));
        }
        const values = this.months.map((m) => (m.inprogress ? null : m.net));
        const li = this.latestIndex;
        return {
            label: _t("%(month)s so far", { month: this.monthName(p.key) }),
            pill: p.stage === 5 ? { text: _t("Complete"), tone: "green" }
                : { text: _t("In progress"), tone: "" },
            big: int(prepared),
            sub: expected ? _t("of %(n)s payslips prepared", { n: int(expected) })
                : _t("payslips prepared"),
            aria: expected ? _t("%(done)s of %(n)s payslips prepared",
                                { done: int(prepared), n: int(expected) })
                : _t("%(done)s payslips prepared", { done: int(prepared) }),
            prog: expected ? Math.min(100, (prepared / expected) * 100) : null,
            progNow: expected ? Math.round(Math.min(100, (prepared / expected) * 100)) : 0,
            facts,
            spark: this.hasMoney ? sparkPath(values, this.state.heroW || 300, 46,
                                             li >= 0 ? li : null) : null,
            sparkW: this.state.heroW || 300,
        };
    }

    // ------------------------------------------------------------ needs you
    get needs() {
        const p = this.period;
        return (this.d.needs_you || []).filter((it) => NEEDS[it.key] && it.n > 0).map((it) => {
            const w = NEEDS[it.key];
            return {
                key: it.key,
                n: int(it.n),
                text: it.n === 1 ? w.one() : w.many(),
                tone: w.rose ? "rose" : "amber",
                go: () => {
                    if (w.door === "run") {
                        if (p.awaiting_run) { this.openRun(p.awaiting_run.id); }
                        else { this.openPay("runs"); }
                    } else {
                        this.openDoor(w.door);
                    }
                },
            };
        });
    }

    get approvalsTail() {
        const n = this.d.approvals_total;
        if (n === null || n === undefined || n <= 0) { return null; }
        return { text: n === 1 ? _t("1 approval") : _t("All %(n)s approvals", { n: int(n) }) };
    }

    get quietLine() {
        const p = this.period;
        const days = p.payday ? this.daysUntil(p.payday) : null;
        const lead = _t("Nothing needs you right now");
        if (days !== null && days >= 0) {
            return { lead, next: _t("next: payday %(date)s", { date: this.shortDate(p.payday) }) };
        }
        return { lead, next: "" };
    }

    // ------------------------------------------------------------- the chart
    value(m, measure) {
        const v = m[measure || this.state.measure];
        return v === null || v === undefined ? 0 : Math.max(0, Number(v) || 0);
    }

    tickLabel(t) {
        if (this.state.measure === "people") { return int(t); }
        const c = compact(t);
        return [c.num.replace(/\.0$/, ""), c.unit].filter(Boolean).join(" ");
    }

    /**
     * The chart's geometry (the prototype's drawChart, as data). Columns at
     * min(24, slot × .55) wide, 4 px rounded tops; gridlines at a nice step of
     * a quarter of the axis; axis max = 1.08 × the largest completed month;
     * the in-progress month is a hollow column at the LATEST month's height
     * with the share prepared so far filled inside it.
     */
    get chart() {
        const months = this.months;
        const W = Math.max(320, this.state.width || 760);
        const H = 236;
        const padL = 46, padR = 10, padT = 22, padB = 30;
        const n = months.length || 12;
        const plotH = H - padT - padB;
        const plotW = W - padL - padR;
        const slot = plotW / n;
        const cw = Math.min(24, slot * 0.55);
        const base = padT + plotH;
        const li = this.latestIndex;
        let max = 0;
        months.forEach((m) => { if (!m.inprogress) { max = Math.max(max, this.value(m)); } });
        const pi = this.progressIndex;
        if (pi >= 0) { max = Math.max(max, this.value(months[pi])); }
        max *= 1.08;
        const empty = !(max > 0);
        if (empty) { max = 1; }
        const ticks = [];
        if (!empty) {
            const nice = niceStep(max / 4);
            for (let t = nice; t <= max + 1e-9; t += nice) {
                ticks.push({ y: base - (t / max) * plotH, label: this.tickLabel(t) });
            }
        }
        const sel = this.state.sel;
        const cols = months.map((m, i) => {
            const x = padL + i * slot + (slot - cw) / 2;
            const isSel = i === sel;
            const h = Math.max(2, (this.value(m) / max) * plotH);
            const y = base - h;
            let ghost = null;
            let d = roundedTop(x, y, cw, h, 4);
            let top = y;
            let topLabel = "";
            if (m.inprogress) {
                const ref = li >= 0 ? this.value(months[li]) : 0;
                if (ref > 0) {
                    const gh = Math.max(2, (ref / max) * plotH);
                    const gy = base - gh;
                    ghost = { y: gy, h: gh, d: roundedTop(x, gy, cw, gh, 4) };
                    d = roundedTop(x + 1, y, cw - 2, Math.max(1, h - 1), 3);
                    top = Math.min(gy, y);
                }
                topLabel = _t("In progress");
            } else if (m.latest) {
                topLabel = _t("Latest");
            } else if (m.note === "tet") {
                topLabel = _t("Tet");
            }
            const yy = m.key.slice(2, 4);
            return {
                key: m.key, x, y, w: cw, h, d,
                fill: isSel ? "sel" : "soft", sel: isSel,
                inprogress: !!m.inprogress, latest: !!m.latest,
                ghost,
                label: this.monthShort(m.key) + (m.year_mark ? ` ${yy}` : ""),
                labelX: x + cw / 2,
                topLabel, topY: top - 7,
                hitX: padL + i * slot, hitW: slot, hitY: padT - 14, hitH: plotH + 14,
                delay: `animation-delay: ${i * 30}ms`,
            };
        });
        return { W, H, padL, padR, base, ticks, cols, empty };
    }

    get chartAria() {
        return _t("Column chart. Use the arrow keys to change month, Escape for the latest month.");
    }

    /** The tooltip for the column under the pointer (or just chosen by key). */
    get tip() {
        const i = this.state.tip;
        const m = this.months[i];
        if (!m) { return null; }
        const col = this.chart.cols[i];
        const title = m.inprogress
            ? _t("%(month)s · in progress", { month: this.monthLabel(m.key) })
            : this.monthLabel(m.key);
        const rows = [];
        if (!m.runs) {
            rows.push({ k: _t("No pay run"), v: "" });
        } else {
            if (m.net !== null && m.net !== undefined) {
                rows.push({ k: _t("Net pay"), v: this.fullMoney(m.net) });
                rows.push({ k: _t("Gross pay"), v: this.fullMoney(m.gross) });
                rows.push({ k: _t("Deductions"), v: this.fullMoney(m.ded) });
                rows.push({ k: _t("Employer cost"), v: this.fullMoney(m.er) });
            }
            const expected = this.period.expected;
            rows.push({
                k: _t("People paid"),
                v: m.inprogress && expected
                    ? _t("%(n)s of %(of)s so far", { n: int(m.people), of: int(expected) })
                    : int(m.people),
            });
        }
        const x = col.x + col.w / 2;
        return {
            title, rows,
            style: `left: ${x.toFixed(1)}px; top: ${(Math.min(col.topY + 7, col.y) - 10).toFixed(1)}px;`,
            flip: x < 120 ? "is-left" : x > this.chart.W - 120 ? "is-right" : "",
        };
    }

    showTip(i) { this.state.tip = i; }

    hideTip() { this.state.tip = -1; }

    setMeasure(key) { this.state.measure = key; }

    select(i, fromKey = false) {
        const n = this.months.length;
        if (!n) { return; }
        const at = Math.max(0, Math.min(n - 1, i));
        this.state.sel = at;
        this.state.tip = fromKey ? at : this.state.tip;
    }

    /** ← → walk the months, Home / End jump to the ends (Escape: onWindowKey). */
    onChartKey(ev) {
        const n = this.months.length;
        const walk = { ArrowLeft: -1, ArrowRight: 1 }[ev.key];
        if (walk !== undefined) {
            ev.preventDefault();
            this.select(this.state.sel + walk, true);
        } else if (ev.key === "Home") {
            ev.preventDefault();
            this.select(0, true);
        } else if (ev.key === "End") {
            ev.preventDefault();
            this.select(n - 1, true);
        }
    }

    onWindowKey(ev) {
        if (ev.key !== "Escape") { return; }
        const el = this.chartRef.el;
        if (!el || !el.contains(document.activeElement)) { return; }
        if (this.state.sel === this.homeIndex) { return; }
        ev.stopPropagation();
        ev.preventDefault();
        this.select(this.homeIndex, true);
    }

    // ------------------------------------------------------- the month panel
    /** The neutral delta under a figure: an arrow and a sentence, never a
     *  colour (H-R5). */
    delta(key, m, prev) {
        if (m.inprogress) {
            return { icon: "clock", text: _t("so far · no comparison yet") };
        }
        const cur = m[key];
        if (cur === null || cur === undefined) { return null; }
        const pv = prev ? prev[key] : null;
        if (!prev || !prev.runs || pv === null || pv === undefined) {
            return { icon: "", text: _t("no earlier month") };
        }
        const month = this.monthShort(prev.key);
        if (key === "people") {
            const diff = Math.round(cur - pv);
            if (diff === 0) {
                return { icon: "moveRight", text: _t("about the same as %(month)s", { month }) };
            }
            return {
                icon: diff > 0 ? "trendingUp" : "trendingDown",
                text: _t("%(delta)s vs %(month)s",
                         { delta: (diff > 0 ? "+" : "−") + int(Math.abs(diff)), month }),
            };
        }
        if (!pv) { return { icon: "", text: _t("no earlier month") }; }
        const pct = ((cur - pv) / Math.abs(pv)) * 100;
        if (Math.abs(pct) < 0.5) {
            return { icon: "moveRight", text: _t("about the same as %(month)s", { month }) };
        }
        return {
            icon: pct > 0 ? "trendingUp" : "trendingDown",
            text: _t("%(delta)s vs %(month)s",
                     { delta: (pct > 0 ? "+" : "−") + Math.abs(pct).toFixed(1) + "%", month }),
        };
    }

    get panel() {
        const months = this.months;
        const m = months[this.state.sel];
        if (!m) { return null; }
        const prev = this.state.sel > 0 ? months[this.state.sel - 1] : null;
        const title = this.monthLabel(m.key);
        let pill;
        if (m.inprogress) {
            pill = { text: _t("In progress"), tone: "amber" };
        } else if (m.latest) {
            pill = { text: _t("Latest completed"), tone: "" };
        } else if (m.done) {
            pill = { text: _t("Completed"), tone: "" };
        } else if (m.runs) {
            pill = { text: _t("Not finished"), tone: "amber" };
        } else {
            pill = null;
        }

        const facts = [];
        if (!m.runs) {
            facts.push({ segs: [{ text: m.inprogress ? _t("No pay run has started yet.")
                                                     : _t("No pay run this month") }],
                         tone: "" });
        } else {
            facts.push({ segs: segs(m.runs === 1 ? _t("%(n)s pay run") : _t("%(n)s pay runs"),
                                    { n: { kind: "b", text: int(m.runs) } }), tone: "" });
            if (m.approved) {
                facts.push({ segs: segs(_t("approved %(date)s"),
                                        { date: { kind: "b", text: this.shortDate(m.approved) } }),
                             tone: "" });
            }
            if (m.delivered) {
                facts.push({ segs: segs(_t("delivered %(date)s"),
                                        { date: { kind: "b", text: this.shortDate(m.delivered) } }),
                             tone: "" });
            }
            if (m.inprogress) {
                facts.push({ segs: [{ text: _t("Figures grow as payslips are prepared") }],
                             tone: "soon", icon: "clock" });
            } else if (m.balance_ok === true) {
                facts.push({ segs: [{ text: _t("All runs balance") }], tone: "ok",
                             icon: "checkCircle" });
            } else if (m.balance_ok === false) {
                facts.push({ segs: [{ text: _t("A run does not balance") }], tone: "bad",
                             icon: "triangleAlert", go: () => this.openPay("runs") });
            }
            const foreign = m.foreign_runs || 0;
            if (foreign) {
                facts.push({
                    segs: [{ text: foreign === 1
                        ? _t("1 run in another currency is not added")
                        : _t("%(n)s runs in another currency are not added", { n: int(foreign) }) }],
                    tone: "",
                });
            }
        }

        const hi = m.inprogress ? (this.latestIndex >= 0 ? this.latestIndex : null) : this.state.sel;
        const spark = (key) => sparkPath(months.map((x) => (x.inprogress ? null : x[key])), 72, 28, hi);
        const figs = [
            { key: "people", label: _t("People paid"), value: m.people || 0, format: this.fmtInt },
            { key: "net", label: _t("Net pay"), value: m.net, format: this.fmtMoney },
            { key: "avg", label: _t("Average net per person"), value: m.avg, format: this.fmtMoney },
            { key: "total", label: _t("Total cost to the company"), value: m.total,
              format: this.fmtMoney },
        ].map((f) => Object.assign(f, { spark: spark(f.key), delta: this.delta(f.key, m, prev) }));

        return { title, pill, facts, figs, bar: this.bar(m), empty: this.noRuns };
    }

    /** Net | Deductions | Employer cost, with the Gross bracket over the
     *  first two. An amount prints inside its segment only when the segment
     *  is at least 90 px wide — a label is dropped, never clipped. */
    bar(m) {
        if (m.total === null || m.total === undefined || !(m.total > 0)) { return null; }
        const net = Math.max(0, m.net || 0);
        const ded = Math.max(0, m.ded || 0);
        const er = Math.max(0, m.er || 0);
        const sum = net + ded + er;
        if (!(sum > 0)) { return null; }
        const width = this.state.stackW || 0;
        const seg = (cls, v, text) => {
            const pct = (v / sum) * 100;
            return { cls, pct: pct.toFixed(2), text, title: this.fullMoney(v),
                     show: (pct / 100) * width >= 90 };
        };
        return {
            total: this.money(m.total),
            gross: this.money(m.gross),
            bracket: Math.min(100, ((m.gross || 0) / sum) * 100).toFixed(2),
            segs: [
                seg("net", net, _t("Net %(amount)s", { amount: this.money(net) })),
                seg("ded", ded, this.money(ded)),
                seg("er", er, this.money(er)),
            ],
        };
    }

    // ------------------------------------------------- steps and coming up
    get stepsTitle() {
        return _t("%(month)s, step by step", { month: this.monthName(this.period.key) });
    }

    get stepsSub() {
        const p = this.period;
        const parts = [];
        const cut = p.cutoff || (this.cutoffItem && this.cutoffItem.date);
        if (cut) { parts.push(_t("Cut-off %(date)s", { date: this.shortDate(cut) })); }
        if (p.payday) { parts.push(_t("payday %(date)s", { date: this.shortDate(p.payday) })); }
        return parts.join(" · ");
    }

    get stepRows() {
        const steps = this.d.steps || [];
        return steps.filter((st) => STEPS[st.key]).map((s, i) => {
            const row = {
                key: s.key, state: s.state, num: i + 1, title: STEPS[s.key].title(),
                sub: "", who: null, rose: "",
                when: { text: "", amber: false },
                go: () => this.openStep(s, i + 1),
            };
            if (s.key === "setup" && s.n) {
                row.sub = s.n === 1 ? _t("1 person added") : _t("%(n)s people added", { n: int(s.n) });
            } else if (s.key === "prepare" && s.run) {
                row.sub = _t("%(run)s run in progress", { run: s.run });
            } else if (s.key === "approve" && s.who && s.who.name && s.run) {
                row.who = s.who.initials || "";
                row.sub = _t("%(who)s submitted the %(run)s run", { who: s.who.name, run: s.run });
            } else if (s.key === "pay") {
                row.sub = _t("Bank file");
                if (s.n) {
                    row.rose = s.n === 1 ? _t("1 person has no bank account")
                        : _t("%(n)s people have no bank account", { n: int(s.n) });
                }
            } else if (s.key === "deliver") {
                row.sub = _t("Email in English and Vietnamese");
            }
            if (s.state === "wait") {
                row.when = { text: _t("waiting on you"), amber: true };
            } else if (s.state === "now") {
                row.when = { text: _t("today"), amber: false };
            } else if (s.when) {
                row.when = { text: this.shortDate(s.when), amber: false };
            }
            return row;
        });
    }

    /** "today" · "tomorrow" · "in 3 days" (amber to 3) · "Friday" (this
     *  week) · "in 19 days". */
    inDays(iso) {
        const n = this.daysUntil(iso);
        if (n === null) { return { text: "", amber: false }; }
        if (n <= 0) { return { text: _t("today"), amber: true }; }
        if (n === 1) { return { text: _t("tomorrow"), amber: true }; }
        if (n <= 3) { return { text: _t("in %(n)s days", { n }), amber: true }; }
        if (n < 7) { return { text: this.date(iso).toFormat("cccc"), amber: false }; }
        return { text: _t("in %(n)s days", { n: int(n) }), amber: false };
    }

    get upcomingRows() {
        return (this.d.upcoming || []).filter((u) => UPCOMING[u.kind]).map((u) => {
            const w = UPCOMING[u.kind];
            const d = this.date(u.date);
            const inn = this.inDays(u.date);
            let amber = "";
            let tail = "";
            if (u.kind === "contracts_end") {
                const ex = u.extra || {};
                if (ex.renewals) {
                    amber = ex.renewals === 1 ? _t("1 renewal to start")
                        : _t("%(n)s renewals to start", { n: int(ex.renewals) });
                }
                if (ex.renewed) {
                    tail = _t("%(n)s already renewed", { n: int(ex.renewed) });
                }
            }
            return {
                key: `${u.kind}-${u.date}`,
                day: d ? d.toFormat("d") : "",
                mon: d ? d.toFormat("LLL") : "",
                hot: inn.amber,
                title: w.title(u, this),
                sub: w.sub(u, this),
                amber, tail,
                inn,
                go: () => (w.door === "deliver" ? this.openPay("deliver") : this.openDoor(w.door)),
            };
        });
    }

    // ---------------------------------------------------------------- doors
    /** The return door every hand-off carries: `hub_nav.js`'s `pb_back`
     *  contract, written by hand (see the header). */
    backDoor() {
        const back = {
            label: _t("Home"), tag: "", xmlid: "pb_home_hub.action_pb_home_hub",
            lens: "", lensKey: "pb_lens", context: {},
        };
        return back;
    }

    /** Open a hub (or any client action) by xmlid with the arrival protocol
     *  filled in. `doAction` is a promise: a screen that is not on this
     *  database gets a notification, never an unhandled rejection. */
    door(xmlid, { lens = "", lensKey = "pb_lens", focus = "", back = true } = {}) {
        if (!xmlid) { return; }
        const additionalContext = {};
        if (lens) { additionalContext[lensKey] = lens; }
        if (focus) { additionalContext.pb_focus = focus; }
        if (back) { additionalContext.pb_back = this.backDoor(); }
        Promise.resolve(this.action.doAction(xmlid, { additionalContext, clearBreadcrumbs: true }))
            .catch(() => {
                this.notification.add(_t("That screen is not installed on this database."), {
                    type: "warning",
                });
            });
    }

    openDoor(key) {
        const d = DOORS[key];
        if (d) { this.door(d.xmlid, d); }
    }

    openPay(lens) { this.door(PAY_HUB, { lens }); }

    /** The Runs board reads `arrival.focus` as a run id (pb_payruns). */
    openRun(id) { this.door(PAY_HUB, { lens: "runs", focus: String(id) }); }

    openStep(step, num) {
        const p = this.period;
        if (step.key === "approve" && step.state === "wait" && p.awaiting_run) {
            this.openRun(p.awaiting_run.id);
        } else if (step.key === "prepare" && step.state === "now" && p.now_run) {
            this.openRun(p.now_run.id);
        } else {
            this.openPay(STAGE_LENS[num] || "runs");
        }
    }

    openApprovals() { this.openDoor("approvals"); }

    toSteps() {
        const el = this.stepsRef.el;
        if (el) {
            el.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "center" });
            el.focus({ preventScroll: true });
        }
    }

    // doAction is a promise: a synchronous try/catch around it catches nothing
    // (pb_learn ledger, Phase C review).
    open(xmlid) {
        if (!xmlid) return;
        Promise.resolve(this.action.doAction(xmlid, { clearBreadcrumbs: true })).catch(() => {
            this.notification.add(_t("That screen is not installed on this database."), {
                type: "warning",
            });
        });
    }

    /** The Insights hub, with a back chip that says Home (Cycle 4). Two
     *  doors: the hero's Insights button and the four month figures. */
    openInsights() {
        this.door(INSIGHTS_HUB);
    }

    /** Start a walkthrough, if there is an engine on this database to start
     *  it. `env.services[...]` rather than `useService`, which THROWS on a
     *  missing service. `fallback` is an xml-id to open instead. */
    scenario(key, mode, fallback) {
        const sc = this.env.services && this.env.services[SCENARIO_SERVICE];
        if (!sc) {
            if (fallback) {
                this.open(fallback);
            } else {
                this.notification.add(_t("The guided tour is not installed on this database."), {
                    type: "warning",
                });
            }
            return;
        }
        // begin() returns false for an unknown key and never throws; it is
        // async, so the rejection path needs a .catch of its own.
        Promise.resolve(sc.begin(key, mode)).then((started) => {
            if (!started && fallback) this.open(fallback);
        }).catch(() => {
            if (fallback) this.open(fallback);
        });
    }
}

registry.category("actions").add("pb_dashboard", PbDashboard);
