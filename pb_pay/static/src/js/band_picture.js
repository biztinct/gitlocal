/** @odoo-module **/
/**
 * The band picture's arithmetic, and nothing else.
 *
 * WHY THIS FILE HAS NO OWL IN IT
 * -----------------------------
 * Two functions decide where every person on a pay band is drawn, and getting
 * either of them slightly wrong hides a person — which is the one thing the
 * TIDY ledger's rule 12 forbids. So they live on their own, take plain
 * numbers, return plain objects, and are checked under node by
 * `pb_pay/tools/band_picture_check.mjs` without a browser, a server or a
 * database anywhere near them. Nothing here may import from `@odoo/owl` or
 * `@web/…`; the moment it does, the check stops running.
 *
 * THE TWO SHAPES
 * --------------
 * A band with a handful of people in it draws one NAMED DOT per person, and
 * dots that would touch step onto another row rather than eclipse each other
 * (`dodgeDots`). A band with more than that draws PEOPLE COLUMNS: the track is
 * cut into bins a few pixels wide, and each bin says how many people stand in
 * it and how they are placed against the band's two edges (`binPeople`).
 *
 * ONE BINNER, TWO PICTURES
 * ------------------------
 * LOOK P2 gave the calibration picture the same problem the band picture had:
 * four and a half thousand people to draw and no room to draw them one at a
 * time. It is the SAME arithmetic over a different axis (a rise in per cent
 * rather than money) with a different three-way split, so `binValues` is the
 * general form and `binPeople` is a thin wrapper over it with the
 * below/inside/above classifier written in. Two pictures, one set of promises:
 * the counts always add back up, the bins are ordered and inside the track,
 * and somebody beyond either end of the axis is placed ON that end and is
 * still counted.
 *
 * Both are measured against the SCOPE's axis — the shared money axis of a
 * currency lane, a job family's own when a reader has asked to fit to it, or
 * ONE BAND'S OWN when a reader has opened that band out. The axis is the only
 * ruler on this screen; a mark measured against anything else lands in the
 * wrong place the moment somebody presses "Fit to this family".
 *
 * AN AXIS HAS TWO ENDS
 * --------------------
 * Until LOOK P1 every function here took a single `axisMax` and assumed the
 * ruler started at zero, which is true of a lane axis and false of a band's
 * own. They now take the axis OBJECT — `{ min, max }` — and read both ends
 * through `axisSpan`, so no two of them can disagree about how wide the ruler
 * is. The change is deliberately a BREAK rather than a signature that accepts
 * both shapes: there are two callers, and a check that fails loudly beats a
 * call site that is quietly measured against the wrong ruler.
 */

/** Keep a value inside a range without pretending it was never outside. */
function clamp(value, low, high) {
    return Math.max(low, Math.min(high, value));
}

/** The low end of an axis, defaulting to zero — every lane axis starts there
 *  and a payload that has never heard of `min` must keep working. */
function axisLow(axis) {
    const low = Number(axis && axis.min);
    return Number.isFinite(low) ? low : 0;
}

/**
 * How much money an axis covers, guarded.
 *
 * Never zero and never negative, whatever it is handed, because every other
 * function here divides by it. One definition, so a mark, a bin edge and a
 * grip cannot end up measured against three slightly different rulers.
 */
export function axisSpan(axis) {
    const high = Number(axis && axis.max);
    const span = (Number.isFinite(high) ? high : 0) - axisLow(axis);
    return span > 0 ? span : 1;
}

/** The pay of the person at `share` of the way up a SORTED list, by rank —
 *  the same arithmetic the server's own lane axis uses for its tail rule. */
function atRank(sorted, share) {
    if (!sorted.length) { return 0; }
    const index = clamp(Math.floor(sorted.length * share), 0,
                        sorted.length - 1);
    return sorted[index];
}

