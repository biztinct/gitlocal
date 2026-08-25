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
    hubPoint,
    itemMatches,
    laneOrderOf,
    placeInLane,
    spreadHubs,
    wireGeometry,
    HEAD,
    LANE_LAST,
} from "@pb_formula_studio/js/mapping/mapping_geometry";
import { ROLES, ROLE_LANE_ORDER, roleIcon }
    from "@pb_formula_studio/js/mapping/mapping_roles";

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
