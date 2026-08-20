/** @odoo-module **/
/**
 * Integrations Cycle 5 — the pure kernel behind the mapping wires.
 *
 * Everything here is numbers in, numbers out: no DOM, no OWL, no state. That is
 * deliberate. The containment rules — where a wire is allowed to end, when it
 * has to admit it is pointing off-screen, how many chips that becomes — are the
 * kind of arithmetic whose mistakes are invisible on a screenshot and obvious
 * in a unit test, and the previous cycle's version of them lived inline in a
 * component that could only be tested by looking at it.
 *
 * The curve form is lifted from the Formula Engine's dependency arrows
 * (`formula_studio.js` `_arrow`), which is the quality bar the owner pointed
 * at: both control points share their endpoint's Y, so the wire LEAVES the
 * source horizontally and ARRIVES at the target horizontally. That is what
 * separates a connection from a diagonal scratch — and it is also what lets the
 * arrowhead be a hand-placed, unrotated triangle instead of an SVG `<marker>`.
 * The Formula Engine is not refactored to import this (its behaviour must stay
 * byte-identical); the geometry is re-expressed, not shared.
 */

/** Pixels reserved at the tip for the arrowhead. */
export const HEAD = 11;
/** Half-height of the arrowhead triangle. */
export const HEAD_H = 6;

/**
 * The wire between two points, as SVG.
 *
 * @param {number} sx  source x (the left card's outer edge)
 * @param {number} sy  source y
 * @param {number} tx  target x (the tip — where the arrow POINTS, not where the stroke stops)
 * @param {number} ty  target y
 * @returns {{d: string, head: string, basex: number, hx: number, hy: number}}
 */
export function wireGeometry(sx, sy, tx, ty) {
    const rtl = tx < sx;                       // pointing left?
    const basex = tx + (rtl ? HEAD : -HEAD);
    const dx = basex - sx;
    const c1 = sx + dx * 0.45;
    const c2 = sx + dx * 0.55;
    const p = hubPoint(sx, sy, tx, ty);
    return {
        d: `M ${sx} ${sy} C ${c1} ${sy} ${c2} ${ty} ${basex} ${ty}`,
        head: `${tx},${ty} ${basex},${ty - HEAD_H} ${basex},${ty + HEAD_H}`,
        basex,
        hx: p.x,
        hy: p.y,
    };
}

/**
 * The point at t=0.5 ON the curve — where the hub pill hangs.
 *
 * The old canvas used the chord midpoint, which drifts off the stroke on any
 * wire with a real vertical run: the badge floated in white space next to its
 * own line. This is the actual Bézier midpoint, which for this curve family
 * simplifies to (P0 + 3P1 + 3P2 + P3)/8 in x and the plain mean in y.
 */
export function hubPoint(sx, sy, tx, ty) {
    const rtl = tx < sx;
    const basex = tx + (rtl ? HEAD : -HEAD);
    const dx = basex - sx;
    const c1 = sx + dx * 0.45;
    const c2 = sx + dx * 0.55;
    return { x: (sx + 3 * c1 + 3 * c2 + basex) / 8, y: (sy + ty) / 2 };
}

/**
 * Park a Y inside a column's visible band.
 *
 * `docked` is the DIRECTION it had to travel to get back in: -1 above the band,
 * +1 below, 0 already inside. A wire never simply disappears and never points
 * at a card that is not there — it ends on the edge, and the direction is what
 * the dock chip is made of.
 */
export function clampY(y, top, bottom) {
    if (y < top) { return { y: top, docked: -1 }; }
    if (y > bottom) { return { y: bottom, docked: 1 }; }
    return { y, docked: 0 };
}

/**
 * One chip per column edge, not one per wire.
 *
 * The reference renderer draws a 4px dot at each parked endpoint. That is right
 * for three arrows and wrong for fifty: on a 200-field connector the dots pile
 * into a smear that says nothing. So parked endpoints on the same edge of the
 * same column collapse into a single counted chip — "▲ 3 above" — which is a
 * sentence rather than a texture, and is clickable.
 */
export function aggregateDocks(geom) {
    const by = new Map();
    const push = (side, dir, g) => {
        if (!dir) { return; }
        const key = `${side}${dir}`;
        let d = by.get(key);
        if (!d) {
            d = { key, side, dir, count: 0, sug: 0, filtered: 0, ids: [] };
            by.set(key, d);
        }
        d.count++;
        d.ids.push(g.id);
        if (g.state === "suggested") { d.sug++; }
        if ((side === "left" ? g.hiddenL : g.hiddenR)) { d.filtered++; }
    };
    for (const g of geom) {
        push("left", g.dockL, g);
        push("right", g.dockR, g);
    }
    // `amber` is ALL of them, not ANY of them. A chip over 51 parked wires of
    // which one is a suggestion used to read "51 suggested below", which is a
    // lie told in the same breath as the honest count beside it.
    return [...by.values()].map((d) => ({ ...d, amber: d.sug === d.count }));
}

/**
 * Does this item match a search query?
 *
 * Label, code (`meta.col`), path (`sublabel`) and sample value all count — with
 * 200 source fields the thing a person remembers is as often the value they saw
 * in the sample line as the name somebody's HR system chose.
 */
export function itemMatches(item, query) {
    const q = (query || "").trim().toLowerCase();
    if (!q) { return true; }
    if (!item) { return false; }
    const hay = [item.label, item.sublabel, item.sample,
                 item.meta && item.meta.col, item.group];
    for (const h of hay) {
        if (h && String(h).toLowerCase().includes(q)) { return true; }
    }
    return false;
}

/**
 * Nudge overlapping hubs apart, vertically, in place.
 *
 * Two wires that cross near their midpoints used to stack two pills at exactly
 * the same coordinate — the top one winning every click. Sorting by Y and
 * pushing each hub below the last one it collides with is the cheapest fix that
 * keeps a hub near its own wire (the cap keeps it from wandering off the line).
 *
 * @param {Array} geom  entries carrying {hx, hy}
 */
export function spreadHubs(geom, minGap = 26, xWindow = 130, cap = 34) {
    const placed = [];
    for (const g of [...geom].sort((a, b) => a.hy - b.hy)) {
        let y = g.hy;
        for (const p of placed) {
            if (Math.abs(p.hx - g.hx) > xWindow) { continue; }
            const gap = y - p.hy;
            if (gap >= 0 && gap < minGap) { y = p.hy + minGap; }
        }
        const shift = Math.max(-cap, Math.min(cap, y - g.hy));
        g.hy += shift;
        placed.push(g);
    }
    return geom;
}
