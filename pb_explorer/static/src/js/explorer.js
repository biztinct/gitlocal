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
};

const FILTER_META = {
    department_id: _t("Department"),
    division:      _t("Division"),
    category_type: _t("Component type"),
    code:          _t("Component"),
    cycle:         _t("Cycle"),
    basis:         _t("Basis"),
};

export class PbExplorer extends Component {
    static template = "pb_explorer.PbExplorer";
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.ic = ic;
        this.chartMeta = CHART_META;
        this.filterMeta = FILTER_META;
        this.canvasRef = useRef("canvas");

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
            },
            openPicker: "",     // which chip dropdown is open
            filterKey: "",      // which filter is being added
            drill: null,
            drillBusy: false,
            hover: null,
            lensId: "",         // the active shipped lens, if any
            ask: "",            // the natural-language box
            asking: false,
            askWhy: null,       // the chips the parser chose — shown, never hidden
            story: null,        // narrate() payload
            storyBusy: false,
            showStory: false,
        });

        this._chart = null;
        this._chartSig = "";

        onWillStart(async () => {
            await ensureChartJs().catch(() => null);
            await this.loadSchema();
            // A gallery card in the Insights cockpit lands here already
            // pointed at its question (context pbex_lens), but the spec stays
            // fully editable — the chips show exactly what it chose.
            const wanted = this.props.action?.context?.pbex_lens;
            const lens = wanted && (this.state.schema?.lenses || [])
                .find((x) => x.id === wanted);
            if (lens) {
                this.state.spec = { ...this.state.spec,
                                    ...JSON.parse(JSON.stringify(lens.spec)) };
                this.state.lensId = lens.id;
            }
            await this.run();
            this.state.loaded = true;
        });
        // BOTH hooks are required: the payload is already loaded by the time
        // the first render happens, so onPatched never fires for it and the
        // canvas would sit at its default 300x150, empty.
        onMounted(() => this.syncChart());
        onPatched(() => this.syncChart());
        onWillUnmount(() => this.destroyChart());
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
        } catch (e) {
            this.state.error = this._msg(e);
            this.state.data = null;
        } finally {
            this.state.busy = false;
        }
    }

    _msg(e) {
        return (e && (e.data?.message || e.message)) || _t("Something went wrong.");
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
        const d = this.state.data;
        if (!d) { return { arcs: [], total: 0, dropped: 0 }; }
        return donutArcs(d.series, { size: 240, thickness: 36 });
    }

    get heatmap() {
        const d = this.state.data;
        if (!d) { return { rows: [] }; }
        return heatmapCells(d.series, d.categories);
    }

    syncChart() {
        if (!this.isCanvasChart || !this.state.data) {
            this.destroyChart();
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
        const sig = JSON.stringify([
            this.state.spec.chart, this.state.data.categories.map((c) => c.key),
            this.state.data.series.map((s) => [s.key, s.values]),
        ]);
        if (sig === this._chartSig && this._chart && this._canvasEl === canvas) {
            return;
        }
        this._chartSig = sig;
        this._canvasEl = canvas;
        this.destroyChart();
        // Any instance Chart.js still has registered against this exact node
        // (ours or a leftover) must go, or `new Chart()` throws "Canvas is
        // already in use".
        window.Chart.getChart?.(canvas)?.destroy();
        const cfg = chartConfig(this.state.spec.chart, this.state.data,
                                { money: (v, s) => this.money(v, s) });
        cfg.options.onClick = (evt, els) => {
            if (!els || !els.length) { return; }
            const el = els[0];
            const s = this.state.data.series[el.datasetIndex];
            const c = this.state.data.categories[el.index];
            if (s && c) { this.openDrill(s.key, c.key, s.label, c.label); }
        };
        this._chart = new window.Chart(canvas, cfg);
        // Force final geometry synchronously — never depend on an animation
        // frame to make the bars visible.
        this._chart.update("none");
    }

    destroyChart() {
        if (this._chart) {
            this._chart.destroy();
            this._chart = null;
            this._chartSig = "";
            this._canvasEl = null;
        }
    }

    // ----------------------------------------------------------------- drill
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

    openLens(lens) {
        this.state.spec = {
            ...JSON.parse(JSON.stringify(lens.spec)),
            date_from: this.state.spec.date_from,
            date_to: this.state.spec.date_to,
        };
        this.state.lensId = lens.id;
        this.state.askWhy = null;
        this.destroyChart();
        this.run();
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
    get grandTotal() { return this.state.data?.grand_total || 0; }

    get hasPending() { return (this.state.data?.pending || []).length > 0; }

    get pendingNames() {
        return (this.state.data?.pending || []).map((p) => p.name).join(", ");
    }
}

registry.category("actions").add("pb_explorer_cockpit", PbExplorer);
