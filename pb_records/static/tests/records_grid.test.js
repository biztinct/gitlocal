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
import { click, press, queryAll, queryAllTexts, queryFirst } from "@odoo/hoot-dom";
import { mountWithCleanup, patchTranslations } from "@web/../tests/web_test_helpers";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";

import {
    RecordsGrid, createGridState, cellKey, dirtyCount, setValue, setForRows,
    revertColumn, undo, redo, pasteAt, parseClipboard, toggleRow, selectRange,
    clearSelection, selectLoaded, initialsOf,
} from "@pb_records/js/records_grid";
import {
    RdDropZone, RdFileMenu, RdFileReview, fileApplyLabel, fileSummaryLine,
    isNarrow, readingLine,
} from "@pb_records/js/records_import";
import {
    RdReviewList, footerReserve, isOnTop, reviewBlocks, GROUP_MIN, SAFE_GAP,
} from "@pb_records/js/records_review";

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

// =====================================================================
//  R3 — a file arrives, and the drawer reads it back
//
//  Same rule as the rest of this file: what is pinned here is what the CLIENT
//  decides on its own — the drag state, the three tabs, and the two sentences
//  a person reads before pressing Apply. Whether a value is legal is still the
//  server's answer, and it is tested in `tests/test_records_r3_roundtrip.py`.
// =====================================================================
function fire(el, type, extra = {}) {
    const ev = new Event(type, { bubbles: true, cancelable: true });
    Object.assign(ev, extra);
    el.dispatchEvent(ev);
}

test("the drop overlay appears on dragenter and hides again on dragleave", async () => {
    await mountWithCleanup(RdDropZone, { props: { onFile: () => {} } });
    const zone = queryFirst(".rd-drop");
    expect(queryAll(".rd-drop-over")).toHaveLength(0);

    fire(zone, "dragenter");
    await animationFrame();
    expect(queryAll(".rd-drop-over")).toHaveLength(1);
    expect(queryAllTexts(".rd-drop-over")[0]).toBe("Drop to review changes");

    fire(zone, "dragleave");
    await animationFrame();
    expect(queryAll(".rd-drop-over")).toHaveLength(0);
});

test("crossing on to a child does not flicker the overlay off", async () => {
    // `dragenter`/`dragleave` fire for every element the pointer crosses, so a
    // boolean would drop the overlay the instant the file moved over the text
    // inside the zone. The depth counter is what makes it steady.
    await mountWithCleanup(RdDropZone, { props: { onFile: () => {} } });
    const zone = queryFirst(".rd-drop");
    fire(zone, "dragenter");
    fire(zone, "dragenter");          // on to the label inside
    await animationFrame();
    fire(zone, "dragleave");          // off the label, still over the zone
    await animationFrame();
    expect(queryAll(".rd-drop-over")).toHaveLength(1);
    fire(zone, "dragleave");
    await animationFrame();
    expect(queryAll(".rd-drop-over")).toHaveLength(0);
});

const PEEK = {
    summary: {
        rows: 20, people_matched: 19, people_unmatched: 3,
        changes_ok: 41, changes_same: 6, changes_refused: 2,
        people_changed: 19, cells_blank: 4, columns_used: 3,
        columns_ignored: ["Shoe size", "Favourite colour"],
    },
    items: [
        { emp_id: 1, emp_name: "Person 1", field_id: "f:hr.employee:job_title",
          field_label: "Job title", old_label: "Operator", new_label: "Line Lead",
          status: "ok", why: "" },
        { emp_id: 2, emp_name: "Person 2", field_id: "f:hr.contract:shuipart",
          field_label: "SHUI participation", old_label: "YES", new_label: "",
          status: "refused", why: "'Maybe' is not one of the choices — use YES, NO" },
        { emp_id: 3, emp_name: "Person 3", field_id: "f:hr.employee:job_title",
          field_label: "Job title", old_label: "Fitter", new_label: "Fitter",
          status: "same", why: "Already set to this." },
    ],
    unmatched: [
        { row: 7, code: "X-9", name: "Nobody Here", email: "", why: "Nobody here matches X-9.",
          values: { "f:hr.employee:job_title": "Line Lead" } },
    ],
};

async function mountReview(props = {}) {
    return mountWithCleanup(RdFileReview, {
        props: {
            summary: PEEK.summary, items: PEEK.items,
            unmatched: PEEK.unmatched, identity: "code", ...props,
        },
    });
}

