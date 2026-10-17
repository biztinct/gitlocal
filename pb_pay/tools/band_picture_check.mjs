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
const {
    axisSpan, bandAxis, binPeople, binValues, busiestBin, dodgeDots,
} = await import(
    "data:text/javascript;base64,"
    + Buffer.from(readFileSync(SOURCE, "utf8"), "utf8").toString("base64"));

/** Every axis this file hands the picture is an OBJECT with two ends. */
function axis(min, max) {
    return { min, max };
}

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
        const top = Math.floor(random() * 90_000_000) + 1_000_000;
        const track = Math.floor(random() * 1200) + 60;
        const bin = Math.floor(random() * 14) + 3;
        const wages = [];
        for (let i = 0; i < people; i += 1) {
            // Deliberately includes wages beyond the end of the axis: those
            // people sit ON the edge and must still be counted.
            wages.push(Math.floor(random() * top * 1.4));
        }
        const lo = Math.floor(random() * top * 0.6);
        const hi = lo + Math.floor(random() * top * 0.5);
        const bins = binPeople(wages, axis(0, top), track, bin, { min: lo, max: hi });
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
    const bins = binPeople(wages, axis(0, 1000), 1000, 8, { min: 404, max: 900 });
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
    const bins = binPeople(wages, axis(0, 1000), 1000, 8, { min: 100, max: 802 });
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
    const bins = binPeople(wages, axis(0, 1000), 1000, 8, { min: 401, max: 405 });
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
    const bins = binPeople(wages, axis(0, 50_000_000), 933, 8, { min: 1, max: 2 });
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
    const bins = binPeople([], axis(0, 1000), 800, 8, { min: 1, max: 2 });
    check("T3d an empty band answers with no bins at all", bins.length === 0);
    check("T3d a missing wage list answers with no bins at all",
          binPeople(undefined, axis(0, 1000), 800, 8, {}).length === 0);
}

console.log("band picture — dodgeDots");

