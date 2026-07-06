/** @odoo-module **/
import { Component, useState, useRef, onPatched, onWillUnmount } from "@odoo/owl";
import { FormulaBar } from "./formula_bar";
import { CellAutocomplete } from "./cell_autocomplete";

// Property rows are a fixed vocabulary — index math stays trivial.
const ROWS = ["name", "category", "type", "formula", "value", "status"];
const EDITABLE_ROWS = new Set(["formula"]); // category/type edit via bulk popover (T2.7)

// Grid Studio v1 (T2.2 — focus model + keyboard nav + cell editing, skeleton S1).
// Orientation per plan D2: components are COLUMNS (frozen header = letter + code),
// property rows Name/Category/Type/Formula/Value/Status (frozen first column).
export class GridStudio extends Component {
    static template = "pb_formula_studio.GridStudio";
    static components = { FormulaBar, CellAutocomplete };
    // Parent passes the SHARED data (never copied) + callbacks. Grid never mutates
    // parent state; it saves/validates through the callbacks and re-reads the
    // refreshed props on the next render.
    static props = {
        components: Array,
        preview: Object,
        graph: { type: Object, optional: true },
        canEdit: { type: Boolean, optional: true },
        selectedId: { optional: true },
        onSelect: Function,          // (ruleId) => parent.selectComponent
        formatValue: Function,       // (col) => display string, mirrors parent previewVal
        sampleName: { type: String, optional: true },
        fieldMeta: { type: Object, optional: true },   // {categories, number_formats, ...}
        onSaveFormula: Function,     // (ruleId, formula) => parent save + refresh + compute_preview
        onValidateLive: Function,    // (formula, excludeRuleId) => {valid, message}
        onBulkUpdate: { type: Function, optional: true },   // (ruleIds, vals) => bulk RPC + refresh
        onTranslateFormula: { type: Function, optional: true }, // (ruleId, cols) => [{col,proposed_formula,valid}]
        onBulkSaveFormulas: { type: Function, optional: true }, // (items) => save + refresh
    };

    setup() {
        // CRITICAL: grid-local UI state lives in its OWN useState, keyed by
        // component *id*, never array index — the parent replaces state.components
        // wholesale after every save, so id-keyed focus/selection survive a refresh.
        this.ui = useState({
            focus: { colId: null, row: "formula" }, // colId = hr.formula.rule id
            selection: [],                           // array of colIds (Ctrl/Shift multi-select)
            anchorId: null,                          // Shift-range anchor
            editing: null,   // { colId, row, buffer, valid, message } | null
            composing: false, // IME guard
            tintCol: null,   // column letter whose dependencies are tinted (T2.4)
            // T2.6 autocomplete: {open, query, start, caret, items, active, left, top}
            autocomplete: { open: false, query: "", start: 0, caret: 0, items: [], active: 0, left: 0, top: 0 },
            // T2.7 bulk edit popover
            bulkOpen: false,
            bulkDraft: { category_id: "", number_format: "", appears_on_payslip: "", is_visible_in_grid: "" },
            // T2.8 drag-fill: {active, pending, srcId, hoverCol, targets:[{col,id,proposed_formula,valid}]}
            fill: { active: false, pending: false, srcId: null, hoverCol: null, targets: [] },
        });
        onWillUnmount(() => this._teardownFill());
        this.scrollerRef = useRef("scroller");
        this.editorRef = useRef("editor");
        this._liveTimer = null;      // same debounce pattern as formula_studio.js
        this._vseq = 0;              // monotonic validation token (supersede guard)
        this._lastCommit = null;     // { ruleId, previousFormula } — single-level undo (T2.9)
        this._editorSeeded = false;  // seed the overlay <input> value exactly once
        onPatched(() => this._afterPatch());
    }