test("the file drawer says what the file would do, in one line", async () => {
    // `_t` returns a LAZY `TranslatedString`, and evaluating one before
    // translations are loaded THROWS — which is what concatenating `_t`
    // fragments into a sentence does the instant it is concatenated. Mounting a
    // component loads them; a pure function called straight from a test does
    // not. An empty catalogue marks them loaded (RD).
    patchTranslations();
    expect(fileSummaryLine(PEEK.summary)).toBe(
        "This file changes 41 values on 19 people · 3 rows match nobody · "
        + "2 values need a look · 6 are already set");
    expect(fileSummaryLine({ changes_ok: 1, people_changed: 1 }))
        .toBe("This file changes 1 value on 1 person");
    expect(fileSummaryLine({})).toBe("This file changes nothing yet");
});

test("the Apply button counts what goes in and what stays behind", async () => {
    patchTranslations();
    expect(fileApplyLabel(PEEK.summary)).toBe("Apply 41 · leave 2");
    expect(fileApplyLabel({ changes_ok: 3 })).toBe("Apply 3 changes");
    expect(fileApplyLabel({ changes_ok: 1 })).toBe("Apply 1 change");
    expect(fileApplyLabel({ changes_ok: 0 })).toBe("Nothing to apply");
});

test("file mode renders three tabs, each counting its own contents", async () => {
    await mountReview();
    expect(queryAll(".rd-file-tab")).toHaveLength(3);
    expect(queryAllTexts(".rd-file-tab .lb"))
        .toEqual(["Changes", "Unmatched", "Ignored columns"]);
    // 41 ok + 2 refused are what the Changes tab is about; `same` rows are not
    // changes and are not counted as any.
    expect(queryAllTexts(".rd-file-tab .ct")).toEqual(["43", "3", "2"]);
});

test("the Changes tab shows old to new and never the unchanged rows", async () => {
    await mountReview();
    expect(queryAll(".rd-rev-row")).toHaveLength(2);
    expect(queryAllTexts(".rd-rev-row.ok .nv")[0]).toBe("Line Lead");
    expect(queryAllTexts(".rd-rev-row.refused .wy")[0])
        .toBe("'Maybe' is not one of the choices — use YES, NO");
});

test("arrow keys walk the tabs, and each tab shows its own panel", async () => {
    await mountReview();
    queryFirst(".rd-file-tab").focus();
    await press("ArrowRight");
    await animationFrame();
    expect(queryAll(".rd-unmatched")).toHaveLength(1);
    expect(queryAllTexts(".rd-unmatched-why")[0]).toBe("Nobody here matches X-9.");
    await press("ArrowRight");
    await animationFrame();
    expect(queryAllTexts(".rd-ignored-chip"))
        .toEqual(["Shoe size", "Favourite colour"]);
    await press("ArrowLeft");
    await animationFrame();
    expect(queryAll(".rd-unmatched")).toHaveLength(1);
});

test("an unmatched row offers to be matched by hand, and nothing else", async () => {
    await mountReview();
    queryFirst(".rd-file-tab").focus();
    await press("ArrowRight");
    await animationFrame();
    expect(queryAll(".rd-unmatched .pbim-btn")).toHaveLength(1);
    expect(queryAllTexts(".rd-unmatched .pbim-btn")[0]
           .includes("Find person")).toBe(true);
    // The typeahead is not on screen until it is asked for — an unmatched row
    // is a fact first and a task second.
    expect(queryAll(".rd-picker")).toHaveLength(0);
});

// =====================================================================
//  R4 — the defect round
//
//  Four of the six defects are decisions the client makes with what the
//  server already said: how the review list FOLDS (D2), how far the drawer's
//  footer must stay off the corner (D1), which header layout a width gets
//  (D3), and what the veil says while a file is being read (D6). All four are
//  pure functions or one-prop components, and all four are asserted here.
// =====================================================================

/** N people, all given the identical change. */
function bulkItems(count, extra = {}) {
    const out = [];
    for (let i = 1; i <= count; i++) {
        out.push({
            emp_id: i, emp_name: `Person ${i}`,
            field_id: "f:hr.contract:shuipart", field_label: "SHUI participation",
            old_label: "YES", new_label: "NO", status: "ok", why: "",
            ...extra,
        });
    }
    return out;
}

test("140 people with the identical change are one row, not 140", async () => {
    const blocks = reviewBlocks(bulkItems(140));
    expect(blocks).toHaveLength(1);
    expect(blocks[0].type).toBe("group");
    expect(blocks[0].count).toBe(140);
    expect(blocks[0].names).toHaveLength(140);
    expect(blocks[0].field_label).toBe("SHUI participation");
    expect(blocks[0].old_label).toBe("YES");
    expect(blocks[0].new_label).toBe("NO");
});

