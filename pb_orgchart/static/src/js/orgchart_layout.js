/** @odoo-module **/
/**
 * ORG CHART P1 — the pure half of the chart: the tree index, the tidy-tree
 * layout with leaf stacks, bounds, edges and colours.
 *
 * Ported from the proof of concept (docs/design/org-chart-poc/app.js, the
 * "tree helpers" and "layout" blocks). Free of the DOM and of OWL so it can be
 * reasoned about (and tested) on its own. Three changes from the POC, all for
 * real data:
 *
 *   1. An INDEX (Maps) instead of `DATA.filter` per call — the POC's `kids()`
 *      is O(n) per call and O(n^2) per render; 4,500 people would stall.
 *   2. A FOREST. The POC draws one tree (the CEO's) and puts every other root
 *      in the lane, which silently drops those roots' teams. Real companies
 *      have several tops (two companies, a board, a demo world with 600
 *      teams), so every root WITH a team is a tree; trees flow left to right
 *      and wrap into rows. Only people with no manager AND no team go in the
 *      "no manager yet" lane.
 *   3. The lane WRAPS into a grid and folds behind a "+N more" tile; a lane of
 *      234 cards in one row (rize, 2026-11-04) is 57,000 px wide.
 */

export const GX = 22;    // gap between siblings
export const GY = 70;    // gap between levels
const IND = 28;          // stack indent
const SY = 12;           // gap inside a stack
const TREE_GAP = 70;     // gap between trees of a forest
const LANE_PAD = 10;
const LANE_HEAD = 34;

export function cardSize(compact) {
    return compact ? { w: 180, h: 52 } : { w: 224, h: 96 };
}

/**
 * The tree as Maps. `nodes` are client rows: `{id, mgr, ...}` with string ids
 * ("12" for a person, "job-5" for an open role) and `mgr` a string or null.
 * A manager who is not in the set makes the node a root.
 */
export function buildIndex(nodes) {
    const byId = new Map();
    for (const n of nodes) { byId.set(n.id, n); }
    const eff = new Map();
    const kids = new Map();
    const roots = [];
    for (const n of nodes) {
        const m = n.mgr && n.mgr !== n.id && byId.has(n.mgr) ? n.mgr : null;
        eff.set(n.id, m);
        if (m) {
            if (!kids.has(m)) { kids.set(m, []); }
            kids.get(m).push(n);
        } else {
            roots.push(n);
        }
    }
    // Managers before individual contributors, open roles last: the stack
    // gathers the leaves anyway, this keeps teams to the left of a row.
    const rank = (n) => (n.isRole ? 2 : (kids.has(n.id) || n.nReports ? 0 : 1));
    for (const list of kids.values()) {
        list.sort((a, b) => rank(a) - rank(b) || a.order - b.order);
    }
    // Depth by breadth-first walk; anything unreached sits on a loop and is cut.
    const depth = new Map();
    let frontier = roots.slice();
    for (const r of frontier) { depth.set(r.id, 0); }
    while (frontier.length) {
        const next = [];
        for (const n of frontier) {
            for (const k of kids.get(n.id) || []) {
                if (!depth.has(k.id)) { depth.set(k.id, depth.get(n.id) + 1); next.push(k); }
            }
        }
        frontier = next;
    }
    for (const n of nodes) {
        if (!depth.has(n.id)) {
            const m = eff.get(n.id);
            if (m && kids.has(m)) { kids.set(m, kids.get(m).filter((k) => k.id !== n.id)); }
            eff.set(n.id, null);
            roots.push(n);
            depth.set(n.id, 0);
            const stack = [n];
            while (stack.length) {
                const c = stack.pop();
                for (const k of kids.get(c.id) || []) {
                    if (!depth.has(k.id)) { depth.set(k.id, depth.get(c.id) + 1); stack.push(k); }
                }
            }
        }
    }
    // Everyone under a node that is LOADED (deepest first).
    const total = new Map();
    for (const n of nodes) { total.set(n.id, 0); }
    const order = nodes.slice().sort((a, b) => depth.get(b.id) - depth.get(a.id));
    for (const n of order) {
        const m = eff.get(n.id);
        if (m) { total.set(m, total.get(m) + 1 + total.get(n.id)); }
    }
    let maxDepth = 0;
    for (const d of depth.values()) { if (d > maxDepth) { maxDepth = d; } }
    // A tree is a root with a team (loaded or not); the rest is the lane.
    const hasTeam = (n) => kids.has(n.id) || (n.nReports || 0) > 0;
    let trees = roots.filter(hasTeam);
    // people first, open roles after them
    let lone = roots.filter((n) => !hasTeam(n))
        .sort((a, b) => (a.isRole - b.isRole) || a.order - b.order);
    if (!trees.length && lone.length === 1) { trees = lone; lone = []; }
    return { byId, eff, kids, roots, depth, total, maxDepth, trees, lone,
             loneSet: new Set(lone.map((n) => n.id)) };
}

