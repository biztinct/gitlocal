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
 * The air between a card's edge and the tip of the arrow that points at it.
 *
 * JOURNEY J8 D2 — this used to be a bare `+ 4` / `- 4` in the canvas, and the
 * number it has to be compared against lives in a stylesheet, so nothing ever
 * compared them.
 */
export const ANCHOR_GAP = 4;

/**
 * The horizontal padding a column body reserves beside its cards — the band a
 * wire's arrowhead is drawn INTO.
 *
 * JOURNEY J8 D2, and the whole of it is one inequality. An arrowhead pointing
 * at a left-hand card is a triangle spanning `cardRight + ANCHOR_GAP` to
 * `cardRight + ANCHOR_GAP + HEAD` — 15px — and `.mc-col-body` used to give it
 * **14px** of padding. One pixel short, which does not sound like a defect until
 * you ask what is in the sixteenth pixel: the column's SCROLLBAR, which is part
 * of `.mc-cols` (`z-index: 2`) and therefore paints OVER `.mc-wires`
 * (`z-index: 1`). Measured live on abm at 1440 before the fix: the head's
 * layout box ran 375→386, its painted pixels stopped at 384, and the flat BASE
 * of the triangle — its widest, most recognisable edge — was the part that was
 * gone. Not clipped by `.mc-board`; occluded by the column layer.
 *
 * So the padding is now a function of the arrowhead rather than a round number
 * that happened to be close, with 3px of air so that a sub-pixel layout or a
 * wider platform scrollbar cannot eat it back. `mapping.scss` sets the same
 * number and a test pins the two together — the previous arrangement was two
 * independent constants that had to agree and had no way to.
 */
export const WIRE_GUTTER = ANCHOR_GAP + HEAD + 3;      // 18

/**
 * Where several wires arriving at ONE card should land — JOURNEY J8.
 *
 * A contract-component card is the destination of every flagged column in the
 * scheme, and abm has twenty of them today. Twenty curves converging on one
 * point is a knot: you cannot tell which wire is which, hovering picks whichever
 * stroke happens to be on top, and the count is unreadable. So the arrival
 * points are combed down the card's own edge instead.
 *
 * Two properties are deliberate:
 *
 *   * the comb is BOUNDED BY THE CARD. `step` shrinks so that N points always
 *     fit between `pad` and `height - pad`, which means an endpoint never leaves
 *     the card it claims to end on however many wires arrive — the invariant
 *     MJ30's harness measures, restated for a segment rather than a point;
 *   * it does nothing at all for `n <= 1`, so every board that has never had a
 *     pile-up gets byte-identical geometry.
 *
 * Returns the offsets from the card's CENTRE, in slot order.
 */
export const ARRIVAL_GAP = 9;
export const ARRIVAL_PAD = 7;

export function combOffsets(n, height, gap = ARRIVAL_GAP, pad = ARRIVAL_PAD) {
    if (!(n > 1)) { return [0]; }
    const room = Math.max(0, (height || 0) - 2 * pad);
    const step = Math.min(gap, room / (n - 1));
    const out = [];
    for (let k = 0; k < n; k++) { out.push((k - (n - 1) / 2) * step); }
    return out;
}

/**
 * The wire between two points, as SVG.
 *
 * @param {number} sx  source x (the left card's outer edge)
 * @param {number} sy  source y
 * @param {number} tx  target x (the tip — where the arrow POINTS, not where the stroke stops)
 * @param {number} ty  target y
 * @param {boolean} [bidi]  JOURNEY J3 S1 — draw a SECOND arrowhead at the source
 *   end, for a board whose rows genuinely run both ways (Employee & contract: the
 *   same row writes the record on import and is read back on a pay run). Opt-in
 *   and defaulted off, so every existing caller gets a byte-identical `d` and
 *   `head`: `headBack` is simply absent when it is not asked for, and the one
 *   thing that changes when it IS asked for — the stroke starting HEAD px in, so
 *   the curve does not run under its own arrowhead — happens only on that branch.
 * @returns {{d: string, head: string, headBack?: string, basex: number, hx: number, hy: number}}
 */