/**
 * ANYTHING, gathered into bins a few pixels wide, and sorted into states.
 *
 * The general form of `binPeople`. It knows nothing about pay bands, money or
 * calibration: it takes values on an axis, a bin width in pixels and a
 * function that says what STATE each item is in, and hands back one entry per
 * non-empty bin.
 *
 * THE PROMISES, all four checked under node:
 *  1. Nobody is lost. Every item lands in exactly one bin, and the per-state
 *     counts always add back up to `count`, which adds back up to the number
 *     of items handed in.
 *  2. An item beyond either end of the axis is placed ON that end and counted
 *     there, rather than dropped (LOOK rule 16).
 *  3. The bins come back left to right, never overlapping, always inside the
 *     track.
 *  4. A classifier that answers something unexpected — nothing, a number, a
 *     name nobody was expecting — still keeps its item: the state is filed
 *     under `other` and the count is unchanged. A picture may not lose a
 *     person because a classifier had a bad day.
 *
 * @param {object[]} values  `[{ value, …anything else }]`. Order does not
 *                           matter to the binning; each bin keeps its items in
 *                           the order they arrived, so the drawing is
 *                           deterministic.
 * @param {object} axis      `{ min, max }` — what the two ends are worth.
 * @param {number} trackPx   how long the axis is on screen, in pixels.
 * @param {number} binPx     how long one bin is, in pixels.
 * @param {function} classify  `(item) => state`, a string.
 * @returns {object[]} one entry per NON-EMPTY bin, in order:
 *   `index`         which bin it is, counted from the low end;
 *   `x0`, `x1`      its two ends in pixels along the track;
 *   `low`, `high`   what those two ends are worth on the axis;
 *   `states`        `{ <state>: count }`, only the states that are there;
 *   `items`         the items themselves, so a picture can draw a thin bin
 *                   one mark at a time and name who is in a busy one;
 *   `count`         how many items are in the bin altogether.
 */
export function binValues(values, axis, trackPx, binPx, classify) {
    const list = Array.isArray(values) ? values : [];
    const floor = axisLow(axis);
    const span = axisSpan(axis);
    const width = Number(trackPx) > 0 ? Number(trackPx) : 1;
    const step = Number(binPx) > 0 ? Number(binPx) : 8;
    const bins = Math.max(1, Math.ceil(width / step));
    const found = new Map();

    for (const item of list) {
        const value = Number(item && item.value) || 0;
        // Beyond either end sits ON that end and is counted there (rule 16).
        const x = clamp(((value - floor) / span) * width, 0, width);
        const index = clamp(Math.floor(x / step), 0, bins - 1);
        let bin = found.get(index);
        if (!bin) {
            const x0 = index * step;
            const x1 = Math.min(x0 + step, width);
            bin = {
                index, x0, x1,
                low: floor + ((x0 / width) * span),
                high: floor + ((x1 / width) * span),
                states: {}, items: [], count: 0,
            };
            found.set(index, bin);
        }
        const answered = typeof classify === "function" ? classify(item) : null;
        const state = typeof answered === "string" && answered
            ? answered : "other";
        bin.states[state] = (bin.states[state] || 0) + 1;
        bin.items.push(item);
        bin.count += 1;
    }

    return Array.from(found.values()).sort((a, b) => a.index - b.index);
}

/**
 * Every person on a band, gathered into bins a few pixels wide.
 *
 * @param {number[]} wages  every person's pay, in whole units of the band's
 *                          currency. Order does not matter; nothing is
 *                          dropped, and the counts always add back up to
 *                          `wages.length`.
 * @param {object} axis     `{ min, max }` — what the two ends of the track are
 *                          worth. A lane axis starts at zero; a band opened
 *                          out on its own scale does not.
 * @param {number} trackPx  how wide the track is on screen, in pixels.
 * @param {number} binPx    how wide one bin is, in pixels.
 * @param {object} edges    `{ min, max }` — the band's two edges AS THEY ARE
 *                          BEING HELD, so a bin recolours while an edge is
 *                          still under the mouse.
 * @returns {object[]} one entry per NON-EMPTY bin, left to right:
 *   `x0`, `x1`      the bin's left and right edge in pixels;
 *   `low`, `high`   what those two edges are worth in money;
 *   `below`, `inside`, `above`  how many people stand on each side of the
 *                   band's edges INSIDE this bin — a bin that straddles an
 *                   edge is therefore drawn as two stacks side by side and the
 *                   colour boundary is exact;
 *   `count`         the three added together.
 */
