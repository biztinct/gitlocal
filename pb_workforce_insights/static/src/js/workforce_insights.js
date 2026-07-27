/** @odoo-module **/
/**
 * Workforce Insights — the workforce analytics cockpit (Sudima Phase O).
 *
 * Replaces the demo-module placeholder that used to hold this sidebar slot:
 * nine CSS-div bars, no filters, no drill, and every query hard-filtered to
 * `is_demo = true` so it rendered empty on any real database.
 *
 * Charts reuse pb_explorer's geometry module — Chart.js from Odoo's own lazy
 * `web.chartjs_lib` bundle for the trends, bespoke SVG for the gauge. No CDN.
 */
import { Component, useState, useRef, onWillStart, onMounted, onPatched,
         onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_explorer/js/pbex_icons";
import { ensureChartJs, chartConfig, colourAt } from "@pb_explorer/js/pbex_charts";

const MODEL = "pb.workforce.insights";

export class PbWorkforceInsights extends Component {
    static template = "pb_workforce_insights.PbWorkforceInsights";
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.ic = ic;
        this.attRef = useRef("attChart");
        this.otRef = useRef("otChart");
        this.hcRef = useRef("hcChart");

        this.state = useState({
            loaded: false, busy: false, error: "",
            data: null,
            months: 3,
            division: null,
            departmentId: null,
            openPicker: "",
        });
        this._charts = {};

        onWillStart(async () => {
            await ensureChartJs().catch(() => null);
            await this.load();
            this.state.loaded = true;
        });
        // BOTH hooks: the payload is already loaded at first render, so
        // onPatched alone never fires for it and the canvases stay blank.
        onMounted(() => this.syncCharts());
        onPatched(() => this.syncCharts());
        onWillUnmount(() => this.destroyCharts());
    }

    async load() {
        this.state.busy = true;
        this.state.error = "";
        try {
            this.state.data = await this.orm.call(MODEL, "get_board", [
                this.state.months, this.state.division, this.state.departmentId,
            ]);
        } catch (e) {
            this.state.error = (e && (e.data?.message || e.message))
                || _t("Something went wrong.");
            this.state.data = null;
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------ filters
    setMonths(m) {
        if (this.state.months === m) { return; }
        this.state.months = m;
        this.load();
    }
    setFilter(kind, value) {
        const key = kind === "division" ? "division" : "departmentId";
        this.state[key] = this.state[key] === value ? null : value;
        this.state.openPicker = "";
        this.load();
    }
    togglePicker(name) {
        this.state.openPicker = this.state.openPicker === name ? "" : name;
    }
    clearFilters() {
        this.state.division = null;
        this.state.departmentId = null;
        this.load();
    }
    get hasFilters() { return !!(this.state.division || this.state.departmentId); }
    get divisionLabel() {
        const o = (this.d.options?.division || [])
            .find((x) => x.value === this.state.division);
        return o ? o.label : _t("All divisions");
    }
    get departmentLabel() {
        const o = (this.d.options?.department_id || [])
            .find((x) => x.value === this.state.departmentId);
        return o ? o.label : _t("All departments");
    }

    // ------------------------------------------------------------ getters
    get d() { return this.state.data || {}; }
    get headcount() { return this.d.headcount || {}; }
    get attendance() { return this.d.attendance; }
    get overtime() { return this.d.overtime; }
    get leave() { return this.d.leave; }
    get cost() { return this.d.cost || {}; }

    money(n, short = true) {
        const v = Number(n || 0);
        const cur = this.d.currency || "";
        const abs = Math.abs(v);
        if (short) {
            for (const [div, suf] of [[1e12, "T"], [1e9, "B"], [1e6, "M"], [1e3, "K"]]) {
                if (abs >= div) {
                    return cur + (v / div).toFixed(abs / div >= 100 ? 0 : 1) + suf;
                }
            }
        }
        return cur + new Intl.NumberFormat(undefined,
            { maximumFractionDigits: 0 }).format(v);
    }
    num(n) { return new Intl.NumberFormat().format(Math.round(Number(n || 0))); }
    hours(n) { return (Math.round(Number(n || 0) * 10) / 10) + "h"; }
    colourAt(i) { return colourAt(i); }

    /** Bar width % against the biggest row in a list. */
    bar(value, rows, key) {
        const max = Math.max(1, ...(rows || []).map((r) => r[key] || 0));
        return Math.max(2, Math.round((Number(value || 0) / max) * 100));
    }

    /**
     * Ceiling gauge — the average utilisation of the people who actually
     * worked overtime this month. Measuring against total headcount instead
     * would divide a handful of hours by the whole payroll and always read 0%.
     */
    get gauge() {
        const ot = this.overtime;
        if (!ot || !ot.cap || !ot.ot_employees) { return null; }
        const avg = (ot.month_hours || 0) / ot.ot_employees;
        const used = Math.min(1, avg / ot.cap);
        const r = 52, c = 2 * Math.PI * r;
        return { r, dash: `${(used * c).toFixed(1)} ${c.toFixed(1)}`,
                 pct: Math.round(used * 100),
                 avg: Math.round(avg * 10) / 10,
                 people: ot.ot_employees };
    }

    // ------------------------------------------------------------- charts
    syncCharts() {
        if (!this.state.data || !window.Chart) { return; }
        this._chart("hc", this.hcRef.el, () => {
            const s = this.headcount.series || [];
            if (!s.length) { return null; }
            return chartConfig("line", {
                categories: s.map((x) => ({ key: x.month, label: x.label })),
                series: [{ key: "hc", label: _t("Employees paid"),
                           values: s.map((x) => x.count) }],
            }, { money: (v) => this.num(v) });
        });
        this._chart("att", this.attRef.el, () => {
            const w = this.attendance?.weeks || [];
            if (!w.length) { return null; }
            return chartConfig("column", {
                categories: w.map((x) => ({ key: x.week, label: x.label })),
                series: [{ key: "exc", label: _t("Exceptions"),
                           values: w.map((x) => x.count) }],
            }, { money: (v) => this.num(v) });
        });
        this._chart("ot", this.otRef.el, () => {
            const w = this.overtime?.weeks || [];
            if (!w.length) { return null; }
            const series = [{ key: "ap", label: _t("Approved hours"),
                              values: w.map((x) => x.approved) }];
            if (this.overtime.has_bonus) {
                series.push({ key: "bo", label: _t("Bonus hours"),
                              values: w.map((x) => x.bonus) });
            }
            return chartConfig("stacked", {
                categories: w.map((x) => ({ key: x.week, label: x.label })),
                series,
            }, { money: (v) => this.hours(v) });
        });
    }

    _chart(key, canvas, build) {
        if (!canvas) { return; }
        const cfg = build();
        if (!cfg) { this._kill(key); return; }
        const sig = JSON.stringify(cfg.data);
        const held = this._charts[key];
        // Rebuild when the payload OR the canvas node changed — OWL replaces
        // the node on re-render, and a signature-only check would leave the
        // instance bound to a detached element while the visible one stays blank.
        if (held && held.sig === sig && held.el === canvas) { return; }
        this._kill(key);
        window.Chart.getChart?.(canvas)?.destroy();
        const chart = new window.Chart(canvas, cfg);
        chart.update("none");        // never depend on an animation frame
        this._charts[key] = { chart, sig, el: canvas };
    }

    _kill(key) {
        if (this._charts[key]) {
            this._charts[key].chart.destroy();
            delete this._charts[key];
        }
    }
    destroyCharts() { Object.keys(this._charts).forEach((k) => this._kill(k)); }

    // ------------------------------------------------------------- drills
    _openEmployees(ids, title) {
        if (!ids || !ids.length) { return; }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: title,
            res_model: "hr.employee",
            domain: [["id", "in", ids]],
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }
    openMovement(which) {
        const m = this.headcount.movement || {};
        const ids = which === "joiners" ? m.joiner_ids : m.leaver_ids;
        this._openEmployees(ids, which === "joiners" ? _t("Joiners") : _t("Leavers"));
    }
    openExceptionKind(row) {
        this._openEmployees(row.employee_ids, row.label);
    }
    openNearCeiling() {
        this._openEmployees(this.overtime?.near_cap_ids, _t("Near the overtime ceiling"));
    }
    openOutToday() {
        this._openEmployees(this.leave?.out_today_ids, _t("Away today"));
    }
    /** Cost rows hand the Explorer the same question, so the numbers agree. */
    openCostRow(row) {
        if (!row || !row.drillable) { return; }
        this.action.doAction("pb_explorer.action_pb_explorer", {
            additionalContext: { pbex_spec: {
                measure: "cost_per_head", dimension: "department_id",
                grain: "month", chart: "line",
                filters: { department_id: [row.id] },
            } },
        }).catch(() => {
            this.notif.add(_t("The Analytics Explorer is not available."),
                           { type: "warning" });
        });
    }
}

registry.category("actions").add("pb_workforce_insights", PbWorkforceInsights);