    // ---- derived (recomputed against CURRENT props each render) ----
    get ordered() {
        return [...this.props.components].sort((a, b) => this._colNum(a.col) - this._colNum(b.col));
    }
    get focused() { return this.props.components.find(c => c.id === this.ui.focus.colId) || null; }
    _colNum(col) {
        let n = 0;
        for (const ch of String(col || "").toUpperCase()) {
            const v = ch.charCodeAt(0) - 64;
            if (v < 1 || v > 26) return 0;
            n = n * 26 + v;
        }
        return n;
    }

    typeLabel(c) { return { input: "Input", formula: "Formula", constant: "Constant" }[c.type] || c.type; }
    formulaText(c) {
        if (c.type === "formula") return c.excel_formula || "—";
        if (c.type === "constant") return String(c.constant_value ?? "");
        return "—";
    }

    // ---- class helpers (id-keyed focus/selection state) ----
    isFocusedCell(colId, row) { return this.ui.focus.colId === colId && this.ui.focus.row === row; }
    inSelection(c) { return this.ui.selection.includes(c.id); }
    isEditingCell(c, row) { return !!this.ui.editing && this.ui.editing.colId === c.id && this.ui.editing.row === row; }
    headClass(c) {
        const cls = ["g2-chead"];
        const dep = this.depClass(c);
        if (dep) cls.push(dep);
        if (this.inSelection(c)) cls.push("in-selection");
        if (this.ui.focus.colId === c.id) cls.push("sel");
        return cls.join(" ");
    }
    cellClass(c, row) {
        const cls = ["g2-cell"];
        if (row === "category") cls.push("muted");
        if (row === "formula") {
            cls.push("g2-formula");
            if (c.type === "formula") cls.push("is-formula");
            if (this.statusOf(c).state === "error") cls.push("has-error");
        }
        if (row === "value") cls.push("g2-value");
        if (row === "status") cls.push("g2-statuscell");
        const dep = this.depClass(c);
        if (dep) cls.push(dep);
        if (this.isFillTarget(c)) cls.push("fill-target");
        if (this.inSelection(c)) cls.push("in-selection");
        if (this.isFocusedCell(c.id, row)) cls.push("focused");
        return cls.join(" ");
    }

    // ---- validation status (T2.5): is_valid / circular-ref → badge + corner ----
    _cycleForCol(col) {
        const cycles = (this.props.graph && this.props.graph.cycles) || [];
        return cycles.find(cy => (cy.cols || []).includes(col)) || null;
    }
    statusOf(comp) {
        if (!comp.is_valid) return { state: "error", message: comp.validation_message || "This formula has an error." };
        const cyc = this._cycleForCol(comp.col);
        if (cyc) return { state: "error", message: cyc.human_explanation };
        return { state: "ok", message: "Valid" };
    }
    formulaTitle(c) {
        const st = this.statusOf(c);
        return st.state === "error" ? st.message : this.formulaText(c);
    }
    // message shown at the footer when a broken cell is focused (keyboard/click)
    get focusedError() {
        const f = this.focused;
        if (!f || this.ui.editing) return "";
        const st = this.statusOf(f);
        return st.state === "error" ? st.message : "";
    }

    // ---- dependency tinting (T2.4): amber upstream / cyan downstream ----
    // BFS over props.graph.edges [depCol, consumerCol]; memoised per tintCol so
    // depClass() (called per cell) recomputes the sets at most once per render.
    _bfsCols(startCol, dir) {
        const edges = (this.props.graph && this.props.graph.edges) || [];
        const seen = new Set([startCol]); const queue = [startCol]; const out = new Set();
        while (queue.length) {
            const cur = queue.shift();
            for (const e of edges) {
                const from = e[0], to = e[1];
                let next = null;
                if (dir === "down" && from === cur) next = to;
                else if (dir === "up" && to === cur) next = from;
                if (next && !seen.has(next)) { seen.add(next); out.add(next); queue.push(next); }
            }
        }
        return out;
    }
    _ensureTint() {
        const col = this.ui.tintCol;
        if (this._tintForCol === col) return;
        this._tintForCol = col;
        this._upstream = col ? this._bfsCols(col, "up") : null;
        this._downstream = col ? this._bfsCols(col, "down") : null;
    }
    depClass(comp) {
        if (!this.ui.tintCol || comp.col === this.ui.tintCol) return "";
        this._ensureTint();
        if (this._upstream && this._upstream.has(comp.col)) return "dep-upstream";
        if (this._downstream && this._downstream.has(comp.col)) return "dep-downstream";
        return "";
    }

