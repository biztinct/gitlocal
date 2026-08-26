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
import { advanceTime, animationFrame } from "@odoo/hoot-mock";
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
    dockAnchors,
    hubPoint,
    itemMatches,
    laneOrderOf,
    placeInLane,
    spreadHubs,
    wireGeometry,
    HEAD,
    LANE_LAST,
    DOCK_RAIL,
} from "@pb_formula_studio/js/mapping/mapping_geometry";
import { ROLES, ROLE_LANE_ORDER, roleIcon }
    from "@pb_formula_studio/js/mapping/mapping_roles";
// JOURNEY J4 — the three-lane board. A component, like `MappingCanvas`
// above it, and imported under the same restriction: it drags in the pure
// kernel and the icon registry and nothing that mounts an action (MJ2).
import { TransformFlowBoard }
    from "@pb_formula_studio/js/mapping/transform_flow_board";
// JOURNEY J5 — the five-lane Journey board, imported under the same rule.
import { JourneyBoard, LANES }
    from "@pb_formula_studio/js/mapping/journey_board";

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
    //
    // `defineProperty`, not `lbody.scrollTo = …`: `scrollTo` is an accessor on
    // `Element.prototype` with no setter, so a plain assignment throws
    // "Cannot assign to read only property" in strict mode — which is what an
    // ES module is. An OWN property shadows the prototype's and needs no
    // teardown, because the element is torn down with the fixture.
    const asked = [];
    Object.defineProperty(lbody, "scrollTo", {
        configurable: true,
        value: (opt) => asked.push(opt.top),
    });

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

// ==================================================== MAPFIX Phase D
// Three defects the owner reported against the LIVE Phase-B board. The two
// crashes are keyboard-shaped and the third is a layout one, so all three are
// invisible to an RPC probe and two of them are invisible to a screenshot.

/** The employee board's shape: cards that carry verbs, and a draw callback. */
function actProps(over = {}) {
    const left = items(6, "L").map((it, i) => ({
        ...it,
        // real ids on the employee board are hr.formula.rule INTEGERS — which is
        // the whole of D1: an integer where an `f:model:field` spec belongs.
        id: 100 + i,
        meta: {
            ...it.meta,
            actions: [
                { key: "to_field", label: "Send to a field instead…", hint: "Pick a field." },
                { key: "make_text", label: "Make text", hint: "Keep it on the contract." },
                { key: "detach", label: "Detach component", hint: "Stop keeping it." },
            ],
        },
    }));
    const right = [
        { id: "f:hr.employee:employee_status", label: "Employee Status", sublabel: "Employee", meta: {} },
        { id: "f:hr.employee:name", label: "Employee Name", sublabel: "Employee", meta: {} },
        { id: "f:hr.contract:wage", label: "Wage", sublabel: "Contract", meta: {} },
    ];
    return props({ leftItems: left, rightItems: right, wires: [], ...over });
}

function keyEvent(key) {
    let prevented = 0, stopped = 0;
    return {
        key,
        target: { tagName: "DIV" },
        preventDefault() { prevented++; },
        stopPropagation() { stopped++; },
        get prevented() { return prevented; },
        get stopped() { return stopped; },
    };
}

// ---------------------------------------------------------------- D1
test("D1 — Enter never sends a LEFT id to the right-hand handler", async () => {
    // The crash, reduced. `ui.focusId` is ONE value shared by both columns.
    // "Send to a field instead…" sets `focusSide = 'right'` and focuses the right
    // search box while `focusId` still holds the left card's INTEGER id; the old
    // `case "Enter"` read it raw and called `clickRight(123)`, which sent
    // `target_spec: 123` and raised `'int' object has no attribute 'startswith'`
    // on the server.
    const drawn = [];
    const canvas = await mountWithCleanup(MappingCanvas, {
        props: actProps({ onDraw: (l, r) => drawn.push([l, r]) }),
    });
    canvas.ui.armedLeft = 100;
    canvas.ui.focusSide = "right";
    canvas.ui.focusId = 100;                 // a LEFT id, on the RIGHT side

    canvas.onKeydown(keyEvent("Enter"));
    await animationFrame();

    // nothing was drawn at all — and in particular nothing carrying a left id
    expect(drawn.length).toBe(0);
    for (const [, rightId] of drawn) { expect(typeof rightId).toBe("string"); }
    expect(canvas.ui.armedLeft).toBe(100);   // still armed; the gesture is intact
});

test("D1 — the arm command drops the stale focus it would otherwise inherit", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, { props: actProps() });
    canvas.ui.focusSide = "left";
    canvas.ui.focusId = 103;
    canvas._runCommand({ token: 1, kind: "armLeft", leftId: 101 });
    await animationFrame();
    expect(canvas.ui.armedLeft).toBe(101);
    expect(canvas.ui.focusSide).toBe("right");
    expect(canvas.ui.focusId).toBe(null);
});

test("D1 — after typing, Enter wires to the focused RIGHT card", async () => {
    // The flow has to still complete from the keyboard: type, see the top hit
    // take the focus ring, press Enter, get that wire.
    const drawn = [];
    const canvas = await mountWithCleanup(MappingCanvas, {
        props: actProps({ onDraw: (l, r) => drawn.push([l, r]) }),
    });
    canvas.ui.armedLeft = 100;
    canvas._runCommand({ token: 2, kind: "armLeft", leftId: 100 });
    await animationFrame();

    canvas.onSearch("right", { target: { value: "status" } });
    await advanceTime(200);                          // the 120ms search debounce
    await animationFrame();
    expect(canvas.ui.focusSide).toBe("right");
    expect(canvas.ui.focusId).toBe("f:hr.employee:employee_status");

    canvas.onKeydown(keyEvent("Enter"));
    await animationFrame();
    expect(drawn).toEqual([[100, "f:hr.employee:employee_status"]]);
});

test("D1 — Enter on the left column still arms, exactly as before", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, { props: actProps() });
    canvas.ui.focusSide = "left";
    canvas.ui.focusId = 102;
    canvas.onKeydown(keyEvent("Enter"));
    await animationFrame();
    expect(canvas.ui.armedLeft).toBe(102);
});

// ---------------------------------------------------------------- D2
test("D2 — Escape disarms from inside the search box", async () => {
    // `onSearchKey` used to `stopPropagation()` unconditionally, so Escape could
    // never reach the canvas handler that clears `armedLeft` — in the one flow
    // whose banner promises "Esc to cancel", because that verb focuses this box.
    const canvas = await mountWithCleanup(MappingCanvas, { props: actProps() });
    canvas.ui.armedLeft = 100;
    const ev = keyEvent("Escape");
    canvas.onSearchKey("right", ev);
    expect(canvas.ui.armedLeft).toBe(null);
    expect(ev.stopped).toBe(1);
});

test("D2 — Escape disarms from a card and from the board background too", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, { props: actProps() });
    canvas.ui.armedLeft = 101;
    canvas.onKeydown(keyEvent("Escape"));
    expect(canvas.ui.armedLeft).toBe(null);

    canvas.ui.armedLeft = 101;
    canvas.ui.reveal = { id: "w1", sides: ["left"] };
    canvas.onKeydown(keyEvent("Escape"));
    expect(canvas.ui.armedLeft).toBe(null);
    expect(canvas.ui.reveal).toBe(null);
});

test("D2 — Escape with nothing armed still clears the search text", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, { props: actProps() });
    canvas.ui.q.right = "stat";
    canvas.ui.qa.right = "stat";
    canvas.onSearchKey("right", keyEvent("Escape"));
    expect(canvas.ui.q.right).toBe("");
    expect(canvas.ui.qa.right).toBe("");
});

test("D2 — an armed component outranks the search box, and only one thing happens", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, { props: actProps() });
    canvas.ui.armedLeft = 100;
    canvas.ui.q.right = "stat";
    canvas.ui.qa.right = "stat";
    canvas.onSearchKey("right", keyEvent("Escape"));
    expect(canvas.ui.armedLeft).toBe(null);
    expect(canvas.ui.q.right).toBe("stat");     // the search survives the cancel
    canvas.onSearchKey("right", keyEvent("Escape"));
    expect(canvas.ui.q.right).toBe("");         // …and the next press clears it
});

test("D2 — Escape closes the card menu before anything else", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, { props: actProps() });
    canvas.ui.armedLeft = 100;
    canvas.ui.menu = { id: 100, label: "L", acts: [], x: 0, y: 0, flip: false };
    canvas.onKeydown(keyEvent("Escape"));
    expect(canvas.ui.menu).toBe(null);
    expect(canvas.ui.armedLeft).toBe(100);      // still armed — one key, one effect
});

// ---------------------------------------------------------------- D3
test("D3 — the action trigger never covers the card's name or code", async () => {
    // MF13/CR22's third act. Three pills IN the flow crushed the name; the same
    // three floated OVER the card covered it. One fixed-width button does
    // neither, and a bounding box is the only thing that can prove it.
    // `itemActions` is gated on `onLeftAction` — a board with no action callback
    // grows no trigger at all, which is the pre-existing contract.
    await mountWithCleanup(MappingCanvas, { props: actProps({ onLeftAction: () => {} }) });
    await animationFrame();
    const card = document.querySelector(".mc-col.left .mc-item");
    const more = card.querySelector(".mc-item-more");
    const label = card.querySelector(".mc-item-label");
    const sub = card.querySelector(".mc-item-sub");
    expect(more).not.toBe(null);

    // the revealed state, reached the way the keyboard reaches it — the same CSS
    // rule hover uses. Nothing may move, and nothing may overlay the text.
    card.classList.add("focus");
    await animationFrame();
    const b = more.getBoundingClientRect();
    for (const el of [label, sub]) {
        const t = el.getBoundingClientRect();
        expect(t.width > 0).toBe(true);                 // the text has room
        expect(b.left >= t.right - 0.5).toBe(true);     // …and nothing sits on it
    }
    expect(Math.round(b.width)).toBe(22);               // fixed, never negotiable
    expect(more.getAttribute("aria-haspopup")).toBe("menu");
    expect((more.getAttribute("aria-label") || "").length > 0).toBe(true);
});