test("three is the threshold, and two people stay two people", async () => {
    expect(GROUP_MIN).toBe(3);
    expect(reviewBlocks(bulkItems(2)).map((b) => b.type))
        .toEqual(["person", "person"]);
    expect(reviewBlocks(bulkItems(3)).map((b) => b.type)).toEqual(["group"]);
});

test("mixed changes stay per person, beside the group they are not in", async () => {
    const mixed = [
        ...bulkItems(3),
        { emp_id: 90, emp_name: "Odd One", field_id: "f:hr.employee:job_title",
          field_label: "Job title", old_label: "Operator", new_label: "Line Lead",
          status: "ok", why: "" },
        { emp_id: 91, emp_name: "Other One", field_id: "f:hr.employee:job_title",
          field_label: "Job title", old_label: "Fitter", new_label: "Line Lead",
          status: "ok", why: "" },
    ];
    const blocks = reviewBlocks(mixed);
    expect(blocks.map((b) => b.type)).toEqual(["group", "person", "person"]);
    // A row that is already set is not a change and is in neither shape.
    const withSame = reviewBlocks([
        ...mixed,
        { emp_id: 92, emp_name: "Same One", field_id: "f:hr.employee:job_title",
          field_label: "Job title", old_label: "Fitter", new_label: "Fitter",
          status: "same", why: "" },
    ]);
    expect(withSame).toHaveLength(3);
});

test("a refusal folds separately from an accepted change of the same shape", async () => {
    const blocks = reviewBlocks([
        ...bulkItems(4),
        ...bulkItems(3, { status: "refused", why: "Not one of the choices." })
            .map((i, n) => ({ ...i, emp_id: 500 + n, emp_name: `Bad ${n}` })),
    ]);
    expect(blocks).toHaveLength(2);
    expect(blocks.map((b) => b.status)).toEqual(["ok", "refused"]);
    expect(blocks[1].why).toBe("Not one of the choices.");
});

test("the folded list renders one group row that opens to the names", async () => {
    patchTranslations();
    await mountWithCleanup(RdReviewList, { props: { items: bulkItems(140) } });
    expect(queryAll(".rd-rev-grp")).toHaveLength(1);
    expect(queryAll(".rd-rev-row")).toHaveLength(0);
    expect(queryAllTexts(".rd-rev-grp-head .ct")[0]).toBe("140 people");
    expect(queryAll(".rd-rev-grp-names")).toHaveLength(0);

    // The head is a real `<button>` carrying `aria-expanded`, which is what
    // makes Enter and Space work without a key handler of its own — and a
    // second handler beside the native one would fire the toggle twice
    // (RD14's lesson, met from the other side). So what is pinned here is the
    // element and the state it advertises; the browser supplies the keys, and
    // the live walk is where that is watched happening.
    expect(queryFirst(".rd-rev-grp-head").tagName).toBe("BUTTON");
    expect(queryFirst(".rd-rev-grp-head").getAttribute("aria-expanded"))
        .toBe("false");

    await click(".rd-rev-grp-head");
    await animationFrame();
    expect(queryAll(".rd-rev-grp-names")).toHaveLength(1);
    expect(queryFirst(".rd-rev-grp-head").getAttribute("aria-expanded"))
        .toBe("true");
    expect(queryAllTexts(".rd-rev-grp-names")[0].includes("Person 140"))
        .toBe(true);

    await click(".rd-rev-grp-head");
    await animationFrame();
    expect(queryAll(".rd-rev-grp-names")).toHaveLength(0);
});

test("three mixed changes render three rows and no group", async () => {
    patchTranslations();
    const items = [
        { emp_id: 1, emp_name: "One", field_id: "f:hr.employee:job_title",
          field_label: "Job title", old_label: "A", new_label: "B",
          status: "ok", why: "" },
        { emp_id: 2, emp_name: "Two", field_id: "f:hr.employee:job_title",
          field_label: "Job title", old_label: "C", new_label: "D",
          status: "ok", why: "" },
        { emp_id: 3, emp_name: "Three", field_id: "f:hr.contract:shuipart",
          field_label: "SHUI participation", old_label: "YES", new_label: "NO",
          status: "ok", why: "" },
    ];
    await mountWithCleanup(RdReviewList, { props: { items } });
    expect(queryAll(".rd-rev-row")).toHaveLength(3);
    expect(queryAll(".rd-rev-grp")).toHaveLength(0);
    expect(queryAllTexts(".rd-rev-name")).toEqual(["One", "Two", "Three"]);
});