    // ---- focus & selection ----
    setFocus(colId, row) {
        if (this.ui.editing) return;                 // an open editor owns the keyboard
        this.ui.focus = { colId, row };
        const comp = this.props.components.find(c => c.id === colId);
        this.ui.tintCol = comp ? comp.col : null;    // tint this column's dependencies
        this.props.onSelect(colId);                  // keep cards/outline in sync
    }
    onScrollerFocus() {
        if (this.ui.focus.colId == null) {
            const first = this.ordered[0];
            if (first) this.setFocus(first.id, "formula");
        } else if (this.ui.tintCol == null) {
            const comp = this.focused;
            if (comp) this.ui.tintCol = comp.col;    // restore tint on re-focus
        }
    }
    onScrollerBlur() {
        // tint clears when the grid loses focus — but not while an overlay editor
        // (a descendant input) is stealing focus mid-edit.
        if (!this.ui.editing) this.ui.tintCol = null;
    }
    onCellClick(ev, comp, row) {
        if (ev.ctrlKey || ev.metaKey) return this._toggleSelect(comp.id);
        if (ev.shiftKey && this.ui.anchorId) return this._rangeSelect(comp.id);
        this.ui.selection = []; this.ui.anchorId = comp.id;
        this.setFocus(comp.id, row);
    }
    onCellDblClick(comp, row) {
        if (!this.props.canEdit || !EDITABLE_ROWS.has(row)) return;
        this.setFocus(comp.id, row);
        this._startEdit();
    }
    _toggleSelect(colId) {
        const i = this.ui.selection.indexOf(colId);
        if (i === -1) { this.ui.selection = [...this.ui.selection, colId]; this.ui.anchorId = colId; }
        else { this.ui.selection = this.ui.selection.filter(x => x !== colId); }
    }
    _rangeSelect(colId) {
        const ids = this.ordered.map(c => c.id);
        const a = ids.indexOf(this.ui.anchorId), b = ids.indexOf(colId);
        if (a === -1 || b === -1) return;
        const [lo, hi] = a < b ? [a, b] : [b, a];
        this.ui.selection = ids.slice(lo, hi + 1);
    }

    // ---- keyboard: ONE handler on the scroller (roving focus; cells are inert) ----
    onKeydown(ev) {
        if (this.ui.editing) return this._onEditorKeydown(ev); // editor has its own path
        if ((ev.ctrlKey || ev.metaKey) && (ev.key === "z" || ev.key === "Z")) {
            ev.preventDefault(); ev.stopPropagation(); this._undo(); return;   // single-level undo (T2.9)
        }
        const cols = this.ordered;
        let ci = cols.findIndex(c => c.id === this.ui.focus.colId);
        if (ci === -1) ci = 0;
        const ri = Math.max(0, ROWS.indexOf(this.ui.focus.row));
        const move = (dc, dr) => {
            const c = cols[Math.max(0, Math.min(cols.length - 1, ci + dc))];
            const r = ROWS[Math.max(0, Math.min(ROWS.length - 1, ri + dr))];
            if (c) this.setFocus(c.id, r);
        };
        const shiftSel = (dc) => {
            if (this.ui.anchorId == null) this.ui.anchorId = this.ui.focus.colId ?? cols[ci]?.id;
            const c = cols[Math.max(0, Math.min(cols.length - 1, ci + dc))];
            if (c) { this.ui.focus = { colId: c.id, row: this.ui.focus.row }; this._rangeSelect(c.id); this.props.onSelect(c.id); }
        };
        switch (ev.key) {
            case "ArrowRight": ev.shiftKey ? shiftSel(+1) : move(+1, 0); break;
            case "ArrowLeft":  ev.shiftKey ? shiftSel(-1) : move(-1, 0); break;
            case "ArrowDown":  move(0, +1); break;
            case "ArrowUp":    move(0, -1); break;
            case "Tab":        move(ev.shiftKey ? -1 : +1, 0); break;
            case "Enter": case "F2": this._startEdit(); break;
            case "Escape": this.ui.selection = []; break;
            default:
                // printable char on an editable cell → open editor pre-seeded with the char
                if (ev.key.length === 1 && !ev.ctrlKey && !ev.metaKey && !ev.altKey
                    && EDITABLE_ROWS.has(this.ui.focus.row) && this.props.canEdit) {
                    this._startEdit(ev.key); break;
                }
                return; // unhandled: let it bubble
        }
        ev.preventDefault(); ev.stopPropagation();
    }

