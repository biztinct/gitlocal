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
         onPatched } from "@odoo/owl";
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
        });

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
            this.writeHash();
        } catch (e) {
            this.state.error = this._msg(e);
            this.state.data = null;
        } finally {
            this.state.busy = false;
        }
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
        // ← walks back up the group, the way a file browser does.
        if (ev.key === "ArrowLeft" && !ev.metaKey && !ev.ctrlKey
            && !/^(INPUT|TEXTAREA|SELECT)$/.test(ev.target?.tagName || "")) {
            const path = this.state.spec.path || [];
            if (path.length) {
                ev.preventDefault();
                this.goToCrumb(path.length - 2);
            }
        }
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