test("the drawer footer clears whatever floats over the corner", async () => {
    // A pill 48px tall sitting 24px off the bottom of a 900px window, inside
    // the drawer's own column (the drawer is 466px wide, right-aligned in a
    // 1600px viewport).
    const view = { height: 900, left: 1134, right: 1600 };
    const pill = { left: 1470, right: 1576, top: 828, bottom: 876 };
    const reserve = footerReserve([pill], view);
    expect(reserve).toBe(900 - 828 + SAFE_GAP);
    // …and the Apply button therefore starts above the pill's top edge.
    expect(reserve).toBeGreaterThan(view.height - pill.top);

    // Two stacked controls reserve down from the HIGHER one, once.
    const coach = { left: 1450, right: 1576, top: 736, bottom: 786 };
    expect(footerReserve([pill, coach], view)).toBe(900 - 736 + SAFE_GAP);

    // Nothing there, nothing reserved — the drawer does not pad itself for a
    // control that is not installed.
    expect(footerReserve([], view)).toBe(0);
    // A control somewhere else on screen is not in the way.
    expect(footerReserve([{ left: 10, right: 120, top: 828, bottom: 876 }],
                         view)).toBe(0);
});

test("a control the drawer covers reserves nothing", async () => {
    // The two corner helpers stack differently — the copilot pill paints over
    // the drawer, the coach launcher sits under it — and reserving for the
    // covered one would push Apply up to clear something nobody can see. The
    // browser is asked, at the control's own centre.
    const box = { left: 1470, right: 1576, top: 828, bottom: 876,
                  width: 106, height: 48 };
    const pill = { getBoundingClientRect: () => box, contains: () => false };
    const overIt = { contains: () => false };
    expect(isOnTop(pill, { elementFromPoint: () => pill })).toBe(true);
    expect(isOnTop(pill, { elementFromPoint: () => overIt })).toBe(false);
    // A control with no box on screen is not on top of anything.
    const gone = { getBoundingClientRect: () => ({ left: 0, right: 0, top: 0,
                                                   bottom: 0, width: 0, height: 0 }),
                   contains: () => false };
    expect(isOnTop(gone, { elementFromPoint: () => gone })).toBe(false);
});

test("under 1440 the header is one File menu, and at 1440 it is not", async () => {
    expect(isNarrow(1280)).toBe(true);
    expect(isNarrow(1439)).toBe(true);
    expect(isNarrow(1440)).toBe(false);
    expect(isNarrow(1600)).toBe(false);
    expect(isNarrow(1920)).toBe(false);
});

test("the narrow header offers all three file commands in one menu", async () => {
    patchTranslations();
    const seen = [];
    await mountWithCleanup(RdFileMenu, {
        props: {
            narrow: true, countLabel: "3 people",
            onExport: (mode) => seen.push(mode), onFile: () => {},
        },
    });
    expect(queryAll(".rd-filemenu")).toHaveLength(1);
    // The split button and the drop zone are the WIDE layout, and they are not
    // also here — one control per command, never two.
    expect(queryAll(".rd-export")).toHaveLength(0);
    expect(queryAll(".rd-drop")).toHaveLength(0);

    await click(".rd-filemenu-btn");
    await animationFrame();
    expect(queryAllTexts(".rd-scheme-menu .nm"))
        .toEqual(["Export with data", "Export blank template", "Import a file"]);
    await click(".rd-scheme-menu button");
    await animationFrame();
    expect(seen).toEqual(["data"]);
});

test("the wide header keeps the split button beside the drop zone", async () => {
    patchTranslations();
    await mountWithCleanup(RdFileMenu, {
        props: { narrow: false, countLabel: "3 people",
                 onExport: () => {}, onFile: () => {} },
    });
    expect(queryAll(".rd-export")).toHaveLength(1);
    expect(queryAll(".rd-drop")).toHaveLength(1);
    expect(queryAll(".rd-filemenu")).toHaveLength(0);
});

test("the veil says how big the job is as soon as it knows", async () => {
    patchTranslations();
    expect(readingLine("march.xlsx", 0)).toBe("Reading march.xlsx…");
    expect(readingLine("march.xlsx", 4512))
        .toBe("Matching 4,512 rows to people…");
    expect(readingLine("march.xlsx", 1)).toBe("Matching 1 row to people…");
});
