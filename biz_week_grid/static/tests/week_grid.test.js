/** @odoo-module **/
/**
 * Workforce P5 — T1/T2/T3: the redesigned WeekGrid, against a mocked adapter.
 *
 * The component carries no product dependencies, so these need no Odoo models:
 * an object with `fetch` and `save` IS the whole contract. What they pin is the
 * three things the redesign is FOR —
 *
 *   T1  a cell renders outcomes and only outcomes (and, specifically, that no
 *       rate ever reaches a cell — the gate the owner's feedback bought);
 *   T2  the editor stages through the dirty mechanism and nothing else, and
 *       its advisory bar never becomes a wall;
 *   T3  the keyboard verbs a dense grid is unusable without.
 */
import { describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { click, keyDown, press, queryAll, queryAllTexts, queryFirst, queryText } from "@odoo/hoot-dom";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";

import { WeekGrid } from "@biz_week_grid/js/week_grid";

describe.current.tags("desktop");

const DAYS = ["2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13",
              "2026-08-14", "2026-08-15", "2026-08-16"];

function days() {
    return DAYS.map((iso, i) => ({
        iso,
        label: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][i],
        sublabel: `Aug ${10 + i}`,
        is_today: i === 2,
        is_weekend: i >= 5,
    }));
}

const MEASURES = [
    { key: "reg", label: "Reg", name: "Regular hours", min: 0, max: 24, step: 0.5 },
    { key: "weekday", label: "150%", name: "Weekday overtime", rate: "150%",
      color: "#5A4BB0", min: 0, max: 24, step: 0.5 },
    { key: "weekend", label: "200%", name: "Weekend overtime", rate: "200%",
      color: "#D97706", min: 0, max: 24, step: 0.5 },
];

/** A cell with a REG value and, per applicable OT type, a chip measure. */
function cell(reg, extras = {}, regOpts = {}) {
    const measures = { reg: { value: reg, editable: true, ...regOpts } };
    for (const [k, v] of Object.entries(extras)) {
        measures[k] = { value: 0, editable: true, state: "", ...v };
    }
    return { measures };
}

/**
 * The fixture week, built to be exactly the matrix T1 is about:
 *   Mon  8 h, nothing else                     — hours only
 *   Tue  8 h + 3 h draft weekday OT            — hours + draft
 *   Wed  8 h + 2 h SUBMITTED weekday OT        — locked chip, solid dot
 *   Thu  8 h + 1 h APPROVED weekday OT, 1 bonus— green dot, split chip
 *   Fri  nothing                               — an EMPTY cell is empty
 *   Sat  0 h, weekend OT applicable, none used — applicable ≠ rendered
 *   Sun  locked by a consumer flag + BT badge
 */
function fixtureRows() {
    return [
        {
            id: 1, label: "Bùi Anh", sublabel: "Line lead",
            flags: { day_badges: { "2026-08-16": { label: "BT", color: "#5A4BB0",
                                                   title: "On authorized trip" } } },
            cells: {
                "2026-08-10": cell(8, { weekday: {} }),
                "2026-08-11": cell(8, { weekday: { value: 3, state: "draft" } }),
                "2026-08-12": cell(8, { weekday: { value: 2, state: "submitted", editable: false,
                                                   lock_reason: "Already submitted." } }),
                "2026-08-13": cell(8, { weekday: { value: 1, state: "approved", editable: false,
                                                   bonus: 1 } }),
                "2026-08-14": cell(0, { weekday: {} }),
                "2026-08-15": cell(0, { weekend: {} }),
                "2026-08-16": cell(0, {}, { editable: false, lock_reason: "On a business trip." }),
            },
        },
        {
            id: 2, label: "Chi Mai", sublabel: "Packer", flags: {},
            cells: Object.fromEntries(DAYS.map((d) => [d, cell(0, { weekday: {} })])),
        },
    ];
}

function makeAdapter(over = {}) {
    return {
        fetch: () => Promise.resolve({
            days: days(), measures: MEASURES, rows: fixtureRows(),
        }),
        save: (payload) => Promise.resolve({
            results: payload.cells.map((c) => ({ ...c, ok: true })),
        }),
        ...over,
    };
}

async function mountGrid(props = {}) {
    const grid = await mountWithCleanup(WeekGrid, {
        props: { adapter: makeAdapter(), ...props },
    });
    await animationFrame();
    return grid;
}

const cellAt = (rowId, iso) => queryFirst(`[data-cell="${rowId}|${iso}"]`);