export function kidsOf(idx, id) {
    return idx.kids.get(id) || [];
}

/** Managers above `id`, nearest first. */
export function ancestors(idx, id) {
    const out = [];
    const seen = new Set([id]);
    let m = idx.eff.get(id);
    while (m && !seen.has(m)) {
        seen.add(m);
        const n = idx.byId.get(m);
        if (!n) { break; }
        out.push(n);
        m = idx.eff.get(m);
    }
    return out;
}

/** Everyone under `id` that is loaded, depth-first. */
export function descendants(idx, id) {
    const out = [];
    const walk = (i) => {
        for (const k of kidsOf(idx, i)) { out.push(k); walk(k.id); }
    };
    walk(id);
    return out;
}

/** Direct reports, counting a team the server has not sent yet. */
export function directCount(idx, n) {
    const loaded = kidsOf(idx, n.id).length;
    return Math.max(loaded, n.nReports || 0);
}

/** Everyone under, counting a team the server has not sent yet. */
export function totalCount(idx, n) {
    return Math.max(idx.total.get(n.id) || 0, n.nTotal || 0);
}

/** True when the server said this person has a team that is not loaded. */
export function isUnloaded(idx, n) {
    if (n.isRole || !n.nReports) { return false; }
    const loadedPeople = kidsOf(idx, n.id).filter((k) => !k.isRole).length;
    return loadedPeople < n.nReports;
}

/**
 * Positions for every card that is drawn.
 *
 * opts: { view: "tree"|"lr", compact, levels (0 = all), collapsed: Set,
 *         laneOpen: bool }
 * Returns { pos: Map id -> {x,y,w,h,stack?}, lane: {x,y,w,h,more,hidden}|null,
 *           laneIds: [], moreId }
 */
