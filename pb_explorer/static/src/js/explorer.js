/** @odoo-module **/
/**
 * Analytics Explorer — the payroll analytics workbench (Sudima Phase N).
 *
 * Compose a question from chips (MEASURE / BY / OVER / WHERE), render it in one
 * of six forms, and drill any cell to the people behind it.
 *
 * RPC facade: pb.explorer (read-only). Chart.js arrives through Odoo's own lazy
 * `web.chartjs_lib` bundle; the donut and heatmap are bespoke SVG. No CDN.
 */
import { Component, useState, useRef, onWillStart, onWillUnmount, onMounted,
         onPatched, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_explorer/js/pbex_icons";
import { donutArcs, heatmapCells, chartConfig, ensureChartJs, colourAt,
         waterfallBars } from "@pb_explorer/js/pbex_charts";

const MODEL = "pb.explorer";

const CHART_META = {
    column:  { icon: "columns",   label: _t("Columns") },
    stacked: { icon: "layers",    label: _t("Stacked") },
    line:    { icon: "lineChart", label: _t("Trend") },
    donut:   { icon: "pie",       label: _t("Share") },
    heatmap: { icon: "thermo",    label: _t("Heatmap") },
    table:   { icon: "table",     label: _t("Table") },
    compare: { icon: "gitMerge",  label: _t("Compare") },
};

const FILTER_META = {
    department_id: _t("Department"),
    division_id:   _t("Division"),
    division:      _t("Division"),
    scheme:        _t("Payroll scheme"),
    kind:          _t("Kind of run"),
    country:       _t("Country"),
    group:         _t("Group"),
    category_type: _t("Component type"),
    code:          _t("Component"),
    cycle:         _t("Kind of run"),
    basis:         _t("Basis"),
    // GROUP P5 — offered by the server only where somebody really is paid in
    // two places, so on every other database this row simply never appears.
    split:         _t("Where they work"),
};

/** The icon each rung of the walk down the group wears. */
const LEVEL_ICON = {
    group: "globe", country: "globe", company_id: "building",
    division_id: "layers", department_id: "users", job_id: "user",
};

/** Where the reader is standing, in the words on the screen. */
const LEVEL_LABEL = {
    group: _t("Group"), country: _t("Country"), company_id: _t("Company"),
    division_id: _t("Division"), department_id: _t("Department"),
    job_id: _t("Job position"),
};

/** The same rungs in the plural, because the "look inside" cue names what
 *  the reader would find down there — "Look inside Retail · departments" —
 *  and "Department" reads as a heading rather than as a promise. */
const LEVEL_MANY = {
    country: _t("countries"), company_id: _t("companies"),
    division_id: _t("divisions"), department_id: _t("departments"),
    job_id: _t("job positions"),
};

/** How long the descent takes. Long enough to be read as one movement,
 *  short enough that nobody waits for it. */
const DESCENT_MS = 300;
const ARRIVE_MS = 340;

/** The one place the URL is written and read. Keys are short on purpose —
 *  the hash is a link somebody pastes into a message, not a payload. */
const HASH_KEY = "pbex";

export class PbExplorer extends Component {
    static template = "pb_explorer.PbExplorer";
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.ic = ic;
        this.chartMeta = CHART_META;
        this.filterMeta = FILTER_META;
        this.levelIcon = LEVEL_ICON;
        this.levelLabel = LEVEL_LABEL;
        this.canvasRef = useRef("canvas");
        this.vizRef = useRef("viz");

        this.state = useState({
            loaded: false,
            busy: false,
            error: "",
            schema: null,
            data: null,
            spec: {
                measure: "net",
                dimension: "department_id",
                grain: "month",
                chart: "column",
                filters: {},
                date_from: null,
                date_to: null,
                // GROUP P3 — the three switches that change what a number
                // MEANS, so each one travels in the spec and in the link.
                advances: "main",
                currency: "group",
                target_currency: 0,
                per_head: false,
                path: [],
            },
            part: 0,            // which currency the chart shows in own mode
            showRates: false,   // the "what rate was used" fold
            openPicker: "",     // which chip dropdown is open
            filterKey: "",      // which filter is being added
            drill: null,
            drillBusy: false,
            hover: null,
            lensId: "",         // the active shipped lens, if any
            lensesOpen: true,   // the lens grid — folded once a lens is chosen
            ask: "",            // the natural-language box
            asking: false,
            askWhy: null,       // the chips the parser chose — shown, never hidden
            story: null,        // narrate() payload
            storyBusy: false,
            showStory: false,
            // GROUP P7 — a bar is a DOOR. `peek` is the bar the pointer or
            // the keyboard is on, `doors` are the focusable proxies laid over
            // a canvas the keyboard cannot otherwise reach, and `descent` /
            // `arrived` are the two halves of the walk down.
            peek: null,
            doors: [],
            descent: null,
            arrived: false,
            // LOOK P4 — the WHEN clause. `stripFocus` is the month chip the
            // keyboard is standing on and `preview` is the stretch under the
            // hand while a sweep is in flight; a preview costs no server call
            // at all, so four months is ONE read and not four.
            stripFocus: "",
            preview: [],
        });

        // The anchor a Shift-press or a sweep extends from. On the instance
        // rather than in `useState`: nothing renders it, and a value the
        // template never reads has no business making the board repaint.
        this.anchor = "";
        this.drag = null;

        this._chart = null;
        this._chartSig = "";

        onWillStart(async () => {
            await ensureChartJs().catch(() => null);
            await this.loadSchema();
            // Two ways to arrive with a question already loaded:
            //   pbex_lens — a named lens (a gallery/sidebar card)
            //   pbex_spec — a full spec handed over by another board, which is
            //               how every clickable number on the Insights cockpit
            //               drills through to here.
            // Either way the spec stays fully editable and the chips show
            // exactly what was chosen — arriving pre-filtered must never feel
            // like a dead end.
            const ctx = this.props.action?.context || {};
            // A ⌘K row says what it MEANT through `pb_focus` — "compare the
            // schemes", not just "open the Explorer".
            const lens = ctx.pbex_lens || (ctx.pb_focus === "compare"
                ? "compare" : "");
            if (ctx.pbex_spec || lens) {
                try {
                    const resolved = await this.orm.call(MODEL, "resolve_spec",
                        [lens || false, ctx.pbex_spec || false]);
                    this.state.spec = { ...this.state.spec, ...resolved };
                    this.state.lensId = lens || "";
                    // An incoming question is the point of the visit; fold the
                    // lens grid away so the answer is what you land on.
                    this.state.lensesOpen = false;
                } catch (e) {
                    this.notif.add(this._msg(e), { type: "warning" });
                }
            } else {
                // A pasted link reproduces the view it was copied from —
                // breadcrumb, chips, money mode and all.
                const had = this.readHash();
                // Otherwise the board OPENS on the first step of the walk.
                // A breadcrumb whose next rung is Country, over a chart
                // already broken down by department, asks the reader to
                // guess that the two are connected.
                const next = this.state.schema?.trail?.next;
                if (!had && next) { this.state.spec.dimension = next; }
            }
            await this.run();
            this.state.loaded = true;
        });
        // BOTH hooks are required: the payload is already loaded by the time
        // the first render happens, so onPatched never fires for it and the
        // canvas would sit at its default 300x150, empty.
        // WF4: the platform's hotkey service listens on `window` and stops
        // propagation for the keys it claims, so a bubble-phase listener in a
        // cockpit never fires. Capture phase, and nothing is prevented that
        // the platform still needs.
        this._onKey = (ev) => this.onKeydown(ev);
        onMounted(() => {
            this.syncChart();
            window.addEventListener("keydown", this._onKey, { capture: true });
            // The doors are laid over the bars in pixels, so they go stale the
            // moment the board is resized — and the hub rail can be folded at
            // any time. A short delay lets the chart finish its own resize
            // first; the doors are invisible, so nothing flickers.
            if (window.ResizeObserver && this.vizRef.el) {
                this._ro = new ResizeObserver(() => {
                    clearTimeout(this._roT);
                    this._roT = setTimeout(() => this.syncDoors(), 120);
                });
                this._ro.observe(this.vizRef.el);
            }
        });
        onPatched(() => this.syncChart());
        // A sweep across the month strip may end anywhere, including off the
        // strip and off the window — releasing there still commits the
        // stretch the hand drew rather than leaving a preview stranded.
        useExternalListener(window, "pointerup", () => this.endMonthDrag());
        useExternalListener(window, "pointercancel", () => this.endMonthDrag());
        onWillUnmount(() => {
            this.destroyChart();
            window.removeEventListener("keydown", this._onKey, { capture: true });
            this._ro?.disconnect();
            clearTimeout(this._roT);
            clearTimeout(this._descentT);
            clearTimeout(this._arriveT);
        });
    }

    // ------------------------------------------------------------- loading
    async loadSchema() {
        try {
            this.state.schema = await this.orm.call(MODEL, "get_schema", []);
        } catch (e) {
            this.state.error = this._msg(e);
        }
    }

    async run() {
        this.state.busy = true;
        this.state.error = "";
        try {
            const spec = JSON.parse(JSON.stringify(this.state.spec));
            this.state.data = await this.orm.call(MODEL, "query", [spec]);
            this.state.drill = null;
            this.state.part = 0;
            // ADOPT WHAT THE SERVER ANSWERED, never what we asked with (rule
            // 18). It is the server that decides what a pair of dates means
            // and refuses one it cannot answer, so the chip, the strip and
            // the link all read the resolved period and not the request.
            const period = this.state.data && this.state.data.period;
            if (period) {
                this.state.spec.date_from = period.date_from || null;
                this.state.spec.date_to = period.date_to || null;
            }
            this.writeHash();
        } catch (e) {
            this.state.error = this._msg(e);
            this.state.data = null;
        } finally {
            this.state.busy = false;
        }
    }

    // ============================================================== the WHEN
    /* THE CLAUSE THIS SENTENCE NEVER HAD.
     *
     * The board reads as a sentence — *Show total cost By department Over
     * month Where …* — and the one thing every number on it depends on was
     * missing from it: the spec has carried `date_from` and `date_to` since
     * the board shipped and the server has always honoured them, but there was
     * no control anywhere that set either one. They arrived only through a
     * saved link, and the link did not even carry them.
     *
     * It is a CLAUSE, in its own chip group between "Over" and "Where", and
     * not a filter in the "Where": a period among the filters would bury the
     * one thing the whole answer is about. */

    /** What the board is about, as the server resolved it. */
    get periodMeta() {
        return (this.state.data && this.state.data.period)
            || { key: "", kind: "all", label: _t("Everything"),
                 date_from: null, date_to: null, preset: "all" };
    }

    get hasPeriod() { return this.periodMeta.kind !== "all"; }

    /** The seven starting points, each naming the dates it means. */
    get periodPresets() {
        return (this.state.schema && this.state.schema.periods
                && this.state.schema.periods.presets) || [];
    }

    /** Every month the facts hold. Empty on a database with nothing built. */
    get periodMonths() {
        return (this.state.schema && this.state.schema.periods
                && this.state.schema.periods.months) || [];
    }

    /** How much of the CURRENT measure sits in each month. */
    get periodWeights() { return (this.state.data && this.state.data.weights) || {}; }

    get heaviestMonth() {
        const vals = Object.values(this.periodWeights).map((v) => Math.abs(Number(v) || 0));
        return vals.length ? Math.max(...vals) : 0;
    }

    /** A month with something in it always draws a sliver, so "some" and
     *  "none" can be told apart at a glance. */
    monthShare(mo) {
        const top = this.heaviestMonth;
        const v = Math.abs(Number(this.periodWeights[mo.key]) || 0);
        if (!top || !v) { return 0; }
        return Math.max(4, Math.min(100, (v / top) * 100));
    }

    /** What one month chip says on hover or focus. ONE expression. */
    monthTitle(mo) {
        const v = Number(this.periodWeights[mo.key]) || 0;
        const label = this.state.data ? this.state.data.measure_label : "";
        if (!v) { return _t("%s — nothing to show for this question.", mo.label); }
        return _t("%(month)s — %(measure)s %(value)s",
                  { month: mo.label, measure: label,
                    value: this.moneyWithSymbol(v) });
    }

    /** Is this month inside what is chosen — or inside the sweep under the
     *  hand, which is painted from the strip itself and costs no read. */
    isMonthLit(key) {
        if (this.state.preview.length) { return this.state.preview.includes(key); }
        const p = this.periodMeta;
        if (!p.date_from || !p.date_to) { return false; }
        return key >= p.date_from.slice(0, 7) && key <= p.date_to.slice(0, 7);
    }

    isMonthEdge(key, side) {
        const keys = this.litMonths;
        if (!keys.length) { return false; }
        return side === "first" ? keys[0] === key : keys[keys.length - 1] === key;
    }

    get litMonths() {
        if (this.state.preview.length) { return this.state.preview; }
        return this.periodMonths.map((m) => m.key).filter((k) => this.isMonthLit(k));
    }

    /** Every month between two chips, in strip order, in either direction. */
    monthSpan(a, b) {
        const keys = this.periodMonths.map((m) => m.key);
        const i = keys.indexOf(a);
        const j = keys.indexOf(b);
        if (i < 0 || j < 0) { return []; }
        return keys.slice(Math.min(i, j), Math.max(i, j) + 1);
    }

    /**
     * The two dates a run of month chips means.
     *
     * THE PICKER STAYS OPEN. A strip is a control you work — press June, then
     * shift-press August, then walk it with the arrows — and a dropdown that
     * shut on the first press made every one of those a single press: the
     * second key went to a chip that no longer existed and nothing happened.
     * A preset is a finished answer and closes; the strip is not.
     */
    async setMonths(keys) {
        this.state.preview = [];
        if (!keys.length) { await this.clearPeriod(); return; }
        const months = this.periodMonths;
        const first = months.find((m) => m.key === keys[0]);
        const last = months.find((m) => m.key === keys[keys.length - 1]);
        if (!first || !last) { return; }
        this.state.stripFocus = keys[0];
        await this.setPeriod(first.date_from, last.date_to, false);
    }

    /**
     * Set the period. Everything on the board becomes about it: the numbers,
     * the chart, the people count, the breadcrumb, the coverage sentences, the
     * drill and the export, because they all read the same spec.
     */
    async setPeriod(from, to, close = true) {
        if (this.state.busy) { return; }
        const s = this.state.spec;
        if ((s.date_from || null) === (from || null)
            && (s.date_to || null) === (to || null)) {
            if (close) { this.state.openPicker = ""; }
            return;
        }
        s.date_from = from || null;
        s.date_to = to || null;
        if (close) { this.state.openPicker = ""; }
        this.state.lensId = "";
        this.destroyChart();
        await this.run();
    }

    async clearPeriod(close = true) {
        this.state.preview = [];
        this.anchor = "";
        this.state.stripFocus = "";
        await this.setPeriod(null, null, close);
    }

    async pickPreset(preset) {
        this.anchor = "";
        this.state.preview = [];
        this.state.stripFocus = "";
        await this.setPeriod(preset.date_from, preset.date_to);
    }

    isPresetOn(preset) {
        const s = this.state.spec;
        return (s.date_from || null) === (preset.date_from || null)
            && (s.date_to || null) === (preset.date_to || null);
    }

    /**
     * ONE press of one month chip, from a mouse, a finger or the keyboard.
     *
     * Shift extends from the anchor — and a Shift-press with NO anchor is a
     * plain press rather than nothing, because a control that ignores a
     * deliberate action is a control a person stops trusting. Pressing the
     * month that is already the whole of the period goes back to Everything,
     * which is the way out a reader finds without being told.
     */
    async pressMonth(key, shift) {
        if (this.state.busy) { return; }
        if (shift && this.anchor) {
            await this.setMonths(this.monthSpan(this.anchor, key));
            return;
        }
        this.anchor = key;
        const lit = this.litMonths;
        if (lit.length === 1 && lit[0] === key) {
            // Pressing the month that IS the whole period goes back to
            // Everything — the way out a reader finds without being told. The
            // strip stays open, because they are still working it.
            await this.clearPeriod(false);
            return;
        }
        await this.setMonths([key]);
    }

    // ---------------------------------------------------------- the sweep
    onMonthDown(mo, ev) {
        if (ev.button !== undefined && ev.button !== 0) { return; }
        if (ev.shiftKey) { return; }             // a Shift-press is not a drag
        this.drag = { from: mo.key, to: mo.key, moved: false };
        this.state.preview = [mo.key];
    }

    /** The click after a mouse gesture is IGNORED — `endMonthDrag` has already
     *  answered it, and one gesture read twice toggles itself back off. What
     *  still comes through is the keyboard (`detail === 0`) and a Shift-press,
     *  which never starts a drag. */
    async onMonthClick(mo, ev) {
        if (ev.detail !== 0 && !ev.shiftKey) { return; }
        await this.pressMonth(mo.key, Boolean(ev.shiftKey));
    }

    onMonthStripMove(ev) {
        if (!this.drag) { return; }
        // Read the chip from the POINT, not from `ev.target`: a touch pointer
        // is captured by the element it started on, so following a finger
        // needs the geometry rather than the event's own target.
        const el = document.elementFromPoint(ev.clientX, ev.clientY);
        const chip = el && el.closest ? el.closest("[data-month]") : null;
        const key = chip && chip.dataset.month;
        if (!key || key === this.drag.to) { return; }
        this.drag.to = key;
        this.drag.moved = this.drag.moved || key !== this.drag.from;
        this.state.preview = this.monthSpan(this.drag.from, key);
    }

    async endMonthDrag() {
        const drag = this.drag;
        this.drag = null;
        if (!drag) { return; }
        this.anchor = drag.from;
        if (!drag.moved) {
            // A press that never moved is a press. Answered HERE and not by a
            // click handler, so one gesture can never be read twice.
            this.state.preview = [];
            await this.pressMonth(drag.from, false);
            return;
        }
        await this.setMonths(this.monthSpan(drag.from, drag.to));
    }

    /**
     * ← and → walk the strip, Home and End jump to its ends, Shift with any of
     * them EXTENDS from the anchor. The ledger's rule 20 contract, the same
     * one the Budget strip answers.
     */
    async onMonthStripKey(ev) {
        const walk = { ArrowLeft: -1, ArrowRight: 1, Home: "first",
                       End: "last" }[ev.key];
        if (walk === undefined) { return; }
        const keys = this.periodMonths.map((m) => m.key);
        if (!keys.length) { return; }
        ev.preventDefault();
        ev.stopPropagation();
        // THE BUSY GUARD IS HERE, never on a chip's `disabled` attribute
        // (T23): a chip disabled under the keyboard loses focus, and the next
        // press is then read against a state it was about to change.
        if (this.state.busy) { return; }
        // WHERE THE KEYBOARD IS STANDING IS THE CHIP THAT HAS FOCUS, never the
        // period in scope.
        const chip = ev.target && ev.target.closest
            ? ev.target.closest("[data-month]") : null;
        const from = (chip && chip.dataset.month) || this.state.stripFocus
            || this.litMonths[0] || "";
        const here = keys.indexOf(from);
        let next;
        if (walk === "first") {
            next = 0;
        } else if (walk === "last") {
            next = keys.length - 1;
        } else if (here < 0) {
            next = walk > 0 ? 0 : keys.length - 1;
        } else {
            next = Math.min(keys.length - 1, Math.max(0, here + walk));
        }
        const key = keys[next];
        this.state.stripFocus = key;
        if (ev.shiftKey && this.anchor) {
            await this.setMonths(this.monthSpan(this.anchor, key));
        } else {
            this.anchor = key;
            await this.setMonths([key]);
        }
        this.focusMonth(key);
    }

    focusMonth(key) {
        const root = document.querySelector(".pbex-when-strip");
        if (!root) { return; }
        const el = root.querySelector(`[data-month="${key}"]`);
        if (el) { el.focus(); }
    }

    /**
     * The server's own sentence, or ours — and never the platform's (GR17).
     *
     * The top-level `.message` of every RPC error on this platform is the
     * literal string "Odoo Server Error". Falling back to it prints the one
     * word this product may never say, in a red box, on the screen the reader
     * is looking at. So it is not a rung on this ladder: either the server
     * told us something a person can act on (`error.data.message`, or the
     * older `error.message.data.message` shape), or we say our own sentence.
     */
    _msg(e) {
        const data = (e && e.data) || (e && e.message && e.message.data);
        return (data && data.message) || _t("Something went wrong.");
    }

    // ----------------------------------------------------------- the link
    /** The view, in the address bar, so a link reproduces exactly this. */
    writeHash() {
        try {
            const s = this.state.spec;
            const compact = {
                m: s.measure, d: s.dimension, g: s.grain, c: s.chart,
                f: s.filters, p: s.path, a: s.advances, u: s.currency,
                t: s.target_currency || 0, h: s.per_head ? 1 : 0,
                // THE PERIOD TRAVELS. Without these two the one thing every
                // number on the screen depends on was lost the moment a link
                // was shared, and the reader at the other end saw a different
                // answer to the same question with no way to tell.
                s: s.date_from || "", e: s.date_to || "",
            };
            const hash = `#${HASH_KEY}=${encodeURIComponent(JSON.stringify(compact))}`;
            if (window.location.hash !== hash) {
                window.history.replaceState(null, "", hash);
            }
        } catch {
            // A URL is a convenience. It never gets in the way of a chart.
        }
    }

    readHash() {
        try {
            const raw = (window.location.hash || "").replace(/^#/, "");
            if (!raw.startsWith(`${HASH_KEY}=`)) { return false; }
            const c = JSON.parse(decodeURIComponent(raw.slice(HASH_KEY.length + 1)));
            const s = this.state.spec;
            if (c.m) { s.measure = c.m; }
            if (c.d) { s.dimension = c.d; }
            if (c.g) { s.grain = c.g; }
            if (c.c) { s.chart = c.c; }
            if (c.f && typeof c.f === "object") { s.filters = c.f; }
            if (Array.isArray(c.p)) { s.path = c.p; }
            if (c.a) { s.advances = c.a; }
            if (c.u) { s.currency = c.u; }
            s.target_currency = Number(c.t) || 0;
            s.per_head = !!c.h;
            // A hand-edited or half-copied period is not an error state: the
            // server refuses anything it cannot read and answers "Everything",
            // which is what the board would have shown anyway.
            s.date_from = typeof c.s === "string" && c.s ? c.s : null;
            s.date_to = typeof c.e === "string" && c.e ? c.e : null;
            return true;
        } catch {
            // A hash somebody edited by hand is not an error state — the
            // board simply opens on its own default view.
            return false;
        }
    }

    // ------------------------------------------------------ the breadcrumb
    get trail() {
        return this.state.data?.trail || this.state.schema?.trail
            || { levels: [], path: [], root_label: "", next: "" };
    }

    /** Group › Vietnam › Retail › Bread — the root plus every step walked. */
    get crumbs() {
        const t = this.trail;
        const out = [{
            level: t.root || "group",
            label: t.root_label || _t("Everything"),
            index: -1,
        }];
        (t.path || []).forEach((step, i) => {
            out.push({ level: step.level, label: step.label, index: i });
        });
        return out;
    }

    /** Can a click on a bar take the reader one level deeper? */
    get canStepDown() {
        const levels = this.trail.levels || [];
        return levels.includes(this.state.spec.dimension)
            && this.state.spec.dimension !== "job_id";
    }

    /** The level shown below the one the reader is standing on.
     *  A rung with only one value is skipped: a chart with one bar is a
     *  click that answers nothing. */
    nextLevelAfter(level) {
        const levels = this.trail.levels || [];
        const skip = this.trail.skip || [];
        let at = levels.indexOf(level);
        if (at < 0) { return ""; }
        for (let i = at + 1; i < levels.length; i++) {
            if (!skip.includes(levels[i])) { return levels[i]; }
        }
        return "";
    }

    stepDown(key, label, box = null) {
        const level = this.state.spec.dimension;
        const next = this.nextLevelAfter(level);
        if (!next) { return; }
        this.clearPeek();
        this.descendFrom(box);
        this.state.spec.path = [...(this.state.spec.path || []),
                                { level, key, label }];
        this.state.spec.dimension = next;
        this.state.lensId = "";
        this.destroyChart();
        this.run();
    }

    // ------------------------------------------------- the door on every bar
    /**
     * "Look inside Retail · departments."
     *
     * A bar in this board is a DOOR — clicking it walks the breadcrumb one
     * rung down the group. Nothing on screen ever said so, so most readers
     * never found the walk at all. Three things fix that and they belong
     * together: the pointer changes over a bar that opens, the bar itself
     * lights up, and a chip names WHERE the click would take you.
     *
     * Empty at the bottom of the walk, and empty whenever the chart is
     * showing something that is not a place — and then no cue is offered
     * anywhere, because there is nothing to look inside.
     */
    get nextRungLabel() {
        if (!this.canStepDown) { return ""; }
        const next = this.nextLevelAfter(this.state.spec.dimension);
        if (!next) { return ""; }
        return LEVEL_MANY[next] || LEVEL_LABEL[next] || "";
    }

    /** The cue, and the same words a screen reader is given. */
    lookInside(name) { return _t("Look inside %s", name); }

    setPeek(key, label) {
        if (!this.nextRungLabel || key === "" || key === "_all") { return; }
        if (this.state.peek && this.state.peek.key === key) { return; }
        this.state.peek = { key, label };
    }

    clearPeek() {
        if (this.state.peek) { this.state.peek = null; }
    }

    onArcEnter(arc) {
        this.state.hover = arc.key;
        this.setPeek(arc.key, arc.label);
    }

    onArcLeave() {
        this.state.hover = null;
        this.clearPeek();
    }

    /**
     * Chart.js paints on a canvas, and a canvas has no children a keyboard
     * can reach: without these there is no way to walk down the group
     * without a mouse. Each door is a real button laid over one bar. It
     * takes NO pointer events — the chart keeps its own tooltip and its own
     * click — but it still takes focus, and Enter or Space on a focused
     * button fires its click the way any button does.
     *
     * One tab stop per series (the tallest bar of it); the rest are reachable
     * only through it, so a year of twelve months does not become twelve tab
     * stops per team.
     */
    syncDoors() {
        const part = this.activePart;
        if (!this._chart || !this.isCanvasChart || this.isCompare
            || !this.nextRungLabel || !part) {
            if (this.state.doors.length) {
                this.state.doors = [];
                this._doorSig = "";
            }
            return;
        }
        const doors = [];
        part.series.forEach((ser, di) => {
            if (ser.key === "" || ser.key === "_all") { return; }
            const meta = this._chart.getDatasetMeta(di);
            if (!meta || meta.hidden) { return; }
            let tallest = null;
            (meta.data || []).forEach((el, ci) => {
                const box = this.barBox(el);
                if (!box) { return; }
                const door = {
                    id: di + ":" + ci, key: ser.key, label: ser.label,
                    tab: false, ...box,
                };
                if (!tallest || door.h > tallest.h) { tallest = door; }
                doors.push(door);
            });
            if (tallest) { tallest.tab = true; }
        });
        // A year of twelve months across twenty teams is 240 nodes nobody
        // asked for. Past that only the tab stops are drawn: every team is
        // still reachable, the highlight simply follows one bar per team.
        const kept = doors.length > 240 ? doors.filter((d) => d.tab) : doors;
        // Handing OWL a fresh array on every patch would re-render for ever.
        // The geometry is deterministic, so a signature ends the loop after
        // one extra pass.
        const sig = JSON.stringify(kept);
        if (sig !== this._doorSig) {
            this._doorSig = sig;
            this.state.doors = kept;
        }
    }

    /** One Chart.js element as a box in the canvas wrapper's own pixels.
     *  A line chart has points rather than bars, so a point becomes a small
     *  square around itself. */
    barBox(el) {
        if (!el || !isFinite(el.x) || !isFinite(el.y)) { return null; }
        const hasBase = isFinite(el.base);
        const w = isFinite(el.width) && el.width > 0 ? el.width : 24;
        const top = hasBase ? Math.min(el.y, el.base) : el.y - 12;
        const h = hasBase ? Math.max(Math.abs(el.base - el.y), 8) : 24;
        return {
            x: Math.round(el.x - w / 2), y: Math.round(top),
            w: Math.round(w), h: Math.round(h),
        };
    }

    /** The offset of the chart wrapper inside the result panel, so a box
     *  measured on the canvas can be drawn over the panel. */
    _wrapOffset() {
        const wrap = this.canvasRef.el ? this.canvasRef.el.parentElement : null;
        return wrap ? { x: wrap.offsetLeft, y: wrap.offsetTop } : { x: 0, y: 0 };
    }

    doorBox(door) {
        const off = this._wrapOffset();
        return { x: door.x + off.x, y: door.y + off.y, w: door.w, h: door.h };
    }

    /** Any clicked element — a slice, a legend row, a table row — as a box
     *  in the result panel's own pixels. */
    eventBox(ev) {
        const viz = this.vizRef.el;
        let el = ev && ev.currentTarget;
        if (!viz || !el || !el.getBoundingClientRect) { return null; }
        // A table's door is a small round button, but what the reader is
        // walking into is the whole row, so the descent starts from the row.
        el = (el.closest && el.closest("tr")) || el;
        const a = el.getBoundingClientRect();
        const b = viz.getBoundingClientRect();
        if (!a.width || !a.height) { return null; }
        return { x: a.left - b.left, y: a.top - b.top, w: a.width, h: a.height };
    }

    onDoorClick(door) {
        this.stepDown(door.key, door.label, this.doorBox(door));
    }

    /**
     * WHICH bar the pointer is actually on.
     *
     * The chart reads its own hover in "index" mode, which is right for the
     * tooltip — a month should list every team at once — but it hands back
     * one element per SERIES at that month, in series order. Taking the first
     * of them means the cue names the first team on the chart wherever the
     * pointer is, and the click that follows opens that team rather than the
     * bar under the finger. So the element is picked by asking each one
     * whether the point is inside it. Between two bars nothing is inside
     * anything: strictly, that is no cue at all; for a click, the chart's own
     * first answer stands, exactly as it always has.
     */
    _pickElement(evt, els, strict) {
        if (!els || !els.length) { return null; }
        const x = evt ? evt.x : null, y = evt ? evt.y : null;
        if (isFinite(x) && isFinite(y)) {
            const hit = els.find((e) => e.element && e.element.inRange
                                        && e.element.inRange(x, y, true));
            if (hit) { return hit; }
        }
        return strict ? null : els[0];
    }

    /** Chart.js tells us what the pointer is over; we turn that into the cue
     *  and the pointer shape, and remember the bar so a click can descend
     *  from exactly where it was pressed. */
    onChartHover(evt, els) {
        const canvas = this.canvasRef.el;
        const part = this.activePart;
        const pick = part ? this._pickElement(evt, els, true) : null;
        const ser = pick ? part.series[pick.datasetIndex] : null;
        if (!ser || !this.nextRungLabel || ser.key === "" || ser.key === "_all") {
            if (canvas) { canvas.style.cursor = ser ? "pointer" : ""; }
            this._hoverBox = null;
            this.clearPeek();
            return;
        }
        if (canvas) { canvas.style.cursor = "zoom-in"; }
        this._hoverBox = this.barBox(pick.element);
        this.setPeek(ser.key, ser.label);
    }

    /** True when this machine has asked for calm. It then gets the finished
     *  chart on the first frame and no overlay at all. */
    get calm() {
        return !!(window.matchMedia
            && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    }

    /**
     * The descent. The bar that was pressed grows out into the board and
     * fades, and the chart that replaces it settles in from just below —
     * so the walk reads as going INTO something rather than as the board
     * being swapped out from under the reader.
     */
    descendFrom(box) {
        clearTimeout(this._descentT);
        clearTimeout(this._arriveT);
        this.state.arrived = false;
        if (this.calm || !box || !box.w || !box.h) {
            if (this.state.descent) { this.state.descent = null; }
            return;
        }
        const viz = this.vizRef.el;
        const rect = viz ? viz.getBoundingClientRect() : null;
        const cap = (v) => Math.max(1.2, Math.min(8, v || 1));
        this.state.descent = {
            ...box,
            sx: rect ? cap(rect.width / box.w) : 4,
            sy: rect ? cap(rect.height / box.h) : 3,
        };
        this._descentT = setTimeout(() => {
            this.state.descent = null;
            this.state.arrived = true;
            this._arriveT = setTimeout(() => {
                this.state.arrived = false;
            }, ARRIVE_MS);
        }, DESCENT_MS);
    }

    get descentStyle() {
        const d = this.state.descent;
        if (!d) { return ""; }
        return `left:${d.x}px;top:${d.y}px;width:${d.w}px;height:${d.h}px;`
            + `--pbex-sx:${d.sx.toFixed(2)};--pbex-sy:${d.sy.toFixed(2)}`;
    }

    doorStyle(door) {
        return `left:${door.x}px;top:${door.y}px;`
            + `width:${door.w}px;height:${door.h}px`;
    }

    /** A crumb is a way BACK: everything after it is dropped, filters too. */
    goToCrumb(index) {
        const path = (this.state.spec.path || []).slice(0, index + 1);
        const dropped = (this.state.spec.path || []).slice(index + 1);
        const filters = { ...this.state.spec.filters };
        for (const step of dropped) {
            delete filters[step.level];
        }
        const level = index < 0 ? (this.trail.root || "")
            : path[path.length - 1].level;
        this.state.spec.path = path;
        this.state.spec.filters = filters;
        const next = this.nextLevelAfter(level);
        if (next) { this.state.spec.dimension = next; }
        this.destroyChart();
        this.run();
    }

    onKeydown(ev) {
        // The month strip owns its own arrows and its own Escape while the
        // keyboard is standing in it, so the ladder below never sees them.
        const inStrip = ev.target?.closest
            && ev.target.closest(".pbex-when-strip");
        /**
         * ESCAPE MEANS "THE LAST THING I OPENED", never "everything".
         *
         * A gesture in flight is the FIRST rung: a hand still on the strip is
         * the most recent thing the reader started (L5). Then the open picker,
         * then the drill, then the period itself — and only when one of those
         * is actually there, so every other Escape on the page still gets its
         * turn.
         */
        if (ev.key === "Escape") {
            if (this.drag) {
                this.drag = null;
                this.state.preview = [];
                ev.stopPropagation();
                return;
            }
            if (this.state.openPicker) {
                this.state.openPicker = "";
                this.state.filterKey = "";
                ev.stopPropagation();
                return;
            }
            if (this.state.drill) {
                this.closeDrill();
                ev.stopPropagation();
                return;
            }
            if (this.hasPeriod) {
                ev.stopPropagation();
                this.clearPeriod();
            }
            return;
        }
        // ← walks back up the group, the way a file browser does.
        if (ev.key === "ArrowLeft" && !inStrip && !ev.metaKey && !ev.ctrlKey
            && !/^(INPUT|TEXTAREA|SELECT)$/.test(ev.target?.tagName || "")) {
            const path = this.state.spec.path || [];
            if (path.length) {
                ev.preventDefault();
                this.goToCrumb(path.length - 2);
            }
        }
    }

    /* THE FOUR SENTENCES THIS CLAUSE OWNS, each built as ONE string here and
     * printed with a single `t-esc`. A sentence written either side of a
     * `<t t-esc/>` comes out of the extractor as TWO msgids no translator can
     * put into their own word order (L17), and the whitespace an XML file
     * indents with is baked into whatever it does collect. Every one of them
     * also branches on the singular rather than bracketing the plural, which
     * is how a screen announces it was written by a programme rather than by
     * a person (R46). The forbidden shape is deliberately NOT spelled out
     * here: the test that hunts for it reads this file, and a grep that fails
     * for saying what it is looking for is WF13, hit for the second time in
     * this phase. */

    /** "3 pay periods are still being prepared" is a different sentence when
     *  a period is on screen: those three are the three INSIDE it, because the
     *  runs were scoped by the same two dates every other figure was. */
    get pendingLine() {
        const n = (this.state.data?.pending || []).length;
        const names = this.pendingNames;
        if (this.hasPeriod) {
            return n === 1
                ? _t("1 pay period inside %(period)s is still being prepared and is not included in these figures: %(names)s. Refresh in a moment.",
                     { period: this.periodMeta.label, names })
                : _t("%(count)s pay periods inside %(period)s are still being prepared and are not included in these figures: %(names)s. Refresh in a moment.",
                     { count: n, period: this.periodMeta.label, names });
        }
        return n === 1
            ? _t("1 pay period is still being prepared and is not included in these figures: %s. Refresh in a moment.", names)
            : _t("%(count)s pay periods are still being prepared and are not included in these figures: %(names)s. Refresh in a moment.",
                 { count: n, names });
    }

    /** "NET PAY BY MONTH" — the strip says which question it is a shape of. */
    get stripHeading() {
        return _t("%s by month",
                  this.state.data ? this.state.data.measure_label : "");
    }

    get whenHint() {
        return _t("Press a month, shift-press another, or drag across them. Arrow keys walk the strip; Escape goes back to Everything.");
    }

    get whenEmptyLine() {
        return _t("No pay periods have been built yet, so there are no months to choose from. The starting points above will start answering as soon as a pay run is done.");
    }

    /** The same, for runs that are built but not yet approved. */
    get provisionalLine() {
        const c = this.state.data?.coverage || {};
        const n = c.provisional_runs || 0;
        if (this.hasPeriod) {
            return n === 1
                ? _t("1 of the %(total)s pay periods in %(period)s is still in progress — its figures are provisional and may change on approval.",
                     { total: c.runs, period: this.periodMeta.label })
                : _t("%(count)s of the %(total)s pay periods in %(period)s are still in progress — their figures are provisional and may change on approval.",
                     { count: n, total: c.runs, period: this.periodMeta.label });
        }
        return n === 1
            ? _t("1 of %(total)s pay periods is still in progress — its figures are provisional and may change on approval.",
                 { total: c.runs })
            : _t("%(count)s of %(total)s pay periods are still in progress — their figures are provisional and may change on approval.",
                 { count: n, total: c.runs });
    }

    /** The empty state's next step. Now that there IS a period control, the
     *  sentence points AT it rather than at a control that did not exist. */
    get emptyHint() {
        if (this.hasPeriod) {
            return this.state.spec.advances === "main"
                ? _t("Nothing was paid in %s that matches. Widen the When clause above, drop a filter, or include mid-month advances.", this.periodMeta.label)
                : _t("Nothing was paid in %s that matches. Widen the When clause above, or drop a filter.", this.periodMeta.label);
        }
        return this.state.spec.advances === "main"
            ? _t("Try widening the filters, picking a period in the When clause above, or including mid-month advances.")
            : _t("Try widening the filters, or picking a period in the When clause above.");
    }

    // ------------------------------------------------------------- money
    /**
     * NOT `money`. This component already has a `money(value)` FORMATTER, and
     * a class may not hold a getter and a method of the same name — the later
     * definition simply wins, silently. It cost a browser walk: every rate
     * badge was missing because `this.money?.rates` was reading a property off
     * the formatter function. One name, one meaning.
     */
    get moneyMeta() { return this.state.data?.money || null; }

    get shownCurrency() {
        return this.activePart?.currency || this.moneyMeta?.target || null;
    }

    get parts() { return this.state.data?.parts || []; }

    get activePart() {
        const parts = this.parts;
        if (!parts.length) { return this.state.data; }
        return parts[Math.min(this.state.part, parts.length - 1)];
    }

    get isMixed() { return !!this.state.data?.mixed; }

    /** The switch appears only when there is genuinely a choice to make. */
    get showCurrencySwitch() {
        if (this.state.data?.measure_kind === "count") { return false; }
        const known = this.state.schema?.money || {};
        return !!(known.many || this.isMixed || this.state.data?.converted);
    }

    get currencyTitle() {
        const cur = this.shownCurrency;
        const money = this.state.schema?.money || {};
        if (!cur) { return _t("Every figure in the money it was paid in."); }
        if (this.state.spec.currency === "own") {
            return _t("Every figure in the money it was paid in.");
        }
        return money.policy
            ? _t("Shown in %(currency)s, converted using %(policy)s.",
                 { currency: cur.name, policy: money.policy.toLowerCase() })
            : _t("Shown in %s.", cur.name);
    }

    get rates() { return this.moneyMeta?.rates || []; }

    get unconverted() { return this.moneyMeta?.unconverted || []; }

    /** Just the number: "17,450". */
    rateValue(rate) {
        return new Intl.NumberFormat(undefined,
            { maximumFractionDigits: rate.rate >= 100 ? 0 : 4 }).format(rate.rate);
    }

    /** "1 SGD = 20,000 VND · 2026-08-31".
     *
     *  Built in ONE string rather than from four template nodes: the spaces
     *  between adjacent `t-esc` nodes are whitespace the browser is free to
     *  collapse, and the first browser walk read back "20,000VND· 2026-08-31".
     */
    rateSentence(rate) {
        const base = `1 ${rate.src} = ${this.rateValue(rate)} ${rate.dst}`;
        return rate.rate_date ? `${base} · ${rate.rate_date}` : base;
    }

    /** "at 17,450 · 31 Aug" — the whole of a rate badge. */
    rateChip(rate) {
        const value = this.rateValue(rate);
        return rate.rate_date ? `${value} · ${rate.rate_date}` : value;
    }

    setCurrencyMode(mode) {
        if (this.state.spec.currency === mode) { return; }
        this.state.spec.currency = mode;
        this.state.part = 0;
        this.destroyChart();
        this.run();
    }

    showPart(index) {
        if (this.state.part === index) { return; }
        this.state.part = index;
        this.destroyChart();
    }

    toggleRates() { this.state.showRates = !this.state.showRates; }

    openRates() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Exchange rates"),
            res_model: "res.currency.rate",
            views: [[false, "list"], [false, "form"]],
        }).catch((e) => this.notif.add(this._msg(e), { type: "danger" }));
    }

    // ------------------------------------------------- runs, people, ratio
    toggleAdvances() {
        this.state.spec.advances =
            this.state.spec.advances === "main" ? "all" : "main";
        this.destroyChart();
        this.run();
    }

    togglePerHead() {
        this.state.spec.per_head = !this.state.spec.per_head;
        this.destroyChart();
        this.run();
    }

    get heads() { return this.state.data?.heads || { people: 0, fte: 0 }; }

    get isCompare() { return this.state.spec.chart === "compare"; }

    /** A row's shape over time, in 68x18 px. Points only — the reader is
     *  comparing directions, not reading values off it. */
    sparkline(values) {
        const nums = (values || []).map((v) => Number(v || 0));
        if (nums.length < 2) { return ""; }
        const min = Math.min(...nums);
        const max = Math.max(...nums);
        const span = max - min || 1;
        const step = 68 / (nums.length - 1);
        return nums.map((v, i) =>
            `${(i * step).toFixed(1)},${(16 - ((v - min) / span) * 14).toFixed(1)}`
        ).join(" ");
    }

    // ----------------------------------------------------------- chip edits
    pick(kind, value) {
        this.state.openPicker = "";
        // Re-picking the current value must be a no-op. Falling through would
        // tear the chart down without OWL re-rendering (the state is
        // unchanged), so onPatched never fires and the board goes blank.
        if (this.state.spec[kind] === value) { return; }
        this.state.spec[kind] = value;
        // A chart form is a presentation choice, not a new question. syncChart
        // keys its signature on spec.chart, so it rebuilds on its own — no
        // manual destroy, which would race the re-render.
        if (kind === "chart") { return; }
        this.run();
    }

    togglePicker(name) {
        this.state.openPicker = this.state.openPicker === name ? "" : name;
    }

    addFilter(key, value) {
        const f = { ...this.state.spec.filters };
        const list = [...(f[key] || [])];
        if (!list.some((v) => String(v) === String(value))) {
            list.push(value);
        }
        f[key] = list;
        this.state.spec.filters = f;
        this.state.openPicker = "";
        this.state.filterKey = "";
        this.run();
    }

    dropFilter(key, value) {
        const f = { ...this.state.spec.filters };
        f[key] = (f[key] || []).filter((v) => String(v) !== String(value));
        if (!f[key].length) { delete f[key]; }
        this.state.spec.filters = f;
        this.run();
    }

    clearFilters() {
        this.state.spec.filters = {};
        this.run();
    }

    get activeFilters() {
        const out = [];
        const opts = this.state.schema?.options || {};
        for (const [key, vals] of Object.entries(this.state.spec.filters || {})) {
            for (const v of vals) {
                const found = (opts[key] || []).find(
                    (o) => String(o.value) === String(v));
                out.push({
                    key,
                    value: v,
                    keyLabel: FILTER_META[key] || key,
                    label: found ? found.label : String(v),
                });
            }
        }
        return out;
    }

    get filterFields() {
        const opts = this.state.schema?.options || {};
        return Object.keys(FILTER_META).filter((k) => (opts[k] || []).length);
    }

    labelOf(list, value) {
        const hit = (this.state.schema?.[list] || []).find(
            (o) => o.value === value);
        return hit ? hit.label : value;
    }

    // ------------------------------------------------------------ formatting
    money(v, short = false) {
        const n = Number(v || 0);
        if (this.state.data?.measure_kind === "count") {
            return new Intl.NumberFormat().format(Math.round(n));
        }
        const abs = Math.abs(n);
        if (short || abs >= 1e6) {
            for (const [div, suf] of [[1e12, "T"], [1e9, "B"], [1e6, "M"], [1e3, "K"]]) {
                if (abs >= div) {
                    return (n / div).toFixed(abs / div >= 100 ? 0 : 1) + suf;
                }
            }
        }
        return new Intl.NumberFormat(undefined,
            { maximumFractionDigits: abs >= 100 ? 0 : 2 }).format(n);
    }

    colourAt(i) { return colourAt(i); }

    // ---------------------------------------------------------------- charts
    get isCanvasChart() {
        return ["column", "stacked", "line"].includes(this.state.spec.chart);
    }

    get donut() {
        const d = this.activePart;
        if (!d) { return { arcs: [], total: 0, dropped: 0 }; }
        return donutArcs(d.series, { size: 240, thickness: 36 });
    }

    get heatmap() {
        const d = this.activePart;
        if (!d) { return { rows: [] }; }
        return heatmapCells(d.series, d.categories);
    }

    /** The money on screen, with its own symbol on it. */
    moneyWithSymbol(value) {
        const text = this.money(value);
        const cur = this.shownCurrency;
        if (!cur || this.state.data?.measure_kind === "count") { return text; }
        return cur.position === "before"
            ? `${cur.symbol}${text}` : `${text}${cur.symbol ? " " + cur.symbol : ""}`;
    }

    syncChart() {
        if (!this.isCanvasChart || this.isCompare || !this.activePart) {
            this.destroyChart();
            this.syncDoors();
            return;
        }
        const canvas = this.canvasRef.el;
        if (!canvas || !window.Chart) { return; }
        // Rebuilding a Chart.js instance on every patch thrashes; only redraw
        // when the payload, the form, or the canvas NODE actually changed.
        // The node matters: OWL replaces the <canvas> when the chart-form
        // branch re-renders, and a signature-only check would then keep an
        // instance bound to a detached element while the visible canvas
        // stayed empty.
        const part = this.activePart;
        const sig = JSON.stringify([
            this.state.spec.chart, this.state.part,
            part.categories.map((c) => c.key),
            part.series.map((s) => [s.key, s.values]),
        ]);
        if (sig === this._chartSig && this._chart && this._canvasEl === canvas) {
            this.syncDoors();
            return;
        }
        this._chartSig = sig;
        this._canvasEl = canvas;
        this.destroyChart();
        // Any instance Chart.js still has registered against this exact node
        // (ours or a leftover) must go, or `new Chart()` throws "Canvas is
        // already in use".
        window.Chart.getChart?.(canvas)?.destroy();
        const cfg = chartConfig(this.state.spec.chart, part,
                                { money: (v, s) => this.money(v, s) });
        cfg.options.onClick = (evt, els) => {
            const el = this._pickElement(evt, els, false);
            if (!el) { return; }
            const s = part.series[el.datasetIndex];
            const c = part.categories[el.index];
            if (s && c) {
                this.onCellClick(s.key, c.key, s.label, c.label, null,
                                 this.barBox(el.element) || this._hoverBox);
            }
        };
        cfg.options.onHover = (evt, els) => this.onChartHover(evt, els);
        this._chart = new window.Chart(canvas, cfg);
        // Force final geometry synchronously — never depend on an animation
        // frame to make the bars visible.
        this._chart.update("none");
        this.syncDoors();
    }

    destroyChart() {
        if (this._chart) {
            this._chart.destroy();
            this._chart = null;
            this._chartSig = "";
            this._canvasEl = null;
        }
        this._hoverBox = null;
    }

    // ----------------------------------------------------------------- drill
    /**
     * One click, two honest meanings.
     *
     * While the reader is walking down the group, a bar is a PLACE — clicking
     * "Retail" goes into Retail. At the bottom of the walk, and whenever the
     * chart is showing something that is not a place (a component, a kind of
     * run), a bar is a NUMBER and clicking it shows the people inside it. The
     * headline's own "Who is in this number" button reaches the people at any
     * level, so neither meaning is ever a dead end.
     */
    onCellClick(seriesKey, categoryKey, seriesLabel, categoryLabel,
                ev = null, box = null) {
        // The test is the same one the cue uses. `canStepDown` alone was one
        // rung too generous: standing on a level whose every remaining rung
        // carries a single value, the click walked into `stepDown`, found no
        // destination and returned — a bar that looked clickable and did
        // nothing at all. If there is nowhere to go, the click shows the
        // people instead, which is never a dead end.
        if (this.nextRungLabel && seriesKey !== "" && seriesKey !== "_all") {
            this.stepDown(seriesKey, seriesLabel,
                          box || (ev ? this.eventBox(ev) : null));
            return;
        }
        this.openDrill(seriesKey, categoryKey, seriesLabel, categoryLabel);
    }

    async openDrill(seriesKey, categoryKey, seriesLabel, categoryLabel, page = 0) {
        this.state.drillBusy = true;
        this.state.drill = {
            seriesKey, categoryKey, seriesLabel, categoryLabel,
            rows: [], total: 0, page, loading: true,
        };
        try {
            const spec = JSON.parse(JSON.stringify(this.state.spec));
            const res = await this.orm.call(MODEL, "drill",
                [spec, seriesKey, categoryKey, page]);
            this.state.drill = {
                seriesKey, categoryKey, seriesLabel, categoryLabel,
                ...res, loading: false,
            };
        } catch (e) {
            this.state.drill = null;
            this.notif.add(this._msg(e), { type: "danger" });
        } finally {
            this.state.drillBusy = false;
        }
    }

    drillPage(delta) {
        const d = this.state.drill;
        if (!d) { return; }
        const next = Math.max(0, (d.page || 0) + delta);
        this.openDrill(d.seriesKey, d.categoryKey, d.seriesLabel,
                       d.categoryLabel, next);
    }

    closeDrill() { this.state.drill = null; }

    /** Computed here, not in the template: OWL resolves bare identifiers
     *  against the component, so `Math.min(...)` inline is not reliable. */
    get drillRange() {
        const d = this.state.drill;
        if (!d || !d.page_size) { return ""; }
        const first = d.page * d.page_size + 1;
        const last = Math.min((d.page + 1) * d.page_size, d.total);
        return `${first}–${last} of ${d.total}`;
    }

    // ---------------------------------------------------------------- export
    async exportCsv() {
        this.state.busy = true;
        try {
            const spec = JSON.parse(JSON.stringify(this.state.spec));
            const res = await this.orm.call(MODEL, "export_csv", [spec]);
            const a = document.createElement("a");
            a.href = "data:text/csv;base64," + res.csv_b64;
            a.download = res.filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            if (res.truncated) {
                this.notif.add(
                    _t("Exported %s rows. %s more were left out by the row cap.",
                       res.rows, res.truncated),
                    { type: "warning" });
            }
        } catch (e) {
            this.notif.add(this._msg(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // --------------------------------------------------------------- lenses
    get lenses() { return this.state.schema?.lenses || []; }

    /** Classic act_window destinations that are not expressible as a lens —
     *  carried here so retiring the Insights gallery loses nothing. */
    get classicReports() { return this.state.schema?.classic || []; }

    get activeLensName() {
        const l = this.lenses.find((x) => x.id === this.state.lensId);
        return l ? l.name : "";
    }

    toggleLenses() { this.state.lensesOpen = !this.state.lensesOpen; }

    openLens(lens) {
        this.state.spec = {
            // A starting point is a fresh question: it keeps the period and
            // the money settings the reader chose, and drops the breadcrumb
            // they walked, because the lens names its own level.
            advances: this.state.spec.advances,
            currency: this.state.spec.currency,
            target_currency: this.state.spec.target_currency,
            per_head: false,
            path: [],
            ...JSON.parse(JSON.stringify(lens.spec)),
            date_from: this.state.spec.date_from,
            date_to: this.state.spec.date_to,
        };
        this.state.lensId = lens.id;
        this.state.askWhy = null;
        this.state.lensesOpen = false;
        this.destroyChart();
        this.run();
    }

    openClassic(rep) {
        this.action.doAction(rep.xmlid).catch((e) => {
            this.notif.add(this._msg(e), { type: "danger" });
        });
    }

    // ------------------------------------------------------------- ask bar
    async submitAsk() {
        const text = (this.state.ask || "").trim();
        if (!text) { return; }
        this.state.asking = true;
        try {
            const res = await this.orm.call(MODEL, "ask", [text]);
            if (res.ok) {
                this.state.spec = { ...this.state.spec, ...res.spec };
                this.state.askWhy = { matched: res.matched || [], source: res.source };
                this.state.lensId = "";
                this.destroyChart();
                await this.run();
            } else {
                this.notif.add(res.error, { type: "warning" });
            }
        } catch (e) {
            this.notif.add(this._msg(e), { type: "danger" });
        } finally {
            this.state.asking = false;
        }
    }

    onAskKey(ev) {
        if (ev.key === "Enter") { this.submitAsk(); }
    }

    clearAsk() {
        this.state.ask = "";
        this.state.askWhy = null;
    }

    // ----------------------------------------------------------- narrative
    async toggleStory() {
        this.state.showStory = !this.state.showStory;
        if (this.state.showStory && !this.state.story) {
            await this.loadStory();
        }
    }

    async loadStory() {
        this.state.storyBusy = true;
        try {
            const spec = JSON.parse(JSON.stringify(this.state.spec));
            this.state.story = await this.orm.call(MODEL, "narrate", [spec]);
        } catch (e) {
            this.notif.add(this._msg(e), { type: "danger" });
            this.state.story = null;
        } finally {
            this.state.storyBusy = false;
        }
    }

    get waterfall() {
        const w = this.state.story?.waterfall;
        if (!w) { return null; }
        return {
            ...w,
            bars: waterfallBars(w.start, w.steps, w.end, {
                height: 190,
                startLabel: w.from_label,
                endLabel: w.to_label,
            }),
        };
    }

    applyAnomalyLens(anomaly) {
        this.state.spec = {
            ...this.state.spec,
            ...JSON.parse(JSON.stringify(anomaly.lens)),
        };
        this.state.lensId = "";
        this.destroyChart();
        this.run();
    }

    // --------------------------------------------------------------- totals
    get grandTotal() { return this.activePart?.grand_total || 0; }

    get hasPending() { return (this.state.data?.pending || []).length > 0; }

    get pendingNames() {
        return (this.state.data?.pending || []).map((p) => p.name).join(", ");
    }
}

registry.category("actions").add("pb_explorer_cockpit", PbExplorer);