export function binPeople(wages, axis, trackPx, binPx, edges) {
    const low = Number((edges && edges.min) || 0);
    const high = Number((edges && edges.max) || 0);
    // A person paid beyond either end of the axis sits ON that end and is
    // counted there (ledger GR43, LOOK rule 16): the axis is honest about its
    // tails in its own note, and this picture may not lose the person. A
    // zoomed axis has a LEFT tail as well as a right one. All of that lives in
    // `binValues` now, so the band picture and the calibration picture cannot
    // drift apart about it.
    const bins = binValues(
        (Array.isArray(wages) ? wages : []).map(
            (raw) => ({ value: Number(raw) || 0 })),
        axis, trackPx, binPx,
        (item) => {
            if (item.value < low) { return "below"; }
            if (item.value > high) { return "above"; }
            return "inside";
        });
    return bins.map((bin) => ({
        index: bin.index, x0: bin.x0, x1: bin.x1,
        low: bin.low, high: bin.high,
        below: bin.states.below || 0,
        inside: bin.states.inside || 0,
        above: bin.states.above || 0,
        count: bin.count,
    }));
}

/**
 * The busiest bin in a set, which every column's height is measured against.
 * Written here so the browser and the node check agree on it.
 */
export function busiestBin(bins) {
    return (bins || []).reduce((most, bin) => Math.max(most, bin.count), 0);
}

/**
 * Every person on a small band as a dot of their own, and no two touching.
 *
 * Placed in pay order. For each dot the rows are tried from the track's
 * midline outwards, and the FIRST free spot on each row is where the dot
 * would have to sit; the row that puts the dot closest to where it belongs
 * wins. That is a beeswarm rather than a queue, so a dozen people paid
 * exactly the same amount spread into a tidy block around their own figure
 * instead of into one long line to the right of it.
 *
 * The promise, checked under node: no two dots on the same row are ever
 * closer than `minGapPx`.
 *
 * @returns {object[]} the dots, each with `row` (…,-1, 0, 1,…), `x` in pixels
 *                     and `pct` across the track.
 */
export function dodgeDots(dots, axis, trackPx, minGapPx) {
    const list = Array.isArray(dots) ? dots.slice() : [];
    const floor = axisLow(axis);
    const span = axisSpan(axis);
    const width = Number(trackPx) > 0 ? Number(trackPx) : 1;
    const gap = Number(minGapPx) > 0 ? Number(minGapPx) : 10;
    const rows = [0, -1, 1, -2, 2];
    const lastOnRow = new Map();

    list.sort((a, b) => (Number(a.wage) || 0) - (Number(b.wage) || 0));
    const out = [];
    for (const dot of list) {
        const wage = Number(dot.wage) || 0;
        const ideal = clamp(((wage - floor) / span) * width, 0, width);
        let best = null;
        for (const row of rows) {
            const last = lastOnRow.has(row) ? lastOnRow.get(row) : null;
            const x = last === null ? ideal : Math.max(ideal, last + gap);
            if (best === null || x < best.x) {
                best = { row, x };
            }
        }
        lastOnRow.set(best.row, best.x);
        out.push({
            ...dot,
            row: best.row,
            x: best.x,
            pct: (best.x / width) * 100,
        });
    }
    return out;
}

