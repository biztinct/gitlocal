/** @odoo-module **/
/**
 * The two pictures the room draws by hand.
 *
 *   * the HORIZON — the year, on the dark stage: a stress band, the comparison
 *     dashed behind, a dotted even pace to the goal, the plan itself, a marker
 *     on the month being explored, and a difference view that swaps all of that
 *     for one row of bars around zero;
 *   * the RING — how much of the work the team can deliver.
 *
 * Canvas rules that are scar tissue, not taste:
 *   * size from `getBoundingClientRect()` x `devicePixelRatio` on EVERY draw.
 *     The hub rail is 76px, a lens can be collapsed, and a canvas sized once at
 *     mount is a blurred canvas for the rest of the session;
 *   * a rectangle with zero width or height is not drawn at all — a zero-size
 *     canvas throws nothing and shows nothing, which is the hardest kind of
 *     bug to see;
 *   * nothing here reads the DOM outside the canvas it was handed, so both
 *     functions are safe to call from a resize observer.
 *
 * Colours are the palette's, written out: a canvas cannot read a CSS custom
 * property without a `getComputedStyle` round trip per draw.
 */

export const STAGE = {
    ink: "#241F52",
    plan: "#D7C6FF",
    planDot: "#E7DDFF",
    base: "#8D84AC",
    band: "rgba(199,184,237,.10)",
    goal: "#F7A6C3",
    grid: "rgba(255,255,255,.08)",
    axis: "#BDB6D6",
    good: "#C5B2F2",
    bad: "#EE9FBA",
};

/** Size a canvas to its box. Returns null when it has no box yet. */
export function canvas2d(canvas) {
    if (!canvas) { return null; }
    const box = canvas.getBoundingClientRect();
    if (box.width < 2 || box.height < 2) { return null; }
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(box.width * dpr);
    canvas.height = Math.round(box.height * dpr);
    const ctx = canvas.getContext("2d");
    if (!ctx) { return null; }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, box.width, box.height);
    return { ctx, w: box.width, h: box.height };
}

/**
 * The stage's year.
 *
 * @param {HTMLCanvasElement} canvas
 * @param {object} o
 *   plan[12], ref[12], lo[12], hi[12], goal[12]|null, month, diff, coverage,
 *   fmt(value) -> string, goodUp
 */