export function layout(idx, opts) {
    const { w: W, h: H } = cardSize(opts.compact);
    const LR = opts.view === "lr";
    // The tree is laid out in BREADTH x DEPTH units and rotated for sideways:
    // top-down a card is W broad and H deep; sideways it is H broad (cards
    // stack down the page) and W deep (levels step right). Rotating x/y alone
    // (the POC) packs 224-px cards into 166-px columns.
    const BW = LR ? H : W;
    const BH = LR ? W : H;
    const SIB = LR ? 14 : GX;          // gap between siblings along the breadth
    const pos = new Map();
    const STACK = !LR;
    const collapsed = opts.collapsed || new Set();
    const levels = opts.levels || 0;

    const shown = (n) => {
        if (collapsed.has(n.id) || isUnloaded(idx, n)) { return []; }
        if (levels && idx.depth.get(n.id) + 1 >= levels) { return []; }
        return kidsOf(idx, n.id);
    };
    const wid = new Map();
    const hgt = new Map();
    const slotsCache = new Map();
    // Leaf stacks (G3): three or more reports with no visible team of their
    // own share ONE column. Sideways keeps the plain tree, as the POC does.
    const slots = (n) => {
        if (slotsCache.has(n.id)) { return slotsCache.get(n.id); }
        const ks = shown(n);
        const leaves = ks.filter((k) => !shown(k).length);
        let out;
        if (!STACK || leaves.length < 3) {
            out = ks.map((k) => ({ node: k }));
        } else {
            out = [];
            let put = false;
            for (const k of ks) {
                if (shown(k).length) { out.push({ node: k }); }
                else if (!put) { out.push({ stack: leaves }); put = true; }
            }
        }
        slotsCache.set(n.id, out);
        return out;
    };
    const measure = (n) => {
        const ss = slots(n);
        if (!ss.length) { hgt.set(n.id, BH); wid.set(n.id, BW); return BW; }
        let w = 0;
        let hh = 0;
        for (const s of ss) {
            if (s.stack) {
                w += BW + IND + SIB;
                hh = Math.max(hh, s.stack.length * (BH + SY) - SY + 8);
            } else {
                w += measure(s.node) + SIB;
                hh = Math.max(hh, hgt.get(s.node.id));
            }
        }
        hgt.set(n.id, BH + GY + hh);
        const ww = Math.max(BW, w - SIB);
        wid.set(n.id, ww);
        return ww;
    };
    const tree = new Map();   // positions in breadth/depth units
    const place = (n, x, y) => {
        const ss = slots(n);
        tree.set(n.id, { x: x + (wid.get(n.id) - BW) / 2, y });
        let cx = x;
        for (const s of ss) {
            if (s.stack) {
                const tx = cx + IND / 2;
                const ty = y + BH + GY - 24;
                s.stack.forEach((k, i) => tree.set(k.id, {
                    x: cx + IND, y: y + BH + GY + i * (BH + SY), stack: { tx, ty },
                }));
                cx += BW + IND + SIB;
            } else {
                place(s.node, cx, y + BH + GY);
                cx += wid.get(s.node.id) + SIB;
            }
        }
    };

    // ---- the forest: biggest tree first, rows (columns, sideways) that wrap
    const trees = idx.trees.slice().sort((a, b) => totalCount(idx, b) - totalCount(idx, a));
    for (const t of trees) { measure(t); }
    const widest = trees.reduce((m, t) => Math.max(m, wid.get(t.id)), 0);
    const rowMax = Math.max(widest, LR ? 2000 : 3000);
    const rows = [];
    let row = null;
    for (const t of trees) {
        const tw = wid.get(t.id);
        if (!row || (row.w + TREE_GAP + tw > rowMax && row.items.length)) {
            row = { items: [], w: -TREE_GAP, h: 0 };
            rows.push(row);
        }
        row.items.push(t);
        row.w += TREE_GAP + tw;
        row.h = Math.max(row.h, hgt.get(t.id));
    }
    const forestBreadth = rows.reduce((m, r) => Math.max(m, r.w), 0);
    let y = 0;
    for (const r of rows) {
        let x = (forestBreadth - r.w) / 2;
        for (const t of r.items) {
            place(t, x, y);
            x += wid.get(t.id) + TREE_GAP;
        }
        y += r.h + GY;
    }
    // Real coordinates (rotated when sideways), forest at the origin.
    let fx1 = 0;
    for (const [id, t] of tree) {
        const p = LR ? { x: t.y, y: t.x, w: W, h: H } : { x: t.x, y: t.y, w: W, h: H, stack: t.stack };
        pos.set(id, p);
        fx1 = Math.max(fx1, p.x + W);
    }
    const forestW = tree.size ? fx1 : 0;

    // ---- the lane above the chart (people with no manager and no team);
    // always a grid that reads left to right, whichever way the tree runs
    let lane = null;
    const laneIds = [];
    let moreId = null;
    // a focus brings the people it lights to the front of the lane
    const first = opts.laneFirst;
    const lone = first && first.size
        ? [...idx.lone.filter((n) => first.has(n.id)), ...idx.lone.filter((n) => !first.has(n.id))]
        : idx.lone;
    let oy = 0;
    const lanePos = [];
    if (lone.length) {
        // as wide as the chart below it, but never a thin column: 8 to 10 cards
        const cols = Math.max(8, Math.min(10, Math.floor(forestW / (W + GX)) || 8));
        const cap = cols * 2;
        let showN = lone.length;
        let hidden = 0;
        if (!opts.laneOpen && lone.length > cap) { showN = cap - 1; hidden = lone.length - showN; }
        const cells = Math.min(lone.length, showN + (hidden ? 1 : 0));
        const usedCols = Math.min(cols, cells);
        const nRows = Math.ceil(cells / cols);
        const lw = usedCols * (W + GX) - GX + LANE_PAD * 2;
        const lh = LANE_HEAD + nRows * (H + SY) - SY + LANE_PAD;
        lane = { x: 0, y: 0, w: lw, h: lh, hidden, total: lone.length, open: !!opts.laneOpen && lone.length > cap };
        const cell = (i) => ({ x: LANE_PAD + (i % cols) * (W + GX), y: LANE_HEAD + Math.floor(i / cols) * (H + SY), w: W, h: H, lane: true });
        for (let i = 0; i < showN; i++) {
            lanePos.push([lone[i].id, cell(i)]);
            laneIds.push(lone[i].id);
        }
        if (hidden) {
            moreId = "__more";
            lanePos.push([moreId, { ...cell(showN), more: hidden }]);
        }
        oy = lh + GY;
    }
    // Centre the narrower of lane and forest on the wider; forest under the lane.
    const fullW = Math.max(forestW, lane ? lane.w : 0);
    const fdx = (fullW - forestW) / 2;
    for (const p of pos.values()) {
        p.x += fdx;
        p.y += oy;
        if (p.stack) { p.stack = { tx: p.stack.tx + fdx, ty: p.stack.ty + oy }; }
    }
    if (lane) {
        const dx = (fullW - lane.w) / 2;
        lane.x = dx;
        for (const [id, p] of lanePos) { p.x += dx; pos.set(id, p); }
    }
    return { pos, lane, laneIds, moreId, W, H };
}