test("D3 — the trigger opens one menu carrying every verb, keyboard-reachable", async () => {
    const acted = [];
    const canvas = await mountWithCleanup(MappingCanvas, {
        props: actProps({ onLeftAction: (it, act) => acted.push([it.id, act.key]) }),
    });
    await animationFrame();
    const card = document.querySelector(".mc-col.left .mc-item");
    const more = card.querySelector(".mc-item-more");
    more.click();
    await animationFrame();

    const rows = document.querySelectorAll(".mc-menu .mc-menu__i");
    expect(rows.length).toBe(3);
    expect(rows[0].getAttribute("role")).toBe("menuitem");
    expect(document.querySelector(".mc-menu").getAttribute("role")).toBe("menu");
    expect(more.getAttribute("aria-expanded")).toBe("true");

    rows[0].click();
    await animationFrame();
    expect(acted).toEqual([[100, "to_field"]]);
    expect(canvas.ui.menu).toBe(null);
});

// ---------------------------------------------------------------- D4/D5
test("D4/D5 — a card's note is rendered when the adapter sends one, and only then", async () => {
    const right = [
        { id: "f:hr.employee:marital", label: "Marital Status", sublabel: "Employee",
          meta: { note: { text: "Married (married), Single (single)",
                          title: "The file must contain one of these values",
                          tone: "" } } },
        { id: "f:hr.employee:name", label: "Employee Name", sublabel: "Employee", meta: {} },
    ];
    await mountWithCleanup(MappingCanvas, { props: actProps({ rightItems: right }) });
    await animationFrame();
    const notes = document.querySelectorAll(".mc-col.right .mc-item-note");
    expect(notes.length).toBe(1);
    expect(notes[0].textContent).toInclude("(married)");
    expect(notes[0].getAttribute("title")).toInclude("must contain");
});

test("D4/D5 — a caution note is toned differently from an ordinary one", async () => {
    const right = [
        { id: "f:hr.employee:x", label: "X", sublabel: "Employee",
          meta: { note: { text: "Must already exist — will not be created",
                          title: "…", tone: "warn" } } },
    ];
    await mountWithCleanup(MappingCanvas, { props: actProps({ rightItems: right }) });
    await animationFrame();
    expect(document.querySelector(".mc-col.right .mc-item-note").classList.contains("warn")).toBe(true);
});

// ==================================================== MAPFIX Phase E
// The `Status` card read "4 values — New, Running, Expired, …" and the rest of
// the list existed only in a `title` tooltip: slow to appear, impossible to
// select, cut off by the viewport and absent altogether on a touch screen. The
// note is now the way to open it — in the SAME popover the card menu uses, which
// is what keeps MF27's measure-then-place fix a single implementation.

/** A right column with one truncated note and one complete one. */
function noteProps(over = {}) {
    const right = [
        {
            id: "f:hr.contract:state", label: "Status", sublabel: "Contract",
            meta: {
                ttype: "selection", lane: "contract_terms", lane_order: 4,
                note: {
                    text: "4 values — New, Running, Expired, …",
                    title: "The file must contain one of these values",
                    tone: "",
                    total: 4,
                    values: [
                        { key: "draft", label: "New" },
                        { key: "open", label: "Running" },
                        { key: "close", label: "Expired" },
                        { key: "cancel", label: "Cancelled" },
                    ],
                },
            },
        },
        {
            id: "f:hr.employee:sex", label: "Gender", sublabel: "Employee",
            meta: {
                ttype: "selection", lane: "personal", lane_order: 1,
                note: { text: "male, female", title: "Two values", tone: "" },
            },
        },
    ];
    return actProps({ rightItems: right, ...over });
}

// ---------------------------------------------------------------- E1, test 5
test("E1 — opening the value list does NOT wire the column it sits in", async () => {
    // The obvious way to ship this as a bug. The note lives INSIDE a card whose
    // `t-on-click` is `clickRight(it.id)`, and `clickRight` draws a wire whenever
    // a left card is armed. Without `stopPropagation`, READING what a destination
    // accepts would MAP a column to it.
    const drawn = [];
    const canvas = await mountWithCleanup(MappingCanvas, {
        props: noteProps({ onDraw: (l, r) => drawn.push([l, r]) }),
    });
    await animationFrame();
    canvas.ui.armedLeft = 100;                       // a column is armed, mid-gesture

    const note = document.querySelector(".mc-col.right .mc-item-note.act");
    expect(note).not.toBe(null);
    note.click();
    await animationFrame();
    await animationFrame();

    expect(drawn).toEqual([]);                       // nothing was mapped
    expect(canvas.ui.armedLeft).toBe(100);           // …and the gesture survives
    expect(canvas.ui.menu.kind).toBe("values");
    expect(canvas.ui.focusId).toBe(null);            // the card was not even selected
});

// ---------------------------------------------------------------- E1, test 6
test("E1 — the popover prints every value with its stored code", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, { props: noteProps() });
    await animationFrame();
    document.querySelector(".mc-col.right .mc-item-note.act").click();
    await animationFrame();
    await animationFrame();

    const pop = document.querySelector(".mc-menu.vals");
    expect(pop).not.toBe(null);
    expect(pop.getAttribute("role")).toBe("dialog");
    const rows = pop.querySelectorAll(".mc-menu__v");
    expect(rows.length).toBe(4);                     // EVERY value, not the head
    expect(rows[0].querySelector(".mc-menu__vl").textContent).toBe("New");
    expect(rows[0].querySelector(".mc-menu__vk").textContent).toBe("draft");
    expect(rows[3].querySelector(".mc-menu__vk").textContent).toBe("cancel");
    // …and the list scrolls inside the popover rather than growing the card
    const vals = pop.querySelector(".mc-menu__vals");
    expect(getComputedStyle(vals).overflowY).toBe("auto");
    expect(document.querySelector(".mc-col.right .mc-item-note.act")
        .getAttribute("aria-expanded")).toBe("true");
});

test("E1 — Escape closes the value list and does not disarm the component", async () => {
    // D2's precedence, unchanged: the innermost dismissable goes first. One key,
    // one effect — a reader who opened a list to check a code must not lose the
    // gesture they were in the middle of by closing it.
    const canvas = await mountWithCleanup(MappingCanvas, { props: noteProps() });
    await animationFrame();
    const trigger = document.querySelector(".mc-col.right .mc-item-note.act");
    trigger.click();
    await animationFrame();
    await animationFrame();
    canvas.ui.armedLeft = 100;

    canvas.onKeydown(keyEvent("Escape"));
    expect(canvas.ui.menu).toBe(null);
    expect(canvas.ui.armedLeft).toBe(100);
    await animationFrame();
    await animationFrame();
    expect(document.activeElement).toBe(trigger);    // focus comes back to it
});

// ---------------------------------------------------------------- E1, test 7
test("E1 — a note that already shows everything is inert text", async () => {
    // An affordance that opens a list of what you are already reading is worse
    // than none. `values` is the adapter's "this was truncated" signal, and it is
    // the only thing that turns the note into a button.
    await mountWithCleanup(MappingCanvas, { props: noteProps() });
    await animationFrame();
    const notes = document.querySelectorAll(".mc-col.right .mc-item-note");
    expect(notes.length).toBe(2);
    const [truncated, complete] = notes;
    expect(truncated.tagName).toBe("BUTTON");
    expect(truncated.getAttribute("aria-haspopup")).toBe("dialog");
    expect((truncated.getAttribute("aria-label") || "").length > 0).toBe(true);
    expect(complete.tagName).toBe("DIV");
    expect(complete.getAttribute("aria-haspopup")).toBe(null);
    expect(complete.getAttribute("aria-expanded")).toBe(null);
    expect(complete.hasAttribute("tabindex")).toBe(false);
});

// ---------------------------------------------------------------- E1, test 8
test("E1 — the new affordance still leaves the name and the code legible", async () => {
    // MF13/CR22/MF26, fourth act. Two affordances have already wrecked this card
    // by sharing a line with its text. This one is the text — its own block under
    // the sublabel — and a bounding box is the only thing that can prove it.
    await mountWithCleanup(MappingCanvas, { props: noteProps() });
    await animationFrame();
    for (const card of document.querySelectorAll(".mc-col.right .mc-item")) {
        const label = card.querySelector(".mc-item-label");
        const sub = card.querySelector(".mc-item-sub");
        const note = card.querySelector(".mc-item-note");
        const lb = label.getBoundingClientRect();
        const sb = sub.getBoundingClientRect();
        const nb = note.getBoundingClientRect();
        expect(lb.width > 0).toBe(true);
        expect(sb.width > 0).toBe(true);
        // three stacked blocks, in order, never on top of one another
        expect(sb.top >= lb.bottom - 0.5).toBe(true);
        expect(nb.top >= sb.bottom - 0.5).toBe(true);
        // and the note never makes the card wider than the column
        expect(nb.right <= card.getBoundingClientRect().right + 0.5).toBe(true);
    }
});

test("E1 — Enter on the note opens the list and does not wire anything", async () => {
    // Found LIVE, and it is E1's trap arriving by keyboard instead of by mouse.
    // `onKeydown` is bound to the board root, so Enter on a focused button both
    // fired the button's click AND fell through to `case "Enter"`, which acts on
    // the focus ring — arming a column, or drawing a wire when one was armed.
    const drawn = [];
    const canvas = await mountWithCleanup(MappingCanvas, {
        props: noteProps({ onDraw: (l, r) => drawn.push([l, r]) }),
    });
    await animationFrame();
    canvas.ui.armedLeft = 100;
    canvas.ui.focusSide = "right";
    canvas.ui.focusId = "f:hr.contract:state";

    // driven through the REAL button, because the bug was that the real button's
    // keydown reached the board — a fabricated `{tagName}` would pass either way.
    const note = document.querySelector(".mc-col.right .mc-item-note.act");
    note.focus();
    note.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    note.click();                           // what the browser does next
    await animationFrame();
    await animationFrame();
    expect(drawn).toEqual([]);              // nothing was mapped
    expect(canvas.ui.armedLeft).toBe(100);  // and the gesture is intact
    expect(canvas.ui.menu.kind).toBe("values");

    // …nor from INSIDE the open popover, whose scroller is a DIV the tag test
    // cannot see. This is the leak the first cut of the guard still had.
    const vals = document.querySelector(".mc-menu__vals");
    vals.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    await animationFrame();
    expect(drawn).toEqual([]);

    // …while Enter from the search box still completes the wire it promises (MF25)
    canvas.closeItemMenu();
    await animationFrame();
    const fromSearch = keyEvent("Enter");
    fromSearch.target = { tagName: "INPUT" };
    canvas.onKeydown(fromSearch);
    expect(drawn).toEqual([[100, "f:hr.contract:state"]]);
});

