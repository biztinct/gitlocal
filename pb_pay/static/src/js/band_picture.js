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
 * Both are measured against the SCOPE's axis — the shared money axis of a
 * currency lane, or a job family's own when a reader has asked to fit to it.
 * The axis is the only ruler on this screen; a mark measured against anything
 * else lands in the wrong place the moment somebody presses "Fit to this
 * family".
 */

/** Keep a value inside a range without pretending it was never outside. */
function clamp(value, low, high) {
    return Math.max(low, Math.min(high, value));
}

/**
 * Every person on a band, gathered into bins a few pixels wide.
 *
 * @param {number[]} wages  every person's pay, in whole units of the band's
 *                          currency. Order does not matter; nothing is
 *                          dropped, and the counts always add back up to
 *                          `wages.length`.
 * @param {number} axisMax  what the right-hand end of the track is worth.
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
export function binPeople(wages, axisMax, trackPx, binPx, edges) {
    const list = Array.isArray(wages) ? wages : [];
    const top = Number(axisMax) > 0 ? Number(axisMax) : 1;
    const width = Number(trackPx) > 0 ? Number(trackPx) : 1;
    const step = Number(binPx) > 0 ? Number(binPx) : 8;
    const low = Number((edges && edges.min) || 0);
    const high = Number((edges && edges.max) || 0);
    const bins = Math.max(1, Math.ceil(width / step));
    const found = new Map();

    for (const raw of list) {
        const wage = Number(raw) || 0;
        // A person paid beyond the end of the axis sits ON the end of it and
        // is counted there (ledger GR43): the axis is honest about the tail
        // in its own note, and this picture may not lose the person.
        const x = clamp((wage / top) * width, 0, width);
        const index = clamp(Math.floor(x / step), 0, bins - 1);
        let bin = found.get(index);
        if (!bin) {
            const x0 = index * step;
            const x1 = Math.min(x0 + step, width);
            bin = {
                index, x0, x1,
                low: (x0 / width) * top,
                high: (x1 / width) * top,
                below: 0, inside: 0, above: 0, count: 0,
            };
            found.set(index, bin);
        }
        if (wage < low) {
            bin.below += 1;
        } else if (wage > high) {
            bin.above += 1;
        } else {
            bin.inside += 1;
        }
        bin.count += 1;
    }

    return Array.from(found.values()).sort((a, b) => a.index - b.index);
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
export function dodgeDots(dots, axisMax, trackPx, minGapPx) {
    const list = Array.isArray(dots) ? dots.slice() : [];
    const top = Number(axisMax) > 0 ? Number(axisMax) : 1;
    const width = Number(trackPx) > 0 ? Number(trackPx) : 1;
    const gap = Number(minGapPx) > 0 ? Number(minGapPx) : 10;
    const rows = [0, -1, 1, -2, 2];
    const lastOnRow = new Map();

    list.sort((a, b) => (Number(a.wage) || 0) - (Number(b.wage) || 0));
    const out = [];
    for (const dot of list) {
        const wage = Number(dot.wage) || 0;
        const ideal = clamp((wage / top) * width, 0, width);
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
