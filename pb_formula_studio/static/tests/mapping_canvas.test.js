/** @odoo-module **/
/**
 * Integrations Cycle 5 — the wires.
 *
 * T1 is the regression that gives this cycle its first commit: `t-on-scroll`
 * used to sit on `.mc-col`, whose child `.mc-col-body` is the actual scroller.
 * DOM `scroll` events DO NOT BUBBLE and OWL binds `t-on-scroll` as a plain,
 * non-delegated listener on that exact element — so the handler never ran, and
 * the wires stayed pinned to where the cards used to be. The bug looked like
 * "lines escaping the screen"; it was stale geometry.
 *
 * Everything else here asserts the PURE geometry/filter kernel, which is where
 * the containment rules live and where a wrong number is invisible on a
 * screenshot.
 */
import { describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
// `mountWithCleanup` starts the real service stack, and on a database with mail
// installed that stack reaches for `discuss.channel` before our component ever
// renders — "did you forget to use defineModels()?". A test-bundle-only import
// (W147); nothing in the addon itself knows mail exists.
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { MappingCanvas } from "@pb_formula_studio/js/mapping/mapping_canvas";
import {
    aggregateDocks,
    clampY,
    hubPoint,
    itemMatches,
    spreadHubs,
    wireGeometry,
    HEAD,
} from "@pb_formula_studio/js/mapping/mapping_geometry";

describe.current.tags("desktop");
defineMailModels();

// ---------------------------------------------------------------- fixtures
function items(n, prefix) {
    return Array.from({ length: n }, (_, i) => ({
        id: `${prefix}${i}`,
        label: `${prefix} field ${i}`,
        sublabel: `${prefix}.path.${i}`,
        meta: { col: `C${i}` },
    }));
}

function props(over = {}) {
    return {
        leftItems: items(40, "L"),
        rightItems: items(20, "R"),
        wires: [
            { id: "w1", leftId: "L0", rightId: "R0", state: "accepted" },
            { id: "w2", leftId: "L30", rightId: "R10", state: "suggested", confidence: 0.9 },
        ],
        leftTitle: "FROM — test",
        rightTitle: "TO — test",
        canEdit: true,
        ...over,
    };
}

// ============================================================ T1 — the bug
test("scroll does not bubble — which is why the old binding could never fire", () => {
    // The pre-fix code bound `t-on-scroll` to `.mc-col`, the PARENT of the
    // scroller. This is that arrangement, reduced to two divs. It is kept as a
    // permanent test because the failure was invisible: no error, no warning,
    // just wires drawn to last frame's coordinates.
    const parent = document.createElement("div");
    const child = document.createElement("div");
    parent.appendChild(child);
    document.body.appendChild(parent);
    let onParent = 0, onChild = 0;
    parent.addEventListener("scroll", () => { onParent++; });
    child.addEventListener("scroll", () => { onChild++; });
    child.dispatchEvent(new Event("scroll"));      // how the browser fires it: no bubbling
    expect(onChild).toBe(1);
    expect(onParent).toBe(0);                      // …the whole life of `onColScroll`
    parent.remove();
});

test("a scroll on .mc-col-body triggers exactly one coalesced recompute", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, { props: props() });
    await animationFrame();

    const body = document.querySelector(".mc-col.left .mc-col-body");
    expect(body).not.toBe(null);

    const before = canvas._recomputes;
    // three scrolls inside one frame — the rAF guard must fold them into one
    body.dispatchEvent(new Event("scroll"));
    body.dispatchEvent(new Event("scroll"));
    body.dispatchEvent(new Event("scroll"));
    expect(canvas._recomputes).toBe(before);      // nothing synchronous
    await animationFrame();
    expect(canvas._recomputes).toBe(before + 1);  // …and exactly one after
});

test("the right column's scroller is bound too", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, { props: props() });
    await animationFrame();
    const body = document.querySelector(".mc-col.right .mc-col-body");
    const before = canvas._recomputes;
    body.dispatchEvent(new Event("scroll"));
    await animationFrame();
    expect(canvas._recomputes).toBe(before + 1);
});