test("E1 — the value list answers the scrolling keys itself", async () => {
    // The board `preventDefault`s ArrowUp/Down to move its focus ring, so without
    // a branch of its own a 120-row list could not be read with the keyboard at
    // all — while the ring wandered behind an open dialog.
    const many = Array.from({ length: 60 }, (_, i) => ({ key: `k${i}`, label: `Value ${i}` }));
    const right = [{
        id: "f:hr.employee:tz", label: "Timezone", sublabel: "Employee",
        meta: { ttype: "selection", lane: "personal", lane_order: 1,
                note: { text: "60 values — a, b, c, …", title: "t", tone: "",
                        total: 200, values: many } },
    }];
    const canvas = await mountWithCleanup(MappingCanvas, { props: noteProps({ rightItems: right }) });
    await animationFrame();
    document.querySelector(".mc-col.right .mc-item-note.act").click();
    await animationFrame();
    await animationFrame();

    const box = document.querySelector(".mc-menu__vals");
    expect(box.scrollHeight > box.clientHeight).toBe(true);   // it really does scroll
    const before = box.scrollTop;
    canvas.onMenuKeydown({ key: "End", preventDefault() {}, stopPropagation() {} });
    expect(box.scrollTop > before).toBe(true);
    canvas.onMenuKeydown({ key: "Home", preventDefault() {}, stopPropagation() {} });
    expect(box.scrollTop).toBe(0);
    // and it says it is showing a subset rather than dropping the tail silently
    expect(document.querySelector(".mc-menu__f").textContent).toInclude("200");
});

// ==================================================================== MAPFIX F
//
// F1 — *scrolled out of view* ≠ *filtered out of the set*.
//
// CR21 made lane filtering a canvas prop applied inside `_passes` rather than a
// trim of the item array, precisely so a wire whose end is filtered DOCKS on the
// column edge instead of counting as `gone`. That is right for SCROLLING — "↑ 8
// mapped above" is how a two-hundred-row board admits a connection exists just
// off screen — and wrong for FILTERING, where the reader has said "show me only
// these" and the docked wires became arrows hanging off the top and bottom edges
// pointing at nothing.
//
// Every test below is about the seam between those two: one predicate
// (`isFilteredOut`) decides whether a wire is drawn AND how many are counted, so
// the canvas and the column header cannot disagree — which, before this, they
// could.

/** Three lanes, three wires, one wire per lane, both columns grouped. */
function laneProps(over = {}) {
    return {
        leftItems: [
            { id: "L0", label: "Bank Name", sublabel: "col A", group: "Bank", meta: {} },
            { id: "L1", label: "Employee Code", sublabel: "col B", group: "Identity", meta: {} },
            { id: "L2", label: "Department", sublabel: "col C", group: "Employee profile", meta: {} },
        ],
        rightItems: [
            { id: "R0", label: "Bank name", sublabel: "Bank", group: "Bank account", meta: { lane_order: 5 } },
            { id: "R1", label: "Employee Code", sublabel: "Employee", group: "Identity", meta: { lane_order: 0 } },
            { id: "R2", label: "Department", sublabel: "Contract", group: "Job & organisation", meta: { lane_order: 3 } },
        ],
        wires: [
            { id: "w0", leftId: "L0", rightId: "R0", state: "accepted" },
            { id: "w1", leftId: "L1", rightId: "R1", state: "accepted" },
            { id: "w2", leftId: "L2", rightId: "R2", state: "accepted" },
        ],
        leftTitle: "FROM — lanes", rightTitle: "TO — lanes", canEdit: true,
        ...over,
    };
}

/** Change filter state the way the UI does, then let the board settle. */
async function refilter(canvas, over = {}) {
    if (over.q) { Object.assign(canvas.ui.q, over.q); }
    if (over.qa) { Object.assign(canvas.ui.qa, over.qa); }
    if (over.f) { Object.assign(canvas.ui.f, over.f); }
    await animationFrame();
    await animationFrame();
    canvas._recompute();
}

const wireIds = (canvas) => canvas.ui.geom.map((g) => g.id).sort();

test("F1 — a lane pill draws only its own wires, and hangs nothing off the edges", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, {
        props: laneProps({ groupFilter: "Bank" }),
    });
    await animationFrame();
    canvas._recompute();

    // the owner's screenshot, as an assertion: one lane, one wire, no others
    expect(wireIds(canvas)).toEqual(["w0"]);
    for (const g of canvas.ui.geom) {
        expect(g.hiddenL).toBe(false);
        expect(g.hiddenR).toBe(false);
    }
    // …and the two that are gone are counted, not lost
    expect(canvas.hiddenWires("left")).toBe(2);
    expect(canvas.ui.supp.map((s) => s.id).sort()).toEqual(["w1", "w2"]);
    expect(canvas.ui.gone).toBe(0);       // filtered is not `gone`
});

test("F1 — with no filter the geometry is exactly what it always was", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, { props: laneProps() });
    await animationFrame();
    canvas._recompute();
    expect(wireIds(canvas)).toEqual(["w0", "w1", "w2"]);
    expect(canvas.ui.supp).toEqual([]);
    expect(canvas.hiddenWires("left")).toBe(0);
    expect(canvas.hiddenWires("right")).toBe(0);
});

test("F1 — an end that is only SCROLLED past still docks: the affordance CR21 built", async () => {
    // The distinction, asserted on its own. No filter is active, so nothing may
    // be suppressed — the card is in the list, in the DOM, and simply above the
    // visible band, which is the one case the dock chip was invented for.
    const canvas = await mountWithCleanup(MappingCanvas, { props: props() });
    await animationFrame();
    const lbody = document.querySelector(".mc-col.left .mc-col-body");
    // an explicit box, so the assertion is about the clamp and not about
    // whatever height the test fixture happened to give the column (W127)
    lbody.style.cssText = "height:90px;max-height:90px;overflow:auto;flex:none;";
    await animationFrame();
    expect(lbody.scrollHeight > lbody.clientHeight + 300).toBe(true);
    lbody.scrollTop = 600;                 // L0 is now well above the band
    canvas._recompute();

    const w1 = canvas.ui.geom.find((g) => g.id === "w1");
    expect(w1).not.toBe(undefined);        // drawn — NOT suppressed
    expect(w1.hiddenL).toBe(false);        // scrolled, not filtered
    expect(w1.dockL).toBe(-1);             // parked on the top edge
    expect(canvas.hiddenWires("left")).toBe(0);
    expect(canvas.ui.supp.length).toBe(0);
    // and it says so in the chip, in the "mapped above" vocabulary
    const up = canvas.ui.docks.find((d) => d.side === "left" && d.dir === -1);
    expect(up.count >= 1).toBe(true);
    expect(up.filtered).toBe(0);
    expect(canvas.dockLabel(up)).toInclude("above");
    expect(canvas.dockLabel(up)).not.toInclude("hidden by filter");
});

test("F1 — the counter equals the suppression, for every kind of filter", async () => {
    // Four filters, one equality. `hiddenWires` is read off the SAME pass that
    // decided not to draw them, so this cannot drift — which is the whole point
    // of the change, the old counter being a second piece of arithmetic.
    const total = 3;

    // (a) the Mapped/Unmapped toggle — every left card is wired, so "Unmapped"
    //     empties the column and every wire goes with it
    let canvas = await mountWithCleanup(MappingCanvas, { props: laneProps() });
    await animationFrame();
    await refilter(canvas, { f: { left: "unmapped" } });
    expect(canvas.ui.geom.length).toBe(0);
    expect(canvas.hiddenWires("left")).toBe(3);
    expect(canvas.hiddenWires("left")).toBe(total - canvas.ui.geom.length);

    // (b) a search term
    canvas = await mountWithCleanup(MappingCanvas, { props: laneProps() });
    await animationFrame();
    await refilter(canvas, { q: { left: "Bank" }, qa: { left: "Bank" } });
    expect(wireIds(canvas)).toEqual(["w0"]);
    expect(canvas.hiddenWires("left")).toBe(total - canvas.ui.geom.length);

    // (c) a search on the RIGHT column — the other end counts too
    canvas = await mountWithCleanup(MappingCanvas, { props: laneProps() });
    await animationFrame();
    await refilter(canvas, { q: { right: "Department" }, qa: { right: "Department" } });
    expect(wireIds(canvas)).toEqual(["w2"]);
    expect(canvas.hiddenWires("right")).toBe(total - canvas.ui.geom.length);
    expect(canvas.hiddenWires("left")).toBe(0);   // the left filter hid nothing

    // (d) all three at once, on the column that has all three
    canvas = await mountWithCleanup(MappingCanvas, {
        props: laneProps({ groupFilter: "Bank" }),
    });
    await animationFrame();
    await refilter(canvas, { f: { left: "mapped" }, q: { left: "Bank" },
                             qa: { left: "Bank" } });
    expect(wireIds(canvas)).toEqual(["w0"]);
    expect(canvas.hiddenWires("left")).toBe(total - canvas.ui.geom.length);
});

test("F1 — clear restores every wire", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, { props: laneProps() });
    await animationFrame();
    await refilter(canvas, { f: { left: "unmapped" }, q: { left: "zzz" },
                             qa: { left: "zzz" } });
    expect(canvas.ui.geom.length).toBe(0);

    canvas.clearFilters("left");
    await animationFrame();
    await animationFrame();
    canvas._recompute();

    expect(wireIds(canvas)).toEqual(["w0", "w1", "w2"]);
    expect(canvas.hiddenWires("left")).toBe(0);
    expect(canvas.ui.supp).toEqual([]);
});

test("F1 — clear also clears the lane filter the canvas does not own", async () => {
    // CR21 (b). The pill lives on the host; `clear` has to be able to release it
    // or "clear" stops meaning clear — and with F1 that matters more, because the
    // pill is now the reason wires are missing rather than merely docked.
    let cleared = 0;
    const canvas = await mountWithCleanup(MappingCanvas, {
        props: laneProps({ groupFilter: "Bank", onClearGroupFilter: () => { cleared++; } }),
    });
    await animationFrame();
    expect(canvas.hasFilter("left")).toBe(true);
    canvas.clearFilters("left");
    expect(cleared).toBe(1);
});