export function wireGeometry(sx, sy, tx, ty, bidi = false) {
    const rtl = tx < sx;                       // pointing left?
    const basex = tx + (rtl ? HEAD : -HEAD);
    const dx = basex - sx;
    const c1 = sx + dx * 0.45;
    const c2 = sx + dx * 0.55;
    const p = hubPoint(sx, sy, tx, ty);
    const startx = bidi ? sx + (rtl ? -HEAD : HEAD) : sx;
    const out = {
        d: `M ${startx} ${sy} C ${c1} ${sy} ${c2} ${ty} ${basex} ${ty}`,
        head: `${tx},${ty} ${basex},${ty - HEAD_H} ${basex},${ty + HEAD_H}`,
        basex,
        hx: p.x,
        hy: p.y,
    };
    if (bidi) {
        out.headBack = `${sx},${sy} ${startx},${sy - HEAD_H} ${startx},${sy + HEAD_H}`;
    }
    return out;
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
 * The height of the strip a column reserves at each end for its dock chips —
 * JOURNEY J7 D1.
 *
 * A dock chip used to be placed AT the clamp band edge (`bandTop`/`bandBot`),
 * which is a point INSIDE the column's scrollport: exactly where the first and
 * the last visible card sit. `.mc-docks` paints at `z-index: 4` over
 * `.mc-cols`' 2, so the chip covered that card's name row — measured live on
 * abm at 167.9 × 23.8px over "Last Working Day", and in the plain scrolled
 * state over all four chips at once.
 *
 * The fix is a reserved strip rather than a re-placement, and the strip is a
 * TRANSPARENT BORDER on `.mc-col-body` (`mapping.scss`), for one reason that
 * decides the whole design: a border is outside the scrollport, so content can
 * never enter it AT ANY SCROLL OFFSET — where padding is inside it and scrolls
 * away the moment the column moves, which is precisely the state ("N above")
 * in which the chip exists at all.
 *
 * It is UNCONDITIONAL on purpose. A strip that appears only when a chip does
 * moves every card by its height, which moves which cards are outside the band,
 * which changes how many chips there are — a placement that feeds back into its
 * own predicate, and the two-frame oscillation that follows is not survivable
 * on a scroll handler.
 *
 * And because a border does not change an element's BORDER BOX — `flex: 1`
 * under `box-sizing: border-box` sizes the outer box — `getBoundingClientRect`
 * on the column body returns the same numbers it always did. The clamp band is
 * measured from that rect, so **wire geometry is byte-identical**: J7 changes
 * where cards start, never where wires end (MJ30's hazard, closed by
 * construction rather than by re-measurement).
 *
 * 30px carries a 24px chip with ~3px of air either side.
 */
export const DOCK_RAIL = 30;

/**
 * Where a column's dock chips hang: the CENTRE LINE of each reserved strip.
 *
 * Deliberately NOT the clamp band, which is what J7 D1 was. The two numbers are
 * independent by design — `top`/`bottom` here are the column body's border-box
 * edges, so a chip is centred in the strip no card can occupy, while the wires
 * keep clamping wherever `BAND` says they should.
 */
export function dockAnchors(top, bottom, rail = DOCK_RAIL) {
    return { railTop: top + rail / 2, railBot: bottom - rail / 2 };
}

/**
 * One chip per column edge, not one per wire.
 *
 * The reference renderer draws a 4px dot at each parked endpoint. That is right
 * for three arrows and wrong for fifty: on a 200-field connector the dots pile
 * into a smear that says nothing. So parked endpoints on the same edge of the
 * same column collapse into a single counted chip — "▲ 3 above" — which is a
 * sentence rather than a texture, and is clickable.
 *
 * MAPFIX F1 — TWO inputs now, and the split is the phase's whole distinction.
 * `geom` is the wires that ARE drawn, parked on an edge because their card is
 * scrolled past. `suppressed` is the wires that are not drawn at all because a
 * filter excludes an end; they have no curve, no arrowhead and no hub — only a
 * direction — and they belong in the chip anyway, because "3 hidden by filter
 * above" is the sentence that stops a suppressed wire from being a lost one.
 * A caller that passes only `geom` behaves exactly as it did.
 */
export function aggregateDocks(geom, suppressed = []) {
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
    for (const s of suppressed) {
        // only the END the filter hides gets a chip. The other end of a
        // suppressed wire is on screen and perfectly visible; claiming it is
        // parked would be the counter lying in the other direction.
        if (s.hiddenL) { push("left", s.dockL, s); }
        if (s.hiddenR) { push("right", s.dockR, s); }
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
 * Insert a card at the END OF ITS OWN LANE — MAPFIX F2.
 *
 * The twin of the server's `_ec_place_in_lane` (`pb_formula_studio.py`), and it
 * lives here for the reason everything else here does: it is arithmetic over an
 * ordered list, its mistakes are invisible on a screenshot, and it had to be
 * callable from a unit test without mounting a two-thousand-line studio.
 *
 * The rule is "before the first card of a LATER lane". Two consequences, both
 * wanted: a card whose lane is already on the board joins the bottom of it and
 * grows no heading, and a card whose lane is NOT on the board lands between two
 * others — where the canvas emits a heading for it automatically, because it
 * emits one whenever `group` changes between consecutive rows.
 *
 * An item with no `lane_order` sorts last, so an adapter that never learned
 * about lanes appends exactly as it always did.
 */
export const LANE_LAST = 99;

export function laneOrderOf(item) {
    const lo = ((item && item.meta) || {}).lane_order;
    return typeof lo === "number" ? lo : LANE_LAST;
}

export function placeInLane(items, item) {
    const lo = laneOrderOf(item);
    let at = items.length;
    for (let n = 0; n < items.length; n++) {
        if (laneOrderOf(items[n]) > lo) { at = n; break; }
    }
    items.splice(at, 0, item);
    return items;
}

/**
 * Nudge overlapping hubs apart, vertically, in place.
 *
 * Two wires that cross near their midpoints used to stack two pills at exactly
 * the same coordinate — the top one winning every click. Sorting by Y and
 * pushing each hub below the last one it collides with is the cheapest fix that
 * keeps a hub near its own wire (the cap keeps it from wandering off the line).
 *
 * The three numbers describe the PILL, so they moved when it did (Integrations
 * Cycle 7, which took the `‹ ›` navigation zones out of the hub):
 *
 *   minGap  30  the pill is 28px tall — 22px of content, 2px padding either
 *               side, 1px border either side. The old 26 was already 2px under
 *               its own height, so two hubs at the minimum gap overlapped very
 *               slightly; the new value clears it with 2px to spare.
 *   xWindow 92  two hubs only contend for space if they are horizontally
 *               within a pill-width of each other. The widest pill left is a
 *               suggestion — confidence text, ✓, ✕, padding — at ~88px, down
 *               from ~180px with the arrows. A window sized for the OLD pill
 *               spreads hubs that no longer touch, and a hub pushed off its own
 *               wire is exactly the defect this function exists to prevent.
 *   cap     34  unchanged: how far a hub may travel from its curve before
 *               being on the wrong line is a property of the wires, not of the
 *               pill.
 *
 * @param {Array} geom  entries carrying {hx, hy}
 */
export function spreadHubs(geom, minGap = 30, xWindow = 92, cap = 34) {
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
