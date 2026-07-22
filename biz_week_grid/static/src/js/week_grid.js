/** @odoo-module **/
/**
 * WeekGrid — a generic, reusable editable weekly grid.
 *
 * Spreadsheet feel: rows (employees / resources) × Mon–Sun day columns; each
 * cell renders a primary measure as the big number and any extra measures as
 * chips. The component owns ALL interaction: keyboard navigation, type-to-edit,
 * dirty tracking (amber dot), an undo stack (Ctrl/Cmd+Z) pre-save, per-row
 * revert, an explicit Save that surfaces per-cell results (failed cells go red
 * and KEEP their value), a local row filter, and flags/`editable:false` locking.
 *
 * It is adapter-driven and carries ZERO product dependencies — it themes itself
 * through --bwg-* CSS custom properties (defaults in week_grid.scss); consumers
 * override those on the host element. No Payobook / HR imports.
 *
 * Adapter contract (props.adapter):
 *   fetch(params)      -> { days:[{iso,label,sublabel?,is_today?,is_weekend?}],
 *                           rows:[{id,label,sublabel?,avatar_url?,flags?,meta?,
 *                                  cells:{ dayISO:{ measures:{ key:{value,editable,
 *                                          style?,state?,note?} }, note? } }}],
 *                           measures:[{key,label,color?,min?,max?,step?}], ...extra }
 *   save(payload)      -> { results:[{rowId,dayISO,measure,ok,error?}] }
 *   validate(cell)     -> { ok, warn?, error? }   (optional; sync, local rules)
 */
import { Component, useState, useRef, useEffect, onWillStart, onWillUpdateProps } from "@odoo/owl";

const cellKey = (rowId, dayISO, mKey) => `${rowId}|${dayISO}|${mKey}`;

export class WeekGrid extends Component {
    static template = "biz_week_grid.WeekGrid";
    static props = {
        adapter: Object,
        params: { type: Object, optional: true },
        paramsKey: { type: String, optional: true },
        showFilter: { type: Boolean, optional: true },
        emptyText: { type: String, optional: true },
        onData: { type: Function, optional: true },
        onDirty: { type: Function, optional: true },
        onSaved: { type: Function, optional: true },
        onFocus: { type: Function, optional: true },
        "*": true,
    };

    setup() {
        this.gridRef = useRef("grid");
        this.state = useState({
            loading: true,
            saving: false,
            days: [],
            rows: [],
            measures: [],
            filter: "",
            // dirty edits, results and messages are keyed by cellKey()
            edits: {},        // key -> Number (typed value, differs from original)
            results: {},      // key -> {ok:false, error} (last save failures)
            msgs: {},         // key -> {warn?, error?} (local validate feedback)
            focus: null,      // {rowId, dayISO}  — primary-cell selection
            editing: null,    // {key, buffer}    — cell currently in text edit
        });
        // original (server) values snapshot, keyed by cellKey — never mutated by typing
        this._orig = {};
        this._undo = [];      // [{key, prev}] pre-save undo stack

        this.activeInputRef = useRef("activeInput");
        onWillStart(() => this.reload());
        onWillUpdateProps((next) => {
            if (next.paramsKey !== this.props.paramsKey) {
                this.reload(next.params);
            }
        });
        // autofocus + select the overlay editor whenever a cell enters edit mode
        useEffect(
            (el) => {
                if (el) { el.focus(); el.select(); }
            },
            () => [this.activeInputRef.el],
        );
    }

    // ---------------------------------------------------------------- display
    fmtVal(v) {
        if (v === null || v === undefined || v === "") { return ""; }
        const n = Number(v);
        if (Number.isNaN(n) || n === 0) { return ""; }  // 0 → blank (placeholder shows "–")
        // trim trailing zeros: 8.0 -> "8", 7.5 -> "7.5"
        return String(Math.round(n * 100) / 100);
    }
    /** Return keyboard focus to the grid root so nav/undo/type-to-edit work
     *  right after an edit commits (the spreadsheet feel). */
    _focusGrid() {
        if (this.gridRef.el) { this.gridRef.el.focus(); }
    }
    anyRowDirty(row) {
        return Object.keys(this.state.edits).some((k) => k.startsWith(`${row.id}|`));
    }
    chipTitle(row, dayISO, m) {
        const err = this.cellError(row, dayISO, m.key);
        if (err) { return `${m.label}: ${err}`; }
        if (!this.isEditable(row, dayISO, m.key)) {
            return this.lockReason(row, dayISO, m.key) || `${m.label} (locked)`;
        }
        return m.label;
    }