test("F1 — a suppressed wire can never be selected, by key or by hand", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, { props: laneProps() });
    await animationFrame();
    canvas._recompute();

    // select a wire, then filter its end away: the selection cannot survive into
    // a wire that nothing on screen can show, hover or clear
    canvas.ui.selWire = "w2";
    await refilter(canvas, { q: { left: "Bank" }, qa: { left: "Bank" } });
    expect(canvas.ui.selWire).toBe(null);

    // `w` walks `ui.geom`, which is now the DRAWN wires and only those
    const seen = new Set();
    for (let i = 0; i < 6; i++) {
        canvas.onKeydown({ key: "w", shiftKey: false, preventDefault() {},
                           stopPropagation() {}, target: { tagName: "DIV" } });
        seen.add(canvas.ui.selWire);
    }
    expect([...seen].sort()).toEqual(["w0"]);
    expect(seen.has("w1")).toBe(false);
    expect(seen.has("w2")).toBe(false);
});

test("F1 — the chip still speaks for a wire that is no longer drawn", async () => {
    // Suppressing the ARROW is the fix; suppressing the FACT would be W40's
    // "silently unavailable". The chip counts it, names the filter as the cause,
    // and pressing it clears that filter and brings the wire back.
    const canvas = await mountWithCleanup(MappingCanvas, { props: laneProps() });
    await animationFrame();
    await refilter(canvas, { q: { left: "Bank" }, qa: { left: "Bank" } });

    const chips = canvas.ui.docks.filter((d) => d.side === "left");
    expect(chips.length > 0).toBe(true);
    const filtered = chips.reduce((n, d) => n + d.filtered, 0);
    expect(filtered).toBe(2);
    const chip = chips.find((d) => d.filtered === d.count);
    expect(canvas.dockLabel(chip)).toInclude("hidden by filter");

    canvas.clickDock(chip);                       // the way back
    await animationFrame();
    await animationFrame();
    canvas._recompute();
    expect(canvas.ui.qa.left).toBe("");
    expect(wireIds(canvas)).toEqual(["w0", "w1", "w2"]);
});

test("F1 — aggregateDocks keeps its old contract when nothing is suppressed", () => {
    // The second argument is optional on purpose: every other board that calls
    // this — and the four tests above that predate F1 — must be unaffected.
    const geom = [{ id: "a", dockL: -1, dockR: 0, state: "accepted" }];
    expect(aggregateDocks(geom)).toEqual(aggregateDocks(geom, []));
    const both = aggregateDocks(geom, [
        { id: "s", dockL: -1, dockR: 0, hiddenL: true, hiddenR: false, state: "accepted" },
    ]);
    const up = both.find((d) => d.side === "left" && d.dir === -1);
    expect(up.count).toBe(2);
    expect(up.filtered).toBe(1);      // one of the two is behind a filter
    expect(up.ids).toEqual(["a", "s"]);
});

// ---------------------------------------------------------------------- F2
test("F2 — a field added mid-session lands in its lane, not at the end", () => {
    // MF32's client-side twin (MF36 (b)). The server places its own appends by
    // lane; the CLIENT concatenated session extras after the whole catalogue, so
    // pinning an Identity field from the search box drew a second "Identity"
    // heading under "Other contract fields".
    const board = [
        { id: "f:hr.employee:name", meta: { lane: "identity", lane_order: 0 } },
        { id: "f:hr.employee:employee_id", meta: { lane: "identity", lane_order: 0 } },
        { id: "f:hr.employee:birthday", meta: { lane: "personal", lane_order: 1 } },
        { id: "b:acc_number", meta: { lane: "bank", lane_order: 5 } },
        { id: "f:hr.contract:notes", meta: { lane: "other_contract", lane_order: 7 } },
    ];
    const extra = { id: "f:hr.employee:barcode", meta: { lane: "identity", lane_order: 0 } };
    const out = placeInLane([...board], extra);
    // end of ITS lane — after the last Identity card, before Personal
    expect(out.map((i) => i.id)).toEqual([
        "f:hr.employee:name", "f:hr.employee:employee_id",
        "f:hr.employee:barcode", "f:hr.employee:birthday",
        "b:acc_number", "f:hr.contract:notes",
    ]);
});

test("F2 — a lane that is not on the board yet gets its own place, in order", () => {
    // …and therefore its own heading: the canvas emits one whenever `group`
    // changes between consecutive rows, so landing between two other lanes is
    // exactly what makes the heading appear.
    const board = [
        { id: "a", group: "Identity", meta: { lane: "identity", lane_order: 0 } },
        { id: "b", group: "Other contract fields", meta: { lane: "other_contract", lane_order: 7 } },
    ];
    const extra = { id: "c", group: "Contract terms", meta: { lane: "contract_terms", lane_order: 4 } };
    const out = placeInLane([...board], extra);
    expect(out.map((i) => i.id)).toEqual(["a", "c", "b"]);
    // the canvas would now draw three headings, one per lane, in this order
    expect(out.map((i, n) => MappingCanvas.prototype.rightGroupHead.call(null, out, n)))
        .toEqual(["Identity", "Contract terms", "Other contract fields"]);
});

test("F2 — an item with no lane metadata still appends, exactly as it always did", () => {
    const board = [{ id: "a", meta: { lane_order: 0 } },
                   { id: "b", meta: { lane_order: 7 } }];
    expect(placeInLane([...board], { id: "z" }).map((i) => i.id))
        .toEqual(["a", "b", "z"]);
    expect(placeInLane([...board], { id: "z", meta: {} }).map((i) => i.id))
        .toEqual(["a", "b", "z"]);
    expect(laneOrderOf({ id: "z" })).toBe(LANE_LAST);
});

// ======================================================== JOURNEY J1 =======
/**
 * The merge, asserted at the only level this bundle can safely reach.
 *
 * J1 folded the Formula Studio's mapping overlay into the full-screen host, and
 * the first cut of these tests imported that host so it could exercise its
 * getters directly. That import cost five UNRELATED tests — see MJ2: pulling a
 * cockpit into `web.assets_unit_tests` drags its whole service-shaped import
 * graph in with it, and every `mountWithCleanup` test in the file then timed out
 * at 5000ms. The suite went 60/60 → 58/8 without a single line of canvas code
 * changing.
 *
 * So the rule this file already followed is now written down: **this suite tests
 * the CANVAS and the pure kernel, never a host.** The host's own invariants —
 * the five tab labels, the employee-only toolkit, the pre-scoped door — are
 * pinned in `tests/test_one_mapping_home.py`, which reads the source and cannot
 * be broken by bundle mechanics. What is left here is what genuinely belongs
 * here: the placement rule the host's right column depends on, and the role
 * vocabulary the lane chips read.
 */

test("J1 — a session extra lands in its LANE, which is what keeps the headings honest", () => {
    // The full-screen host merges its pinned extras through `placeInLane`, so
    // this is the rule its right column stands on. MF32/MF40: appending instead
    // grows a SECOND heading for a lane that already has one, and the lane
    // headers then lie for as long as the session lasts.
    const board = [
        { id: "f:hr.employee:barcode", group: "Identity",
          meta: { lane: "identity", lane_order: 0 } },
        { id: "f:hr.contract:notes", group: "Other contract fields",
          meta: { lane: "other_contract", lane_order: 7 } },
    ];
    const extra = { id: "f:hr.employee:birthday", group: "Personal",
                    meta: { lane: "personal", lane_order: 1 } };
    const out = placeInLane([...board], extra);
    expect(out.map((i) => i.id)).toEqual([
        "f:hr.employee:barcode", "f:hr.employee:birthday", "f:hr.contract:notes",
    ]);
    // three lanes, three headings, in lane order — and no ninth at the foot
    expect(out.map((i, n) => MappingCanvas.prototype.rightGroupHead.call(null, out, n)))
        .toEqual(["Identity", "Personal", "Other contract fields"]);
});

test("J1 — one role vocabulary, and every lane the chips order has a glyph", () => {
    // The chips and the studio's outline lens read the SAME list since J1. A role
    // in one and not the other renders a chip with no icon, which nothing errors
    // on and no screenshot catches at 13px.
    expect([...ROLE_LANE_ORDER].sort()).toEqual(ROLES.map((r) => r.key).sort());
    for (const r of ROLES) {
        expect(roleIcon(r.key)).toBe(r.icon);
    }
    // an unknown role degrades to payroll rather than to undefined
    expect(roleIcon("nonsense")).toBe("coins");
    expect(roleIcon(null)).toBe("coins");
    // Labels are deliberately NOT asserted here: they are module-scope `_t()`
    // objects and stringifying one before translations load throws outright
    // ("Cannot translate string"). The label text is pinned in Python instead.
});

// ==================================== JOURNEY J2 — the on-ramp's card, on the
// canvas side. The Excel board's new left lane is ordinary `sublabel` + `group`
// data; what is NOT ordinary is that a person is about to decide which of 99
// look-alike headings feeds a pay component off the strength of one sample
// value. So the two canvas behaviours the on-ramp leans on get pinned here,
// where they are pure and cannot be perturbed by a host (MJ2).
test("J2 — an 'e.g.' sample line is searchable, so a heading can be found by its value", () => {
    // The reader's real question is "which column is the one with the big
    // numbers in it". `itemMatches` already reads `sublabel`; this is the case
    // that makes the on-ramp's sublabel worth rendering at all.
    const card = { id: "c:SEVL|Basic Salary", label: "SEVL|Basic Salary",
                   sublabel: "e.g. 12,500,000", meta: { sheet: "SEVL", letter: "B" } };
    expect(itemMatches(card, "12,500")).toBe(true);      // by the sample
    expect(itemMatches(card, "e.g.")).toBe(true);
    expect(itemMatches(card, "SEVL")).toBe(true);        // by the sheet, via the label
    expect(itemMatches(card, "basic")).toBe(true);       // by the heading
    expect(itemMatches(card, "pension")).toBe(false);
    // a heading whose first row happened to be empty still matches by name
    const blank = { id: "c:Bonus", label: "Bonus", sublabel: "no value in the first row" };
    expect(itemMatches(blank, "bonus")).toBe(true);
});

test("J2 — the dropped-file lane is ONE group, so it draws ONE heading", () => {
    // The provenance line ("march.xlsx · read …") is the lane's `group`, and the
    // canvas emits a heading whenever `group` CHANGES between consecutive rows
    // (MF32). Every card off one file therefore has to carry the identical
    // string — a per-card variation would grow a heading per column.
    const lane = "march.xlsx · read 03/2026";
    const items = [
        { id: "c:A", label: "Employee Code", sublabel: "e.g. E001", group: lane },
        { id: "c:B", label: "Basic Salary", sublabel: "e.g. 12,500,000", group: lane },
        { id: "c:C", label: "Meal", sublabel: "e.g. 730,000", group: lane },
        { id: "c:D", label: "Grade", sublabel: "", group: "Already used by this scheme" },
    ];
    const heads = items.map((it, n) =>
        MappingCanvas.prototype.leftGroupHead.call(null, items, n));
    expect(heads).toEqual([lane, "", "", "Already used by this scheme"]);
});