export function bounds(pos, lane) {
    let x0 = Infinity;
    let y0 = Infinity;
    let x1 = -Infinity;
    let y1 = -Infinity;
    for (const p of pos.values()) {
        x0 = Math.min(x0, p.x); y0 = Math.min(y0, p.y);
        x1 = Math.max(x1, p.x + p.w); y1 = Math.max(y1, p.y + p.h);
    }
    if (lane) {
        x0 = Math.min(x0, lane.x); y0 = Math.min(y0, lane.y);
        x1 = Math.max(x1, lane.x + lane.w); y1 = Math.max(y1, lane.y + lane.h);
    }
    if (x0 === Infinity) { return { x: 0, y: 0, w: 400, h: 300 }; }
    return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

/** One SVG path from manager A to report B (POC renderEdges). */
export function edgePath(A, B, lr, dotted) {
    if (B.stack && !dotted) {
        const { tx, ty } = B.stack;
        const x1 = A.x + A.w / 2;
        const y1 = A.y + A.h;
        const my = y1 + (ty - y1) / 2;
        return `M${x1},${y1} C${x1},${my} ${tx},${my} ${tx},${ty} V${B.y + B.h / 2} H${B.x}`;
    }
    if (lr) {
        const x1 = A.x + A.w;
        const y1 = A.y + A.h / 2;
        const x2 = B.x;
        const y2 = B.y + B.h / 2;
        const mx = (x1 + x2) / 2;
        return `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`;
    }
    const x1 = A.x + A.w / 2;
    const y1 = A.y + A.h;
    const x2 = B.x + B.w / 2;
    const y2 = B.y;
    const my = y1 + (y2 - y1) / 2;
    return `M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}`;
}

/** Every solid and dotted edge between drawn cards. */
export function edges(idx, lay, lr) {
    const out = [];
    for (const [id, B] of lay.pos) {
        const m = idx.eff.get(id);
        if (m && lay.pos.has(m)) {
            out.push({ id, from: m, d: edgePath(lay.pos.get(m), B, lr, false), dot: false });
        }
        const n = idx.byId.get(id);
        if (n && n.dotted && lay.pos.has(n.dotted)) {
            // P2 fills `dotted`; the code path is drawn now (amber, dashed).
            out.push({ id: id + ":dot", from: n.dotted, d: edgePath(lay.pos.get(n.dotted), B, lr, true), dot: true });
        }
    }
    return out;
}

// ------------------------------------------------------------------ colours
export const LOC_COLORS = ["#5A4BB0", "#0F7B4F", "#2563EB", "#B45309", "#64748B",
                           "#0F7C6B", "#DC2655", "#7C3AED", "#0E7490", "#9D174D"];
export const TYPE_COLORS = { fulltime: "#5A4BB0", parttime: "#0F7C6B",
                             contractor: "#B45309", trainee: "#2563EB" };
export const TENURE = [
    { max: 90, color: "#0F7B4F" }, { max: 365, color: "#2563EB" },
    { max: 1095, color: "#5A4BB0" }, { max: Infinity, color: "#241F52" },
];

export function daysSince(dateStr, today) {
    if (!dateStr) { return null; }
    const d = new Date(dateStr + "T00:00:00");
    return Math.round((today - d) / 864e5);
}

/**
 * The card's colour. `ctx`: { colorBy, deptColor: Map, locations: [],
 * typeKeyOf(n), today }.
 */
export function colorOf(n, ctx) {
    if (n.isRole) { return "#B45309"; }
    if (ctx.colorBy === "loc") {
        const i = ctx.locations.indexOf(n.loc);
        return i >= 0 ? LOC_COLORS[i % LOC_COLORS.length] : "#64748B";
    }
    if (ctx.colorBy === "type") { return TYPE_COLORS[n.typeKey] || "#64748B"; }
    if (ctx.colorBy === "tenure") {
        const d = daysSince(n.joined, ctx.today);
        if (d === null) { return "#64748B"; }
        return TENURE.find((t) => d < t.max).color;
    }
    return ctx.deptColor.get(n.dept_id) || "#64748B";
}