// T3e — no two dots on one row are ever closer than the gap.
{
    const random = makeRandom(31337);
    let worst = null;
    for (let round = 0; round < 400 && worst === null; round += 1) {
        const people = Math.floor(random() * 24) + 1;
        const top = Math.floor(random() * 90_000_000) + 1_000_000;
        const track = Math.floor(random() * 1200) + 60;
        const gap = Math.floor(random() * 14) + 4;
        const dots = [];
        for (let i = 0; i < people; i += 1) {
            // One in four boards makes everybody the same wage on purpose:
            // that is the case a naive dodge draws on top of itself.
            const wage = random() < 0.25
                ? Math.floor(top * 0.5)
                : Math.floor(random() * top);
            dots.push({ id: i, wage });
        }
        const placed = dodgeDots(dots, axis(0, top), track, gap);
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
    const placed = dodgeDots(dots, axis(0, 10_000_000), 800, 10);
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
    const placed = dodgeDots([{ id: 1, wage: 500 }], axis(0, 1000), 800, 10);
    check("T3g a lone dot sits exactly where its pay says",
          Math.abs(placed[0].x - 400) < 1e-9
          && Math.abs(placed[0].pct - 50) < 1e-9,
          `${placed[0].x}px / ${placed[0].pct}%`);
}

console.log("band picture — an axis has two ends");

// T3h — a ruler that does not start at zero places a mark correctly.
{
    // 6M to 11M across 1000px: 8.5M is exactly halfway.
    const bins = binPeople([8_500_000], axis(6_000_000, 11_000_000), 1000, 8,
                           { min: 6_600_000, max: 11_000_000 });
    const dots = dodgeDots([{ id: 1, wage: 8_500_000 }],
                           axis(6_000_000, 11_000_000), 1000, 10);
    check("T3h a bin on an axis that starts above zero lands at the middle",
          bins.length === 1 && bins[0].x0 === 496 && bins[0].x1 === 504,
          bins.length === 1 ? `${bins[0].x0}-${bins[0].x1}` : `${bins.length}`);
    check("T3h and a dot on the same axis lands at 50%",
          Math.abs(dots[0].pct - 50) < 1e-9, `${dots[0].pct}%`);
    check("T3h and the bin's own money reads back as the money it was given",
          Math.abs(bins[0].low - 8_480_000) < 1
          && Math.abs(bins[0].high - 8_520_000) < 1,
          `${bins[0].low} … ${bins[0].high}`);
}

// T3h — the same person is drawn in TWO places on two different rulers, and
// that is the whole point of opening a band out.
{
    const lane = binPeople([8_500_000], axis(0, 136_000_000), 1000, 8,
                           { min: 6_600_000, max: 11_000_000 });
    const zoom = binPeople([8_500_000], axis(6_000_000, 11_000_000), 1000, 8,
                           { min: 6_600_000, max: 11_000_000 });
    check("T3h the lane axis and the band's own put the same person apart",
          lane[0].x0 === 56 && zoom[0].x0 === 496,
          `${lane[0].x0}px vs ${zoom[0].x0}px`);
}

// T3i — the guarded span, which every other function divides by.
{
    check("T3i axisSpan is the distance between the two ends",
          axisSpan(axis(6, 11)) === 5, `${axisSpan(axis(6, 11))}`);
    check("T3i axisSpan is never zero, negative, missing or nonsense",
          axisSpan(axis(5, 5)) === 1 && axisSpan(axis(9, 2)) === 1
          && axisSpan(undefined) === 1 && axisSpan({}) === 1
          && axisSpan(axis(null, "x")) === 1);
    check("T3i an axis with no min at all is read as starting at zero",
          axisSpan({ max: 40 }) === 40);
}

console.log("band picture — bandAxis");

// T3j — the band's own edges are always inside its own axis.
{
    const random = makeRandom(4242);
    let worst = null;
    for (let round = 0; round < 400 && worst === null; round += 1) {
        const low = Math.floor(random() * 40_000_000);
        const high = low + Math.floor(random() * 30_000_000);
        const people = Math.floor(random() * 600);
        const wages = [];
        for (let i = 0; i < people; i += 1) {
            wages.push(Math.floor(random() * 90_000_000));
        }
        const got = bandAxis({ min: low, max: high, wages });
        if (got.min > low || got.max < high || !(got.max > got.min)) {
            worst = `round ${round}: band ${low}-${high} `
                + `axis ${got.min}-${got.max}`;
        }
    }
    check("T3j a band's own edges are inside its own axis, 400 random bands",
          worst === null, worst);
}

// T3k — one huge outlier does not flatten the zoom.
{
    const wages = [];
    for (let i = 0; i < 100; i += 1) { wages.push(9_000_000 + (i * 10_000)); }
    const withOutlier = wages.concat([90_000_000]);
    const plain = bandAxis({ min: 8_000_000, max: 11_000_000, wages });
    const bent = bandAxis({ min: 8_000_000, max: 11_000_000,
                            wages: withOutlier });
    check("T3k a single ten-times outlier does not stretch the axis",
          Math.abs(bent.max - plain.max) < 1,
          `${plain.max} vs ${bent.max}`);
    check("T3k and that outlier is COUNTED on the right-hand edge",
          bent.above === 1 && bent.below === 0,
          `${bent.below} below / ${bent.above} above`);
}

// T3l — both tails, because a zoom has a left-hand one as well.
{
    const wages = [1_000_000, 2_000_000];
    for (let i = 0; i < 100; i += 1) { wages.push(9_000_000 + (i * 10_000)); }
    wages.push(80_000_000, 90_000_000, 95_000_000);
    const got = bandAxis({ min: 9_000_000, max: 10_000_000, wages });
    const drawn = binPeople(wages, got, 900, 8,
                            { min: 9_000_000, max: 10_000_000 });
    const total = drawn.reduce((sum, b) => sum + b.count, 0);
    check("T3l both tails are counted",
          got.below === 2 && got.above === 3,
          `${got.below} below / ${got.above} above`);
    check("T3l and nobody is lost: every person is still in a bin",
          total === wages.length, `${total} of ${wages.length}`);
}

// T3m — the shapes that have no width of their own.
{
    const same = bandAxis({ min: 5_000_000, max: 5_000_000,
                            wages: [5_000_000, 5_000_000, 5_000_000] });
    const one = bandAxis({ min: 7_000_000, max: 7_000_000,
                           wages: [7_000_000] });
    const none = bandAxis({ min: 6_000_000, max: 9_000_000, wages: [] });
    const zeros = bandAxis({ min: 0, max: 0, wages: [0, 0, 0] });
    const nothing = bandAxis({});
    const rubbish = bandAxis({ min: "x", max: null, wages: "no" });
    check("T3m everybody on the same wage still gets a ruler",
          same.max > same.min && same.below === 0 && same.above === 0,
          `${same.min} … ${same.max}`);
    check("T3m one person on a band of no width still gets a ruler",
          one.max > one.min, `${one.min} … ${one.max}`);
    check("T3m a band with nobody on it is still drawn on its own scale",
          none.max > none.min && none.min <= 6_000_000
          && none.max >= 9_000_000, `${none.min} … ${none.max}`);
    check("T3m a band where everybody is paid nothing answers 0 to 1",
          zeros.min === 0 && zeros.max === 1);
    check("T3m and nonsense in is still a usable ruler out",
          nothing.max > nothing.min && rubbish.max > rubbish.min);
    check("T3m the low end is never below zero",
          [same, one, none, zeros, nothing, rubbish]
              .every((got) => got.min >= 0));
}

// T3n — the same band twice is the same axis twice.
{
    const wages = [];
    const random = makeRandom(99);
    for (let i = 0; i < 500; i += 1) {
        wages.push(Math.floor(random() * 40_000_000));
    }
    const band = { min: 6_600_000, max: 11_000_000, wages };
    const first = bandAxis(band);
    const second = bandAxis({ min: band.min, max: band.max,
                             wages: wages.slice().reverse() });
    check("T3n the same band gives the same axis twice, whatever the order",
          first.min === second.min && first.max === second.max
          && first.below === second.below && first.above === second.above,
          `${first.min}-${first.max} vs ${second.min}-${second.max}`);
}

// T3o — the drag's headroom: always further to go than the picture shows.
{
    const wages = [];
    for (let i = 0; i < 200; i += 1) { wages.push(7_000_000 + (i * 20_000)); }
    const band = { min: 6_600_000, max: 11_000_000, wages };
    const shown = bandAxis(band);
    const held = bandAxis(band, { headroom: 0.3 });
    check("T3o a drag can always go beyond the end of the picture",
          held.max > shown.max && held.min <= shown.min,
          `${shown.min}-${shown.max} vs ${held.min}-${held.max}`);
    check("T3o and the headroom axis still contains the band",
          held.min <= band.min && held.max >= band.max);
}

console.log("band picture — binValues");

// T3p — the counts always add back up, whatever the classifier says.
{
    const random = makeRandom(20260909);
    let worst = null;
    const words = ["normal", "outlier", "blocked"];
    for (let round = 0; round < 400 && worst === null; round += 1) {
        const people = Math.floor(random() * 4500) + 1;
        const top = (random() * 40) + 1;
        const track = Math.floor(random() * 500) + 40;
        const bin = Math.floor(random() * 10) + 2;
        const items = [];
        for (let i = 0; i < people; i += 1) {
            // Deliberately includes values beyond BOTH ends of the axis.
            items.push({ id: i, value: (random() * top * 1.4) - (top * 0.2) });
        }
        const bins = binValues(items, axis(0, top), track, bin,
                               (item) => words[item.id % 3]);
        const total = bins.reduce((sum, b) => sum + b.count, 0);
        const byState = bins.reduce(
            (sum, b) => sum + Object.values(b.states)
                .reduce((n, v) => n + v, 0), 0);
        const held = bins.reduce((sum, b) => sum + b.items.length, 0);
        if (total !== items.length || byState !== items.length
                || held !== items.length) {
            worst = `round ${round}: ${total}/${byState}/${held} of `
                + `${items.length}`;
        }
    }
    check("T3p every value lands in one bin and every state adds back up, "
          + "400 random boards", worst === null, worst);
}

// T3q — ordered, non-overlapping, inside the track.
{
    const random = makeRandom(515);
    const items = [];
    for (let i = 0; i < 3000; i += 1) {
        items.push({ id: i, value: random() * 25 });
    }
    const bins = binValues(items, axis(0, 25), 371, 6, () => "normal");
    let ok = true;
    for (let i = 0; i < bins.length; i += 1) {
        if (bins[i].x0 < 0 || bins[i].x1 > 371 || bins[i].x1 <= bins[i].x0) {
            ok = false;
        }
        if (i && (bins[i].x0 < bins[i - 1].x1
                  || bins[i].index <= bins[i - 1].index)) {
            ok = false;
        }
    }
    check("T3q bins are ordered, non-overlapping and inside the track", ok);
}

// T3r — a value beyond either end is clamped ON and still counted.
{
    const items = [
        { id: 1, value: -40 }, { id: 2, value: 5 }, { id: 3, value: 400 },
    ];
    const bins = binValues(items, axis(0, 10), 100, 10, () => "normal");
    const total = bins.reduce((sum, b) => sum + b.count, 0);
    const first = bins[0];
    const last = bins[bins.length - 1];
    check("T3r a value beyond either end is clamped on and still counted",
          total === 3 && first.index === 0 && last.index === 9,
          `${total} counted, bins ${first.index}…${last.index}`);
}

// T3s — nothing in, nothing out, and never a throw.
{
    check("T3s an empty input answers with no bins at all",
          binValues([], axis(0, 10), 100, 8, () => "normal").length === 0);
    check("T3s and so does a missing one",
          binValues(undefined, axis(0, 10), 100, 8, () => "normal").length === 0
          && binValues(null, undefined, 0, 0, null).length === 0);
}

// T3t — a classifier that answers something unexpected loses nobody.
{
    const items = [
        { id: 1, value: 1 }, { id: 2, value: 1 }, { id: 3, value: 1 },
        { id: 4, value: 1 }, { id: 5, value: 1 },
    ];
    const bins = binValues(items, axis(0, 10), 100, 100, (item) => {
        if (item.id === 1) { return undefined; }
        if (item.id === 2) { return 7; }
        if (item.id === 3) { return ""; }
        if (item.id === 4) { return "wildcard"; }
        return "normal";
    });
    const bin = bins[0];
    const summed = Object.values(bin.states).reduce((n, v) => n + v, 0);
    check("T3t an unexpected state does not lose the person",
          bins.length === 1 && bin.count === 5 && summed === 5
          && bin.states.other === 3 && bin.states.wildcard === 1
          && bin.states.normal === 1,
          bins.length === 1 ? JSON.stringify(bin.states) : `${bins.length} bins`);
    check("T3t and no classifier at all is still five people in a bin",
          binValues(items, axis(0, 10), 100, 100)[0].count === 5);
}

// T3u — the same items in, the same bins out, in the order they arrived.
{
    const items = [
        { id: 9, value: 2 }, { id: 4, value: 2 }, { id: 7, value: 8 },
    ];
    const first = binValues(items, axis(0, 10), 100, 50, () => "normal");
    const again = binValues(items, axis(0, 10), 100, 50, () => "normal");
    check("T3u a bin keeps its items in the order they arrived",
          first[0].items.map((i) => i.id).join(",") === "9,4"
          && again[0].items.map((i) => i.id).join(",") === "9,4",
          first[0].items.map((i) => i.id).join(","));
}

// T3v — binPeople is binValues, and its own answers did not move.
{
    const wages = [400, 401, 402, 403, 404, 405, 406, 407];
    const bins = binPeople(wages, axis(0, 1000), 1000, 8,
                           { min: 404, max: 900 });
    const general = binValues(
        wages.map((w) => ({ value: w })), axis(0, 1000), 1000, 8,
        (item) => (item.value < 404 ? "below"
            : (item.value > 900 ? "above" : "inside")));
    check("T3v the wrapper's bins are the general form's bins",
          bins.length === general.length
          && bins[0].x0 === general[0].x0 && bins[0].x1 === general[0].x1
          && bins[0].below === (general[0].states.below || 0)
          && bins[0].inside === (general[0].states.inside || 0)
          && bins[0].above === (general[0].states.above || 0)
          && bins[0].count === general[0].count);
    check("T3v and it still answers with the three keys the band picture reads",
          "below" in bins[0] && "inside" in bins[0] && "above" in bins[0]
          && "low" in bins[0] && "high" in bins[0] && "index" in bins[0]);
}

console.log("");
if (failures.length) {
    console.log(`${failures.length} FAILED, ${passed} passed`);
    for (const line of failures) { console.log(`  - ${line}`); }
    process.exit(1);
}
console.log(`${passed} checks passed.`);
