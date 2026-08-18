/** @odoo-module **/
/**
 * WeekGrid — a generic, reusable editable weekly grid.
 *
 * ONE PRINCIPLE (P5): **cells show OUTCOMES; entry lives in a focused editor.**
 *
 * The first version rendered a pill per APPLICABLE extra measure in every cell,
 * whether or not it held anything — inputs masquerading as data. On a real week
 * that is a wall of coloured pills with the two real entries lost inside it, and
 * the pills spelled out configuration (rates) that is identical on every row of
 * the screen. So a cell now renders, at most:
 *
 *   · the primary measure as a bold tabular number (blank when zero);
 *   · one chip per extra measure that actually HAS hours, tinted by measure,
 *     carrying a status micro-dot — never the measure's label, never a rate;
 *   · the consumer's own flag badges (`flags.day_badges`);
 *   · a dirty dot / lock icon / error ring, as before.
 *
 * Everything that was in the cells and is still needed moved to two places that
 * each say it ONCE: a legend row above the grid (swatch · name · rate) and the
 * cell editor, a popover mounted through the OVERLAY service (W43) that owns
 * the whole of one cell — primary hours, a stepper per applicable extra
 * measure, a live ceiling bar and the consumer's advisory warnings.
 *
 * NOTHING here autosaves. The editor STAGES through the same dirty-cell
 * mechanism the keyboard fast path uses; the sticky tray at the bottom is the
 * single commit point (the floating top-right Save is gone).
 *
 * It is adapter-driven and carries ZERO product dependencies — it themes itself
 * through --bwg-* CSS custom properties (defaults in week_grid.scss); consumers
 * override those on the host element. No Payobook / HR imports.
 *
 * Adapter contract (props.adapter) — UNCHANGED:
 *   fetch(params)      -> { days:[{iso,label,sublabel?,is_today?,is_weekend?}],
 *                           rows:[{id,label,sublabel?,avatar_url?,flags?,meta?,
 *                                  cells:{ dayISO:{ measures:{ key:{value,editable,
 *                                          style?,state?,note?} }, note? } }}],
 *                           measures:[{key,label,name?,rate?,color?,min?,max?,step?}],
 *                           ...extra }
 *   save(payload)      -> { results:[{rowId,dayISO,measure,ok,error?}] }
 *   validate(cell)     -> { ok, warn?, error? }   (optional; sync, local rules)
 *
 * `name` / `rate` on a measure are OPTIONAL and additive: they are what the
 * legend and the editor print. A consumer that sends neither keeps the old
 * behaviour minus the in-cell rate text, which is the whole point.
 */
