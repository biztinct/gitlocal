#!/usr/bin/env node
/**
 * `node pb_pay/tools/band_picture_check.mjs`
 *
 * The band picture's arithmetic, checked without a browser, a server or a
 * database. The two functions in `band_picture.js` decide where every person
 * on a pay band is drawn; the TIDY ledger's rule 12 says none of them may be
 * lost, and a rule of that kind is worth a check that runs in a second.
 *
 * The precedent is `tools/decision_engine_check.mjs`: a pure module, a list of
 * numbered assertions, one line of output per check and a non-zero exit code
 * the moment one of them fails — and the module read off disk and handed to
 * the runtime as a data: URL, EXACTLY AS IT SHIPS. Importing the file by path
 * would make node read a `.js` beside no `package.json` as a CommonJS module
 * and find no named exports at all; going through a data: URL also means no
 * copy, no shim and no build step, so this cannot pass against a transformed
 * version of a file that is broken where it ships.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SOURCE = resolve(HERE, "..", "static", "src", "js", "band_picture.js");
const { binPeople, busiestBin, dodgeDots } = await import(
    "data:text/javascript;base64,"
    + Buffer.from(readFileSync(SOURCE, "utf8"), "utf8").toString("base64"));

let passed = 0;
const failures = [];

function check(name, ok, detail) {
    if (ok) {
        passed += 1;
        console.log(`  ok   ${name}`);
    } else {
        failures.push(`${name}${detail ? ` — ${detail}` : ""}`);
        console.log(`  FAIL ${name}${detail ? ` — ${detail}` : ""}`);
    }
}

/** A repeatable pseudo-random source, so a failure can be reproduced. */
function makeRandom(seed) {
    let state = seed >>> 0;
    return () => {
        state = (state * 1664525 + 1013904223) >>> 0;
        return state / 4294967296;
    };
}

console.log("band picture — binPeople");

// T3a — nobody is lost, whatever the numbers are.
{
    const random = makeRandom(20260908);
    let worst = null;
    for (let round = 0; round < 400; round += 1) {
        const people = Math.floor(random() * 900) + 1;
        const axis = Math.floor(random() * 90_000_000) + 1_000_000;
        const track = Math.floor(random() * 1200) + 60;
        const bin = Math.floor(random() * 14) + 3;
        const wages = [];
        for (let i = 0; i < people; i += 1) {
            // Deliberately includes wages beyond the end of the axis: those
            // people sit ON the edge and must still be counted.
            wages.push(Math.floor(random() * axis * 1.4));
        }
        const lo = Math.floor(random() * axis * 0.6);
        const hi = lo + Math.floor(random() * axis * 0.5);
        const bins = binPeople(wages, axis, track, bin, { min: lo, max: hi });
        const total = bins.reduce((sum, b) => sum + b.count, 0);
        const parts = bins.reduce(
            (sum, b) => sum + b.below + b.inside + b.above, 0);
        if (total !== wages.length || parts !== wages.length) {
            worst = `round ${round}: ${total}/${parts} of ${wages.length}`;
            break;
        }
    }
    check("T3a every person lands in exactly one bin, 400 random boards",
          worst === null, worst);
}

// T3b — a bin that straddles an edge is split exactly.
{
    // Axis 1000, track 1000px, bins 8px: one bin covers exactly 8 money units.
    // The band's low edge at 404 falls in the middle of the bin 400-408.
    const wages = [400, 401, 402, 403, 404, 405, 406, 407];
    const bins = binPeople(wages, 1000, 1000, 8, { min: 404, max: 900 });
    const bin = bins[0];
    check("T3b a bin straddling the low edge splits 4 below / 4 inside",
          bins.length === 1 && bin.below === 4 && bin.inside === 4
          && bin.above === 0,
          bins.length === 1
              ? `${bin.below}/${bin.inside}/${bin.above}` : `${bins.length} bins`);
}

{
    // The same bin straddling the HIGH edge.
    const wages = [800, 801, 802, 803, 804, 805, 806, 807];
    const bins = binPeople(wages, 1000, 1000, 8, { min: 100, max: 802 });
    const bin = bins[0];
    check("T3b a bin straddling the high edge splits 3 inside / 5 above",
          bins.length === 1 && bin.below === 0 && bin.inside === 3
          && bin.above === 5,
          bins.length === 1
              ? `${bin.below}/${bin.inside}/${bin.above}` : `${bins.length} bins`);
}