    // ---- editing (single <input> overlay swapped into the focused cell) ----
    _startEdit(seed) {
        const f = this.focused;
        // Only formula-type components have an editable formula; input/constant
        // rows show "—" and are read-only in the grid (change type via full editor).
        if (!f || f.type !== "formula" || !EDITABLE_ROWS.has(this.ui.focus.row) || !this.props.canEdit) return;
        this._editorSeeded = false;
        this._closeAutocomplete();
        this.ui.editing = {
            colId: f.id, row: this.ui.focus.row,
            buffer: seed !== undefined ? seed : (f.excel_formula || ""),
            valid: null, message: "",
        };
    }
    onEditorInput(ev) {
        this.ui.editing.buffer = ev.target.value;
        if (this.ui.composing) return;               // IME: never validate mid-composition
        this._scheduleValidate();
        this._updateAutocomplete();
    }
    _scheduleValidate() {
        clearTimeout(this._liveTimer);
        const mine = this.ui.editing;
        if (!mine) return;
        const seq = ++this._vseq;                     // token: only the latest validate applies
        const val = mine.buffer;
        this._liveTimer = setTimeout(async () => {
            const res = await this.props.onValidateLive(val, mine.colId);
            // stale-guard: same editor session AND no newer request superseded this one
            if (this.ui.editing === mine && seq === this._vseq && res) {
                Object.assign(mine, { valid: res.valid, message: res.message || "" });
            }
        }, 260);
    }