export function drawHorizon(canvas, o) {
    const g = canvas2d(canvas);
    if (!g) { return false; }
    const { ctx, w, h } = g;
    const pad = { l: w < 420 ? 40 : 52, r: 14, t: 16, b: 24 };
    const plan = o.plan || [];
    if (plan.length !== 12) { return false; }
    const diff = !!o.diff;
    const delta = plan.map((v, i) => v - (o.ref[i] || 0));
    const values = diff ? delta : plan;

    const pool = diff
        ? [...delta, 0]
        : [...plan, ...(o.ref || []), ...(o.lo || []), ...(o.hi || []),
           ...(o.goal || [])];
    let min = Math.min(...pool);
    let max = Math.max(...pool);
    if (!o.coverage || diff) { min = Math.min(min, 0); }
    const span = Math.max(max - min, o.coverage ? 5 : 1);
    min -= span * 0.08;
    max += span * 0.16;
    if (!diff && min < 0 && pool.every((v) => v >= 0)) { min = 0; }

    const X = (i) => pad.l + (w - pad.l - pad.r) * i / 11;
    const Y = (v) => pad.t + (h - pad.t - pad.b) * (max - v) / (max - min || 1);
    const line = (arr) => {
        ctx.beginPath();
        arr.forEach((v, i) => (i ? ctx.lineTo(X(i), Y(v)) : ctx.moveTo(X(i), Y(v))));
    };

    // ---- the ruled paper -------------------------------------------------
    ctx.font = "10px system-ui, sans-serif";
    ctx.textAlign = "right";
    for (let i = 0; i < 5; i++) {
        const v = min + (max - min) * i / 4;
        const y = Y(v);
        ctx.strokeStyle = STAGE.grid;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(pad.l, y);
        ctx.lineTo(w - pad.r, y);
        ctx.stroke();
        ctx.fillStyle = STAGE.axis;
        ctx.fillText(o.fmt(v), pad.l - 8, y + 3);
    }

    if (!diff) {
        // the stress band
        if (o.lo && o.hi && o.lo.length === 12) {
            ctx.beginPath();
            o.hi.forEach((v, i) => (i ? ctx.lineTo(X(i), Y(v))
                                     : ctx.moveTo(X(i), Y(v))));
            for (let i = 11; i >= 0; i--) { ctx.lineTo(X(i), Y(o.lo[i])); }
            ctx.closePath();
            ctx.fillStyle = STAGE.band;
            ctx.fill();
        }
        // the comparison, dashed and behind
        if (o.ref && o.ref.length === 12) {
            line(o.ref);
            ctx.setLineDash([4, 5]);
            ctx.strokeStyle = STAGE.base;
            ctx.lineWidth = 1.5;
            ctx.stroke();
            ctx.setLineDash([]);
        }
        // an even pace to the goal
        if (o.goal && o.goal.length === 12) {
            line(o.goal);
            ctx.setLineDash([2, 5]);
            ctx.strokeStyle = STAGE.goal;
            ctx.lineWidth = 1.6;
            ctx.stroke();
            ctx.setLineDash([]);
        }
        // the plan
        line(plan);
        ctx.strokeStyle = STAGE.plan;
        ctx.lineWidth = 2.8;
        ctx.lineJoin = "round";
        ctx.stroke();
        plan.forEach((v, i) => {
            ctx.beginPath();
            ctx.arc(X(i), Y(v), i === o.month ? 5 : 2.7, 0, Math.PI * 2);
            ctx.fillStyle = STAGE.planDot;
            ctx.fill();
            if (i === o.month) {
                ctx.strokeStyle = "rgba(215,198,255,.22)";
                ctx.lineWidth = 9;
                ctx.stroke();
            }
        });
    } else {
        ctx.strokeStyle = "rgba(189,180,214,.7)";
        ctx.setLineDash([3, 4]);
        ctx.beginPath();
        ctx.moveTo(pad.l, Y(0));
        ctx.lineTo(w - pad.r, Y(0));
        ctx.stroke();
        ctx.setLineDash([]);
        const bw = Math.max(7, (w - pad.l - pad.r) / 18);
        values.forEach((v, i) => {
            const good = o.goodUp ? v >= 0 : v <= 0;
            ctx.fillStyle = good ? STAGE.good : STAGE.bad;
            ctx.globalAlpha = i === o.month ? 1 : 0.65;
            const top = Math.min(Y(0), Y(v));
            const height = Math.max(2, Math.abs(Y(0) - Y(v)));
            ctx.beginPath();
            if (ctx.roundRect) { ctx.roundRect(X(i) - bw / 2, top, bw, height, 3); }
            else { ctx.rect(X(i) - bw / 2, top, bw, height); }
            ctx.fill();
        });
        ctx.globalAlpha = 1;
    }

    // ---- the month being explored ---------------------------------------
    ctx.beginPath();
    ctx.moveTo(X(o.month), pad.t);
    ctx.lineTo(X(o.month), h - pad.b);
    ctx.lineWidth = 1;
    ctx.strokeStyle = "rgba(215,198,255,.28)";
    ctx.stroke();

    ctx.fillStyle = "#C1B8D8";
    ctx.textAlign = "center";
    ctx.font = "9px system-ui, sans-serif";
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"].forEach((name, i) => {
        if (w > 440 || i % 2 === 0) { ctx.fillText(name, X(i), h - 7); }
    });
    return true;
}

/**
 * The palette of the LIGHT cards — the three charts in the detail workspace
 * sit on white, not on the stage, and a canvas cannot read a custom property
 * without a `getComputedStyle` round trip on every draw.
 */
