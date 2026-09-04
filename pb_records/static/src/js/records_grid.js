/** @odoo-module **/
/**
 * Records Desk — the grid.
 *
 * A spreadsheet over real records, which means three things stock list views do
 * not do, and they are the whole reason this file exists:
 *
 *   1. **It stages.** Typing changes nothing. Every edit lands in `state.dirty`
 *      and is shown as `old → new` until somebody presses Apply. That is the
 *      safety rail the whole phase is built on, and it is also the thing that
 *      makes bulk editing feel safe enough to do.
 *   2. **It is windowed.** Payobook's roster is 4,500 people. Rows are laid out
 *      against a spacer of the full height and only the visible slice is in the
 *      DOM, so scrolling to person 4,000 costs the same as scrolling to person 4.
 *      Pages of 100 are fetched as the window moves over them.
 *   3. **It has a keyboard.** Arrows move, Enter/F2 edits, Escape backs out,
 *      Tab walks right, typing starts typing, Ctrl-Z undoes, and a clipboard
 *      block pastes into the rectangle below-right of the focused cell.
 *
 * The mutation helpers below are plain functions over a plain state object, and
 * they are exported for the same reason they are plain: the hoot test drives
 * them without a server, and a grid whose editing rules can only be exercised
 * through a mounted component is a grid whose editing rules are not tested.
 *
 * `grid_studio.js` is the precedent for the interaction vocabulary (selection
 * `:444-607`, bulk `:736-755`, paste `:868`), and it is a precedent rather than
 * a base class on purpose — that grid is COLUMN-oriented over one config, this
 * one is ROW-oriented over people. The ideas transpose; the code would not.
 */
import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { RdCellEditor, cellText, labelFor } from "@pb_records/js/records_cells";

export const ROW_H = 46;
const OVERSCAN = 8;
export const PAGE = 100;
/**
 * The hard ceiling on rows in the DOM, whatever the measurement says.
 *
 * `measure()` sizes the window from the scroller's `clientHeight`, and that is
 * only meaningful when something above it constrains the height. Put the grid
 * anywhere that does not — a test fixture, a print stylesheet, a future host
 * that forgets `min-height: 0` — and the scroller grows to fit its own content,
 * `clientHeight` becomes 207,000px, and the "virtualised" grid renders all
 * 4,500 rows. Caught by the hoot test, which is exactly that host (RD12).
 * 120 rows is 5,520px of grid: taller than any viewport, cheap in any DOM.
 */
const MAX_WINDOW = 120;

// ---------------------------------------------------------------------------
//  State + the mutations, as plain functions
// ---------------------------------------------------------------------------
export function cellKey(empId, fieldId) {
    return `${empId}|${fieldId}`;
}

export function createGridState(overrides = {}) {
    return Object.assign({
        columns: [],        // picked cards, in the order they were picked
        rows: [],           // sparse, indexed by position in the match set
        total: 0,
        loading: false,
        selected: [],       // employee ids
        allMatching: false, // "Select all N matching" is on
        anchor: -1,         // shift-range anchor (row index)
        focus: { r: -1, c: -1 },
        editing: null,      // { r, c }
        menu: -1,           // open column menu (column index)
        dirty: {},          // cellKey -> { empId, fieldId, value, label }
        refusals: {},       // cellKey -> sentence
        undoStack: [],
        redoStack: [],
    }, overrides);
}

/** How many values are staged, and over how many people. */
export function dirtyCount(state) {
    const keys = Object.keys(state.dirty);
    const people = new Set(keys.map((k) => state.dirty[k].empId));
    return { values: keys.length, people: people.size };
}

function record(state, entries) {
    if (!entries.length) { return; }
    state.undoStack.push(entries);
    state.redoStack.length = 0;
}

function put(state, empId, fieldId, value, label) {
    const key = cellKey(empId, fieldId);
    const before = state.dirty[key] ? { ...state.dirty[key] } : undefined;
    if (value === undefined) {
        delete state.dirty[key];
    } else {
        state.dirty[key] = { empId, fieldId, value, label };
    }
    delete state.refusals[key];
    return { key, empId, fieldId, before,
             after: value === undefined ? undefined : { empId, fieldId, value, label } };
}