    // ------------------------------------------------------------------ data
    async reload(params) {
        this.state.loading = true;
        let data;
        try {
            data = await this.props.adapter.fetch(params || this.props.params || {});
        } catch (e) {
            this.state.loading = false;
            throw e;
        }
        this._ingest(data);
        this.state.loading = false;
    }

    _ingest(data) {
        this.state.days = data.days || [];
        this.state.rows = data.rows || [];
        this.state.measures = data.measures || this.state.measures || [];
        // rebuild the original-value snapshot and drop any stale edit state
        const orig = {};
        for (const row of this.state.rows) {
            for (const day of this.state.days) {
                const cell = (row.cells || {})[day.iso];
                if (!cell) { continue; }
                for (const m of this.state.measures) {
                    const meas = (cell.measures || {})[m.key];
                    if (meas && meas.value !== undefined && meas.value !== null) {
                        orig[cellKey(row.id, day.iso, m.key)] = Number(meas.value);
                    }
                }
            }
        }
        this._orig = orig;
        this.state.edits = {};
        this.state.results = {};
        this.state.msgs = {};
        this._undo = [];
        if (this.props.onData) { this.props.onData(data); }
        this._emitDirty();
    }

    // --------------------------------------------------------------- getters
    get primaryKey() {
        return this.state.measures.length ? this.state.measures[0].key : null;
    }
    get chipMeasures() {
        return this.state.measures.slice(1);
    }
    get filteredRows() {
        const q = (this.state.filter || "").toLowerCase().trim();
        if (!q) { return this.state.rows; }
        return this.state.rows.filter((r) =>
            (r.label || "").toLowerCase().includes(q) ||
            (r.sublabel || "").toLowerCase().includes(q));
    }
    get dirtyCount() {
        return Object.keys(this.state.edits).length;
    }

    measureDef(mKey) {
        return this.state.measures.find((m) => m.key === mKey) || {};
    }
    cellFor(row, dayISO) {
        return (row.cells || {})[dayISO] || { measures: {} };
    }
    measureCell(row, dayISO, mKey) {
        return (this.cellFor(row, dayISO).measures || {})[mKey] || null;
    }
    /** Is a given (row,day,measure) editable? flags-driven lock + per-cell editable. */
    isEditable(row, dayISO, mKey) {
        if (row.flags && (row.flags.locked || row.flags.readonly)) { return false; }
        const meas = this.measureCell(row, dayISO, mKey);
        // an absent primary measure is still editable (blank cell you can fill);
        // an absent chip measure is not offered.
        if (!meas) { return mKey === this.primaryKey; }
        return meas.editable !== false;
    }
    lockReason(row, dayISO, mKey) {
        if (row.flags && row.flags.lock_reason) { return row.flags.lock_reason; }
        const meas = this.measureCell(row, dayISO, mKey);
        return (meas && meas.lock_reason) || (meas && meas.note) || "";
    }

    original(row, dayISO, mKey) {
        const k = cellKey(row.id, dayISO, mKey);
        return k in this._orig ? this._orig[k] : null;
    }
    /** Displayed value = dirty edit if present, else the server original. */
    displayed(row, dayISO, mKey) {
        const k = cellKey(row.id, dayISO, mKey);
        if (k in this.state.edits) { return this.state.edits[k]; }
        return this.original(row, dayISO, mKey);
    }
    isDirtyCell(row, dayISO, mKey) {
        return cellKey(row.id, dayISO, mKey) in this.state.edits;
    }
    cellError(row, dayISO, mKey) {
        const k = cellKey(row.id, dayISO, mKey);
        if (this.state.results[k] && !this.state.results[k].ok) {
            return this.state.results[k].error || "error";
        }
        return (this.state.msgs[k] && this.state.msgs[k].error) || "";
    }
    cellWarn(row, dayISO, mKey) {
        const k = cellKey(row.id, dayISO, mKey);
        return (this.state.msgs[k] && this.state.msgs[k].warn) || "";
    }
    isFocused(row, dayISO) {
        const f = this.state.focus;
        return !!f && f.rowId === row.id && f.dayISO === dayISO;
    }
    isEditing(row, dayISO, mKey) {
        const e = this.state.editing;
        return !!e && e.key === cellKey(row.id, dayISO, mKey);
    }

    // ------------------------------------------------------------ interaction
    focusCell(row, dayISO) {
        this.state.focus = { rowId: row.id, dayISO };
        if (this.props.onFocus) { this.props.onFocus(row.id); }
    }
    onCellMouseDown(row, dayISO) {
        // clicking the primary area selects + (if editable) opens the primary editor
        this.focusCell(row, dayISO);
        if (this.isEditable(row, dayISO, this.primaryKey)) {
            this.startEdit(row, dayISO, this.primaryKey);
        } else {
            this._focusGrid();  // locked cell: keep keyboard nav alive
        }
    }
    onChipMouseDown(ev, row, dayISO, mKey) {
        ev.stopPropagation();
        this.focusCell(row, dayISO);
        if (this.isEditable(row, dayISO, mKey)) {
            this.startEdit(row, dayISO, mKey);
        }
    }