export const PAPER = {
    ink: "#1E1B2E",
    sub: "#64748B",
    line: "#E7E4F0",
    primary: "#5A4BB0",
    soft: "#CBC2EE",
    teal: "#0F766E",
    rose: "#DC2668",
    good: "#8477BF",
    bad: "#E0A97F",
    dark: "#352F4E",
    dim: "#CBB5C1",
};

const MONTHS_3 = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Two lines of a label, split near the middle on a word boundary. */
function twoLines(label) {
    const words = String(label || "").split(" ");
    if (words.length < 2) { return [label, ""]; }
    const cut = Math.ceil(words.length / 2);
    return [words.slice(0, cut).join(" "), words.slice(cut).join(" ")];
}

/**
 * Will the work and the team line up?
 *
 * Three lines in HOURS: the work arriving, what the team could deliver if
 * every hour found work, and what is actually delivered once the two are
 * matched shift by shift. The gap between the first two is the story; the
 * third says how much of it is being closed.
 *
 * @param {object} o  demand[12], capacity[12], served[12], month, fmt(v)
 */
export function drawDemand(canvas, o) {
    const g = canvas2d(canvas);
    if (!g) { return false; }
    const { ctx, w, h } = g;
    const pad = { l: w < 420 ? 44 : 58, r: 14, t: 16, b: 26 };
    const sets = [
        { values: o.demand || [], colour: PAPER.rose, dash: [4, 4] },
        { values: o.capacity || [], colour: PAPER.teal, dash: [2, 4] },
        { values: o.served || [], colour: PAPER.primary, dash: [] },
    ].filter((s) => s.values.length === 12);
    if (!sets.length) { return false; }
    const max = Math.max(...sets.flatMap((s) => s.values), 1) * 1.15;
    const X = (i) => pad.l + (w - pad.l - pad.r) * i / 11;
    const Y = (v) => pad.t + (h - pad.t - pad.b) * (1 - v / max);

    ctx.font = "9px system-ui, sans-serif";
    ctx.textAlign = "right";
    for (let i = 0; i <= 4; i++) {
        const v = max * i / 4;
        ctx.strokeStyle = PAPER.line;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(pad.l, Y(v));
        ctx.lineTo(w - pad.r, Y(v));
        ctx.stroke();
        ctx.fillStyle = PAPER.sub;
        ctx.fillText(o.fmt(v), pad.l - 7, Y(v) + 3);
    }
    // the month being explored
    if (o.month >= 0 && o.month <= 11) {
        ctx.strokeStyle = "rgba(90,75,176,.22)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(X(o.month), pad.t);
        ctx.lineTo(X(o.month), h - pad.b);
        ctx.stroke();
    }
    for (const set of sets) {
        ctx.beginPath();
        set.values.forEach((v, i) => (i ? ctx.lineTo(X(i), Y(v))
                                       : ctx.moveTo(X(i), Y(v))));
        ctx.setLineDash(set.dash);
        ctx.strokeStyle = set.colour;
        ctx.lineWidth = set.dash.length ? 1.7 : 2.6;
        ctx.lineJoin = "round";
        ctx.stroke();
        ctx.setLineDash([]);
        if (o.month >= 0 && o.month <= 11) {
            ctx.beginPath();
            ctx.arc(X(o.month), Y(set.values[o.month]), 3.4, 0, Math.PI * 2);
            ctx.fillStyle = set.colour;
            ctx.fill();
        }
    }
    ctx.textAlign = "center";
    ctx.fillStyle = PAPER.sub;
    ctx.font = "9px system-ui, sans-serif";
    MONTHS_3.forEach((name, i) => {
        if (w > 440 || i % 2 === 0) { ctx.fillText(name, X(i), h - 8); }
    });
    return true;
}

/**
 * Every difference has a reason — the profit bridge.
 *
 * A waterfall from the comparison to this plan: one bar per step, each
 * starting where the last one left off, with a dotted connector so the eye
 * can follow the running level. The two ends are drawn from zero, because
 * they are totals and not differences.
 *
 * @param {object} o  start, end, steps[{label,value}], startName, fmt(v),
 *                    signed(v)
 */