test("a numeric item id is not a different id from its data-id string", async () => {
    // Found on the owner's own abm board. `dataset.id` is ALWAYS a string, and
    // the API adapter's right items are integers (`183`) while its left items
    // are strings (`f:account_number`). The old code interpolated the id into a
    // CSS attribute selector, which stringifies for free; a Map does not, and
    // `has(183)` against the key `"183"` misses in silence — on screen it read
    // as "this wire's target was filtered away", which was a lie.
    const canvas = await mountWithCleanup(MappingCanvas, {
        props: props({
            rightItems: [{ id: 183, label: "Employee Code", sublabel: "EMPLOYEECODE" },
                         { id: 210, label: "Employee Name", sublabel: "EMPLOYEENAME" }],
            wires: [{ id: "w1", leftId: "L0", rightId: 183, state: "accepted" }],
        }),
    });
    await animationFrame();
    const { R } = canvas._indexes();
    expect(R.has("183")).toBe(true);
    expect(canvas.ui.gone).toBe(0);
    expect(canvas.hiddenWires("right")).toBe(0);
    // and the jump has to find the same card by the same rule
    const body = document.querySelector(".mc-col.right .mc-col-body");
    expect(canvas._itemEl(body, 183)).not.toBe(null);
    expect(canvas._itemEl(body, "183")).not.toBe(null);
});

// =================================================== T5 — the wire geometry
test("control points share the endpoint Y, so a wire leaves and arrives flat", () => {
    const g = wireGeometry(100, 50, 400, 300);
    // M sx sy C c1 sy c2 ty basex ty
    const m = g.d.match(/^M ([\d.-]+) ([\d.-]+) C ([\d.-]+) ([\d.-]+) ([\d.-]+) ([\d.-]+) ([\d.-]+) ([\d.-]+)$/);
    expect(m).not.toBe(null);
    const [, sx, sy, , c1y, , c2y, basex, ey] = m.map(Number);
    expect(sx).toBe(100);
    expect(sy).toBe(50);
    expect(c1y).toBe(50);     // first control point rides the SOURCE y
    expect(c2y).toBe(300);    // second rides the TARGET y
    expect(ey).toBe(300);
    expect(basex).toBe(400 - HEAD);   // the head's 11px is reserved on the path
});

test("the arrowhead apex is exactly the wire tip", () => {
    const g = wireGeometry(100, 50, 400, 300);
    const [apex] = g.head.split(" ");
    expect(apex).toBe("400,300");
    // and it is a triangle, not a rotated marker
    expect(g.head.split(" ").length).toBe(3);
});

test("a right-to-left wire reserves its head on the other side", () => {
    const g = wireGeometry(400, 50, 100, 300);
    expect(g.d.endsWith(`${100 + HEAD} 300`)).toBe(true);
    expect(g.head.startsWith("100,300")).toBe(true);
});

test("the hub sits ON the curve at t=0.5", () => {
    const g = wireGeometry(100, 50, 400, 300);
    const p = hubPoint(100, 50, 400, 300);
    // y at t=.5 of a curve whose control points share endpoint Ys is the mean
    expect(p.y).toBe(175);
    expect(p.x).toBeGreaterThan(100);
    expect(p.x).toBeLessThan(400);
    expect(g.hx).toBe(p.x);
});

// ================================================= T2/T3 — containment rules
test("clampY parks an out-of-band endpoint on the band edge and says so", () => {
    expect(clampY(150, 100, 400)).toEqual({ y: 150, docked: 0 });
    expect(clampY(40, 100, 400)).toEqual({ y: 100, docked: -1 });    // above
    expect(clampY(900, 100, 400)).toEqual({ y: 400, docked: 1 });    // below
});

test("docks aggregate per column edge, never one chip per wire", () => {
    const geom = [
        { id: "a", dockL: -1, dockR: 0, state: "accepted" },
        { id: "b", dockL: -1, dockR: 0, state: "accepted" },
        { id: "c", dockL: -1, dockR: 0, state: "suggested" },
        { id: "d", dockL: 1, dockR: 0, state: "accepted" },
        { id: "e", dockL: 0, dockR: 1, state: "accepted" },
        { id: "f", dockL: 0, dockR: 0, state: "accepted" },
    ];
    const docks = aggregateDocks(geom);
    expect(docks.length).toBe(3);
    const up = docks.find((d) => d.side === "left" && d.dir === -1);
    expect(up.count).toBe(3);
    expect(up.sug).toBe(1);
    // ALL of them, not ANY of them — a mixed pile is not "suggested"
    expect(up.amber).toBe(false);
    expect(up.ids).toEqual(["a", "b", "c"]);
    const down = docks.find((d) => d.side === "left" && d.dir === 1);
    expect(down.count).toBe(1);
    expect(down.amber).toBe(false);
    expect(docks.find((d) => d.side === "right" && d.dir === 1).count).toBe(1);
});