    startEdit(row, dayISO, mKey, seed) {
        const k = cellKey(row.id, dayISO, mKey);
        const cur = this.displayed(row, dayISO, mKey);
        const buffer = seed !== undefined ? seed
            : (cur === null || cur === undefined ? "" : String(cur));
        this.state.editing = { key: k, buffer, rowId: row.id, dayISO, mKey };
    }
    onEditInput(ev) {
        if (this.state.editing) { this.state.editing.buffer = ev.target.value; }
    }
    commitEditing(moveNext) {
        const e = this.state.editing;
        if (!e) { return; }
        const row = this.state.rows.find((r) => r.id === e.rowId);
        if (row) { this._applyEdit(row, e.dayISO, e.mKey, e.buffer); }
        this.state.editing = null;
        if (moveNext) { this._move(0, 1); }
        this._focusGrid();   // hand focus back to the grid for keyboard nav/undo
    }
    cancelEditing() {
        this.state.editing = null;
        this._focusGrid();
    }

    _applyEdit(row, dayISO, mKey, raw) {
        const k = cellKey(row.id, dayISO, mKey);
        const def = this.measureDef(mKey);
        const prevDisplayed = this.displayed(row, dayISO, mKey);
        let num;
        const trimmed = String(raw).trim();
        if (trimmed === "") {
            num = 0;
        } else {
            num = Number(trimmed.replace(",", "."));
            if (Number.isNaN(num)) { return; }  // ignore garbage, keep prior
        }
        // clamp to measure bounds (client-side; server re-validates)
        if (def.min !== undefined && num < def.min) { num = def.min; }
        if (def.max !== undefined && num > def.max) { num = def.max; }

        // local validate hook (warn/error feedback, non-blocking)
        if (this.props.adapter.validate) {
            const v = this.props.adapter.validate({
                rowId: row.id, dayISO, measureKey: mKey, value: num, row,
            }) || {};
            if (v.warn || v.error) {
                this.state.msgs[k] = { warn: v.warn, error: v.error };
            } else {
                delete this.state.msgs[k];
            }
        }

        const origVal = this.original(row, dayISO, mKey);
        // push undo BEFORE mutating
        this._undo.push({ key: k, prev: prevDisplayed });
        if (origVal !== null && num === origVal) {
            delete this.state.edits[k];   // typed back to original → clean
        } else {
            this.state.edits[k] = num;
        }
        // a fresh edit clears a prior save-failure ring on that cell
        delete this.state.results[k];
        this._emitDirty();
    }

    undo() {
        const last = this._undo.pop();
        if (!last) { return; }
        const [rowId, dayISO, mKey] = last.key.split("|");
        const row = this.state.rows.find((r) => String(r.id) === rowId);
        const origVal = row ? this.original(row, dayISO, mKey) : null;
        if (last.prev === null || last.prev === undefined
            || (origVal !== null && Number(last.prev) === origVal)) {
            delete this.state.edits[last.key];
        } else {
            this.state.edits[last.key] = Number(last.prev);
        }
        delete this.state.results[last.key];
        delete this.state.msgs[last.key];
        this._emitDirty();
    }

    revertRow(row) {
        for (const k of Object.keys(this.state.edits)) {
            if (k.startsWith(`${row.id}|`)) {
                delete this.state.edits[k];
                delete this.state.results[k];
                delete this.state.msgs[k];
            }
        }
        this._undo = this._undo.filter((u) => !u.key.startsWith(`${row.id}|`));
        this._emitDirty();
    }