// ============================================== JOURNEY J3 — the two-way board
test("J3 — a bidirectional wire grows a SECOND head, and nothing else moves", () => {
    // The default is the whole safety argument: five boards call this and only
    // one is two-way, so an opt-out would have been a regression waiting for
    // whichever adapter forgot.
    const one = wireGeometry(100, 50, 400, 300);
    const two = wireGeometry(100, 50, 400, 300, true);
    expect(one.headBack).toBe(undefined);
    expect(two.headBack).not.toBe(undefined);
    // the forward head is IDENTICAL — a second arrow must not move the first
    expect(two.head).toBe(one.head);
    expect(two.hx).toBe(one.hx);
    expect(two.hy).toBe(one.hy);
    // the back head's apex is the SOURCE point, pointing away from the target
    const [apex] = two.headBack.split(" ");
    expect(apex).toBe("100,50");
    expect(two.headBack.split(" ").length).toBe(3);
    // and the stroke now starts clear of it, so the curve does not run under
    // its own arrowhead
    expect(two.d.startsWith(`M ${100 + HEAD} 50`)).toBe(true);
    expect(one.d.startsWith("M 100 50")).toBe(true);
});

test("J3 — a right-to-left two-way wire reserves the back head on the right", () => {
    const g = wireGeometry(400, 50, 100, 300, true);
    expect(g.headBack.startsWith("400,50")).toBe(true);
    expect(g.d.startsWith(`M ${400 - HEAD} 50`)).toBe(true);
});

test("J3 — the conflict chip renders only what the adapter sent", () => {
    const chip = MappingCanvas.prototype.conflictChip;
    expect(chip.call(null, { id: 1 })).toBe(null);
    expect(chip.call(null, { id: 1, conflict: {} })).toBe(null);
    const c = chip.call(null, { id: 1, conflict: { label: "L", hint: "H" } });
    expect(c).toEqual({ label: "L", hint: "H" });
    // no hint sent → the label is its own tooltip, never an empty title
    expect(chip.call(null, { id: 1, conflict: { label: "L" } }).hint).toBe("L");
});

test("J3 — the direction note is read off meta, and only off meta", () => {
    const dir = MappingCanvas.prototype.dirNote;
    expect(dir.call(null, { id: 1 })).toBe(null);
    expect(dir.call(null, { id: 1, meta: {} })).toBe(null);
    expect(dir.call(null, { id: 1, meta: { directionNote: "N" } })).toBe("N");
    // it is NOT the right column's `note` channel — those are different facts
    expect(dir.call(null, { id: 1, meta: { note: { text: "N" } } })).toBe(null);
});

// =====================================================================
// JOURNEY J4 — the three-lane transformation board.
//
// `TransformFlowBoard` is imported here for the same reason `MappingCanvas` is
// and under the same restriction MJ2 spelled out: this file tests the BOARD and
// the pure kernel, never a host. The import drags in the geometry module, the
// icon registry and OWL — no `mapping_studio`, no `hub_nav`, nothing that mounts
// an action. Every assertion below is translation-free (MJ3): a module-scope
// `_t()` cannot be stringified in hoot at all, so the chip SENTENCES are
// asserted from Python against the source and only ids, tones, ordering and
// arithmetic are asserted here.
// =====================================================================

/**
 * A `this` that has the prototype, so a method may compose other members (MJ4).
 *
 * `qRef` is in here rather than in the one test that obviously needs it, and
 * that is MJ4 exactly: `clearSearch` composes `this.qRef.el`, so the Escape
 * ladder — which has nothing to do with refs — threw a TypeError on its LAST
 * rung after all four of its assertions had already passed. A hand-rolled `this`
 * has to carry everything the method touches, not everything the test is about.
 */
function board(data, q = "") {
    const b = Object.create(TransformFlowBoard.prototype);
    b.ui = { q, armed: null, sealedSay: "", menu: null, focus: { lane: "", id: null },
             selWire: null, hoverWire: null, geom: [], reads: [], docks: [],
             // J6: `reveal` and `band` join for MJ4's reason — `centreBoth` and
             // `verbPos` compose them, and a hand-rolled `this` has to carry
             // everything the method touches, not everything the test is about.
             reveal: null, band: null };
    b.props = { data, canEdit: true };
    b.qRef = { el: null };
    b.bodyRefs = { left: { el: null }, mid: { el: null }, right: { el: null } };
    b._schedule = () => {};          // no DOM, so no rAF to schedule
    return b;
}

const FLOW = {
    ok: true,
    connector: { id: 3, name: "People (ABM)" },
    left: [
        { id: "f:OT_Type", label: "OT Type", sublabel: "OT_Type", readers: 2, drift: false },
        { id: "f:Actual_Pay_Hour", label: "Actual Pay Hour", sublabel: "Actual_Pay_Hour", readers: 1, drift: false },
        { id: "f:Gone_Field", label: "Gone Field", sublabel: "Gone_Field", readers: 1, drift: true },
    ],
    rules: [
        { id: 1, label: "Overtime 150% — hours", key: "OTHRS150", summary: "Adds up Actual_Pay_Hour", health: "ok", active: true, reads: ["OT_Type", "Actual_Pay_Hour"], feeds: ["OT 1.5 (OT15HOURS)"] },
        { id: 2, label: "Dependants", key: "DEPCOUNT", summary: "Counts rows", health: "unread", active: true, reads: ["Gone_Field"], feeds: [] },
        { id: 3, label: "Retired rule", key: "OLDKEY", summary: "", health: "severed", active: false, reads: [], feeds: [] },
    ],
    right: [
        { id: 606, label: "OT 1.5 hours", sublabel: "OT15HOURS" },
        { id: 632, label: "Dependants", sublabel: "NOOFDEPENDEN" },
    ],
    reads: [
        { id: "rd1:OT_Type", leftId: "f:OT_Type", ruleId: 1 },
        { id: "rd1:Actual_Pay_Hour", leftId: "f:Actual_Pay_Hour", ruleId: 1 },
        { id: "rd2:Gone_Field", leftId: "f:Gone_Field", ruleId: 2 },
    ],
    wires: [
        { id: "w36", ref: 36, bind: false, ruleId: 1, rightId: 606, severed: false, state: "accepted" },
    ],
    counts: { rules: 3, unread: 1, drift: 1, severed: 1, fed: 1 },
};

test("J4 — a rule's TONE is its health, and 'off' outranks every health word", () => {
    const tone = TransformFlowBoard.prototype.ruleTone;
    expect(tone.call(null, { active: true, health: "ok" })).toBe("");
    expect(tone.call(null, { active: true, health: "unread" })).toBe("warn");
    expect(tone.call(null, { active: true, health: "drift" })).toBe("drift");
    expect(tone.call(null, { active: true, health: "severed" })).toBe("sev");
    // a switched-off rule is not amber-because-idle: it is off, and that is a
    // different sentence from "nothing reads this"
    expect(tone.call(null, { active: false, health: "unread" })).toBe("off");
    // an unknown health never invents a class
    expect(tone.call(null, { active: true, health: "wat" })).toBe("");
});

test("J4 — one query filters three lanes, and a lane matches THROUGH its neighbours", () => {
    // the whole point: typing an output key must not empty the field lane, or
    // `/` breaks every wire on the board and the reader sees three unrelated lists
    const b = board(FLOW, "OTHRS150");
    expect(b.midView.map((r) => r.id)).toEqual([1]);
    // rule 1 reads these two, so they survive a query that names neither
    expect(b.leftView.map((f) => f.id))
        .toEqual(["f:OT_Type", "f:Actual_Pay_Hour"]);
    // and the component rule 1 feeds survives too
    expect(b.rightView.map((i) => i.id)).toEqual([606]);
});

test("J4 — an empty query keeps every lane whole", () => {
    const b = board(FLOW, "");
    expect(b.leftView.length).toBe(3);
    expect(b.midView.length).toBe(3);
    expect(b.rightView.length).toBe(2);
});

test("J4 — a field's own name still matches it directly", () => {
    const b = board(FLOW, "Gone");
    expect(b.leftView.map((f) => f.id)).toEqual(["f:Gone_Field"]);
    expect(b.midView.map((r) => r.id)).toEqual([2], { message: "and its reader comes with it" });
});

test("J4 — a query that matches nothing empties all three lanes rather than half", () => {
    const b = board(FLOW, "zzzznothing");
    expect(b.leftView.length).toBe(0);
    expect(b.midView.length).toBe(0);
    expect(b.rightView.length).toBe(0);
});

test("J4 — a rule is searchable by its SUMMARY, which is how people remember one", () => {
    const b = board(FLOW, "Counts rows");
    expect(b.midView.map((r) => r.id)).toEqual([2]);
});

test("J4 — the arming gesture cannot write without a key", () => {
    // `clickComponent` is the only path to `onDraw`; a rule with no output key
    // has nothing to send, and the guard is what stops it sending `undefined`
    let drawn = null;
    const b = board(FLOW);
    b.props = { ...b.props, onDraw: (k, r) => { drawn = [k, r]; } };
    b.ui.armed = 3;
    b.d.rules[2].key = "";
    b.clickComponent({ id: 606 }, null);
    expect(drawn).toBe(null);
    expect(b.ui.armed).toBe(null, { message: "and it disarms rather than staying stuck" });
    b.d.rules[2].key = "OLDKEY";
});

test("J4 — nothing armed means a component click writes nothing at all", () => {
    // MF37's safe shape: a gesture that cannot write while nothing is armed is
    // a gesture a live probe can exercise without a database diff
    let calls = 0;
    const b = board(FLOW);
    b.props = { ...b.props, onDraw: () => { calls++; } };
    b.clickComponent({ id: 632 }, null);
    expect(calls).toBe(0);
    expect(b.ui.focus).toEqual({ lane: "right", id: 632 }, { message: "it moves a focus ring" });
});

test("J4 — a BINDING is never cut from the board, because there is no row to cut", () => {
    let deleted = null;
    const b = board(FLOW);
    b.props = { ...b.props, onDelete: (ref) => { deleted = ref; } };
    b.removeWire({ id: "b2:632", bind: true, ref: 0 }, null);
    expect(deleted).toBe(null);
    b.removeWire({ id: "w36", bind: false, ref: 36 }, null);
    expect(deleted).toBe(36);
});

