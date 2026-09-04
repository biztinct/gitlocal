/** @odoo-module **/
/**
 * Chart geometry for the Analytics Explorer.
 *
 * Hybrid by design:
 *   * DONUT and HEATMAP are computed here and rendered as bespoke SVG in the
 *     OWL template, so they match the Insights cockpit's visual language
 *     exactly and every segment stays individually hoverable and clickable.
 *   * COLUMN / STACKED / LINE go to Chart.js, which Odoo already ships in its
 *     LAZY `web.chartjs_lib` bundle — loaded on demand via loadBundle().
 *
 * Never touch a bare `window.Chart`: the global that happens to exist on this
 * server is pb_payroll_ai_insights' own vendored jsDelivr copy. Depending on it
 * would couple this cockpit to that module AND re-import a CDN artefact the
 * asset test explicitly forbids.
 */
import { loadBundle } from "@web/core/assets";

/** The categorical ramp. One indigo primary, then supporting hues — no
 *  gradients (design system). Deterministic: series N always gets colour N. */
export const RAMP = [
    "#5A4BB0", "#2563EB", "#0D9488", "#D97706", "#DC2668", "#7C3AED",
    "#0891B2", "#65A30D", "#DB2777", "#4F46E5", "#EA580C", "#0F766E",
    "#9333EA", "#1D4ED8", "#15803D", "#B45309", "#BE123C", "#6D28D9",
    "#0E7490", "#4D7C0F", "#A21CAF", "#1E40AF", "#166534", "#92400E",
];

export const colourAt = (i) => RAMP[i % RAMP.length];

/** Chart.js lives in a lazy bundle; resolve it before first paint. */
export async function ensureChartJs() {
    if (window.Chart && window.Chart.version) {
        return window.Chart;
    }
    await loadBundle("web.chartjs_lib");
    return window.Chart;
}

// ---------------------------------------------------------------- helpers
const TAU = Math.PI * 2;

function polar(cx, cy, r, a) {
    return [cx + r * Math.cos(a - Math.PI / 2), cy + r * Math.sin(a - Math.PI / 2)];
}

/**
 * Donut geometry. Returns one arc per series with its SVG path `d`.
 * Negative values are dropped (a pie of signed numbers is meaningless) and the
 * count of dropped slices is reported so the caller can SAY so.
 */
export function donutArcs(series, { size = 240, thickness = 34 } = {}) {
    const cx = size / 2, cy = size / 2;
    const rOuter = size / 2 - 4, rInner = rOuter - thickness;
    const usable = series.filter((s) => s.total > 0);
    const dropped = series.length - usable.length;
    const total = usable.reduce((a, s) => a + s.total, 0);
    if (!total) {
        return { arcs: [], total: 0, dropped, cx, cy, rInner, rOuter };
    }
    let acc = 0;
    const arcs = usable.map((s, i) => {
        const frac = s.total / total;
        const a0 = acc * TAU, a1 = (acc + frac) * TAU;
        acc += frac;
        const large = a1 - a0 > Math.PI ? 1 : 0;
        const [x0, y0] = polar(cx, cy, rOuter, a0);
        const [x1, y1] = polar(cx, cy, rOuter, a1);
        const [x2, y2] = polar(cx, cy, rInner, a1);
        const [x3, y3] = polar(cx, cy, rInner, a0);
        return {
            key: s.key,
            label: s.label,
            value: s.total,
            pct: frac * 100,
            colour: colourAt(i),
            d: `M ${x0} ${y0} A ${rOuter} ${rOuter} 0 ${large} 1 ${x1} ${y1} ` +
               `L ${x2} ${y2} A ${rInner} ${rInner} 0 ${large} 0 ${x3} ${y3} Z`,
        };
    });
    return { arcs, total, dropped, cx, cy, rInner, rOuter };
}

/**
 * Heatmap cells: series (rows) x categories (columns), colour keyed to each
 * cell's deviation from the grand mean. Diverging scale so "hotter/colder than
 * typical" is readable at a glance rather than "big/small".
 */
export function heatmapCells(series, categories) {
    const flat = [];
    series.forEach((s) => s.values.forEach((v) => flat.push(v)));
    const live = flat.filter((v) => v !== 0);
    const mean = live.length ? live.reduce((a, b) => a + b, 0) / live.length : 0;
    const spread = live.length
        ? Math.max(...live.map((v) => Math.abs(v - mean))) || 1
        : 1;
    const rows = series.map((s) => ({
        key: s.key,
        label: s.label,
        total: s.total,
        cells: s.values.map((v, i) => {
            const dev = spread ? (v - mean) / spread : 0;   // -1 .. +1
            return {
                value: v,
                col: categories[i] ? categories[i].key : String(i),
                colLabel: categories[i] ? categories[i].label : "",
                dev,
                colour: heatColour(dev, v === 0),
                ink: Math.abs(dev) > 0.55 ? "#fff" : "#1B1733",
            };
        }),
    }));
    return { rows, mean, spread };
}