test("a dock chip never names a kind the pile is not entirely made of", () => {
    // found on the live 200x40 stress board: 51 wires parked below, one of them
    // a suggestion, and the chip read "51 suggested below"
    const mixed = aggregateDocks([
        { id: "a", dockL: 1, dockR: 0, state: "accepted" },
        { id: "b", dockL: 1, dockR: 0, state: "accepted" },
        { id: "c", dockL: 1, dockR: 0, state: "suggested" },
    ])[0];
    expect(mixed.amber).toBe(false);
    const allSug = aggregateDocks([
        { id: "a", dockL: 1, dockR: 0, state: "suggested" },
        { id: "b", dockL: 1, dockR: 0, state: "suggested" },
    ])[0];
    expect(allSug.amber).toBe(true);
    expect(allSug.sug).toBe(2);
});

test("a wire with both ends in view produces no chip at all", () => {
    expect(aggregateDocks([{ id: "x", dockL: 0, dockR: 0, state: "accepted" }])).toEqual([]);
});

// ======================================================= T7 — search matching
test("search matches label, code and sample — not just the label", () => {
    const it = { label: "Basic Salary", sublabel: "employee.basic_salary",
                 sample: "12,500,000", meta: { col: "BASIC" } };
    expect(itemMatches(it, "basic")).toBe(true);        // label
    expect(itemMatches(it, "BASIC")).toBe(true);        // case-insensitive code
    expect(itemMatches(it, "basic_salary")).toBe(true); // path
    expect(itemMatches(it, "12,500")).toBe(true);       // sample
    expect(itemMatches(it, "")).toBe(true);             // empty query matches all
    expect(itemMatches(it, "pension")).toBe(false);
});

test("search tolerates items with no sublabel, sample or meta", () => {
    expect(itemMatches({ label: "Net" }, "net")).toBe(true);
    expect(itemMatches({ label: "Net" }, "gross")).toBe(false);
    expect(itemMatches({}, "x")).toBe(false);
});

// ============================================ Cycle 6 — provenance on a card
//
// `provChip` decides what a source card admits about itself. Every branch here
// fails SILENTLY if it is wrong: a missing chip is a card that looks like it
// came from the vendor, which is the exact defect this cycle closed — 206
// `hr.employee` columns printed under "FROM — ZOHO PEOPLE (ABM)".
// C7 WP-1: the fallback chip names THIS PRODUCT. `prov`/`tone` keep the value
// `odoo` because they are the server's vocabulary and a CSS class — neither is
// a string an end user reads — but the label and the hint are, and they say
// Payobook. The assertion on the label doubles as the regression guard: it is
// the one place a future edit could put the platform's name back on screen.
test("a delivered field wears no chip, and a fallback field says whose it is", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, { props: props() });
    expect(canvas.provChip({ prov: "live" })).toBe(null);
    expect(canvas.provChip({ prov: "odoo" }).label).toBe("Payobook field");
    expect(canvas.provChip({ prov: "odoo" }).tone).toBe("odoo");
    const hint = canvas.provChip({ prov: "odoo" }).hint;
    expect(hint.includes("Payobook")).toBe(true);
    expect(/\bOdoo\b/.test(hint)).toBe(false);
});

test("expected, computed and drift are three different sentences", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, { props: props() });
    const expected = canvas.provChip({ prov: "catalog", provKind: "feed" });
    expect(expected.label).toBe("expected");
    expect(expected.tone).toBe("exp");

    const computed = canvas.provChip({ prov: "catalog", provKind: "computed" });
    expect(computed.label).toBe("computed");
    expect(computed.tone).toBe("calc");

    // Drift outranks both: a catalogue field the feed HAS run and did not send
    // is the one case that is a warning, and it must not be softened into
    // "expected" merely because the row came from the catalogue.
    const drift = canvas.provChip({ prov: "catalog", provKind: "feed", drift: true });
    expect(drift.label).toBe("not sent");
    expect(drift.tone).toBe("warn");
});

test("an adapter that sends no provenance renders exactly as it did before", async () => {
    // Four of the five boards (import, employee, scheme, cycle) never carried
    // `prov`. `undefined` must fall through to no chip rather than to a chip
    // reading "undefined" — the failure would be on every card of four boards.
    const canvas = await mountWithCleanup(MappingCanvas, { props: props() });
    expect(canvas.provChip({ label: "Basic" })).toBe(null);
    expect(canvas.provChip(null)).toBe(null);
    expect(canvas.provChip(undefined)).toBe(null);
});