// =====================================================================
//  T1 — cell anatomy v2
// =====================================================================
test("T1 a cell renders its hours as a plain number and nothing else", async () => {
    await mountGrid();
    const mon = cellAt(1, "2026-08-10");
    expect(queryText(".bwg-prim__v", { root: mon })).toBe("8");
    expect(queryAll(".bwg-chip", { root: mon })).toHaveLength(0);
});

test("T1 a chip appears ONLY where hours were entered, never per applicable rate", async () => {
    await mountGrid();
    // Monday: weekday OT applies (it is in the payload) but holds 0 hours
    expect(queryAll(".bwg-chip", { root: cellAt(1, "2026-08-10") })).toHaveLength(0);
    // Saturday: weekend OT applies, still nothing entered
    expect(queryAll(".bwg-chip", { root: cellAt(1, "2026-08-15") })).toHaveLength(0);
    // Tuesday: 3 h really are there
    const tue = cellAt(1, "2026-08-11");
    expect(queryAll(".bwg-chip", { root: tue })).toHaveLength(1);
    expect(queryText(".bwg-chip__v", { root: tue })).toBe("+3");
    // and the whole second row (all zeros) draws no chip at all
    expect(queryAll(`[data-cell^="2|"] .bwg-chip`)).toHaveLength(0);
});

test("T1 NO RATE reaches any cell — the owner's actual complaint", async () => {
    await mountGrid();
    for (const el of queryAll(".bwg-cell")) {
        expect(el.textContent).not.toInclude("%");
        expect(el.textContent).not.toInclude("150");
        expect(el.textContent).not.toInclude("200");
    }
    // …while the legend says both, once
    const legend = queryAllTexts(".bwg-legend .bwg-lg");
    expect(legend.join(" ")).toInclude("150%");
    expect(legend.join(" ")).toInclude("200%");
    expect(legend.join(" ")).toInclude("Weekday overtime");
});

test("T1 the legend follows the consumer's measure order and colours", async () => {
    await mountGrid();
    const names = queryAllTexts(".bwg-legend .bwg-lg__n");
    expect(names).toEqual(["Weekday overtime", "Weekend overtime"]);
    expect(queryAll(".bwg-legend .bwg-lg")[0].style.getPropertyValue("--bwg-chip-c").trim())
        .toBe("#5A4BB0");
});

test("T1 the status micro-dot tells draft from submitted from approved", async () => {
    await mountGrid();
    expect(queryAll(".bwg-sdot--draft", { root: cellAt(1, "2026-08-11") })).toHaveLength(1);
    expect(queryAll(".bwg-sdot--sent", { root: cellAt(1, "2026-08-12") })).toHaveLength(1);
    expect(queryAll(".bwg-sdot--ok", { root: cellAt(1, "2026-08-13") })).toHaveLength(1);
    // an approved chip carrying bonus hours is marked, and says so in its title
    const thu = queryFirst(".bwg-chip", { root: cellAt(1, "2026-08-13") });
    expect(thu).toHaveClass("bwg-chip--split");
    expect(thu.getAttribute("title")).toInclude("bonus");
});

test("T1 an empty cell is empty; the + is an affordance, not content", async () => {
    await mountGrid();
    const fri = cellAt(1, "2026-08-14");
    expect(queryAll(".bwg-prim__v", { root: fri })).toHaveLength(0);
    expect(queryAll(".bwg-plus", { root: fri })).toHaveLength(1);
});

test("T1 consumer flags still render: the day badge and the lock", async () => {
    await mountGrid();
    const sun = cellAt(1, "2026-08-16");
    expect(queryText(".bwg-badge", { root: sun })).toBe("BT");
    expect(queryAll(".bwg-mark--lock", { root: sun })).toHaveLength(1);
    expect(sun).toHaveClass("bwg-cell--locked");
});

test("T1 the footer sums each day and the row column sums each week", async () => {
    await mountGrid();
    const foot = queryAll(".bwg-foot");
    // corner + 7 days + grand total
    expect(foot).toHaveLength(9);
    expect(queryText(".bwg-foot__v", { root: foot[1] })).toBe("8");   // Monday REG
    expect(queryText(".bwg-foot__x", { root: foot[2] })).toBe("+3");  // Tuesday OT
    const rowTot = queryAll(".bwg-tot")[0];
    expect(queryText(".bwg-tot__v", { root: rowTot })).toBe("32");    // 4 × 8 h
    expect(queryText(".bwg-tot__x", { root: rowTot })).toBe("+6");    // 3 + 2 + 1
});