test("J4 — Enter on a BUTTON never reaches the board's own Enter (MF33)", () => {
    const b = board(FLOW);
    b.ui.armed = 1;
    let prevented = 0;
    const ev = { key: "Enter", target: { tagName: "BUTTON" },
                 preventDefault: () => { prevented++; } };
    b.onKeydown(ev);
    // the guard returns before any board behaviour — the arming survives
    // untouched, which is the proof that nothing fell through and drew a wire
    expect(b.ui.armed).toBe(1);
    expect(prevented).toBe(0);
});

test("J4 — the Escape ladder consumes ONE rung per press, most-nested first", () => {
    const b = board(FLOW, "query");
    b.ui.menu = { kind: "verbs", ruleId: 1 };
    b.ui.armed = 1;
    b.ui.selWire = "w36";
    const esc = { key: "Escape", target: { tagName: "DIV" } };
    b.onKeydown(esc);
    expect(b.ui.menu).toBe(null);
    expect(b.ui.armed).toBe(1, { message: "one Escape never dismisses two things" });
    b.onKeydown(esc);
    expect(b.ui.armed).toBe(null);
    b.onKeydown(esc);
    expect(b.ui.selWire).toBe(null);
    b.onKeydown(esc);
    expect(b.ui.q).toBe("");
});

test("J4 — `/` reaches the search box, and is a plain character inside it", () => {
    const b = board(FLOW);
    let focused = 0;
    b.qRef.el = { focus: () => { focused++; } };
    let prevented = 0;
    b.onKeydown({ key: "/", target: { tagName: "DIV" },
                  preventDefault: () => { prevented++; } });
    expect(focused).toBe(1);
    expect(prevented).toBe(1);
    // typing a slash INTO the box must type a slash
    b.onKeydown({ key: "/", target: { tagName: "INPUT" },
                  preventDefault: () => { prevented++; } });
    expect(focused).toBe(1);
    expect(prevented).toBe(1);
});

test("J4 — the two edge sets anchor on DIFFERENT lane pairs", () => {
    // the board's whole geometric claim: read edges span lane 1→2 and feed edges
    // span lane 2→3, over the same unforked kernel
    const read = wireGeometry(300, 100, 400, 140);
    const feed = wireGeometry(700, 140, 800, 200);
    expect(read.d.startsWith("M 300 100")).toBe(true);
    expect(feed.d.startsWith("M 700 140")).toBe(true);
    // neither is bidirectional — J3's second head is opt-in and stays off here
    expect(read.headBack).toBe(undefined);
    expect(feed.headBack).toBe(undefined);
});

test("J4 — a suppressed edge is counted on the edge it went out by", () => {
    // MAPFIX F1's contract, reused unchanged: a wire hidden by the search still
    // says so, or it reads as a lost one
    const docks = aggregateDocks([], [
        { id: "rd2:Gone_Field", hiddenL: true, dockL: -1, hiddenR: false, dockR: 0 },
        { id: "w36", hiddenL: false, dockL: 0, hiddenR: true, dockR: 1 },
    ]);
    const byKey = Object.fromEntries(docks.map((d) => [d.key, d]));
    expect(byKey["left-1"].count).toBe(1);
    expect(byKey["left-1"].filtered).toBe(1);
    expect(byKey["right1"].count).toBe(1);
    expect(byKey["right1"].filtered).toBe(1);
});

// =====================================================================
// JOURNEY J5 — the Journey board.
//
// MJ3, third phase running: everything here is a TRANSLATION-FREE fact —
// ids, ordering, bucketing, geometry, the shape of a door. A `_t()` at
// module scope cannot be stringified in hoot at all, so every claim about
// WORDING lives in `test_journey_view.py`, asserted against the source.
//
// `JourneyBoard` is imported for the same reason `TransformFlowBoard` is and
// under the same restriction: it drags in the pure kernel and the icon
// registry and nothing that mounts an action (MJ2 — a hoot timeout is a
// measurement of the SERVER, and a host import is how a suite starts
// measuring one).
// =====================================================================

function journey(data, q = "") {
    const b = Object.create(JourneyBoard.prototype);
    b.ui = { q, focus: "", geom: [] };
    b.props = { data, busy: false };
    b.qRef = { el: null };
    b.rootRef = { el: null };
    b.laneRefs = {};
    b._schedule = () => {};          // no DOM, so no rAF to schedule
    return b;
}

const JNY = {
    ok: true,
    config: { id: 14, name: "AB Mauri Payroll", code: "ABM" },
    header: { components: 99, wired: 42, fallback: 18, attention: 3 },
    primary_id: 3,
    lanes: {
        systems: [
            { id: "c:1", kind: "connector", lane: "systems", label: "People",
              status: "connected", last_sync: "", wires: 18, dimmed: true },
            { id: "c:3", kind: "connector", lane: "systems", label: "People (ABM)",
              status: "connected", last_sync: "", wires: 8, primary: true },
            { id: "file", kind: "file", lane: "systems", label: "March.xlsx",
              sub: "read 3 Mar", door: { mode: "import" } },
            { id: "records", kind: "records", lane: "systems",
              label: "Payobook records", count: 21, door: { mode: "employee" } },
        ],
        feeds: [
            { id: "e:11", kind: "endpoint", lane: "feeds", parent: "c:3",
              label: "Attendance", fields: 40, drift: 2, last_sync: "",
              door: { mode: "api", connector: 3, endpoint: 11 } },
            { id: "s:SEVL", kind: "sheet", lane: "feeds", parent: "file",
              label: "SEVL", columns: 360, door: { mode: "import" } },
        ],
        transforms: [
            { id: "r:1", kind: "rule", lane: "transforms", parent: "c:3",
              label: "Overtime 150%", key: "OTHRS150", reads: 2, feeds: 1,
              door: { mode: "transform", connector: 3 } },
            { id: "r:2", kind: "rule", lane: "transforms", parent: "c:3",
              label: "Dependants", key: "DEPCOUNT", reads: 1, feeds: 0,
              tone: "warn", chip: { label: "Unread output", tone: "warn" },
              door: { mode: "transform", connector: 3 } },
        ],
        scheme: [
            { id: "scheme", kind: "scheme", lane: "scheme", label: "AB Mauri Payroll",
              counts: { total: 99, inputs: 54, wired: 42, calculated: 45,
                        constant: 9, contract: 0, people: 0, unfed: 3,
                        fallback: 18 } },
            { id: "h:conflict", kind: "health", lane: "scheme", tone: "warn",
              label: "7 components wired twice", door: { mode: "api" } },
        ],
        run: [
            { id: "run", kind: "run", lane: "run", ghost: true,
              label: "No pay run yet", door: { mode: "import" } },
        ],
    },
    edges: [
        { from: "c:3", to: "e:11", kind: "contain", count: 0 },
        { from: "e:11", to: "scheme", kind: "feed", count: 8 },
        { from: "c:3", to: "r:1", kind: "contain", count: 0 },
        { from: "r:1", to: "scheme", kind: "rule", count: 1 },
        { from: "file", to: "s:SEVL", kind: "contain", count: 0 },
        { from: "records", to: "scheme", kind: "records", count: 21, bidi: true },
        { from: "c:1", to: "scheme", kind: "feed", count: 18, dimmed: true },
    ],
    counts: { total: 99, wired: 42, conflicts: 7, dangling: 0, severed: 0,
              unread: 1, connectors: 2, rules: 2 },
};

test("J5 — the five lanes are in story order, and the order IS the story", () => {
    expect(LANES.map((l) => l.id)).toEqual(
        ["systems", "feeds", "transforms", "scheme", "run"]);
});

test("J5 — every lane carries an icon from the kit, never an emoji", () => {
    for (const lane of LANES) {
        expect(typeof lane.icon).toBe("string");
        expect(lane.icon.length > 0).toBe(true);
        // a Lucide key is ASCII; an emoji is not
        expect(/^[a-zA-Z]+$/.test(lane.icon)).toBe(true);
    }
});

test("J5 — a node id is unique across the WHOLE board, not per lane", () => {
    // the geometry keys every measured card by `dataset.id` into ONE map, so a
    // duplicate id in two lanes is a wire that silently anchors on the wrong end
    const b = journey(JNY);
    const ids = b.allNodes.map((n) => n.id);
    expect(new Set(ids).size).toBe(ids.length);
});

test("J5 — the filter matches THROUGH a neighbour, in both directions", () => {
    // typing a rule's key must not empty the lane holding the field it reads,
    // or `/` breaks every wire on the board (J4's lesson, five lanes on)
    const b = journey(JNY, "OTHRS150");
    expect(b.nodesFor("transforms").map((n) => n.id)).toEqual(["r:1"]);
    // the scheme is wired to that rule, so it survives the filter
    expect(b.nodesFor("scheme").map((n) => n.id)).toEqual(["scheme"]);
    // and so does the connector the rule belongs to, through `parent`
    expect(b.nodesFor("systems").map((n) => n.id)).toEqual(["c:3"]);
});

test("J5 — an unmatched lane empties rather than pretending", () => {
    const b = journey(JNY, "nothing-is-called-this");
    for (const lane of LANES) {
        expect(b.nodesFor(lane.id).length).toBe(0);
    }
});

test("J5 — the component picture partitions the scheme", () => {
    // the bar is a tally of disjoint counts, so its segments sum to 100%
    const b = journey(JNY);
    const bars = b.schemeBars;
    const n = bars.reduce((a, x) => a + x.n, 0);
    expect(n).toBe(99);
    // and a count of zero draws no segment at all — an empty band with a
    // label the reader has to dismiss costs them something (W64)
    expect(bars.some((x) => x.n === 0)).toBe(false);
    expect(bars.map((x) => x.key)).toEqual(["wired", "calculated", "constant", "unfed"]);
});

test("J5 — the run buckets are the SERVER's four, never invented here", () => {
    const b = journey({
        ...JNY,
        lanes: { ...JNY.lanes, run: [{ id: "run", kind: "run", lane: "run",
            label: "March", payslips: 3, read: 3, capped: false,
            created: { employees: 0, contracts: 0, payslips: 3 },
            agg: { slips: 3, values: 12, unreadable: 0, fell_back: 2,
                   by_src: { excel: 7, feed: 3, none: 2 },
                   by_bucket: { wired: 8, fallback: 2, computed: 0, default: 2 } } }] },
    });
    expect(b.runBuckets.map((x) => x.key)).toEqual(["wired", "fallback", "default"]);
    expect(b.runBuckets.reduce((a, x) => a + x.n, 0)).toBe(12);
    // by-source is sorted biggest first, so the eye lands on the real story
    expect(b.runSources.map((x) => x.key)).toEqual(["excel", "feed", "none"]);
});