// ==================================== Cycle 7 — one gesture, both ends home
//
// Cycle 5's answer to "take me to the other end of this wire" was a `‹` and a
// `›` on every hub, and its report records both as working (T4). They did —
// one end at a time, which on a 200-row column means the FIRST end has scrolled
// away by the time the second arrives. The reader never saw the connection.
// These tests replace that record deliberately: the arrows are gone, and what
// stands in their place is asserted here rather than described in prose.
//
// `_recompute` is stubbed and `ui.geom` written directly wherever the MARKUP is
// the thing under test. The board only builds geometry from real rects, and a
// DOM assertion that passes because nothing rendered is a gate that cannot fail
// (W127) — forcing the state is what makes "the arrow zones are absent" a claim
// about the template instead of about the fixture's height.
function forceGeom(canvas, over = {}) {
    canvas._recompute = () => {};
    canvas.ui.geom = [{
        id: "w1", leftId: "L0", rightId: "R0", state: "accepted",
        d: "M 0 0 C 10 0 20 40 30 40", head: "30,40 19,34 19,46",
        hx: 120, hy: 90, sx: 0, tx: 240, y1: 0, y2: 40,
        dockL: 0, dockR: 0, hiddenL: false, hiddenR: false,
        transform: { type: "multiply", value: 2 },
        ...over,
    }];
}

test("the hub carries meaning only — the ‹ › navigation zones are gone", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, { props: props() });
    forceGeom(canvas);
    canvas.ui.selWire = "w1";              // hubVisible() without a pointer
    await animationFrame();

    // the precondition, asserted rather than assumed
    expect(document.querySelectorAll(".mc-hub").length).toBe(1);
    // …and the removal
    expect(document.querySelectorAll(".mc-hub__z").length).toBe(0);
    // what the pill still has to be able to say
    expect(document.querySelectorAll(".mc-hub .mc-tf-chip").length).toBe(1);
    expect(document.querySelector(".mc-hub").getAttribute("title"))
        .toBe("Double-click to bring both ends into view");
});

test("a suggestion keeps its confidence and both verbs after the zones went", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, { props: props() });
    forceGeom(canvas, { state: "suggested", confidence: 0.92, transform: null });
    canvas.ui.selWire = "w1";
    await animationFrame();
    expect(document.querySelectorAll(".mc-hub__z").length).toBe(0);
    expect(document.querySelector(".mc-hub .mc-conf").textContent).toBe("92%");
    expect(document.querySelectorAll(".mc-hub .mc-b-ok").length).toBe(1);
    expect(document.querySelectorAll(".mc-hub .mc-b-x").length).toBe(1);
});

test("double-click centres BOTH ends and rings both cards", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, { props: props() });
    forceGeom(canvas);
    // start from a scroll position where neither end is where it will end up
    const lbody = document.querySelector(".mc-col.left .mc-col-body");
    const rbody = document.querySelector(".mc-col.right .mc-col-body");
    lbody.scrollTop = 400;
    rbody.scrollTop = 300;

    canvas.centreBoth(canvas.ui.geom[0]);
    await animationFrame();

    expect(canvas.ui.selWire).toBe("w1");
    expect(canvas.ui.reveal).toBe(null);
    // BOTH, which is the entire point — Cycle 5 could only ever light one
    expect(canvas.ui.flash.left).toBe("L0");
    expect(canvas.ui.flash.right).toBe("R0");
    expect(canvas.isFlashing("left", "L0")).toBe(true);
    expect(canvas.isFlashing("right", "R0")).toBe(true);
    expect(canvas.isFlashing("left", "L1")).toBe(false);
});

test("an end at the very top of its list scrolls as close as it can, and still rings", async () => {
    // `offsetTop - (clientHeight - offsetHeight)/2` is NEGATIVE for the first
    // card in a list. `Math.max(0, …)` is what turns "cannot be centred" into
    // "scrolled as far as it goes" rather than into a refusal — the honest edge
    // case, and the one a reader hits on every board's first wire.
    const canvas = await mountWithCleanup(MappingCanvas, { props: props() });
    forceGeom(canvas);
    const lbody = document.querySelector(".mc-col.left .mc-col-body");
    // the ASKED-FOR offset, not the resulting scrollTop: `behavior: "smooth"`
    // means the property has not moved yet when the next frame runs, and
    // asserting on it would be asserting on the engine's animation clock.
    const asked = [];
    lbody.scrollTo = (opt) => asked.push(opt.top);

    canvas.centreBoth(canvas.ui.geom[0]);
    await animationFrame();
    expect(canvas.ui.flash.left).toBe("L0");
    expect(asked.length).toBe(1);
    expect(asked[0]).toBe(0);          // clamped, not negative, not refused
});