import { Component, useState, useRef, useEffect, onWillStart, onWillUpdateProps, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { WeekCellEditor } from "@biz_week_grid/js/week_cell_editor";

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
        // Optional: makes each row's identity (avatar + label) a clickable door
        // back to the host — a drawer, a form, whatever the host owns. Absent,
        // the name cell renders exactly as it always has.
        onRowOpen: { type: Function, optional: true },
        // Optional advisory feed for the cell editor: the consumer answers
        // "given these staged values, what is this person's budget and what
        // should I warn about?". Pure, synchronous, NO RPC — the ceiling data
        // the host already loaded is what it reads. Advisory only: nothing it
        // returns can block a stage or a save.
        editorInfo: { type: Function, optional: true },
        // The tray is the single commit point. It appears by itself whenever
        // there are staged edits; a host with its own tray actions (a submit
        // queue, an approve button) sets this so the ONE bar is always there
        // rather than stacking a second one underneath.
        showTray: { type: Boolean, optional: true },
        slots: { type: Object, optional: true },
        "*": true,
    };

    setup() {
        this.gridRef = useRef("grid");
        this.overlay = useService("overlay");
        this.state = useState({
            loading: true,
            saving: false,
            days: [],
            rows: [],
            measures: [],
            filter: "",
            entriesOnly: false,   // "only rows with entries" filter chip
            helpOpen: false,      // the `?` shortcut map
            // dirty edits, results and messages are keyed by cellKey()
            edits: {},        // key -> Number (typed value, differs from original)
            results: {},      // key -> {ok:false, error} (last save failures)
            msgs: {},         // key -> {warn?, error?} (local validate feedback)
            focus: null,      // {rowId, dayISO}  — primary-cell selection
            editing: null,    // {key, buffer}    — cell in the inline FAST PATH
            editorAt: null,   // {rowId, dayISO}  — cell whose popover is open
        });
        // original (server) values snapshot, keyed by cellKey — never mutated by typing
        this._orig = {};
        this._undo = [];      // [{key, prev}] pre-save undo stack
        // W43: keep the overlay's own remove() and null it in onRemove, or a
        // second Enter opens a second editor on top of the first.
        this._closeEditor = null;

        this.activeInputRef = useRef("activeInput");
        onWillStart(() => this.reload());
        onWillUpdateProps((next) => {
            if (next.paramsKey !== this.props.paramsKey) {
                this.closeEditor();
                this.reload(next.params);
            }
        });
        onWillUnmount(() => this.closeEditor());
        // autofocus + select the inline editor whenever a cell enters edit mode
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
    /** Same rounding, but 0 prints as "0" — totals rows want a real zero. */
    fmtTot(v) {
        const n = Number(v || 0);
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
    /** A measure's human identity — what the LEGEND and the EDITOR print.
     *  Deliberately not reachable from the cell templates (T4 gate). */
    measureName(m) { return m.name || m.label || m.key; }
    measureRate(m) { return m.rate || ""; }

    chipTitle(row, dayISO, m) {
        const err = this.cellError(row, dayISO, m.key);
        const who = this.measureName(m) + (m.rate ? ` · ${m.rate}` : "");
        if (err) { return `${who}: ${err}`; }
        if (!this.isEditable(row, dayISO, m.key)) {
            return this.lockReason(row, dayISO, m.key) || `${who} (locked)`;
        }
        const bits = [who];
        const st = this.chipState(row, dayISO, m.key);
        if (st) { bits.push(this.stateLabel(st)); }
        const bonus = this.chipBonus(row, dayISO, m.key);
        if (bonus > 0) { bits.push(`${bonus} h recorded as bonus hours`); }
        return bits.join(" · ");
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
    get primaryDef() {
        return this.state.measures.length ? this.state.measures[0] : {};
    }
    get chipMeasures() {
        return this.state.measures.slice(1);
    }
    /** The legend — the ONE place a rate is written (§3.4). Fixed order: the
     *  order the consumer sent its measures in, which is also the order the
     *  categorical colours were assigned in. */
    get legendMeasures() {
        return this.chipMeasures;
    }
    get filteredRows() {
        const q = (this.state.filter || "").toLowerCase().trim();
        let rows = this.state.rows;
        if (q) {
            rows = rows.filter((r) =>
                (r.label || "").toLowerCase().includes(q) ||
                (r.sublabel || "").toLowerCase().includes(q));
        }
        if (this.state.entriesOnly) {
            rows = rows.filter((r) => this.rowHasEntries(r));
        }
        return rows;
    }
    /** Does this row hold (or have staged) anything at all this week? */
    rowHasEntries(row) {
        for (const day of this.state.days) {
            for (const m of this.state.measures) {
                if (Number(this.displayed(row, day.iso, m.key) || 0) > 0) { return true; }
            }
        }
        return false;
    }
    get dirtyCount() {
        return Object.keys(this.state.edits).length;
    }
    /** Hours of EXTRA-measure (overtime) work staged but not yet committed —
     *  the tray's second number. Net of what was already there. */
    get dirtyExtraHours() {
        const keys = new Set(this.chipMeasures.map((m) => m.key));
        let h = 0;
        for (const [k, v] of Object.entries(this.state.edits)) {
            const mKey = k.split("|")[2];
            if (!keys.has(mKey)) { continue; }
            h += Number(v || 0) - Number(this._orig[k] || 0);
        }
        return Math.round(h * 10) / 10;
    }
    get trayOpen() {
        return this.dirtyCount > 0 || !!this.props.showTray;
    }

    /** Every total the footer and the row-total column need, in ONE pass.
     *  Read once per render via `t-set` — a per-cell getter would walk the
     *  whole week for each of 200×7 cells. */
    get totals() {
        const byDay = {};
        const byRow = {};
        const grand = { reg: 0, extra: 0 };
        const pk = this.primaryKey;
        const extras = this.chipMeasures;
        for (const d of this.state.days) { byDay[d.iso] = { reg: 0, extra: 0 }; }
        for (const row of this.filteredRows) {
            const rt = { reg: 0, extra: 0 };
            for (const d of this.state.days) {
                const reg = Number(this.displayed(row, d.iso, pk) || 0);
                let ex = 0;
                for (const m of extras) {
                    ex += Number(this.displayed(row, d.iso, m.key) || 0);
                }
                rt.reg += reg; rt.extra += ex;
                byDay[d.iso].reg += reg; byDay[d.iso].extra += ex;
            }
            byRow[row.id] = rt;
            grand.reg += rt.reg; grand.extra += rt.extra;
        }
        return { byDay, byRow, grand };
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
    /** The extra measures the consumer says APPLY on this day — presence in the
     *  payload IS the applicability rule, and it is the same payload the pills
     *  used to render from. The editor offers exactly these. */
    applicableMeasures(row, dayISO) {
        return this.chipMeasures.filter((m) => !!this.measureCell(row, dayISO, m.key));
    }
    /** The extra measures with hours ON them — the only ones a CELL draws. */
    enteredMeasures(row, dayISO) {
        return this.chipMeasures.filter((m) =>
            Number(this.displayed(row, dayISO, m.key) || 0) > 0);
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
    /** Can this cell be edited AT ALL — the primary or any applicable extra?
     *  A cell where every measure is locked opens nothing. */
    isCellOpenable(row, dayISO) {
        if (this.isEditable(row, dayISO, this.primaryKey)) { return true; }
        return this.applicableMeasures(row, dayISO)
            .some((m) => this.isEditable(row, dayISO, m.key));
    }
    lockReason(row, dayISO, mKey) {
        if (row.flags && row.flags.lock_reason) { return row.flags.lock_reason; }
        const meas = this.measureCell(row, dayISO, mKey);
        return (meas && meas.lock_reason) || (meas && meas.note) || "";
    }
    /** Optional per-day cell badge (generic — the consumer supplies label/color/
     *  title on `row.flags.day_badges[dayISO]`; the grid stays product-neutral). */
    dayBadge(row, dayISO) {
        const b = row.flags && row.flags.day_badges;
        return (b && b[dayISO]) || null;
    }
    /** The extra measure's workflow state, straight from the payload —
     *  rendered as a MICRO-DOT, never as words, inside a cell. */
    chipState(row, dayISO, mKey) {
        const mc = this.measureCell(row, dayISO, mKey);
        return (mc && mc.state) || "";
    }
    chipBonus(row, dayISO, mKey) {
        const mc = this.measureCell(row, dayISO, mKey);
        return Number((mc && mc.bonus) || 0);
    }
    /** draft → hollow, submitted → solid, approved → check, refused → cross. */
    stateTone(state) {
        if (state === "approved") { return "ok"; }
        if (state === "refused") { return "bad"; }
        if (state === "submitted") { return "sent"; }
        if (state) { return "draft"; }
        return "";
    }
    stateLabel(state) {
        const L = {
            draft: "Draft", submitted: "Submitted",
            approved: "Approved", refused: "Refused",
        };
        return L[state] || state || "";
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
    /** Is ANY measure of this cell staged? (the cell's amber dot) */
    isDirtyAnywhere(row, dayISO) {
        if (this.isDirtyCell(row, dayISO, this.primaryKey)) { return true; }
        return this.chipMeasures.some((m) => this.isDirtyCell(row, dayISO, m.key));
    }
    cellError(row, dayISO, mKey) {
        const k = cellKey(row.id, dayISO, mKey);
        if (this.state.results[k] && !this.state.results[k].ok) {
            return this.state.results[k].error || "error";
        }
        return (this.state.msgs[k] && this.state.msgs[k].error) || "";
    }
    /** The cell's error ring: any measure that failed to save, not just REG —
     *  an overtime refusal used to colour nothing but its own chip. */
    anyCellError(row, dayISO) {
        if (this.cellError(row, dayISO, this.primaryKey)) { return true; }
        return this.chipMeasures.some((m) => !!this.cellError(row, dayISO, m.key));
    }
    cellWarn(row, dayISO, mKey) {
        const k = cellKey(row.id, dayISO, mKey);
        return (this.state.msgs[k] && this.state.msgs[k].warn) || "";
    }
    isFocused(row, dayISO) {
        const f = this.state.focus;
        return !!f && f.rowId === row.id && f.dayISO === dayISO;
    }
    isEditorOpen(row, dayISO) {
        const e = this.state.editorAt;
        return !!e && e.rowId === row.id && e.dayISO === dayISO;
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
    onCellClick(ev, row, dayISO) {
        this.focusCell(row, dayISO);
        if (this.isCellOpenable(row, dayISO)) {
            this.openEditor(ev.currentTarget, row, dayISO);
        } else {
            this._focusGrid();  // locked cell: keep keyboard nav alive
        }
    }

    // ------------------------------------------------------------- the editor
    /**
     * Open the cell editor in the OVERLAY (W43), anchored to the cell's
     * measured rect. It goes in the overlay rather than inside the grid for the
     * reason W43 exists: `.bwg-scroll` is an `overflow: auto` box, so an
     * absolutely-positioned panel would be CLIPPED at the scroller's edge
     * (W34's corollary) and a lens modal at z-index 1050 would sit over it.
     */
    openEditor(anchorEl, row, dayISO) {
        this.closeEditor();
        if (this.state.editing) { this.commitEditing(false); }
        const r = anchorEl.getBoundingClientRect();
        const rect = { top: r.top, left: r.left, bottom: r.bottom,
                       right: r.right, width: r.width, height: r.height };
        const pk = this.primaryKey;
        const chips = this.applicableMeasures(row, dayISO).map((m) => ({
            key: m.key,
            name: this.measureName(m),
            rate: this.measureRate(m),
            color: m.color || "",
            value: Number(this.displayed(row, dayISO, m.key) || 0),
            editable: this.isEditable(row, dayISO, m.key),
            lockReason: this.lockReason(row, dayISO, m.key),
            state: this.chipState(row, dayISO, m.key),
            stateLabel: this.stateLabel(this.chipState(row, dayISO, m.key)),
            bonus: this.chipBonus(row, dayISO, m.key),
            min: m.min, max: m.max, step: m.step || 0.5,
        }));
        const prev = { [pk]: Number(this.displayed(row, dayISO, pk) || 0) };
        for (const c of chips) { prev[c.key] = c.value; }

        this.state.editorAt = { rowId: row.id, dayISO };
        const day = this.state.days.find((d) => d.iso === dayISO) || {};
        this._closeEditor = this.overlay.add(
            WeekCellEditor,
            {
                rect,
                title: row.label || "",
                subtitle: [day.label, day.sublabel].filter(Boolean).join(" "),
                primary: {
                    key: pk,
                    name: this.measureName(this.primaryDef),
                    value: prev[pk],
                    editable: this.isEditable(row, dayISO, pk),
                    lockReason: this.lockReason(row, dayISO, pk),
                    min: this.primaryDef.min, max: this.primaryDef.max,
                    step: this.primaryDef.step || 0.5,
                },
                chips,
                recompute: (values) => this._editorInfo(row, dayISO, values, prev),
                onCommit: (values) => this._commitEditor(row, dayISO, values, prev),
                onClose: () => this.closeEditor(),
            },
            {
                onRemove: () => {
                    this._closeEditor = null;
                    this.state.editorAt = null;
                },
            },
        );
    }
    closeEditor() {
        if (this._closeEditor) {
            const close = this._closeEditor;
            this._closeEditor = null;
            close();
        }
        this.state.editorAt = null;
    }
    _editorInfo(row, dayISO, values, prev) {
        if (!this.props.editorInfo) { return {}; }
        try {
            return this.props.editorInfo({
                rowId: row.id, dayISO, values, prev, row,
            }) || {};
        } catch (e) {
            // W40: a broken advisory must not delete the editor. Warn and show
            // the panel without its bar rather than swallowing it into nothing.
            console.warn("WeekGrid: editorInfo failed", e);
            return {};
        }
    }
    /** The editor STAGES (W21: this runs from the panel's Save click handler,
     *  never from a lifecycle hook) — the tray still owns the commit. */
    _commitEditor(row, dayISO, values, prev) {
        for (const [mKey, v] of Object.entries(values)) {
            if (Number(v || 0) === Number(prev[mKey] || 0)) { continue; }
            if (!this.isEditable(row, dayISO, mKey)) { continue; }
            this._applyEdit(row, dayISO, mKey, String(v));
        }
        this.closeEditor();
        this._focusGrid();
    }

    // -------------------------------------------------------- the fast path
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
    /** The tray's Discard: everything staged, gone. Nothing is written. */
    discardAll() {
        this.state.edits = {};
        this.state.results = {};
        this.state.msgs = {};
        this._undo = [];
        this._emitDirty();
        this._focusGrid();
    }

    // -------------------------------------------------------- keyboard driving
    onGridKeydown(ev) {
        const meta = ev.ctrlKey || ev.metaKey;
        if (meta && (ev.key === "z" || ev.key === "Z")) {
            ev.preventDefault();
            this.undo();
            return;
        }
        if (meta && (ev.key === "d" || ev.key === "D")) {
            ev.preventDefault();
            this.fillDown();
            return;
        }
        if (this.state.editing) { return; }   // editor input owns its own keys
        if (ev.key === "Escape" && this.state.helpOpen) {
            ev.preventDefault(); this.state.helpOpen = false; return;
        }
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
                // Enter is the OT door: it opens the full cell editor, which is
                // the only surface that can reach an extra measure by keyboard.
                ev.preventDefault();
                const { row, dayISO } = this._focusTarget();
                if (row && this.isCellOpenable(row, dayISO)) {
                    const el = this._cellEl(row.id, dayISO);
                    if (el) { this.openEditor(el, row, dayISO); }
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
                // type-to-edit: a digit / dot starts editing the focused primary
                // cell IN PLACE — the fast path that makes a dense grid usable,
                // deliberately NOT routed through the popover.
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

    /** Copy the PRIMARY value of the cell directly above into the focused cell
     *  (Ctrl/Cmd+D) — the one spreadsheet verb this grid was missing. */
    fillDown() {
        const rows = this.filteredRows;
        const f = this.state.focus;
        if (!f) { return; }
        const ri = rows.findIndex((r) => r.id === f.rowId);
        if (ri <= 0) { return; }
        const from = rows[ri - 1];
        const to = rows[ri];
        if (!this.isEditable(to, f.dayISO, this.primaryKey)) { return; }
        const v = this.displayed(from, f.dayISO, this.primaryKey);
        this._applyEdit(to, f.dayISO, this.primaryKey,
                        v === null || v === undefined ? "0" : String(v));
    }

    _cellEl(rowId, dayISO) {
        if (!this.gridRef.el) { return null; }
        return this.gridRef.el.querySelector(
            `[data-cell="${rowId}|${dayISO}"]`);
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
        const el = this._cellEl(rows[ri].id, days[di].iso);
        if (el && el.scrollIntoView) {
            el.scrollIntoView({ block: "nearest", inline: "nearest" });
        }
    }

    // ----------------------------------------------------------------- saving
    setFilter(ev) { this.state.filter = ev.target.value; }
    toggleEntriesOnly() { this.state.entriesOnly = !this.state.entriesOnly; }
    toggleHelp() { this.state.helpOpen = !this.state.helpOpen; }

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
        this.closeEditor();
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