/** Stage one cell. `value === undefined` un-stages it (Revert). */
export function setValue(state, empId, fieldId, value, label, push = true) {
    const entry = put(state, empId, fieldId, value, label);
    if (push) { record(state, [entry]); }
    return entry;
}

/** Stage one value across many people as ONE undoable step. */
export function setForRows(state, empIds, fieldId, value, label) {
    const col = state.columns.find((c) => c.id === fieldId);
    if (!col || !col.editable) { return 0; }
    const entries = empIds.map((id) => put(state, id, fieldId, value, label));
    record(state, entries);
    return entries.length;
}

/** Un-stage every edit in one column. */
export function revertColumn(state, fieldId) {
    const entries = Object.values(state.dirty)
        .filter((d) => d.fieldId === fieldId)
        .map((d) => put(state, d.empId, fieldId, undefined));
    record(state, entries);
    return entries.length;
}

function replay(state, entries, direction) {
    for (const entry of entries) {
        const target = direction === "undo" ? entry.before : entry.after;
        const key = entry.key;
        if (target === undefined) {
            delete state.dirty[key];
        } else {
            state.dirty[key] = { ...target };
        }
        delete state.refusals[key];
    }
}

export function undo(state) {
    const entries = state.undoStack.pop();
    if (!entries) { return false; }
    replay(state, entries, "undo");
    state.redoStack.push(entries);
    return true;
}

export function redo(state) {
    const entries = state.redoStack.pop();
    if (!entries) { return false; }
    replay(state, entries, "redo");
    state.undoStack.push(entries);
    return true;
}

/** Split a clipboard payload into a matrix. Tabs first, then commas. */
export function parseClipboard(text) {
    const lines = String(text || "").replace(/\r/g, "").replace(/\n+$/, "").split("\n");
    const sep = lines.some((l) => l.includes("\t")) ? "\t" : ",";
    return lines.map((l) => l.split(sep));
}

/**
 * Paste a block starting at one cell, filling right and down.
 *
 * Only over EDITABLE columns and LOADED rows — a paste that silently ran past
 * the end of what is on screen would stage changes to people the person
 * pasting never saw.
 */
export function pasteAt(state, r0, c0, matrix) {
    const entries = [];
    for (let dr = 0; dr < matrix.length; dr++) {
        const row = state.rows[r0 + dr];
        if (!row) { break; }
        for (let dc = 0; dc < matrix[dr].length; dc++) {
            const col = state.columns[c0 + dc];
            if (!col) { break; }
            if (!col.editable) { continue; }
            const raw = matrix[dr][dc];
            entries.push(put(state, row.id, col.id, raw, labelFor(col, raw)));
        }
    }
    record(state, entries);
    return entries.length;
}

// -------------------------------------------------------------- selection
export function toggleRow(state, empId) {
    const i = state.selected.indexOf(empId);
    if (i >= 0) { state.selected.splice(i, 1); } else { state.selected.push(empId); }
    state.allMatching = false;
}

export function selectRange(state, fromIdx, toIdx) {
    const [a, b] = fromIdx <= toIdx ? [fromIdx, toIdx] : [toIdx, fromIdx];
    for (let i = a; i <= b; i++) {
        const row = state.rows[i];
        if (row && !state.selected.includes(row.id)) { state.selected.push(row.id); }
    }
    state.allMatching = false;
}

export function clearSelection(state) {
    state.selected.length = 0;
    state.allMatching = false;
}

export function selectLoaded(state) {
    state.selected = state.rows.filter(Boolean).map((r) => r.id);
    state.allMatching = false;
}

// ---------------------------------------------------------------------------
//  The component
// ---------------------------------------------------------------------------
export class RecordsGrid extends Component {
    static template = "pb_records.RecordsGrid";
    static components = { RdCellEditor };
    static props = {
        state: { type: Object },
        // (offset) => void — the window has moved over rows we do not hold
        onNeedPage: { type: Function, optional: true },
        // () => void — the staged set changed, revalidate
        onChanged: { type: Function, optional: true },
        // (comodel, term) => Promise<[{id,label}]>
        onLookup: { type: Function, optional: true },
        // (fieldId, scope) => void — open the "Set for…" popover
        onSetFor: { type: Function, optional: true },
        // (fieldId) => void — take the column off the grid
        onHideColumn: { type: Function, optional: true },
        // () => void — the strip nudge, when nothing is picked
        onPickFields: { type: Function, optional: true },
        // () => void — clear the filters, from the empty state
        onClearFilters: { type: Function, optional: true },
        // (n) => void — "Pasted 24 cells"
        onPasted: { type: Function, optional: true },
        // () => void — "Select all N matching" was clicked
        onSelectAllMatching: { type: Function, optional: true },
        emptyReason: { type: String, optional: true },
    };