test("an end hidden by a filter is SAID, not silently un-filtered", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, { props: props() });
    forceGeom(canvas, { hiddenL: true });
    canvas.ui.q.left = "nothing-matches-this";
    canvas.ui.qa.left = "nothing-matches-this";

    canvas.centreBoth(canvas.ui.geom[0]);
    await animationFrame();

    // the refusal is visible…
    expect(canvas.ui.reveal.id).toBe("w1");
    expect(canvas.ui.reveal.sides).toEqual(["left"]);
    expect(canvas.revealText)
        .toBe("The source end of this wire is hidden by this column's filter.");
    // …the reader's search is still there…
    expect(canvas.ui.qa.left).toBe("nothing-matches-this");
    // …and the end that IS reachable was still centred, so the gesture never
    // looks like it did nothing (W40)
    expect(canvas.ui.flash.right).toBe("R0");
    expect(canvas.ui.flash.left).toBe(null);
});

test("both ends behind filters is one sentence, not two", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, { props: props() });
    forceGeom(canvas, { hiddenL: true, hiddenR: true });
    canvas.centreBoth(canvas.ui.geom[0]);
    expect(canvas.ui.reveal.sides).toEqual(["left", "right"]);
    expect(canvas.revealText)
        .toBe("Both ends of this wire are hidden by the column filters.");
});

test("the reveal verb clears only the filters that were hiding an end", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, { props: props() });
    forceGeom(canvas, { hiddenL: true });
    canvas.ui.qa.left = "zzz"; canvas.ui.q.left = "zzz"; canvas.ui.f.left = "mapped";
    canvas.ui.qa.right = "R1"; canvas.ui.q.right = "R1";

    canvas.centreBoth(canvas.ui.geom[0]);
    canvas.revealBoth();
    await animationFrame();
    await animationFrame();

    expect(canvas.ui.qa.left).toBe("");
    expect(canvas.ui.f.left).toBe("all");
    expect(canvas.ui.reveal).toBe(null);
    // the OTHER column's search was never the problem and is left alone
    expect(canvas.ui.qa.right).toBe("R1");
});

test("clearing a column's filter by hand retires the half of the bar it disproved", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, { props: props() });
    forceGeom(canvas, { hiddenL: true, hiddenR: true });
    canvas.centreBoth(canvas.ui.geom[0]);
    expect(canvas.ui.reveal.sides.length).toBe(2);
    canvas.clearFilters("left");
    expect(canvas.ui.reveal.sides).toEqual(["right"]);
    canvas.clearFilters("right");
    expect(canvas.ui.reveal).toBe(null);
});

test("Enter on a selected wire is the keyboard twin of the double-click", async () => {
    // A gesture reachable by exactly one input device is not reachable. `‹ ›`
    // had `←`/`→`; the double-click has Enter, and the transform editor moves
    // to `t` to make room for it.
    const canvas = await mountWithCleanup(MappingCanvas, { props: props() });
    forceGeom(canvas);
    canvas.ui.selWire = "w1";

    canvas.onKeydown({ key: "Enter", preventDefault() {}, stopPropagation() {},
                       target: { tagName: "DIV" } });
    await animationFrame();
    expect(canvas.ui.flash.left).toBe("L0");
    expect(canvas.ui.flash.right).toBe("R0");
    expect(canvas.ui.tfOpen).toBe(null);

    canvas.onKeydown({ key: "t", preventDefault() {}, stopPropagation() {},
                       target: { tagName: "DIV" } });
    expect(canvas.ui.tfOpen).toBe("w1");
});

test("the single-ended jump survives, because nothing was ever wrong with it", async () => {
    // Dock chips and `←`/`→` still visit ONE end. The gesture that changed is
    // the wire's, not theirs.
    const canvas = await mountWithCleanup(MappingCanvas, { props: props() });
    forceGeom(canvas);
    canvas.jumpTo("right", canvas.ui.geom[0]);
    await animationFrame();
    expect(canvas.ui.flash.right).toBe("R0");
    expect(canvas.ui.flash.left).toBe(null);
});

test("the collision window shrank with the pill it describes", () => {
    // Two hubs 100px apart horizontally do not contend for space now the `‹ ›`
    // zones are gone — the widest pill left is ~88px. Spreading them would push
    // one off its own wire, which is the defect spreadHubs exists to prevent.
    const far = [{ id: "a", hx: 0, hy: 100 }, { id: "b", hx: 100, hy: 104 }];
    spreadHubs(far);
    expect(far[1].hy).toBe(104);

    // …and two that genuinely overlap are still pushed apart, by at least the
    // pill's own height.
    const near = [{ id: "a", hx: 0, hy: 100 }, { id: "b", hx: 30, hy: 104 }];
    spreadHubs(near);
    expect(near[1].hy - near[0].hy >= 28).toBe(true);
});