function heatColour(dev, empty) {
    if (empty) { return "#F1F5F9"; }
    const t = Math.max(-1, Math.min(1, dev));
    if (t >= 0) {
        // neutral -> indigo (above typical)
        return mix([237, 242, 250], [90, 75, 176], t);
    }
    // neutral -> teal (below typical)
    return mix([237, 242, 250], [13, 148, 136], -t);
}

function mix(a, b, t) {
    const c = a.map((v, i) => Math.round(v + (b[i] - v) * t));
    return `rgb(${c[0]},${c[1]},${c[2]})`;
}

/**
 * Waterfall bars for the narrative layer: a start value, signed steps, an end.
 * Each bar carries its floating base so the classic staircase reads correctly.
 */
export function waterfallBars(start, steps, end,
                              { height = 160, pad = 26, startLabel = "Start",
                                endLabel = "End" } = {}) {
    const pts = [{ label: startLabel, value: start, kind: "anchor" }];
    let running = start;
    steps.forEach((s) => {
        pts.push({ label: s.label, value: s.value, kind: s.value >= 0 ? "up" : "down",
                   base: s.value >= 0 ? running : running + s.value });
        running += s.value;
    });
    pts.push({ label: endLabel, value: end, kind: "anchor" });

    const tops = pts.map((p) => (p.kind === "anchor" ? p.value : p.base + Math.abs(p.value)));
    const bottoms = pts.map((p) => (p.kind === "anchor" ? 0 : p.base));
    const hi = Math.max(...tops, 0), lo = Math.min(...bottoms, 0);
    const span = hi - lo || 1;
    // `pad` reserves room ABOVE the tallest bar: the value label is drawn at
    // (bar.y - 7), so without it the label on a full-height bar lands at a
    // negative y and is clipped outside the viewBox entirely.
    const y = (v) => pad + height - ((v - lo) / span) * height;

    return pts.map((p, i) => {
        const top = p.kind === "anchor" ? Math.max(p.value, 0) : p.base + Math.abs(p.value);
        const bot = p.kind === "anchor" ? Math.min(p.value, 0) : p.base;
        return {
            ...p,
            index: i,
            y: y(top),
            h: Math.max(1, y(bot) - y(top)),
            colour: p.kind === "anchor" ? "#5A4BB0"
                  : p.value >= 0 ? "#2E7D4F" : "#DC2668",
        };
    });
}

/** Build a Chart.js config for the generic forms. */
export function chartConfig(kind, payload, { money }) {
    const { categories, series } = payload;
    const labels = categories.map((c) => c.label);
    const datasets = series.map((s, i) => {
        const colour = colourAt(i);
        const base = {
            label: s.label,
            data: s.values,
            borderColor: colour,
            backgroundColor: kind === "line" ? `${colour}22` : colour,
            borderWidth: kind === "line" ? 2.4 : 0,
            borderRadius: kind === "line" ? 0 : 6,
            maxBarThickness: 46,
        };
        if (kind === "line") {
            Object.assign(base, { tension: 0.32, pointRadius: 2.5,
                                  pointHoverRadius: 5, fill: series.length === 1 });
        }
        return base;
    });
    const stacked = kind === "stacked";
    return {
        type: kind === "line" ? "line" : "bar",
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            // Animation OFF, deliberately. When a chart is rebuilt as OWL
            // re-renders the canvas, Chart.js's rAF animator can fail to tick
            // and every bar stays frozen at its start geometry (y === base):
            // a permanently blank chart with correct data behind it. The
            // cockpit already has its own CSS entrance motion, so there is
            // nothing to gain and a silent blank board to lose.
            animation: false,
            plugins: {
                legend: {
                    display: series.length > 1,
                    position: "bottom",
                    labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true,
                              pointStyle: "circle", padding: 14,
                              font: { size: 11.5, family: "inherit" } },
                },
                tooltip: {
                    backgroundColor: "#241F52",
                    padding: 10,
                    cornerRadius: 8,
                    titleFont: { size: 12, family: "inherit" },
                    bodyFont: { size: 12, family: "inherit" },
                    callbacks: {
                        label: (ctx) =>
                            ` ${ctx.dataset.label}: ${money(ctx.parsed.y)}`,
                    },
                },
            },
            scales: {
                x: { stacked, grid: { display: false },
                     ticks: { font: { size: 11, family: "inherit" },
                              color: "#64748B", maxRotation: 0, autoSkipPadding: 12 } },
                y: { stacked, beginAtZero: true,
                     grid: { color: "#EEF1F6", drawBorder: false },
                     ticks: { font: { size: 11, family: "inherit" },
                              color: "#64748B",
                              callback: (v) => money(v, true) } },
            },
        },
    };
}
