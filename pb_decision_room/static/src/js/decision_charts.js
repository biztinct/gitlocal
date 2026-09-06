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