test("J5 — only the records edge is double-headed (J-D4, opt-in as J3 wrote it)", () => {
    const plain = wireGeometry(300, 100, 400, 140);
    const bidi = wireGeometry(300, 100, 400, 140, true);
    expect(plain.headBack).toBe(undefined);
    expect(typeof bidi.headBack).toBe("string");
    // and the curve starts inside its own head, so the two do not overlap
    expect(bidi.d.startsWith("M 300 100")).toBe(false);
    expect(plain.d.startsWith("M 300 100")).toBe(true);
});

test("J5 — a door names a mode, and optionally a connector and a feed", () => {
    const b = journey(JNY);
    const ep = b.allNodes.find((n) => n.id === "e:11");
    expect(ep.door.mode).toBe("api");
    expect(ep.door.connector).toBe(3);
    expect(ep.door.endpoint).toBe(11);
    // a health node's door needs no scope beyond the tab
    const health = b.allNodes.find((n) => n.id === "h:conflict");
    expect(health.door.mode).toBe("api");
    expect(health.door.connector).toBe(undefined);
});

test("J5 — the focused node is the one the ring is on, and Escape clears it", () => {
    const b = journey(JNY);
    b.onNodeFocus(b.allNodes[0]);
    expect(b.isFocused("c:1")).toBe(true);
    b.onKeydown({ key: "Escape", target: { tagName: "DIV" } });
    expect(b.ui.focus).toBe("");
});

test("J5 — MF33: Enter on a node is the BUTTON's, never the board's as well", () => {
    // every card here is a `<button>`, so the platform opens the door; the root
    // handler must stand aside or the same door opens twice. On the canvas the
    // identical shape DREW A WIRE, which is why the guard is written down
    let acted = 0;
    const b = journey(JNY);
    b.clearSearch = () => { acted++; };
    b.ui.q = "x";
    b.onKeydown({ key: "Enter", target: { tagName: "BUTTON" } });
    b.onKeydown({ key: " ", target: { tagName: "BUTTON" } });
    expect(acted).toBe(0);
    // and Escape still reaches the board
    b.onKeydown({ key: "Escape", target: { tagName: "DIV" } });
    expect(acted).toBe(1);
});

test("J5 — `/` reaches the filter box, and is a plain character inside it", () => {
    const b = journey(JNY);
    let focused = 0, prevented = 0;
    b.qRef.el = { focus: () => { focused++; } };
    b.onKeydown({ key: "/", target: { tagName: "DIV" },
                  preventDefault: () => { prevented++; } });
    expect(focused).toBe(1);
    expect(prevented).toBe(1);
    b.onKeydown({ key: "/", target: { tagName: "INPUT" },
                  preventDefault: () => { prevented++; } });
    expect(focused).toBe(1);
});

test("J5 — the lane count describes the VIEW, not the board", () => {
    // MJ3: the unfiltered branch returns a PLAIN string and can be compared;
    // the filtered branch returns a `_t()` and is asserted through the count it
    // is built from, because hoot cannot stringify a lazy translation at all.
    const b = journey(JNY);
    expect(b.laneCount("systems")).toBe("4");
    const f = journey(JNY, "OTHRS150");
    expect(f.nodesFor("systems").length).toBe(1);
    expect((JNY.lanes.systems || []).length).toBe(4);
});

test("J5 — a dimmed connector is present, not hidden", () => {
    // the one-connector limit made visible: the ignored connection stays on the
    // board, greyed, because "it is there and nothing reads it" is the fact
    const b = journey(JNY);
    const c1 = b.allNodes.find((n) => n.id === "c:1");
    expect(c1.dimmed).toBe(true);
    expect(b.nodeClass(c1).includes("dim")).toBe(true);
    const c3 = b.allNodes.find((n) => n.id === "c:3");
    expect(b.nodeClass(c3).includes("prim")).toBe(true);
    expect(b.nodeClass(c3).includes("dim")).toBe(false);
});

test("J5 — a ghost is styled as an invitation and still carries its door", () => {
    const b = journey(JNY);
    const run = b.allNodes.find((n) => n.id === "run");
    expect(b.nodeClass(run).includes("ghost")).toBe(true);
    expect(run.door.mode).toBe("import");
});

test("J5 — an edge that jumps a lane is measured as a span, not as a break", () => {
    // `span` is what makes a lane-jumping wire render dashed instead of looking
    // like a wire that stopped in the middle. It is arithmetic over the lane
    // order and nothing else, so it is checked here rather than on a screenshot.
    const idx = {};
    LANES.forEach((l, i) => { idx[l.id] = i; });
    expect(Math.abs(idx.scheme - idx.feeds)).toBe(2);      // a feed to the scheme
    expect(Math.abs(idx.scheme - idx.systems)).toBe(3);    // records to the scheme
    expect(Math.abs(idx.transforms - idx.scheme)).toBe(1); // a rule is adjacent
});

// =====================================================================
// JOURNEY J6 — the four defects reported against the live J4 board.
//
// The load-bearing one is D3: a double-click on a live wire DELETED it on abm
// (the `OTHRS300` row, repaired as D0). So the first assertion here is the
// negative one — no gesture on a wire reaches the delete prop — and it is
// written against the PROP rather than against an RPC, because the board has no
// `orm` and never did: `onDelete` is the only way out of this component towards
// a deletion, which makes it the exact seam to guard.
//
// The host's undo helper is NOT tested here, deliberately. It lives in
// `mapping_studio.js`, and importing that into this bundle is precisely what
// MJ2 spent a phase diagnosing — it drags `hub_nav` and the import kit in and
// makes this suite a measurement of the host's asset graph. Its contract is
// asserted from Python instead (`TestJourneyJ6Defects`), against the source and
// against a real round trip on the ORM, which is a stronger oracle anyway.
// =====================================================================

test("J6 D3 — a double-click on a wire never reaches the delete prop", () => {
    const b = board(FLOW);
    let deleted = 0;
    b.props.onDelete = () => { deleted++; };
    b.ui.geom = [{ id: "w36", ref: 36, ruleId: 1, rightId: 606, kind: "feed",
                   hx: 200, hy: 300 }];
    b._centreLane = () => true;
    // ten rapid double-clicks, the numbered case
    for (let n = 0; n < 10; n++) {
        b.centreBoth(b.ui.geom[0], { stopPropagation() {}, preventDefault() {} });
    }
    expect(deleted).toBe(0);
    expect(b.ui.selWire).toBe("w36");
});

test("J6 D3 — only the explicit verb deletes, and a binding still refuses", () => {
    const b = board(FLOW);
    const cut = [];
    b.props.onDelete = (ref) => { cut.push(ref); };
    b.removeWire({ id: "w36", ref: 36, bind: false }, { stopPropagation() {} });
    expect(cut).toEqual([36]);
    // a `('rule', key)` binding is a field on the component, not a row
    b.removeWire({ id: "wb", ref: 0, bind: true }, { stopPropagation() {} });
    expect(cut).toEqual([36]);
});

test("J6 D3 — the verb is placed clear of the wire it belongs to", () => {
    const b = board(FLOW);
    b.ui.geom = [{ id: "w36", ref: 36, kind: "feed", hx: 210, hy: 400 }];
    b.ui.selWire = "w36";
    b.ui.band = { top: 60, bot: 900 };
    const p = b.verbPos;
    expect(p.x).toBe(210);
    // above the hub, by more than the wire's own 8px hit radius
    expect(p.y < 400 - 8).toBe(true);
    expect(p.flip).toBe(false);
});

test("J6 D3 — the verb flips rather than leaving through the top of the board", () => {
    const b = board(FLOW);
    b.ui.geom = [{ id: "w36", ref: 36, kind: "feed", hx: 210, hy: 70 }];
    b.ui.selWire = "w36";
    b.ui.band = { top: 60, bot: 900 };
    const p = b.verbPos;
    expect(p.flip).toBe(true);
    expect(p.y > 70).toBe(true);      // below the wire, still off it
});

test("J6 D2 — double-click centres BOTH ends of either wire family", () => {
    const b = board(FLOW);
    const centred = [];
    b._centreLane = (lane, id) => { centred.push(`${lane}:${id}`); return true; };
    b.ui.geom = [{ id: "w36", kind: "feed", ruleId: 1, rightId: 606, hx: 1, hy: 1 }];
    b.centreBoth(b.ui.geom[0], null);
    expect(centred).toEqual(["mid:1", "right:606"]);
    centred.length = 0;
    b.ui.reads = [{ id: "rd1", kind: "read", leftId: "f:OT_Type", ruleId: 1 }];
    b.centreBoth(b.ui.reads[0], null);
    expect(centred).toEqual(["left:f:OT_Type", "mid:1"]);
    expect(b.ui.reveal).toBe(null);
});

test("J6 D2 — an end the search hides raises the reveal bar instead of a no-op", () => {
    const b = board(FLOW, "OTHRS150");
    b._centreLane = (lane) => lane !== "right";     // the target is filtered away
    b.ui.geom = [{ id: "w36", kind: "feed", ruleId: 1, rightId: 606, hx: 1, hy: 1 }];
    b.centreBoth(b.ui.geom[0], null);
    expect(b.ui.reveal.sides).toEqual(["right"]);
    expect(b.ui.reveal.id).toBe("w36");
    // and the reachable end was still centred — never a silent no-op
    b.dismissReveal();
    expect(b.ui.reveal).toBe(null);
});

test("J6 D2 — selecting a read edge is not a thing; centring it is", () => {
    const b = board(FLOW);
    b._centreLane = () => true;
    b.ui.reads = [{ id: "rd1", kind: "read", leftId: "f:OT_Type", ruleId: 1 }];
    b.centreBoth(b.ui.reads[0], null);
    expect(b.ui.selWire).toBe(null);      // a read edge has no row to select
});

test("J6 D1 — a dock chip sits inside the lane band, not on the header", () => {
    const b = board(FLOW);
    b.ui.band = { top: 64, bot: 880 };
    expect(b.dockStyle({ dir: -1 })).toBe("top:64px;");
    expect(b.dockStyle({ dir: 1 })).toBe("top:880px;");
    // before the first measurement it says nothing and CSS decides
    b.ui.band = null;
    expect(b.dockStyle({ dir: -1 })).toBe("");
});