/**
 * ONE BAND'S OWN MONEY SCALE — the heart of "open this band out".
 *
 * A level 2 band that runs 6.6M to 11M ₫ on a lane axis reaching 136M ₫ is
 * forty pixels of picture with five hundred people inside it. Everything in
 * that picture is correct and none of it is readable. This works out the
 * ruler that band would have if it had the track to itself, from numbers the
 * browser already holds — no server call, no stored value, nothing anybody is
 * paid changes (LOOK rule 17).
 *
 * THE RULES, in the order they are applied:
 *
 *  1. It CONTAINS THE BAND. The band's own two edges are always inside, so a
 *     band with nobody on it still draws as a range rather than as nothing.
 *  2. It is NOT FLATTENED BY ONE OUTLIER. The lane axis has a tail rule
 *     (GR43) and a zoom needs the same one at band scale: the ends are the
 *     5th and 95th person of the band's own wages, widened to the band's
 *     edges. One person paid ten times the top of the band therefore sits ON
 *     the right-hand edge and is counted, exactly as they do on the lane.
 *  3. It is PADDED by 6% of the span at each end, and then the low end is
 *     clamped at zero: money does not go negative, and a ruler whose left
 *     edge is below zero is a lie about what the picture is measuring.
 *  4. It is never DEGENERATE. A band where everybody is paid the same amount
 *     has a span of nothing at all; it is widened to a tenth either side of
 *     that amount, or to 0 … 1 when the amount is itself zero. `max` is
 *     always greater than `min`, so nothing downstream ever divides by zero.
 *  5. BOTH TAILS ARE COUNTED. Unlike a lane axis, a zoom has a left-hand tail
 *     as well as a right-hand one, and a picture that clamps people onto an
 *     edge has to say how many it put there.
 *  6. It is DETERMINISTIC. Same band in, same axis out, every time — it reads
 *     no clock, no window and no DOM, which is what lets it be checked under
 *     node beside everything else in this file.
 *
 * @param {object} band  `{ min, max, wages }` — the band's two edges and
 *                       every person on it, in whole currency units.
 * @param {object} opts  `pad` (default 0.06) and `headroom` (default 0) —
 *                       the second is the extra room a DRAG asks for, so an
 *                       edge dragged to the end of the picture can keep going
 *                       instead of hitting an invisible wall.
 * @returns {object} `{ min, max, below, above }`.
 */
export function bandAxis(band, opts) {
    const options = opts || {};
    const padShare = Number.isFinite(Number(options.pad))
        ? Math.max(0, Number(options.pad)) : 0.06;
    const headShare = Number.isFinite(Number(options.headroom))
        ? Math.max(0, Number(options.headroom)) : 0;

    const wages = (Array.isArray(band && band.wages) ? band.wages : [])
        .map((wage) => Number(wage) || 0)
        .sort((a, b) => a - b);
    const edgeA = Number(band && band.min) || 0;
    const edgeB = Number(band && band.max) || 0;

    // 1 + 2 — the band's edges, widened to the 5th and 95th person.
    let low = Math.min(edgeA, edgeB);
    let high = Math.max(edgeA, edgeB);
    if (wages.length) {
        low = Math.min(low, atRank(wages, 0.05));
        high = Math.max(high, atRank(wages, 0.95));
    }

    // 3 — pad, then the drag's headroom, then the floor at zero.
    const room = (high - low) * (padShare + headShare);
    if (room > 0) {
        low -= room;
        high += room;
    }
    if (low < 0) { low = 0; }

    // 4 — a span of nothing is widened rather than divided by.
    if (!(high > low)) {
        const value = Math.max(high, low, 0);
        if (value > 0) {
            const spread = value * (0.1 + headShare);
            low = Math.max(0, value - spread);
            high = value + spread;
        } else {
            low = 0;
            high = 1;
        }
    }

    // 5 — the two tails, counted against the ends as they finally are.
    let below = 0;
    let above = 0;
    for (const wage of wages) {
        if (wage < low) { below += 1; }
        else if (wage > high) { above += 1; }
    }
    return { min: low, max: high, below, above };
}