export function drawBridge(canvas, o) {
    const g = canvas2d(canvas);
    if (!g) { return false; }
    const { ctx, w, h } = g;
    const pad = { l: w < 460 ? 52 : 64, r: 12, t: 22, b: 48 };
    const items = [
        { label: o.startName || "Comparison", value: o.start, total: true },
        ...(o.steps || []).map((s) => ({ label: s.label, value: s.value })),
        { label: "Your plan", value: o.end, total: true },
    ];
    // THE SCALE IS THE JOURNEY, NOT THE DESTINATION.
    //
    // Anchoring the axis at zero is the obvious thing to do and it makes this
    // chart useless: on a ₫286 billion profit, a ₫2 billion step is four
    // pixels tall, so the waterfall reads as two towers with a flat dotted
    // line between them and the whole point — WHY it changed — is invisible.
    // So the axis spans the running level only, and the two totals are drawn
    // as columns from the floor of that axis. The footnote under the chart
    // says the scale does not start at zero, because a column that is not
    // proportional has to say so.
    let run = 0;
    let lo = Math.min(o.start, o.end);
    let hi = Math.max(o.start, o.end);
    for (const item of items) {
        if (item.total) { run = item.value; } else { run += item.value; }
        lo = Math.min(lo, run);
        hi = Math.max(hi, run);
    }
    const span = (hi - lo) || Math.max(1, Math.abs(hi) * 0.02);
    lo -= span * 0.35;
    hi += span * 0.22;
    const n = items.length;
    const slot = (w - pad.l - pad.r) / n;
    const bw = Math.min(48, Math.max(6, slot * 0.6));
    const Y = (v) => pad.t + (h - pad.t - pad.b) * (hi - v) / (hi - lo || 1);

    ctx.font = "9px system-ui, sans-serif";
    ctx.textAlign = "right";
    for (let k = 0; k <= 4; k++) {
        const v = lo + (hi - lo) * k / 4;
        ctx.strokeStyle = PAPER.line;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(pad.l, Y(v));
        ctx.lineTo(w - pad.r, Y(v));
        ctx.stroke();
        ctx.fillStyle = PAPER.sub;
        ctx.fillText(o.fmt(v), pad.l - 7, Y(v) + 3);
    }

    let level = 0;
    items.forEach((item, i) => {
        const cx = pad.l + slot * i + slot / 2;
        const x0 = cx - bw / 2;
        let top;
        let bottom;
        let colour;
        if (item.total) {
            top = Y(item.value);
            bottom = h - pad.b;          // a column from the floor of the axis
            colour = PAPER.dark;
            level = item.value;
        } else {
            const from = level;
            const to = level + item.value;
            top = Y(Math.max(from, to));
            bottom = Y(Math.min(from, to));
            colour = item.value >= 0 ? PAPER.good : PAPER.bad;
            level = to;
        }
        ctx.fillStyle = colour;
        ctx.beginPath();
        const height = Math.max(2, bottom - top);
        if (ctx.roundRect) { ctx.roundRect(x0, top, bw, height, 3); }
        else { ctx.rect(x0, top, bw, height); }
        ctx.fill();
        if (i < n - 1) {
            ctx.strokeStyle = "#B2ADC7";
            ctx.setLineDash([2, 3]);
            ctx.beginPath();
            ctx.moveTo(x0 + bw, Y(level));
            ctx.lineTo(pad.l + slot * (i + 1) + slot / 2 - bw / 2, Y(level));
            ctx.stroke();
            ctx.setLineDash([]);
        }
        ctx.textAlign = "center";
        ctx.fillStyle = PAPER.ink;
        ctx.font = "600 9px system-ui, sans-serif";
        ctx.fillText(item.total ? o.fmt(item.value) : o.signed(item.value),
                     cx, top - 7);
        ctx.fillStyle = PAPER.sub;
        ctx.font = "8px system-ui, sans-serif";
        const [one, two] = twoLines(item.label);
        ctx.fillText(one, cx, h - pad.b + 17);
        if (two) { ctx.fillText(two, cx, h - pad.b + 27); }
    });
    return true;
}