test("T1 'only rows with entries' hides the rows that hold nothing", async () => {
    await mountGrid();
    expect(queryAll(".bwg-name")).toHaveLength(2);
    await click(".bwg-chipbtn");
    await animationFrame();
    expect(queryAll(".bwg-name")).toHaveLength(1);
    expect(queryText(".bwg-name__l")).toBe("Bùi Anh");
});

// =====================================================================
//  T2 — the cell editor
// =====================================================================
test("T2 clicking a cell opens the editor in the OVERLAY, not inside the grid", async () => {
    await mountGrid();
    await click(cellAt(1, "2026-08-10"));
    await animationFrame();
    const panel = queryFirst(".bwgx");
    expect(panel).not.toBe(null);
    // W43: it mounts outside the grid root, which is the whole point
    expect(queryFirst(".bwg").contains(panel)).toBe(false);
    expect(queryText(".bwgx-head__t")).toBe("Bùi Anh");
});

test("T2 the editor writes the rate and the name — the second and last place", async () => {
    await mountGrid();
    await click(cellAt(1, "2026-08-10"));
    await animationFrame();
    expect(queryAllTexts(".bwgx-rate")).toEqual(["150%"]);
    expect(queryText(".bwgx-sect__h")).toBe("Overtime");
});

test("T2 the editor offers only the OT types that APPLY on that day", async () => {
    await mountGrid();
    await click(cellAt(1, "2026-08-15"));   // Saturday: weekend only
    await animationFrame();
    expect(queryAllTexts(".bwgx-rate")).toEqual(["200%"]);
});

test("T2 Done STAGES through the dirty mechanism — it never saves", async () => {
    const staged = [];
    const adapter = makeAdapter({
        save: () => { throw new Error("the editor must not save"); },
    });
    await mountWithCleanup(WeekGrid, {
        props: { adapter, onDirty: (l) => staged.push(l) },
    });
    await animationFrame();
    await click(cellAt(1, "2026-08-14"));
    await animationFrame();
    const input = queryFirst(".bwgx-in");
    input.value = "7.5";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    await animationFrame();
    await click(".bwgx-btn--primary");
    await animationFrame();
    const last = staged.at(-1);
    expect(last).toHaveLength(1);
    expect(last[0]).toInclude("rowId");
    expect(last[0].value).toBe(7.5);
    expect(last[0].dayISO).toBe("2026-08-14");
    // the cell now shows the staged outcome and the tray is the commit point
    expect(queryText(".bwg-prim__v", { root: cellAt(1, "2026-08-14") })).toBe("7.5");
    expect(queryText(".bwg-tray__info")).toInclude("1 cell edited");
    expect(queryAll(".bwg-btn--primary")).toHaveLength(1);
});

test("T2 Esc discards, and the panel closes without staging", async () => {
    const staged = [];
    await mountGrid({ onDirty: (l) => staged.push(l) });
    await click(cellAt(1, "2026-08-14"));
    await animationFrame();
    const input = queryFirst(".bwgx-in");
    input.value = "6";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    await animationFrame();
    await press("Escape");
    await animationFrame();
    expect(queryAll(".bwgx")).toHaveLength(0);
    expect(staged.at(-1)).toHaveLength(0);
    expect(queryAll(".bwg-prim__v", { root: cellAt(1, "2026-08-14") })).toHaveLength(0);
});

test("T2 a locked OT chip is shown with its reason instead of a stepper", async () => {
    await mountGrid();
    await click(cellAt(1, "2026-08-12"));   // submitted → locked
    await animationFrame();
    expect(queryAll(".bwgx-locked")).toHaveLength(1);
    expect(queryText(".bwgx-locked__r")).toBe("Already submitted.");
});