    // ---- cell autocomplete (T2.6) ----
    // Detect an identifier being typed right after '=', an operator, '(' or ',';
    // propose matching component codes; insert the column-letter reference.
    _updateAutocomplete() {
        const el = this.editorRef.el;
        if (!el) return this._closeAutocomplete();
        const caret = el.selectionStart;
        const text = el.value;
        const before = text.slice(0, caret);
        const m = before.match(/([A-Za-z][A-Za-z0-9_]*)$/);
        if (!m) return this._closeAutocomplete();
        const query = m[1];
        const start = caret - query.length;
        const prev = start > 0 ? text[start - 1] : "=";   // treat start-of-buffer like after '='
        if (!/[=+\-*/(%,\s]/.test(prev)) return this._closeAutocomplete();
        const q = query.toLowerCase();
        const items = this.props.components
            .filter(c => (c.code || "").toLowerCase().startsWith(q) || (c.name || "").toLowerCase().includes(q))
            .sort((a, b) => this._colNum(a.col) - this._colNum(b.col))
            .slice(0, 8)
            .map(c => ({ id: c.id, col: c.col, code: c.code, name: c.name, value: this.props.formatValue(c.col) }));
        if (!items.length) return this._closeAutocomplete();
        const r = el.getBoundingClientRect();
        this.ui.autocomplete = { open: true, query, start, caret, items, active: 0, left: r.left, top: r.bottom + 2 };
    }
    _closeAutocomplete() {
        if (this.ui.autocomplete.open) {
            this.ui.autocomplete = { open: false, query: "", start: 0, caret: 0, items: [], active: 0, left: 0, top: 0 };
        }
    }
    _refRow() {
        for (const c of this.props.components) {
            const mm = (c.excel_formula || "").match(/[A-Za-z]+(\d+)/);
            if (mm) return mm[1];
        }
        return "2";
    }
    _insertAutocomplete(item) {
        const ac = this.ui.autocomplete;
        const el = this.editorRef.el;
        if (!ac.open || !item || !el) return;
        const text = el.value;
        const ref = item.col + this._refRow();       // e.g. "A2"
        const head = text.slice(0, ac.start) + ref;
        const newText = head + text.slice(ac.caret);
        el.value = newText;
        const caret = head.length;
        el.setSelectionRange(caret, caret);
        this.ui.editing.buffer = newText;
        this._closeAutocomplete();
        el.focus();
        this._scheduleValidate();                     // revalidate; do NOT reopen autocomplete
    }
    get autocompleteStyle() {
        const ac = this.ui.autocomplete;
        return `left:${Math.round(ac.left)}px; top:${Math.round(ac.top)}px;`;
    }
    onAutocompletePick(item) { this._insertAutocomplete(item); }
    onAutocompleteHover(i) { this.ui.autocomplete.active = i; }

    // ---- bulk edit (T2.7): whitelisted fields across ≥2 selected columns ----
    get selectionCount() { return this.ui.selection.length; }
    get bulkCategories() { return (this.props.fieldMeta && this.props.fieldMeta.categories) || []; }
    get bulkNumberFormats() { return (this.props.fieldMeta && this.props.fieldMeta.number_formats) || []; }
    clearSelection() { this.ui.selection = []; this.ui.bulkOpen = false; }
    openBulk() {
        this.ui.bulkDraft = { category_id: "", number_format: "", appears_on_payslip: "", is_visible_in_grid: "" };
        this.ui.bulkOpen = true;
    }
    closeBulk() { this.ui.bulkOpen = false; }
    setBulkField(field, ev) { this.ui.bulkDraft[field] = ev.target.value; }
    async applyBulk() {
        const d = this.ui.bulkDraft, vals = {};
        if (d.category_id !== "") vals.category_id = parseInt(d.category_id, 10);
        if (d.number_format !== "") vals.number_format = d.number_format;
        if (d.appears_on_payslip !== "") vals.appears_on_payslip = d.appears_on_payslip === "true";
        if (d.is_visible_in_grid !== "") vals.is_visible_in_grid = d.is_visible_in_grid === "true";
        this.ui.bulkOpen = false;
        if (!Object.keys(vals).length || !this.props.onBulkUpdate) return;
        const ids = [...this.ui.selection];         // id-keyed → selection survives the refresh
        await this.props.onBulkUpdate(ids, vals);
    }

    // ---- drag-fill (T2.8): fill a formula right with relative translation ----
    // Preview/confirm only (no series detection): drag right → ghost proposals →
    // Enter commits, Escape discards. Nothing is written until Enter.
    canFillFrom(c) {
        return this.props.canEdit && this.props.onTranslateFormula && c
            && c.type === "formula" && this.isFocusedCell(c.id, "formula") && !this.ui.editing;
    }
    ghostFor(comp) {
        if (!this.ui.fill.active && !this.ui.fill.pending) return null;
        return this.ui.fill.targets.find(t => t.id === comp.id) || null;
    }
    isFillTarget(comp) { return !!this.ghostFor(comp); }
    onFillDown(ev) {
        ev.preventDefault(); ev.stopPropagation();
        const f = this.focused;
        if (!this.canFillFrom(f)) return;
        this.ui.fill = { active: true, pending: false, srcId: f.id, hoverCol: null, targets: [] };
        this._fillMove = this._onFillMove.bind(this);
        this._fillUp = this._onFillUp.bind(this);
        document.addEventListener("mousemove", this._fillMove);
        document.addEventListener("mouseup", this._fillUp);
    }
    // On move: compute the target formula columns SYNCHRONOUSLY (client-side) so
    // the highlight/ghost is immediate and race-free; fire a best-effort translate
    // for live ghost text (guarded by hoverCol so stale replies are ignored).
    _fillTargetsFor(src, hover) {
        return this.ordered.filter(c =>
            c.type === "formula"
            && this._colNum(c.col) > this._colNum(src.col)
            && this._colNum(c.col) <= this._colNum(hover.col));
    }
    async _onFillMove(ev) {
        if (!this.ui.fill.active) return;
        const el = document.elementFromPoint(ev.clientX, ev.clientY);
        const cellEl = el && el.closest("[data-col-id]");
        if (!cellEl) return;
        const hoverId = parseInt(cellEl.getAttribute("data-col-id"), 10);
        const src = this.props.components.find(c => c.id === this.ui.fill.srcId);
        const hover = this.props.components.find(c => c.id === hoverId);
        if (!src || !hover) return;
        if (this._colNum(hover.col) <= this._colNum(src.col)) {       // src or left → nothing
            if (this.ui.fill.hoverCol !== null) this.ui.fill = { ...this.ui.fill, hoverCol: null, targets: [] };
            return;
        }
        if (this.ui.fill.hoverCol === hover.col) return;             // unchanged span
        const targets = this._fillTargetsFor(src, hover);
        // synchronous placeholders → instant highlight/ghost, no post-mouseup race
        this.ui.fill = { ...this.ui.fill, hoverCol: hover.col,
            targets: targets.map(c => ({ col: c.col, id: c.id, proposed_formula: "…", valid: true })) };
        const cols = targets.map(c => c.col), byCol = {};
        targets.forEach(c => { byCol[c.col] = c.id; });
        const proposals = await this.props.onTranslateFormula(this.ui.fill.srcId, cols);
        if (this.ui.fill.hoverCol === hover.col && proposals) {       // still the same span
            this.ui.fill.targets = proposals.map(p => ({ ...p, id: byCol[p.col] }));
        }
    }
    async _onFillUp() {
        document.removeEventListener("mousemove", this._fillMove);
        document.removeEventListener("mouseup", this._fillUp);
        const current = this.ui.fill.targets;
        if (!current.length) { this._clearFill(); return; }
        // definitive translate for the final span (awaited) so ghosts are correct
        const cols = current.map(t => t.col), byCol = {};
        current.forEach(t => { byCol[t.col] = t.id; });
        const proposals = await this.props.onTranslateFormula(this.ui.fill.srcId, cols);
        if (!proposals || !proposals.length) { this._clearFill(); return; }
        this.ui.fill = { ...this.ui.fill, active: false, pending: true,
            targets: proposals.map(p => ({ ...p, id: byCol[p.col] })) };
        this._fillKey = this._onFillKey.bind(this);
        document.addEventListener("keydown", this._fillKey, true);   // capture Enter/Escape
    }
    _onFillKey(ev) {
        if (ev.key === "Enter") { ev.preventDefault(); ev.stopPropagation(); this._commitFill(); }
        else if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); this._discardFill(); }
    }
    async _commitFill() {
        const targets = this.ui.fill.targets.filter(t => t.valid && t.id);
        this._teardownFill();
        if (!targets.length || !this.props.onBulkSaveFormulas) return;
        await this.props.onBulkSaveFormulas(targets.map(t => ({ rule_id: t.id, formula: t.proposed_formula })));
    }
    _discardFill() { this._teardownFill(); }
    _teardownFill() {
        if (this._fillMove) { document.removeEventListener("mousemove", this._fillMove); this._fillMove = null; }
        if (this._fillUp) { document.removeEventListener("mouseup", this._fillUp); this._fillUp = null; }
        if (this._fillKey) { document.removeEventListener("keydown", this._fillKey, true); this._fillKey = null; }
        this._clearFill();
    }
    _clearFill() { this.ui.fill = { active: false, pending: false, srcId: null, hoverCol: null, targets: [] }; }
    onCompositionStart() { this.ui.composing = true; }
    onCompositionEnd(ev) { this.ui.composing = false; this.onEditorInput(ev); }
    _onEditorKeydown(ev) {
        const ac = this.ui.autocomplete;
        if (ac.open) {
            // dropdown owns arrows/Enter/Tab/Escape — never move grid focus
            if (ev.key === "ArrowDown") { ev.preventDefault(); ev.stopPropagation(); ac.active = Math.min(ac.items.length - 1, ac.active + 1); return; }
            if (ev.key === "ArrowUp") { ev.preventDefault(); ev.stopPropagation(); ac.active = Math.max(0, ac.active - 1); return; }
            if (ev.key === "Enter" || ev.key === "Tab") { ev.preventDefault(); ev.stopPropagation(); this._insertAutocomplete(ac.items[ac.active]); return; }
            if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); this._closeAutocomplete(); return; }
        }
        if (ev.key === "Enter" && !this.ui.composing) { ev.preventDefault(); this._commit(); }
        else if (ev.key === "Escape") { ev.preventDefault(); this._closeAutocomplete(); this.ui.editing = null; } // discard
        ev.stopPropagation(); // NEVER let editor keys reach the grid navigator
    }
    async _commit() {
        const e = this.ui.editing, comp = this.props.components.find(c => c.id === e.colId);
        if (!comp) return;
        // Final synchronous guard: invalid syntax must never call save_formula,
        // even if the user hits Enter before the debounced validation resolved.
        const res = await this.props.onValidateLive(e.buffer, e.colId);
        if (res && res.valid === false) { Object.assign(e, { valid: false, message: res.message || "Invalid formula" }); return; }
        this._lastCommit = { ruleId: comp.id, previousFormula: comp.excel_formula };
        this._closeAutocomplete();
        this.ui.editing = null;
        await this.props.onSaveFormula(comp.id, e.buffer); // parent saves + refreshes + compute_preview
        this.scrollerRef.el?.focus();   // regain roving focus so Ctrl+Z works right after a commit
        // focus survives refresh automatically: ui.focus.colId is an id, and `focused`
        // re-resolves against the NEW props.components on next render.
    }
    async _undo() {
        if (!this._lastCommit) return;             // single-level: nothing to undo → no-op
        const { ruleId, previousFormula } = this._lastCommit;
        this._lastCommit = null;                   // consume it; a second Ctrl+Z does nothing
        await this.props.onSaveFormula(ruleId, previousFormula);
        this.scrollerRef.el?.focus();
    }

    // ---- post-render: seed the overlay input once, keep focus in view ----
    _afterPatch() {
        if (this.ui.editing && this.editorRef.el && !this._editorSeeded) {
            this._editorSeeded = true;
            const el = this.editorRef.el;
            el.value = this.ui.editing.buffer || "";
            el.focus();
            const n = el.value.length;
            try { el.setSelectionRange(n, n); } catch (e) { /* non-text input */ }
            return;
        }
        if (!this.ui.editing) {
            this._editorSeeded = false;
            this._scrollFocusIntoView();
        }
    }
    _scrollFocusIntoView() {
        const root = this.scrollerRef.el;
        if (!root || this.ui.focus.colId == null) return;
        const el = root.querySelector(`[data-col-id="${this.ui.focus.colId}"][data-row="${this.ui.focus.row}"]`);
        if (el) el.scrollIntoView({ block: "nearest", inline: "nearest" });
    }
}