{
    // A band narrower than one bin: all three parts in one bin.
    const wages = [400, 402, 404, 406];
    const bins = binPeople(wages, 1000, 1000, 8, { min: 401, max: 405 });
    const bin = bins[0];
    check("T3b a band narrower than a bin splits into all three parts",
          bins.length === 1 && bin.below === 1 && bin.inside === 2
          && bin.above === 1,
          bins.length === 1
              ? `${bin.below}/${bin.inside}/${bin.above}` : `${bins.length} bins`);
}

// T3c — the bins are ordered, non-overlapping and inside the track.
{
    const random = makeRandom(7);
    const wages = [];
    for (let i = 0; i < 500; i += 1) {
        wages.push(Math.floor(random() * 50_000_000));
    }
    const bins = binPeople(wages, 50_000_000, 933, 8, { min: 1, max: 2 });
    let ok = true;
    for (let i = 0; i < bins.length; i += 1) {
        if (bins[i].x0 < 0 || bins[i].x1 > 933 || bins[i].x1 <= bins[i].x0) {
            ok = false;
        }
        if (i && bins[i].x0 < bins[i - 1].x1) { ok = false; }
    }
    check("T3c bins are ordered, non-overlapping and inside the track", ok);
    check("T3c the busiest bin is the largest count",
          busiestBin(bins) === bins.reduce((m, b) => Math.max(m, b.count), 0));
}

// T3d — an empty band draws nothing rather than throwing.
{
    const bins = binPeople([], 1000, 800, 8, { min: 1, max: 2 });
    check("T3d an empty band answers with no bins at all", bins.length === 0);
    check("T3d a missing wage list answers with no bins at all",
          binPeople(undefined, 1000, 800, 8, {}).length === 0);
}

console.log("band picture — dodgeDots");

// T3e — no two dots on one row are ever closer than the gap.
{
    const random = makeRandom(31337);
    let worst = null;
    for (let round = 0; round < 400 && worst === null; round += 1) {
        const people = Math.floor(random() * 24) + 1;
        const axis = Math.floor(random() * 90_000_000) + 1_000_000;
        const track = Math.floor(random() * 1200) + 60;
        const gap = Math.floor(random() * 14) + 4;
        const dots = [];
        for (let i = 0; i < people; i += 1) {
            // One in four boards makes everybody the same wage on purpose:
            // that is the case a naive dodge draws on top of itself.
            const wage = random() < 0.25
                ? Math.floor(axis * 0.5)
                : Math.floor(random() * axis);
            dots.push({ id: i, wage });
        }
        const placed = dodgeDots(dots, axis, track, gap);
        if (placed.length !== dots.length) {
            worst = `round ${round}: ${placed.length} of ${dots.length} drawn`;
            break;
        }
        const byRow = new Map();
        for (const dot of placed) {
            if (!byRow.has(dot.row)) { byRow.set(dot.row, []); }
            byRow.get(dot.row).push(dot.x);
        }
        for (const [row, xs] of byRow) {
            xs.sort((a, b) => a - b);
            for (let i = 1; i < xs.length; i += 1) {
                if (xs[i] - xs[i - 1] < gap - 1e-9) {
                    worst = `round ${round}: row ${row} has `
                        + `${xs[i] - xs[i - 1]}px < ${gap}px`;
                    break;
                }
            }
        }
    }
    check("T3e no two dots on a row are closer than the gap, 400 boards",
          worst === null, worst);
}

// T3f — every dot is drawn, and the rows stay in the five the track has.
{
    const dots = [];
    for (let i = 0; i < 24; i += 1) { dots.push({ id: i, wage: 5_000_000 }); }
    const placed = dodgeDots(dots, 10_000_000, 800, 10);
    const rows = new Set(placed.map((d) => d.row));
    check("T3f twenty-four people on the same wage are all drawn",
          placed.length === 24, `${placed.length}`);
    check("T3f and they use only the five rows the track has",
          [...rows].every((r) => r >= -2 && r <= 2), [...rows].join(","));
    check("T3f and they spread sideways rather than stacking",
          Math.max(...placed.map((d) => d.x))
          > Math.min(...placed.map((d) => d.x)));
}

// T3g — a dot's percentage matches the pixel it was placed at.
{
    const placed = dodgeDots([{ id: 1, wage: 500 }], 1000, 800, 10);
    check("T3g a lone dot sits exactly where its pay says",
          Math.abs(placed[0].x - 400) < 1e-9
          && Math.abs(placed[0].pct - 50) < 1e-9,
          `${placed[0].x}px / ${placed[0].pct}%`);
}

console.log("");
if (failures.length) {
    console.log(`${failures.length} FAILED, ${passed} passed`);
    for (const line of failures) { console.log(`  - ${line}`); }
    process.exit(1);
}
console.log(`${passed} checks passed.`);