test("T2 the ceiling bar reads the consumer's payload and moves with the steppers", async () => {
    await mountGrid({
        editorInfo: ({ values }) => ({
            ceiling: { label: "Overtime this month", used: 30 + (values.weekday || 0), cap: 40 },
            warnings: (30 + (values.weekday || 0)) > 40
                ? [{ tone: "warn", text: "past the monthly ceiling — recorded as bonus hours" }]
                : [],
        }),
    });
    await click(cellAt(1, "2026-08-10"));
    await animationFrame();
    expect(queryText(".bwgx-ceil__top span:last-child")).toBe("30 / 40 h");
    expect(queryAll(".bwgx-warn")).toHaveLength(0);

    // push the weekday stepper past the cap
    const otInput = queryAll(".bwgx-in")[1];
    otInput.value = "12";
    otInput.dispatchEvent(new Event("input", { bubbles: true }));
    await animationFrame();
    expect(queryText(".bwgx-ceil__top span:last-child")).toBe("42 / 40 h");
    expect(queryFirst(".bwgx-ceil__fill")).toHaveClass("bwgx-ceil__fill--danger");
    // ADVISORY: it warns, it does not block
    expect(queryText(".bwgx-warn")).toInclude("bonus hours");
    expect(queryFirst(".bwgx-btn--primary").disabled).toBe(false);
});

test("T2 a throwing editorInfo degrades to no bar, never to no editor (W40)", async () => {
    await mountGrid({
        editorInfo: () => { throw new Error("boom"); },
    });
    await click(cellAt(1, "2026-08-10"));
    await animationFrame();
    expect(queryAll(".bwgx")).toHaveLength(1);
    expect(queryAll(".bwgx-ceil")).toHaveLength(0);
});

test("T2 a second Enter does not stack a second editor (W43)", async () => {
    await mountGrid();
    await click(cellAt(1, "2026-08-10"));
    await animationFrame();
    await click(cellAt(1, "2026-08-11"));
    await animationFrame();
    expect(queryAll(".bwgx")).toHaveLength(1);
    expect(queryText(".bwgx-head__s")).toInclude("Tue");
});

// =====================================================================
//  T3 — keyboard
// =====================================================================
test("T3 arrows move the focused cell", async () => {
    await mountGrid();
    await click(cellAt(1, "2026-08-10"));
    await animationFrame();
    await press("Escape");            // close the editor, keep the focus
    await animationFrame();
    await press("ArrowRight");
    await animationFrame();
    expect(cellAt(1, "2026-08-11")).toHaveClass("bwg-cell--focus");
    await press("ArrowDown");
    await animationFrame();
    expect(cellAt(2, "2026-08-11")).toHaveClass("bwg-cell--focus");
});

test("T3 typing a digit edits in place — the fast path, no popover", async () => {
    const staged = [];
    await mountGrid({ onDirty: (l) => staged.push(l) });
    await click(cellAt(1, "2026-08-14"));
    await animationFrame();
    await press("Escape");
    await animationFrame();
    await press("6");
    await animationFrame();
    expect(queryAll(".bwgx")).toHaveLength(0);          // no editor
    expect(queryAll(".bwg-input")).toHaveLength(1);     // an inline input
    await press("Enter");
    await animationFrame();
    expect(staged.at(-1)[0].value).toBe(6);
});

test("T3 Ctrl+D fills down from the cell above", async () => {
    const staged = [];
    await mountGrid({ onDirty: (l) => staged.push(l) });
    await click(cellAt(2, "2026-08-10"));   // row 2, Monday — empty
    await animationFrame();
    await press("Escape");
    await animationFrame();
    await keyDown("d", { ctrlKey: true });
    await animationFrame();
    const last = staged.at(-1);
    expect(last).toHaveLength(1);
    expect(last[0].rowId).toBe(2);
    expect(last[0].value).toBe(8);          // row 1's Monday
});

test("T3 the focused cell carries a visible ring", async () => {
    await mountGrid();
    await click(cellAt(1, "2026-08-10"));
    await animationFrame();
    await press("Escape");
    await animationFrame();
    expect(cellAt(1, "2026-08-10")).toHaveClass("bwg-cell--focus");
    expect(queryAll(".bwg-helpbtn")).toHaveLength(1);   // the shortcut map exists
});

test("T3 Discard throws the whole staging away without a save", async () => {
    const adapter = makeAdapter({
        save: () => { throw new Error("Discard must not save"); },
    });
    await mountWithCleanup(WeekGrid, { props: { adapter } });
    await animationFrame();
    await click(cellAt(1, "2026-08-14"));
    await animationFrame();
    const input = queryFirst(".bwgx-in");
    input.value = "5";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    await animationFrame();
    await click(".bwgx-btn--primary");
    await animationFrame();
    expect(queryText(".bwg-tray__info")).toInclude("1 cell edited");
    await click(".bwg-tray .bwg-btn:not(.bwg-btn--primary):not(.bwg-btn--ghost)");
    await animationFrame();
    expect(queryAll(".bwg-prim__v", { root: cellAt(1, "2026-08-14") })).toHaveLength(0);
});
