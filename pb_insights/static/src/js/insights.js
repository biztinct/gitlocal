/** @odoo-module **/
/**
 * Insights — the executive Analytics cockpit (Sudima Phase M).
 *
 * One briefing-style board: hero band (animated NET headline + delta + 12-run
 * sparkline), the cost story (per-run layered columns with a hover readout),
 * a department leaderboard + statutory donut, the workforce pulse row, the
 * read-only payroll.analytics snapshots and the report gallery that replaced
 * the retired pb_hr_payroll_analytics menu forest.
 *
 * RPC facade: pb.insights (read-only). All charts are bespoke SVG / CSS
 * geometry — no external library, no CDN asset anywhere (test 9).
 */
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_insights/js/pbin_icons";

const MODEL = "pb.insights";
const DRAW_MS = 380;      // bar / spark draw-in (design spec: <= 400ms)
const COUNT_MS = 650;     // headline count-up

export class PbInsights extends Component {
    static template = "pb_insights.PbInsights";
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.ic = ic;
        this.state = useState({
            loaded: false,
            busy: false,
            error: "",
            data: null,
            months: 6,
            deptMode: "total",   // "total" | "perhead"
            hover: -1,           // hovered trend column
            heroNet: 0,
            drawn: false,
        });
        this._raf = null;
        this._timer = null;
        onWillStart(async () => { await this.load(); });
        onMounted(() => {
            // draw-in on the next frame so the transition actually runs
            this._timer = setTimeout(() => { this.state.drawn = true; }, 30);
            this._countUp(this.hero.net || 0);
        });
        onWillUnmount(() => {
            if (this._raf) { cancelAnimationFrame(this._raf); }
            if (this._timer) { clearTimeout(this._timer); }
        });
    }

    async load() {
        this.state.busy = true;
        try {
            this.state.data = await this.orm.call(MODEL, "get_insights", [this.state.months]);
            this.state.error = "";
        } catch (e) {
            this.state.error = (e && e.data && e.data.message) || (e && e.message)
                || _t("Insights could not be loaded.");
        } finally {
            this.state.loaded = true;
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------- getters
    // Every getter fills its own defaults: a section whose server-side collector
    // degraded returns {} rather than the full shape, and the board must still
    // render (soft-dep doctrine, safety rail 3).
    get d() { return this.state.data || {}; }
    get hero() {
        const h = this.d.hero || {};
        return Object.assign({ spark: [], headcount: 0, net: 0 }, h);
    }
    get trend() {
        const t = this.d.trend || {};
        return Object.assign(
            { points: [], max: 1, hidden: 0, scanned: 0, totals: { runs: 0 } }, t);
    }
    get points() { return this.trend.points || []; }
    get departments() {
        const dep = this.d.departments || {};
        return Object.assign({ rows: [], max: 1, max_head: 1, hidden: 0 }, dep);
    }
    get statutory() {
        const s = this.d.statutory || {};
        return Object.assign({ rows: [], employee: 0, employer: 0, total: 0 }, s);
    }
    get pulse() { return this.d.pulse || {}; }
    get snapshots() { return this.d.snapshots || []; }
    get reports() { return this.d.reports || []; }
    get timings() { return this.d.timings || {}; }

    /** The run shown in the cost-story readout: hovered, else the newest. */
    get readout() {
        const pts = this.points;
        if (!pts.length) { return null; }
        const idx = this.state.hover >= 0 && this.state.hover < pts.length
            ? this.state.hover : pts.length - 1;
        return pts[idx];
    }

    get deltaUp() { return (this.hero.delta_pct || 0) >= 0; }
    get hasDelta() { return this.hero.delta_pct !== null && this.hero.delta_pct !== undefined; }
    get deltaTitle() { return _t("Month over month, all pay runs in the month"); }

    // ------------------------------------------------------------ format
    money(n) {
        const cur = this.d.currency || "₫";
        const v = Number(n || 0);
        const a = Math.abs(v);
        const sign = v < 0 ? "-" : "";
        if (a >= 1e9) { return `${sign}${cur}${(a / 1e9).toFixed(2)}B`; }
        if (a >= 1e6) { return `${sign}${cur}${(a / 1e6).toFixed(1)}M`; }
        if (a >= 1e3) { return `${sign}${cur}${(a / 1e3).toFixed(0)}K`; }
        return `${sign}${cur}${Math.round(a)}`;
    }
    num(n) { return new Intl.NumberFormat().format(Math.round(Number(n || 0))); }
    hours(n) {
        const v = Number(n || 0);
        return (Number.isInteger(v) ? v : v.toFixed(1)) + "h";
    }
    pct(n, max) {
        const p = (Number(n || 0) / (Number(max) || 1)) * 100;
        return Math.max(0, Math.min(100, Math.round(p * 10) / 10));
    }
    /** Bar size honours the draw-in: 0 until mounted, then the real value. */
    bar(n, max) { return this.state.drawn ? this.pct(n, max) : 0; }

    dateShort(iso) {
        if (!iso) { return ""; }
        const parts = String(iso).split("-");
        return parts.length === 3 ? `${parts[2]}/${parts[1]}` : String(iso);
    }
    monthShort(iso) {
        if (!iso) { return ""; }
        const dt = new Date(`${iso}T00:00:00`);
        return Number.isNaN(dt.getTime())
            ? "" : dt.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
    }

    // ------------------------------------------------------------- labels
    // Sentences that interleave text and values are built HERE, not in the
    // template: a mixed QWeb text node splits into fragment msgids that are
    // painful to translate reliably, while a _t() call has one stable msgid
    // (and the vi.po test asserts these actually load — C18.74).
    get latestRunLabel() { return _t("· latest run %s", this.hero.run_name); }
    get paidLabel() { return _t("%s employees paid", this.num(this.hero.employees_paid)); }
    get vsLabel() {
        const h = this.hero;
        return _t("%s %s vs %s %s",
                  this.monthShort(h.month), this.money(h.month_net),
                  this.monthShort(h.prev_month), this.money(h.prev_month_net));
    }
    /** Axis label: print the month only where it CHANGES — 18 columns that all
     *  read "30/06" is noise, and the run name is in the readout on hover. */
    colLabel(index) {
        const pts = this.points;
        const cur = this.monthShort(pts[index] && pts[index].date);
        const prev = index > 0 ? this.monthShort(pts[index - 1].date) : null;
        return cur === prev ? "" : cur;
    }
    get sparkLabel() { return _t("%s-run trend", (this.hero.spark || []).length); }
    get trendHint() {
        return _t("%s runs · net and gross per pay run", this.trend.totals.runs || 0);
    }
    get trendCapLabel() {
        // never a silent top-N: say what is off the chart
        return _t("newest %s of %s runs in this window",
                  this.trend.totals.runs || 0, this.trend.scanned || 0);
    }
    get readoutMeta() {
        const r = this.readout || {};
        return _t("%s slips · %s", this.num(r.count), r.date || "");
    }
    get deptHint() {
        return this.departments.approx
            ? _t("Approximated from running contracts — no approved run yet")
            : _t("Net paid · %s", this.departments.run_name || "");
    }
    get deptMoreLabel() {
        return _t("+%s more departments", this.departments.hidden || 0);
    }
    get statutoryHint() { return this.statutory.run_name || _t("No run yet"); }
    excLabel(kind) {
        const n = ((this.pulse.attendance || {}).kinds || {})[kind] || 0;
        switch (kind) {
            case "missing_punch": return _t("%s missing punch", n);
            case "late": return _t("%s late", n);
            case "early_leave": return _t("%s early leave", n);
            default: return _t("%s open punch", n);
        }
    }
    get excWeekLabel() {
        return _t("week of %s", (this.pulse.attendance || {}).date_from || "");
    }
    get leaveLabel() {
        return _t("out today · %s awaiting approval", (this.pulse.leave || {}).pending || 0);
    }
    // the type label itself comes from the server (already translated there)
    otTypeLabel(row) { return `${this.hours(row.hours)} ${row.label}`; }
    get otCeilingLabel() {
        const ot = this.pulse.ot || {};
        return _t("%s employee(s) at 90%% of the %s monthly ceiling",
                  ot.near_cap || 0, this.hours(ot.cap));
    }
    get bonusLabel() {
        return _t("over the ceiling on %s request(s)", (this.pulse.bonus || {}).requests || 0);
    }
    snapEmployeesLabel(snap) { return _t("%s employees", this.num(snap.employees)); }
    snapAlertsLabel(snap) { return _t("%s alert(s)", snap.anomalies); }
    get footLabel() {
        const companies = this.d.companies || [];
        return companies.length > 1
            ? _t("Board built in %s ms · %s companies", this.timings.total, companies.length)
            : _t("Board built in %s ms", this.timings.total);
    }

    // ------------------------------------------------------------- charts
    /** Area + line path for the hero sparkline (viewBox 0 0 100 34). */
    get spark() {
        const pts = (this.hero.spark || []).map((p) => Number(p.net || 0));
        if (pts.length < 2) { return { line: "", area: "", dots: [] }; }
        const max = Math.max(...pts, 1);
        const min = Math.min(...pts, 0);
        const span = max - min || 1;
        const step = 100 / (pts.length - 1);
        const xy = pts.map((v, i) => [
            +(i * step).toFixed(2),
            +(32 - ((v - min) / span) * 28).toFixed(2),
        ]);
        const line = xy.map(([x, y], i) => `${i ? "L" : "M"}${x} ${y}`).join(" ");
        const area = `${line} L100 34 L0 34 Z`;
        return { line, area, dots: xy.map(([x, y]) => ({ x, y })) };
    }

    /** Donut geometry for the statutory split (r=54 in a 140x140 box). */
    get donut() {
        const s = this.statutory;
        const emp = Math.abs(Number(s.employee || 0));
        const er = Math.abs(Number(s.employer || 0));
        const total = emp + er;
        const r = 54;
        const c = 2 * Math.PI * r;
        const empLen = total ? (c * emp) / total : 0;
        const drawn = this.state.drawn;
        return {
            r, c, total,
            empDash: `${drawn ? empLen : 0} ${c}`,
            erDash: `${drawn ? c - empLen : 0} ${c}`,
            erOffset: -(drawn ? empLen : 0),
            empPct: total ? Math.round((emp / total) * 100) : 0,
            erPct: total ? Math.round((er / total) * 100) : 0,
        };
    }

    deptValue(row) {
        return this.state.deptMode === "perhead" ? row.per_head : row.net;
    }
    deptMax() {
        return this.state.deptMode === "perhead"
            ? this.departments.max_head : this.departments.max;
    }
    setDeptMode(mode) { this.state.deptMode = mode; }

    // -------------------------------------------------------- interaction
    async setMonths(m) {
        if (m === this.state.months) { return; }
        this.state.months = m;
        this.state.hover = -1;
        await this.load();
    }
    hoverPoint(i) { this.state.hover = i; }
    clearHover() { this.state.hover = -1; }

    async refresh() {
        this.state.drawn = false;
        await this.load();
        this.state.drawn = true;
        this._countUp(this.hero.net || 0);
    }

    _countUp(target) {
        if (this._raf) { cancelAnimationFrame(this._raf); }
        const reduce = window.matchMedia
            && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        if (reduce || !target) { this.state.heroNet = target; return; }
        const t0 = performance.now();
        const step = (now) => {
            const k = Math.min(1, (now - t0) / COUNT_MS);
            this.state.heroNet = target * (1 - Math.pow(1 - k, 3));
            this._raf = k < 1 ? requestAnimationFrame(step) : null;
        };
        this._raf = requestAnimationFrame(step);
    }

    // ------------------------------------------------------------ actions
    /**
     * Open a gallery card. Lens cards carry a `lens` id and land in the
     * Analytics Explorer already pointed at that question; classic cards are
     * plain act_windows.
     */
    openReport(rep) {
        const xmlid = typeof rep === "string" ? rep : rep.xmlid;
        const opts = { clearBreadcrumbs: true };
        if (rep && rep.lens) {
            opts.additionalContext = { pbex_lens: rep.lens };
        }
        this.action.doAction(xmlid, opts).catch((e) => {
            this.notif.add(
                (e && e.data && e.data.message) || _t("That report is not available."),
                { type: "danger" });
        });
    }
    openRun(runId) {
        if (!runId) { return; }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Pay Run"),
            res_model: "hr.payslip.run",
            res_id: runId,
            views: [[false, "form"]],
            target: "current",
        });
    }
    openSnapshot(snapId) {
        if (!snapId) { return; }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Payroll Analytics"),
            res_model: "payroll.analytics",
            res_id: snapId,
            views: [[false, "form"]],
            target: "current",
        });
    }
    openDepartment(row) {
        if (!row || !row.id) { return; }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: row.name,
            res_model: "hr.employee",
            domain: [["department_id", "=", row.id]],
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }
}

PbInsights.DRAW_MS = DRAW_MS;

registry.category("actions").add("pb_insights", PbInsights);
