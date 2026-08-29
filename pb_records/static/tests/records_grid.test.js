/** @odoo-module **/
/**
 * RECORDS R2 — the grid's editing rules, against no server at all.
 *
 * The grid's contract is a plain state object and a handful of pure mutations
 * over it, which is why these tests need neither a model nor a mock RPC: what
 * is being pinned is the behaviour a spreadsheet is JUDGED on — selection,
 * keyboard focus, staging, paste, undo/redo, and "set this for everybody I
 * ticked" — and every one of those is a decision the client makes on its own.
 *
 * What is deliberately NOT here: whether a value is legal. That is the server's
 * answer (`preview_changes`), it is tested in `tests/test_records_r2_desk.py`,
 * and a client-side copy of it would be the second opinion this whole phase is
 * built to avoid.
 */
import { describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { press, queryAll, queryAllTexts, queryFirst } from "@odoo/hoot-dom";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";

import {
    RecordsGrid, createGridState, cellKey, dirtyCount, setValue, setForRows,
    revertColumn, undo, redo, pasteAt, parseClipboard, toggleRow, selectRange,
    clearSelection, selectLoaded, initialsOf,
} from "@pb_records/js/records_grid";

describe.current.tags("desktop");

// `mountWithCleanup` boots the full web env, and that env fetches the mail
// store — without the mail models declared every mount dies on "could not get
// model discuss.channel from server environment" before a single assertion
// runs. Nothing here is about mail; this is the price of mounting a component.
defineMailModels();

const COLUMNS = [
    { id: "f:hr.employee:job_title", group: "employee", label: "Job title",
      sub: "Designation ← DESIG", ttype: "char", selection: [], m2o: null,
      editable: true, model: "hr.employee", field: "job_title" },
    { id: "f:hr.contract:shuipart", group: "contract", label: "SHUI participation",
      sub: "SHUI ← SHUIPARTICIP", ttype: "selection",
      selection: [{ key: "YES", label: "YES" }, { key: "NO", label: "NO" }],
      m2o: null, editable: true, model: "hr.contract", field: "shuipart" },
    { id: "f:hr.employee:barcode", group: "employee", label: "Badge id",
      sub: "", ttype: "char", selection: [], m2o: null, editable: false,
      model: "hr.employee", field: "barcode" },
];

function person(id, name, extras = {}) {
    return {
        id, name, code: `E${id}`, avatar: "", department: "Production",
        job: "Operator", contract_id: id * 10, contract_state: "open",
        status: "Active",
        values: {
            "f:hr.employee:job_title": { v: `Operator ${id}`, label: `Operator ${id}` },
            "f:hr.contract:shuipart": { v: "YES", label: "YES" },
            "f:hr.employee:barcode": { v: `B${id}`, label: `B${id}` },
        },
        ...extras,
    };
}

function state(n = 4) {
    const rows = [];
    for (let i = 1; i <= n; i++) { rows.push(person(i, `Person ${i}`)); }
    return createGridState({ columns: [...COLUMNS], rows, total: n });
}

async function mountGrid(st, props = {}) {
    const grid = await mountWithCleanup(RecordsGrid, { props: { state: st, ...props } });
    // The grid listens for keys on ITSELF (`tabindex="0"`), so a test that
    // presses a key without focusing it is testing the document body.
    queryFirst(".rd-grid").focus();
    await animationFrame();
    return grid;
}

/** A modifier-click. `click()` does not carry `ctrlKey` through to the handler. */
async function modClick(el, mods = {}) {
    el.dispatchEvent(new MouseEvent("click", { bubbles: true, ...mods }));
    await animationFrame();
}

// =====================================================================
//  Selection
// =====================================================================
test("clicking a row's box selects it, clicking again clears it", async () => {
    const st = state();
    toggleRow(st, 2);
    expect(st.selected).toEqual([2]);
    toggleRow(st, 2);
    expect(st.selected).toEqual([]);
});

test("shift-range selects everything between the anchor and the click", async () => {
    const st = state(5);
    toggleRow(st, 1);
    selectRange(st, 0, 3);
    expect(st.selected.sort()).toEqual([1, 2, 3, 4]);
});

test("ctrl-click toggles one row without disturbing the rest", async () => {
    const st = state();
    await mountGrid(st);
    const cells = queryAll(".rd-row .rd-c-data");
    await modClick(cells[0], { ctrlKey: true });
    expect(st.selected).toEqual([1]);
    await modClick(cells[3], { ctrlKey: true });   // row 2, first data column
    expect(st.selected.sort()).toEqual([1, 2]);
});

test("Escape clears the selection", async () => {
    const st = state();
    selectLoaded(st);
    expect(st.selected.length).toBe(4);
    await mountGrid(st);
    await press("Escape");
    await animationFrame();
    expect(st.selected).toEqual([]);
});

test("select-all-loaded ticks every loaded row and nothing else", async () => {
    const st = state(3);
    st.rows.push(null);            // a page that has not arrived
    st.total = 4;
    selectLoaded(st);
    expect(st.selected).toEqual([1, 2, 3]);
});

// =====================================================================
//  Keyboard
// =====================================================================
test("arrow keys move the focused cell inside the grid", async () => {
    const st = state();
    await mountGrid(st);
    await modClick(queryFirst(".rd-row .rd-c-data"));
    queryFirst(".rd-grid").focus();
    await animationFrame();
    expect(st.focus).toEqual({ r: 0, c: 0 });
    await press("ArrowDown");
    await press("ArrowRight");
    await animationFrame();
    expect(st.focus).toEqual({ r: 1, c: 1 });
    await press("ArrowUp");
    await press("ArrowLeft");
    await animationFrame();
    expect(st.focus).toEqual({ r: 0, c: 0 });
});

test("arrow keys stop at the edges rather than wrapping", async () => {
    const st = state();
    await mountGrid(st);
    await modClick(queryFirst(".rd-row .rd-c-data"));
    queryFirst(".rd-grid").focus();
    await press("ArrowUp");
    await press("ArrowLeft");
    await animationFrame();
    expect(st.focus).toEqual({ r: 0, c: 0 });
});

test("Enter opens the editor and Escape closes it without staging anything", async () => {
    const st = state();
    await mountGrid(st);
    await modClick(queryFirst(".rd-row .rd-c-data"));
    queryFirst(".rd-grid").focus();
    await press("Enter");
    await animationFrame();
    expect(queryAll(".rd-editor").length).toBe(1);
    await press("Escape");
    await animationFrame();
    expect(queryAll(".rd-editor").length).toBe(0);
    expect(dirtyCount(st).values).toBe(0);
});

test("a read-only column refuses to open an editor", async () => {
    const st = state();
    await mountGrid(st);
    st.focus = { r: 0, c: 2 };            // the locked Badge id column
    await press("Enter");
    await animationFrame();
    expect(queryAll(".rd-editor").length).toBe(0);
});

// =====================================================================
//  Staging, undo, redo
// =====================================================================
test("an edit stages a value and never touches the row's own data", async () => {
    const st = state();
    setValue(st, 1, "f:hr.employee:job_title", "Line Lead", "Line Lead");
    expect(dirtyCount(st)).toEqual({ values: 1, people: 1 });
    expect(st.dirty[cellKey(1, "f:hr.employee:job_title")].value).toBe("Line Lead");
    expect(st.rows[0].values["f:hr.employee:job_title"].v).toBe("Operator 1");
});

test("undo puts a cell back and redo puts the edit back again", async () => {
    const st = state();
    setValue(st, 1, "f:hr.employee:job_title", "Line Lead", "Line Lead");
    setValue(st, 2, "f:hr.employee:job_title", "Fitter", "Fitter");
    expect(dirtyCount(st).values).toBe(2);
    undo(st);
    expect(dirtyCount(st).values).toBe(1);
    undo(st);
    expect(dirtyCount(st).values).toBe(0);
    redo(st);
    redo(st);
    expect(dirtyCount(st).values).toBe(2);
    expect(st.dirty[cellKey(2, "f:hr.employee:job_title")].value).toBe("Fitter");
});

test("undo of a bulk fill is ONE step, not one per row", async () => {
    const st = state();
    setForRows(st, [1, 2, 3, 4], "f:hr.contract:shuipart", "NO", "NO");
    expect(dirtyCount(st)).toEqual({ values: 4, people: 4 });
    undo(st);
    expect(dirtyCount(st).values).toBe(0);
});

test("Ctrl-Z from the grid undoes, Shift-Ctrl-Z redoes", async () => {
    const st = state();
    await mountGrid(st);
    setValue(st, 1, "f:hr.employee:job_title", "Line Lead", "Line Lead");
    await press(["ctrl", "z"]);
    await animationFrame();
    expect(dirtyCount(st).values).toBe(0);
    await press(["ctrl", "shift", "z"]);
    await animationFrame();
    expect(dirtyCount(st).values).toBe(1);
});

test("reverting a column drops only that column's edits", async () => {
    const st = state();
    setValue(st, 1, "f:hr.employee:job_title", "Line Lead", "Line Lead");
    setValue(st, 1, "f:hr.contract:shuipart", "NO", "NO");
    revertColumn(st, "f:hr.employee:job_title");
    expect(dirtyCount(st).values).toBe(1);
    expect(st.dirty[cellKey(1, "f:hr.contract:shuipart")].value).toBe("NO");
});

// =====================================================================
//  "Set for everyone selected"
// =====================================================================
test("Set for selected fills the ticked rows and leaves the rest alone", async () => {
    const st = state();
    toggleRow(st, 2);
    toggleRow(st, 4);
    const n = setForRows(st, [...st.selected], "f:hr.contract:shuipart", "NO", "NO");
    expect(n).toBe(2);
    expect(dirtyCount(st)).toEqual({ values: 2, people: 2 });
    expect(st.dirty[cellKey(2, "f:hr.contract:shuipart")].label).toBe("NO");
    expect(st.dirty[cellKey(1, "f:hr.contract:shuipart")]).toBe(undefined);
});

test("Set for selected refuses a read-only column outright", async () => {
    const st = state();
    selectLoaded(st);
    expect(setForRows(st, [...st.selected], "f:hr.employee:barcode", "X", "X")).toBe(0);
    expect(dirtyCount(st).values).toBe(0);
});

// =====================================================================
//  Paste
// =====================================================================
test("a clipboard block is split on tabs, then on commas", async () => {
    expect(parseClipboard("a\tb\nc\td")).toEqual([["a", "b"], ["c", "d"]]);
    expect(parseClipboard("a,b\nc,d")).toEqual([["a", "b"], ["c", "d"]]);
});

test("pasting a 2x2 block fills four cells down and right", async () => {
    const st = state();
    const n = pasteAt(st, 0, 0, [["Line Lead", "NO"], ["Fitter", "NO"]]);
    expect(n).toBe(4);
    expect(dirtyCount(st)).toEqual({ values: 4, people: 2 });
    expect(st.dirty[cellKey(1, "f:hr.employee:job_title")].value).toBe("Line Lead");
    expect(st.dirty[cellKey(2, "f:hr.contract:shuipart")].value).toBe("NO");
});

test("a paste runs off neither the loaded rows nor the read-only columns", async () => {
    const st = state(2);
    // three rows of two columns, starting one column before the locked one
    const n = pasteAt(st, 0, 1, [["NO", "X"], ["NO", "X"], ["NO", "X"]]);
    expect(n).toBe(2);                       // 2 rows exist, 1 writable column
    expect(st.dirty[cellKey(1, "f:hr.employee:barcode")]).toBe(undefined);
});

test("a whole paste is one undo step", async () => {
    const st = state();
    pasteAt(st, 0, 0, [["Line Lead", "NO"], ["Fitter", "NO"]]);
    undo(st);
    expect(dirtyCount(st).values).toBe(0);
});

// =====================================================================
//  What the Review button says
// =====================================================================
test("the staged count is what the Review button counts", async () => {
    const st = state();
    expect(dirtyCount(st)).toEqual({ values: 0, people: 0 });
    setForRows(st, [1, 2, 3], "f:hr.contract:shuipart", "NO", "NO");
    setValue(st, 1, "f:hr.employee:job_title", "Line Lead", "Line Lead");
    expect(dirtyCount(st)).toEqual({ values: 4, people: 3 });
});

test("a dirty cell shows the new value with the old one struck through", async () => {
    const st = state();
    setValue(st, 1, "f:hr.employee:job_title", "Line Lead", "Line Lead");
    await mountGrid(st);
    await animationFrame();
    expect(queryAll(".rd-cell.dirty")).toHaveLength(1);
    expect(queryAllTexts(".rd-cell.dirty .rd-v")[0]).toBe("Line Lead");
    expect(queryAllTexts(".rd-cell.dirty .rd-was")[0]).toBe("Operator 1");
});

test("a refusal paints the cell and carries the reason as its tooltip", async () => {
    const st = state();
    setValue(st, 1, "f:hr.contract:shuipart", "Maybe", "Maybe");
    st.refusals[cellKey(1, "f:hr.contract:shuipart")] =
        "'Maybe' is not one of the choices — use YES, NO";
    await mountGrid(st);
    await animationFrame();
    expect(queryAll(".rd-cell.bad").length).toBe(1);
    expect(queryFirst(".rd-bad-dot").title)
        .toBe("'Maybe' is not one of the choices — use YES, NO");
});

// =====================================================================
//  Windowing + a person with no contract
// =====================================================================
test("only the visible slice of a huge roster is in the DOM", async () => {
    const st = createGridState({
        columns: [COLUMNS[0]], rows: new Array(4500).fill(null), total: 4500,
    });
    for (let i = 0; i < 120; i++) { st.rows[i] = person(i + 1, `Person ${i + 1}`); }
    await mountGrid(st);
    await animationFrame();
    expect(queryAll(".rd-row").length).toBeLessThan(200);
    expect(queryFirst(".rd-body").style.height).toBe(`${4500 * 46}px`);
});

test("a contract cell for somebody with no contract says so and cannot be typed in", async () => {
    const st = state(1);
    st.rows[0].contract_id = false;
    await mountGrid(st);
    await animationFrame();
    expect(queryAllTexts(".rd-nocon")[0]).toBe("No contract");
    st.focus = { r: 0, c: 1 };
    await press("Enter");
    await animationFrame();
    expect(queryAll(".rd-editor").length).toBe(0);
});

test("initials fall back to a single character rather than an empty avatar", async () => {
    expect(initialsOf("Nguyen Van A")).toBe("NV");
    expect(initialsOf("")).toBe("?");
});

test("clearing the selection is a function, not a re-render side effect", async () => {
    const st = state();
    selectLoaded(st);
    clearSelection(st);
    expect(st.selected).toEqual([]);
    expect(st.allMatching).toBe(false);
});