    setup() {
        this.st = useState(this.props.state);
        this.view = useState({ start: 0, count: 30 });
        this.scrollRef = useRef("scroll");
        onMounted(() => this.measure());
    }

    ic(n, s = 15) { return ic(n, s); }
    get ROW_H() { return ROW_H; }

    // ------------------------------------------------------------ windowing
    measure() {
        const el = this.scrollRef.el;
        if (!el) { return; }
        this.view.count = Math.min(
            MAX_WINDOW, Math.ceil(el.clientHeight / ROW_H) + OVERSCAN * 2);
        this.requestWindow();
    }

    onScroll(ev) {
        const start = Math.max(0, Math.floor(ev.target.scrollTop / ROW_H) - OVERSCAN);
        if (start !== this.view.start) {
            this.view.start = start;
            this.requestWindow();
        }
    }

    requestWindow() {
        if (!this.props.onNeedPage) { return; }
        const end = Math.min(this.st.total, this.view.start + this.view.count);
        for (let i = this.view.start; i < end; i += 1) {
            if (!this.st.rows[i]) {
                this.props.onNeedPage(Math.floor(i / PAGE) * PAGE);
                i = (Math.floor(i / PAGE) + 1) * PAGE - 1;
            }
        }
    }

    get windowRows() {
        const out = [];
        const end = Math.min(this.st.total, this.view.start + this.view.count);
        for (let i = this.view.start; i < end; i++) {
            out.push({ i, row: this.st.rows[i] || null });
        }
        return out;
    }

    get spacerTop() { return this.view.start * ROW_H; }
    get spacerAll() { return this.st.total * ROW_H; }

    // ------------------------------------------------------------- reading
    dirtyOf(empId, fieldId) { return this.st.dirty[cellKey(empId, fieldId)]; }
    refusalOf(empId, fieldId) { return this.st.refusals[cellKey(empId, fieldId)]; }

    text(col, row) {
        return cellText(col, (row.values || {})[col.id], this.dirtyOf(row.id, col.id));
    }

    oldText(col, row) {
        const cell = (row.values || {})[col.id];
        return cell ? (cell.label || "") : "";
    }

    /** A contract cell for somebody with no contract is not a blank — say so. */
    noContract(col, row) {
        return (col.group === "contract" || col.group === "component") && !row.contract_id;
    }

    editable(col, row) {
        return !!col.editable && !this.noContract(col, row);
    }

    isSelected(id) { return this.st.selected.includes(id); }

    cellClass(col, row) {
        const parts = ["rd-cell"];
        if (isNumericCol(col)) { parts.push("num"); }
        if (this.dirtyOf(row.id, col.id)) { parts.push("dirty"); }
        if (this.refusalOf(row.id, col.id)) { parts.push("bad"); }
        if (!this.editable(col, row)) { parts.push("locked"); }
        return parts.join(" ");
    }

    isFocused(i, c) { return this.st.focus.r === i && this.st.focus.c === c; }
    isEditing(i, c) {
        return !!this.st.editing && this.st.editing.r === i && this.st.editing.c === c;
    }

    // ------------------------------------------------------------- clicking
    onRowCheck(ev, i, row) {
        ev.stopPropagation();
        if (ev.shiftKey && this.st.anchor >= 0) {
            selectRange(this.st, this.st.anchor, i);
        } else {
            toggleRow(this.st, row.id);
            this.st.anchor = i;
        }
    }

