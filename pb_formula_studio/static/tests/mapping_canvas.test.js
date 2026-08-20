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
    expect(up.amber).toBe(true);        // one of the three is a suggestion
    expect(up.ids).toEqual(["a", "b", "c"]);
    const down = docks.find((d) => d.side === "left" && d.dir === 1);
    expect(down.count).toBe(1);
    expect(down.amber).toBe(false);
    expect(docks.find((d) => d.side === "right" && d.dir === 1).count).toBe(1);
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