    // -------------------------------------------------------- keyboard driving
    onGridKeydown(ev) {
        const meta = ev.ctrlKey || ev.metaKey;
        if (meta && (ev.key === "z" || ev.key === "Z")) {
            ev.preventDefault();
            this.undo();
            return;
        }
        if (this.state.editing) { return; }   // editor input owns its own keys
        if (!this.state.focus) { return; }
        switch (ev.key) {
            case "ArrowLeft": ev.preventDefault(); this._move(-1, 0); break;
            case "ArrowRight": ev.preventDefault(); this._move(1, 0); break;
            case "ArrowUp": ev.preventDefault(); this._move(0, -1); break;
            case "ArrowDown": ev.preventDefault(); this._move(0, 1); break;
            case "Tab":
                ev.preventDefault();
                this._move(ev.shiftKey ? -1 : 1, 0);
                break;
            case "Enter": {
                ev.preventDefault();
                const { row, dayISO } = this._focusTarget();
                if (row && this.isEditable(row, dayISO, this.primaryKey)) {
                    this.startEdit(row, dayISO, this.primaryKey);
                }
                break;
            }
            case "Backspace":
            case "Delete": {
                ev.preventDefault();
                const t = this._focusTarget();
                if (t.row && this.isEditable(t.row, t.dayISO, this.primaryKey)) {
                    this._applyEdit(t.row, t.dayISO, this.primaryKey, "0");
                }
                break;
            }
            default:
                // type-to-edit: a digit / dot starts editing the focused primary cell
                if (/^[0-9.]$/.test(ev.key)) {
                    const t = this._focusTarget();
                    if (t.row && this.isEditable(t.row, t.dayISO, this.primaryKey)) {
                        ev.preventDefault();
                        this.startEdit(t.row, t.dayISO, this.primaryKey, ev.key);
                    }
                }
        }
    }
    onEditKeydown(ev) {
        if (ev.key === "Enter") { ev.preventDefault(); this.commitEditing(true); }
        else if (ev.key === "Escape") { ev.preventDefault(); this.cancelEditing(); }
        else if (ev.key === "Tab") { ev.preventDefault(); this.commitEditing(false); this._move(ev.shiftKey ? -1 : 1, 0); }
    }

    _focusTarget() {
        const rows = this.filteredRows;
        const f = this.state.focus;
        if (!f) { return {}; }
        const row = rows.find((r) => r.id === f.rowId);
        return { row, dayISO: f.dayISO };
    }
    _move(dCol, dRow) {
        const rows = this.filteredRows;
        const days = this.state.days;
        if (!rows.length || !days.length) { return; }
        let ri = 0, di = 0;
        if (this.state.focus) {
            ri = Math.max(0, rows.findIndex((r) => r.id === this.state.focus.rowId));
            di = Math.max(0, days.findIndex((d) => d.iso === this.state.focus.dayISO));
        }
        di += dCol; ri += dRow;
        // wrap columns into adjacent rows for a natural Tab flow
        while (di >= days.length) { di -= days.length; ri += 1; }
        while (di < 0) { di += days.length; ri -= 1; }
        ri = Math.min(rows.length - 1, Math.max(0, ri));
        this.state.focus = { rowId: rows[ri].id, dayISO: days[di].iso };
        if (this.props.onFocus) { this.props.onFocus(rows[ri].id); }
    }

    // ----------------------------------------------------------------- saving
    setFilter(ev) { this.state.filter = ev.target.value; }

    _emitDirty() {
        if (!this.props.onDirty) { return; }
        const list = [];
        for (const [k, v] of Object.entries(this.state.edits)) {
            const [rowId, dayISO, measureKey] = k.split("|");
            list.push({
                rowId: this._rowIdCoerce(rowId), dayISO, measureKey,
                value: v, prevValue: k in this._orig ? this._orig[k] : 0,
            });
        }
        this.props.onDirty(list);
    }
    _rowIdCoerce(rowId) {
        const n = Number(rowId);
        return Number.isNaN(n) ? rowId : n;
    }

    async save() {
        if (this.state.saving || !this.dirtyCount) { return; }
        if (this.state.editing) { this.commitEditing(false); }
        this.state.saving = true;
        const cells = [];
        for (const [k, v] of Object.entries(this.state.edits)) {
            const [rowId, dayISO, measure] = k.split("|");
            cells.push({ rowId: this._rowIdCoerce(rowId), dayISO, measure, value: v });
        }
        let res;
        try {
            res = await this.props.adapter.save({ cells });
        } catch (e) {
            this.state.saving = false;
            throw e;
        }
        const results = (res && res.results) || [];
        let anyFail = false, okCount = 0;
        for (const r of results) {
            const k = cellKey(r.rowId, r.dayISO, r.measure);
            if (r.ok) {
                okCount += 1;
                // bake into the original snapshot; the cell is clean now
                if (k in this.state.edits) { this._orig[k] = this.state.edits[k]; }
                delete this.state.edits[k];
                delete this.state.results[k];
            } else {
                anyFail = true;
                this.state.results[k] = { ok: false, error: r.error || "error" };
            }
        }
        this.state.saving = false;
        if (this.props.onSaved) { this.props.onSaved(results); }
        // full success → reload authoritative server state (fresh chip states/tokens).
        // On any failure OR a no-op/cancelled save (empty results), KEEP the dirty
        // edits (and red rings) so nothing the user typed is lost.
        if (!anyFail && okCount > 0) {
            await this.reload();
        } else {
            this._emitDirty();
        }
        return results;
    }
}