    onCellClick(ev, i, c, row, col) {
        this.st.menu = -1;
        if (ev.shiftKey && this.st.anchor >= 0) {
            selectRange(this.st, this.st.anchor, i);
            return;
        }
        if (ev.ctrlKey || ev.metaKey) {
            toggleRow(this.st, row.id);
            this.st.anchor = i;
            return;
        }
        this.st.focus = { r: i, c };
        this.st.anchor = i;
        this.st.editing = null;
    }

    onCellDblClick(i, c, row, col) {
        if (this.editable(col, row)) { this.st.editing = { r: i, c }; }
    }

    // ------------------------------------------------------------ keyboard
    onKeyDown(ev) {
        if (this.st.editing) { return; }
        const key = ev.key;
        const cols = this.st.columns.length;
        const { r, c } = this.st.focus;

        if ((ev.ctrlKey || ev.metaKey) && (key === "z" || key === "Z")) {
            ev.preventDefault();
            if (ev.shiftKey) { redo(this.st); } else { undo(this.st); }
            this.changed();
            return;
        }
        if ((ev.ctrlKey || ev.metaKey) && (key === "y" || key === "Y")) {
            ev.preventDefault();
            redo(this.st);
            this.changed();
            return;
        }
        if ((ev.ctrlKey || ev.metaKey) && (key === "a" || key === "A")) {
            ev.preventDefault();
            selectLoaded(this.st);
            return;
        }
        if (key === "Escape") {
            ev.preventDefault();
            this.st.menu = -1;
            clearSelection(this.st);
            return;
        }
        if (r < 0 || cols === 0) {
            if (key === "ArrowDown" && this.st.total) {
                ev.preventDefault();
                this.st.focus = { r: 0, c: 0 };
            }
            return;
        }
        if (key === "ArrowDown" || key === "ArrowUp"
            || key === "ArrowLeft" || key === "ArrowRight"
            || key === "Tab") {
            ev.preventDefault();
            let nr = r, nc = c;
            if (key === "ArrowDown") { nr = Math.min(this.st.total - 1, r + 1); }
            if (key === "ArrowUp") { nr = Math.max(0, r - 1); }
            if (key === "ArrowLeft") { nc = Math.max(0, c - 1); }
            if (key === "ArrowRight") { nc = Math.min(cols - 1, c + 1); }
            if (key === "Tab") {
                nc = c + (ev.shiftKey ? -1 : 1);
                if (nc >= cols) { nc = 0; nr = Math.min(this.st.total - 1, r + 1); }
                if (nc < 0) { nc = cols - 1; nr = Math.max(0, r - 1); }
            }
            this.st.focus = { r: nr, c: nc };
            this.scrollIntoView(nr);
            return;
        }
        if (key === " " && this.st.rows[r]) {
            ev.preventDefault();
            toggleRow(this.st, this.st.rows[r].id);
            return;
        }
        if (key === "Enter" || key === "F2") {
            ev.preventDefault();
            this.startEdit(r, c);
            return;
        }
        if (key.length === 1 && !ev.ctrlKey && !ev.metaKey && !ev.altKey) {
            // Typing starts typing — the spreadsheet reflex. The character is
            // not swallowed: the editor opens with it as the draft.
            ev.preventDefault();
            this.startEdit(r, c, key);
        }
    }

    /** What the editor opens with: the character just typed, or the value. */
    editorValue(col, row) {
        if (this._seed) { return this._seed; }
        const dirty = this.dirtyOf(row.id, col.id);
        if (dirty) { return dirty.value; }
        const cell = (row.values || {})[col.id];
        return cell ? cell.v : "";
    }

    startEdit(r, c, seed) {
        const row = this.st.rows[r];
        const col = this.st.columns[c];
        if (!row || !col || !this.editable(col, row)) { return; }
        this._seed = seed || null;
        this.st.editing = { r, c };
    }

    get editorSeed() { return this._seed; }

    scrollIntoView(r) {
        const el = this.scrollRef.el;
        if (!el) { return; }
        const top = r * ROW_H;
        if (top < el.scrollTop) { el.scrollTop = top; }
        else if (top + ROW_H > el.scrollTop + el.clientHeight) {
            el.scrollTop = top + ROW_H - el.clientHeight;
        }
    }