/**
 * How much room do we have? — profit against additional people.
 *
 * Teal where every goal still holds, rose where one has broken. The segments
 * between two met points are teal too, so a run reads as a range rather than
 * as a row of dots.
 *
 * @param {object} o  points[{add,profit,met}], fmt(v)
 */
export function drawRoom(canvas, o) {
    const g = canvas2d(canvas);
    if (!g) { return false; }
    const { ctx, w, h } = g;
    const points = o.points || [];
    if (points.length < 2) { return false; }
    const pad = { l: w < 460 ? 48 : 62, r: 16, t: 20, b: 30 };
    const values = points.map((p) => p.profit);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = Math.max(Math.abs(max) * 1e-6, max - min, 1);
    const low = min - span * 0.18;
    const high = max + span * 0.18;
    const X = (i) => pad.l + (w - pad.l - pad.r) * i
        / Math.max(1, points.length - 1);
    const Y = (v) => pad.t + (h - pad.t - pad.b) * (high - v) / (high - low);

    ctx.font = "9px system-ui, sans-serif";
    ctx.textAlign = "right";
    for (let i = 0; i <= 4; i++) {
        const v = low + (high - low) * i / 4;
        ctx.strokeStyle = PAPER.line;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(pad.l, Y(v));
        ctx.lineTo(w - pad.r, Y(v));
        ctx.stroke();
        ctx.fillStyle = PAPER.sub;
        ctx.fillText(o.fmt(v), pad.l - 7, Y(v) + 3);
    }
    for (let i = 1; i < points.length; i++) {
        ctx.beginPath();
        ctx.moveTo(X(i - 1), Y(points[i - 1].profit));
        ctx.lineTo(X(i), Y(points[i].profit));
        ctx.strokeStyle = (points[i].met && points[i - 1].met)
            ? PAPER.teal : PAPER.dim;
        ctx.lineWidth = 2.4;
        ctx.stroke();
    }
    const radius = points.length > 35 ? 2.2 : 3.2;
    points.forEach((p, i) => {
        ctx.beginPath();
        ctx.arc(X(i), Y(p.profit), radius, 0, Math.PI * 2);
        ctx.fillStyle = p.met ? PAPER.teal : PAPER.rose;
        ctx.fill();
    });
    ctx.fillStyle = PAPER.sub;
    const marks = [...new Set([0, Math.floor((points.length - 1) / 2),
                               points.length - 1])];
    marks.forEach((i) => {
        // The first and last labels sit ON the edge of the plot, so they are
        // aligned INTO it — centred, the last one runs off the canvas and
        // reads "+200 peo".
        ctx.textAlign = i === 0 ? "left"
            : (i === points.length - 1 ? "right" : "center");
        ctx.fillText(`+${points[i].add} people`, X(i), h - 9);
    });
    ctx.textAlign = "center";
    return true;
}

/** How much of the work the team can deliver, as a dial. */
export function drawRing(canvas, o) {
    const g = canvas2d(canvas);
    if (!g) { return false; }
    const { ctx, w, h } = g;
    const cx = w / 2;
    const cy = h / 2;
    const r = Math.max(6, Math.min(w, h) / 2 - 7);
    const START = Math.PI * 0.75;
    const SWEEP = Math.PI * 1.5;
    const arc = (from, to, colour, width) => {
        ctx.lineWidth = width;
        ctx.lineCap = "round";
        ctx.strokeStyle = colour;
        ctx.beginPath();
        ctx.arc(cx, cy, r, from, to);
        ctx.stroke();
    };
    arc(START, START + SWEEP, "#E7E4F0", 9);
    const ref = Math.max(0, Math.min(1, o.ref || 0));
    arc(START, START + SWEEP * ref, "#BDB8D3", 3);
    const value = Math.max(0, Math.min(1, o.value || 0));
    arc(START, START + SWEEP * value,
        value >= (o.goodAt || 0.95) ? "#5A4BB0" : "#D97706", 9);
    return true;
}