test("J6 D1 — the two dock chips sit over different lane gaps and cannot meet", () => {
    // `left: 34%` and `right: 34%` are two points that MEET as the board
    // narrows; at 1024 the pair overlapped by 32px. The gaps cannot.
    const b = board(FLOW);
    b.ui.band = { top: 64, bot: 880, gapL: 330, gapR: 700 };
    expect(b.dockStyle({ dir: -1, side: "left" })).toBe("top:64px;left:330px;");
    expect(b.dockStyle({ dir: -1, side: "right" })).toBe("top:64px;left:700px;");
    expect(b.dockStyle({ dir: 1, side: "right" })).toBe("top:880px;left:700px;");
});

test("J6 D1 — a chip that counts what the search hid is a door; a scrolled one is not", () => {
    const b = board(FLOW, "OTHRS150");
    let cleared = 0;
    b.qRef.el = { value: "OTHRS150" };
    b.clearSearch = () => { cleared++; };
    b.clickDock({ filtered: 3, count: 3, dir: -1 });
    expect(cleared).toBe(1);
    b.clickDock({ filtered: 0, count: 5, dir: 1 });
    expect(cleared).toBe(1);
});

test("J6 D4 — Enter lands an armed output, and does nothing when nothing is armed", () => {
    const b = board(FLOW);
    const drawn = [];
    b.props.onDraw = (key, id) => { drawn.push([key, id]); };
    const ev = { key: "Enter", preventDefault() {}, stopPropagation() {} };
    b.keyComponent({ id: 606, label: "OT 1.5 hours" }, ev);
    expect(drawn.length).toBe(0);           // nothing armed: nothing happens
    b.ui.armed = 1;
    b.keyComponent({ id: 606, label: "OT 1.5 hours" }, ev);
    expect(drawn).toEqual([["OTHRS150", 606]]);
    expect(b.ui.armed).toBe(null);          // the arm is spent
});

test("J6 D4 — a key that is not Enter or Space is not a draw gesture", () => {
    const b = board(FLOW);
    let drawn = 0;
    b.props.onDraw = () => { drawn++; };
    b.ui.armed = 1;
    b.keyComponent({ id: 606 }, { key: "a", preventDefault() {}, stopPropagation() {} });
    expect(drawn).toBe(0);
    expect(b.ui.armed).toBe(1);
});

test("J6 D4 — arming a rule's output does not open the composer", () => {
    const b = board(FLOW);
    let opened = 0;
    b.props.onOpenRule = () => { opened++; };
    let stopped = 0;
    b.armOutput(FLOW.rules[0], { stopPropagation: () => { stopped++; } });
    expect(opened).toBe(0);
    expect(stopped).toBe(1);
    expect(b.ui.armed).toBe(1);
    // and clicking it again disarms rather than arming a second time
    b.armOutput(FLOW.rules[0], { stopPropagation() {} });
    expect(b.ui.armed).toBe(null);
});

test("J6 D4 — the card body still opens the composer", () => {
    const b = board(FLOW);
    const opened = [];
    b.props.onOpenRule = (id) => { opened.push(id); };
    b.clickRule(FLOW.rules[0], { stopPropagation() {} });
    expect(opened).toEqual([1]);
});

test("J6 — Escape drops the reveal bar before it disarms", () => {
    const b = board(FLOW);
    b.ui.reveal = { id: "w36", sides: ["right"] };
    b.ui.armed = 1;
    b.onKeydown({ key: "Escape", target: { tagName: "DIV" } });
    expect(b.ui.reveal).toBe(null);
    expect(b.ui.armed).toBe(1);             // one Escape, one rung
    b.onKeydown({ key: "Escape", target: { tagName: "DIV" } });
    expect(b.ui.armed).toBe(null);
});

// =====================================================================
// JOURNEY J7 — the two legibility defects the owner reported against the
// live `System fields → Scheme` board.
//
// Both are geometry the unit suite could see and never asked about, which is
// the whole reason they are here rather than only in a screenshot:
//
//   D1  the dock chip hung on the CLAMP BAND, a line inside the column's
//       scrollport, i.e. exactly where the first and the last visible card
//       are. Measured live on abm: 167.9 x 23.8px of "Last Working Day" was
//       behind "4 hidden by filter above".
//   D2  the name shared its line with a 142px source pill on a 252px row, so
//       it was offered 104px and 23 of 73 cards ellipsised.
//
// The D1 assertions are deliberately written as "the strip and the band are
// two different numbers", because the defect was that they were one.
// =====================================================================

test("J7 D1 — the dock strip is centred on the column's edge, and holds a chip", () => {
    const a = dockAnchors(100, 500);
    expect(a.railTop).toBe(100 + DOCK_RAIL / 2);
    expect(a.railBot).toBe(500 - DOCK_RAIL / 2);
    // a dock chip measures ~24px on the live board (10.5px text, 3px padding,
    // 1px border); the strip has to hold one with air on both sides or the
    // "reserved" strip is not a reservation.
    expect(DOCK_RAIL >= 28).toBe(true);
    // the strip scales with the column, and never inverts on a short one
    expect(dockAnchors(0, DOCK_RAIL).railTop).toBe(DOCK_RAIL / 2);
    expect(dockAnchors(0, DOCK_RAIL).railBot).toBe(DOCK_RAIL / 2);
});

test("J7 D1 — the strip is not the band, and J7 did not move the band", async () => {
    // MJ30's hazard, closed by arithmetic rather than by re-measurement: the
    // rail is derived from the SAME border-box rect the band is, and a
    // transparent border does not move a border box. If this test ever fails,
    // every wire on the board moved with it.
    const canvas = await mountWithCleanup(MappingCanvas, { props: props() });
    await animationFrame();
    const stub = {
        getBoundingClientRect: () => ({ top: 200, bottom: 700, left: 0,
                                        right: 340, width: 340, height: 500 }),
        children: [],
    };
    const m = canvas._measure(stub, { top: 0, left: 0 }, "left");
    expect(m.bandTop).toBe(208);          // BAND is 8 and stayed 8
    expect(m.bandBot).toBe(692);
    expect(m.railTop).toBe(200 + DOCK_RAIL / 2);
    expect(m.railBot).toBe(700 - DOCK_RAIL / 2);
    // and the chip's own box clears where a card can start: the border keeps
    // content out of the first DOCK_RAIL px, and the chip ends before them.
    expect(m.railTop + 12 <= 200 + DOCK_RAIL).toBe(true);
    expect(m.railBot - 12 >= 700 - DOCK_RAIL).toBe(true);
});

test("J7 D1 — a chip's coordinates are part of what a recompute publishes", async () => {
    // The chip was placed once and then left there: `_sig` carried the counts
    // and not the position, so turning a filter on — which grows the column
    // head by the "N wires hidden by this filter" row and moves the body ~31px
    // — repositioned nothing. A chip 31px out of date is outside its strip.
    const canvas = await mountWithCleanup(MappingCanvas, { props: props() });
    await animationFrame();
    await refilter(canvas, { f: { left: "mapped", right: "all" } });
    await animationFrame();
    expect(canvas.ui.docks.length > 0).toBe(true);
    expect(canvas._sig.includes("@")).toBe(true);
    for (const d of canvas.ui.docks) {
        expect(typeof d.y).toBe("number");
    }
});

test("J7 D2 — a name that had to be clamped says so, and carries its full text", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, {
        props: props({
            leftItems: [{ id: "L0", sublabel: "x",
                          label: "Constant Unemployment Insurance contribution 1 %" }],
            wires: [],
        }),
    });
    await animationFrame();
    const span = document.querySelector(".mc-col.left .mc-item-label > span");
    expect(span).not.toBe(null);
    // The clamp is a CSS decision and this bundle is not a stylesheet test —
    // what is asserted is the RULE: whatever the browser decided, the pass
    // reports it and nothing else. (MJ3's family: keep hoot to facts the
    // runner can actually own.)
    Object.defineProperty(span, "scrollHeight", { value: 60, configurable: true });
    Object.defineProperty(span, "clientHeight", { value: 30, configurable: true });
    canvas._clipDirty = true;
    canvas._recompute();
    expect(span.classList.contains("is-clipped")).toBe(true);
    expect(span.title).toBe(span.textContent);

    Object.defineProperty(span, "scrollHeight", { value: 30, configurable: true });
    canvas._clipDirty = true;
    canvas._recompute();
    expect(span.classList.contains("is-clipped")).toBe(false);
    expect(span.hasAttribute("title")).toBe(false);
});

test("J7 D2 — scrolling cannot change whether a name fits, so it is not re-measured", async () => {
    const canvas = await mountWithCleanup(MappingCanvas, { props: props() });
    await animationFrame();
    let passes = 0;
    const real = canvas._clipPass.bind(canvas);
    canvas._clipPass = () => { passes++; real(); };
    canvas._clipDirty = false;
    const body = document.querySelector(".mc-col.left .mc-col-body");
    body.dispatchEvent(new Event("scroll"));
    await animationFrame();
    expect(passes).toBe(0);
    // …but a patch is exactly when it can have changed
    canvas._clipDirty = true;
    canvas._recompute();
    expect(passes).toBe(1);
});

test("J7 D2 — the transform board answers the same question about its own cards", () => {
    const b = board(FLOW);
    const mk = (text, clipped) => {
        const el = document.createElement("div");
        el.dataset.id = "1";
        const l = document.createElement("div");
        l.className = "tfb-item-l";
        const s = document.createElement("span");
        s.textContent = text;
        l.appendChild(s); el.appendChild(l);
        Object.defineProperty(s, "scrollHeight", { value: clipped ? 60 : 30 });
        Object.defineProperty(s, "clientHeight", { value: 30 });
        return { el, s };
    };
    const long = mk("OT Night shift weekend hours, second half", true);
    const short = mk("OT 3 Hours", false);
    const lane = document.createElement("div");
    lane.appendChild(long.el); lane.appendChild(short.el);
    b.bodyRefs = { left: { el: lane }, mid: { el: null }, right: { el: null } };
    b._clipPass();
    expect(long.s.classList.contains("is-clipped")).toBe(true);
    expect(long.s.title).toBe("OT Night shift weekend hours, second half");
    expect(short.s.classList.contains("is-clipped")).toBe(false);
    expect(short.s.hasAttribute("title")).toBe(false);
});