    // --------------------------------------------------------------- edits
    commit(value, label) {
        const { r, c } = this.st.editing || {};
        const row = this.st.rows[r];
        const col = this.st.columns[c];
        this.st.editing = null;
        this._seed = null;
        if (!row || !col) { return; }
        setValue(this.st, row.id, col.id, value, label);
        this.changed();
    }

    cancelEdit() {
        this.st.editing = null;
        this._seed = null;
    }

    moveFrom(direction) {
        const { r, c } = this.st.focus;
        const cols = this.st.columns.length;
        if (direction === "down") {
            this.st.focus = { r: Math.min(this.st.total - 1, r + 1), c };
        } else if (direction === "next") {
            this.st.focus = c + 1 < cols ? { r, c: c + 1 }
                : { r: Math.min(this.st.total - 1, r + 1), c: 0 };
        } else if (direction === "prev") {
            this.st.focus = c > 0 ? { r, c: c - 1 }
                : { r: Math.max(0, r - 1), c: cols - 1 };
        }
        this.scrollIntoView(this.st.focus.r);
    }

    changed() { if (this.props.onChanged) { this.props.onChanged(); } }

    onPaste(ev) {
        if (this.st.editing) { return; }
        const { r, c } = this.st.focus;
        if (r < 0 || c < 0) { return; }
        const text = (ev.clipboardData || window.clipboardData).getData("text");
        if (!text) { return; }
        ev.preventDefault();
        const n = pasteAt(this.st, r, c, parseClipboard(text));
        this.changed();
        if (this.props.onPasted) { this.props.onPasted(n); }
    }

    /**
     * `undefined`, never `null`, for a column that needs no typeahead.
     *
     * A typed OPTIONAL prop still rejects `null` (W35) — OWL only treats
     * `undefined` as "absent" — so returning null here made every non-m2o
     * editor die on "Invalid props for component 'RdCellEditor'".
     */
    lookupFor(col) {
        if (col.ttype !== "many2one" || !this.props.onLookup) { return undefined; }
        return (term) => this.props.onLookup(col.m2o.comodel, term);
    }

    // ------------------------------------------------------- column header
    toggleMenu(c) { this.st.menu = this.st.menu === c ? -1 : c; }

    menuSetSelected(col) {
        this.st.menu = -1;
        if (this.props.onSetFor) { this.props.onSetFor(col.id, "selected"); }
    }

    menuSetAll(col) {
        this.st.menu = -1;
        if (this.props.onSetFor) { this.props.onSetFor(col.id, "shown"); }
    }

    menuClear(col) {
        this.st.menu = -1;
        const ids = this.st.selected.length
            ? [...this.st.selected]
            : this.st.rows.filter(Boolean).map((r) => r.id);
        setForRows(this.st, ids, col.id, "", "");
        this.changed();
    }

    menuRevert(col) {
        this.st.menu = -1;
        revertColumn(this.st, col.id);
        this.changed();
    }

    menuHide(col) {
        this.st.menu = -1;
        if (this.props.onHideColumn) { this.props.onHideColumn(col.id); }
    }

    // ------------------------------------------------------------- header
    get allLoadedSelected() {
        const loaded = this.st.rows.filter(Boolean);
        return loaded.length > 0 && loaded.every((r) => this.st.selected.includes(r.id));
    }

    toggleAll() {
        if (this.allLoadedSelected) { clearSelection(this.st); }
        else { selectLoaded(this.st); }
    }

    get loadedCount() { return this.st.rows.filter(Boolean).length; }

    get showSelectAllMatching() {
        return this.st.selected.length > 0
            && this.st.total > this.loadedCount
            && !this.st.allMatching;
    }

    /** The desk owns this: it fetches every matching id, we only ask. */
    selectAllMatching() {
        if (this.props.onSelectAllMatching) { this.props.onSelectAllMatching(); }
    }

    get selectionLabel() {
        if (this.st.allMatching) {
            return _t("All %s people selected", this.st.total);
        }
        return _t("%s selected", this.st.selected.length);
    }

    ini(name) { return initialsOf(name); }
}

export function initialsOf(name) {
    return String(name || "?").split(" ").filter(Boolean)
        .map((p) => p[0]).join("").slice(0, 2).toUpperCase() || "?";
}

function isNumericCol(col) {
    return ["integer", "float", "monetary", "amount"].includes(col.ttype);
}
