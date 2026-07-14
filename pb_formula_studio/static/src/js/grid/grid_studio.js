/** @odoo-module **/
import { Component, useState, useRef, onMounted, onPatched, onWillUnmount } from "@odoo/owl";
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
        // W4 — extra pinned sample value rows (display-only; never focusable, C3/D-F3)
        extraPreviews: { type: Array, optional: true },       // [{sample_id, name, values}]
        formatValueFor: { type: Function, optional: true },   // (col, values) => display string
        onUnpinSample: { type: Function, optional: true },    // (sid) => parent unpins
        sampleName: { type: String, optional: true },
        fieldMeta: { type: Object, optional: true },   // {categories, number_formats, ...}
        onSaveFormula: Function,     // (ruleId, formula) => parent save + refresh + compute_preview
        onValidateLive: Function,    // (formula, excludeRuleId) => {valid, message}
        onBulkUpdate: { type: Function, optional: true },   // (ruleIds, vals) => bulk RPC + refresh
        onTranslateFormula: { type: Function, optional: true }, // (ruleId, cols) => [{col,proposed_formula,valid}]
        onBulkSaveFormulas: { type: Function, optional: true }, // (items) => save + refresh
        // F14 — scenario columns (what-if overlays; ghost columns next to their base)
        scenarios: { type: Array, optional: true },
        onScenarioCreate: { type: Function, optional: true },   // (ruleId) => new scenario payload
        onScenarioSave: { type: Function, optional: true },     // (sid, formula) => {ok,valid,message}
        onScenarioEval: { type: Function, optional: true },     // (sid, sampleId) => {base_value,scenario_value,net_*}
        onScenarioPromote: { type: Function, optional: true },  // (sid) => write into base rule (versioned)
        onScenarioDiscard: { type: Function, optional: true },  // (sid) => delete
        // F111 — display reorder + group by category (letters stay frozen)
        onReorder: { type: Function, optional: true },          // (dragId, beforeId|false) => reorder + refresh
        onGroupByCategory: { type: Function, optional: true },  // () => group + refresh
        // W8 — collapse by category (display fold; parent owns {catKey:true})
        folds: { type: Object, optional: true },
        onToggleFold: { type: Function, optional: true },       // (catKey) => parent flips state.folds
        formatSum: { type: Function, optional: true },          // (total) => display string for a summary Σ
        // W104 — snippet library: autocomplete rows + palette-queued insertion
        snippets: { type: Array, optional: true },
        pendingSnippet: { optional: true },                     // snippet id queued by the palette | null
        onSnippetConsumed: { type: Function, optional: true },  // () => parent clears the queue
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
            // F14 scenario editing: {id, buffer, valid, message} | null (one at a time)
            scenarioEdit: null,
            // F111 column drag-reorder
            dragId: null,
            dragOverId: null,
        });
        // F14 scenario overlay values, keyed by scenario id → {base_value, scenario_value,
        // net_base, net_scenario, forSample, loading}. Separate reactive store so a value
        // refresh doesn't churn the main ui state.
        this.scenarioValues = useState({});
        this._scSeq = 0;             // scenario-validate supersede token
        this._scEditorSeeded = false;
        // W109 — column virtualization window. Dormant (on:false) below the
        // activation threshold, so typical configs render byte-identically to
        // before. `first/last` are indices into `this.ordered` (base columns).
        this.vcols = useState({ on: false, first: 0, last: Infinity });
        this._colW = null;           // fixed column width (px) read from --g2-colw once
        this._labelW = null;         // frozen row-label column width, measured once
        this._lastN = null;          // last ordered length (recompute window on change)
        this._scrollRaf = null;      // rAF handle coalescing scroll → window recompute
        this._edgeDir = 0;           // auto-scroll direction at a drag/fill window edge
        this._edgeTimer = null;
        onWillUnmount(() => { this._teardownFill(); this._detachScroll(); this._stopEdgeScroll(); });
        onMounted(() => { this._attachScroll(); this._consumePendingSnippet(); });
        this.scrollerRef = useRef("scroller");
        this.editorRef = useRef("editor");
        this.scEditorRef = useRef("scEditor");
        this._liveTimer = null;      // same debounce pattern as formula_studio.js
        this._vseq = 0;              // monotonic validation token (supersede guard)
        this._lastCommit = null;     // { ruleId, previousFormula } — single-level undo (T2.9)
        this._editorSeeded = false;  // seed the overlay <input> value exactly once
        onPatched(() => this._afterPatch());
    }

    // ---- derived (recomputed against CURRENT props each render) ----
    // F111: display order follows `sequence` (letters are frozen identities that
    // no longer track position), falling back to letter order for older payloads.
    get ordered() {
        return [...this.props.components].sort((a, b) =>
            ((a.sequence ?? 0) - (b.sequence ?? 0)) || (this._colNum(a.col) - this._colNum(b.col)));
    }
    get focused() { return this.props.components.find(c => c.id === this.ui.focus.colId) || null; }

    // ==== W8 — collapse by category (display transform; S-F1) =================
    // ONE unit list downstream of `ordered`; every windowing/nav/fill consumer
    // reads `viewOrdered` (or `baseCols`) instead of `ordered`. `ordered` itself
    // is never touched, so letters/sequence stay authoritative.
    _catKey(c) { return String((c && (c.category_id || c.category || c.group)) || "?"); }
    get viewOrdered() {
        const folds = this.props.folds || {};
        const out = [];
        let openCat = null;                       // contiguous folded run being absorbed
        for (const c of this.ordered) {
            const k = this._catKey(c);
            if (folds[k]) {
                if (openCat === k) { out[out.length - 1].members.push(c); continue; }
                openCat = k;
                out.push({ kind: "summary", cat: k, label: c.category || c.group || k, members: [c], key: "cat:" + k + ":" + c.id });
            } else {
                openCat = null;
                out.push({ kind: "base", comp: c, key: "b" + c.id });
            }
        }
        return out;
    }
    // Visible base components only — the vocabulary keyboard nav and drag-fill walk
    // (folded columns never participate, D-F5).
    get baseCols() { return this.viewOrdered.filter(u => u.kind === "base").map(u => u.comp); }
    // Distinct categories in display order, for the toolbar fold chips.
    get foldableCategories() {
        const seen = new Map();
        for (const c of this.ordered) {
            const k = this._catKey(c);
            if (!seen.has(k)) seen.set(k, { key: k, label: c.category || c.group || k });
        }
        const folds = this.props.folds || {};
        return [...seen.values()].map(x => ({ ...x, folded: !!folds[x.key] }));
    }
    toggleFold(catKey) {
        if (!this.props.onToggleFold) return;
        const willFold = !((this.props.folds || {})[catKey]);
        // GOTCHA (S-F1): relocate focus OUT of a category that is about to fold
        // BEFORE the parent flips state and re-renders, else `focused` resolves to
        // a cell that no longer exists and _scrollFocusIntoView queries a dead node.
        if (willFold) this._relocateFocusOutOf(catKey);
        this.props.onToggleFold(catKey);
    }
    _relocateFocusOutOf(catKey) {
        const f = this.focused;
        if (!f) return;
        const folds = { ...(this.props.folds || {}), [catKey]: true };
        const visible = (c) => !folds[this._catKey(c)];
        if (visible(f)) return;                   // focused column stays visible
        if (this.ui.editing) this.ui.editing = null;   // its editor cell is unmounting
        const ord = this.ordered;
        const i = ord.findIndex(c => c.id === f.id);
        let target = null;
        for (let d = 1; d < ord.length && !target; d++) {
            const r = ord[i + d]; if (r && visible(r)) { target = r; break; }
            const l = ord[i - d]; if (l && visible(l)) { target = l; break; }
        }
        if (target) { this.setFocus(target.id, this.ui.focus.row); }
        else { this.ui.focus = { colId: null, row: this.ui.focus.row }; this.ui.tintCol = null; }
    }
    // Summary cell content: Σ of member values from the given values map (D-F6).
    summaryValue(summary, valuesMap) {
        let total = 0;
        for (const c of summary.members) {
            const v = valuesMap ? valuesMap[c.col] : undefined;
            if (typeof v === "number") total += v;
        }
        return this.props.formatSum ? this.props.formatSum(total) : this._fmtNum(total);
    }
    summaryBandStyle(summary) {
        const g = summary.members[0] && summary.members[0].group;
        return "--band:" + this._bandColor(g);
    }

    // ==== W109 — column virtualization (columns only; the 6 rows are fixed) ====
    // Activate only above THRESHOLD; below it the window stays off and the DOM is
    // identical to the pre-W109 grid (zero regression for typical configs).
    static VCOL_THRESHOLD = 60;
    static VCOL_OVERSCAN = 8;

    _attachScroll() {
        const el = this.scrollerRef.el;
        if (el) {
            this._onScroll = () => {
                if (this._scrollRaf) return;               // coalesce: at most one recompute per frame
                this._scrollRaf = requestAnimationFrame(() => { this._scrollRaf = null; this._recomputeWindow(); });
            };
            el.addEventListener("scroll", this._onScroll, { passive: true });
        }
        this._recomputeWindow();
    }
    _detachScroll() {
        if (this._scrollRaf) { cancelAnimationFrame(this._scrollRaf); this._scrollRaf = null; }
        const el = this.scrollerRef.el;
        if (el && this._onScroll) el.removeEventListener("scroll", this._onScroll);
        this._onScroll = null;
    }
    // Recompute {first,last} from scrollLeft/clientWidth. Only mutates vcols when
    // the visible span actually changed, so it is safe to call from onPatched.
    _recomputeWindow() {
        const vord = this.viewOrdered;      // W8: window indexes into viewOrdered
        const n = vord.length;
        if (n <= GridStudio.VCOL_THRESHOLD) {
            if (this.vcols.on) Object.assign(this.vcols, { on: false, first: 0, last: Infinity });
            return;
        }
        const el = this.scrollerRef.el;
        if (!el) return;
        if (!this._colW) this._colW = parseFloat(getComputedStyle(el).getPropertyValue("--g2-colw")) || 168;
        const over = GridStudio.VCOL_OVERSCAN, w = this._colW;
        const sl = el.scrollLeft, sr = sl + el.clientWidth;

        // Scenario ghosts (what-if columns) render at full colW too, and a base
        // column's pixel offset is (i + ghostsBefore(i)) × colW — matching the
        // displayColumns layout, where the spacer bridging a hidden run counts
        // only hidden BASE columns (ghost-bearing columns are always pinned, so
        // they never fall in a gap). Walking cumulative unit widths keeps the
        // window's scrollLeft→index inverse consistent with that layout; the old
        // `floor(scrollLeft/colW)` ignored ghost width and drifted the window
        // right by the ghost count left of the viewport (W109 review fix).
        // No scenarios → units == index, i.e. identical to the previous math.
        const scen = this.props.scenarios || [];
        let ghost = null;
        if (scen.length) {
            ghost = new Map();
            for (const s of scen) ghost.set(s.rule_id, (ghost.get(s.rule_id) || 0) + 1);
        }
        // A base unit occupies 1 colW + one per scenario ghost of that column; a
        // summary unit occupies exactly 1 colW (summaries never carry ghosts, D-F5).
        let first = -1, last = 0, units = 0;
        for (let i = 0; i < n; i++) {
            const colLeft = units * w;
            if (colLeft >= sr) break;              // this unit and all after are past the viewport
            if (first === -1 && colLeft + w > sl) first = i;   // first at-least-partially-visible
            last = i;
            const u = vord[i];
            const gcount = (u.kind === "base" && ghost) ? (ghost.get(u.comp.id) || 0) : 0;
            units += 1 + gcount;
        }
        if (first === -1) first = 0;
        first = Math.max(0, first - over);
        last = Math.min(n - 1, last + over);
        if (!this.vcols.on || this.vcols.first !== first || this.vcols.last !== last) {
            Object.assign(this.vcols, { on: true, first, last });
        }
    }
    // PINNED SET — columns owning transient UI (or a scenario) must render even
    // when off-window, so a cell never unmounts mid-interaction (D-A2).
    get _pinnedIds() {
        const p = new Set();
        const add = id => { if (id != null) p.add(id); };
        add(this.ui.focus.colId); add(this.ui.editing?.colId); add(this.ui.dragId);
        if (this.ui.fill.active || this.ui.fill.pending) {
            add(this.ui.fill.srcId);
            this.ui.fill.targets.forEach(t => add(t.id));
        }
        // Scenario ghosts pin with their base so a what-if cell never unmounts
        // mid-interaction AND so no ghost ever lands in a hidden gap (keeping the
        // spacer math — which bridges only hidden BASE columns — exact).
        for (const s of (this.props.scenarios || [])) add(s.rule_id);
        return p;
    }
    // Edge auto-scroll shared by drag-fill and column reorder: while the pointer
    // sits in the left/right margin, scroll the window so far columns come in.
    _edgeAutoScroll(clientX) {
        const el = this.scrollerRef.el;
        if (!el) return;
        const r = el.getBoundingClientRect();
        const M = 52;
        let dir = 0;
        if (clientX > r.right - M) dir = 1;
        else if (clientX < r.left + (this._labelW || 0) + M) dir = -1;
        this._edgeDir = dir;
        if (dir && !this._edgeTimer) this._edgeTimer = setInterval(() => this._edgeTick(), 16);
        else if (!dir && this._edgeTimer) this._stopEdgeScroll();
    }
    _edgeTick() {
        const el = this.scrollerRef.el;
        if (!el || !this._edgeDir) return;
        el.scrollLeft += this._edgeDir * 26;
        // drag-fill: the pointer may be stationary at the edge while we scroll, so
        // re-resolve the hovered target from the last known pointer position.
        if (this.ui.fill.active) this._recomputeFillHover(this._fillPointerX, this._fillPointerY);
    }
    _stopEdgeScroll() { if (this._edgeTimer) { clearInterval(this._edgeTimer); this._edgeTimer = null; } this._edgeDir = 0; }

    // ---- F111: column drag-reorder (display only) ----
    onColDragStart(ev, c) {
        if (!this.props.canEdit || !this.props.onReorder) { ev.preventDefault(); return; }
        this.ui.dragId = c.id;
        ev.dataTransfer.effectAllowed = "move";
        try { ev.dataTransfer.setData("text/plain", String(c.id)); } catch (e) { /* older browsers */ }
    }
    onColDragOver(ev, c) {
        if (this.ui.dragId == null || c.id === this.ui.dragId) return;
        ev.preventDefault();
        ev.dataTransfer.dropEffect = "move";
        this._edgeAutoScroll(ev.clientX);               // W109: dropping past the window edge auto-scrolls
        if (this.ui.dragOverId !== c.id) this.ui.dragOverId = c.id;
    }
    onColDrop(ev, c) {
        ev.preventDefault();
        this._stopEdgeScroll();
        const dragId = this.ui.dragId;
        this.ui.dragId = null; this.ui.dragOverId = null;
        if (dragId == null || c.id === dragId) return;
        // Resolve the insertion point in the order WITHOUT the dragged column, so
        // "after c" is the real next column — never the dragged column itself
        // (else dropping on the right half of the drag's own left neighbour, an
        // intended no-op, would send the column to the far end).
        const ord = this.ordered.filter(x => x.id !== dragId);
        const idx = ord.findIndex(x => x.id === c.id);
        const rect = ev.currentTarget.getBoundingClientRect();
        let beforeId = c.id; // left half: land just before c
        if ((ev.clientX - rect.left) > rect.width / 2) { // right half: land after c
            beforeId = (idx >= 0 && idx + 1 < ord.length) ? ord[idx + 1].id : false; // false = to the end
        }
        this.props.onReorder(dragId, beforeId);
    }
    onColDragEnd() { this.ui.dragId = null; this.ui.dragOverId = null; this._stopEdgeScroll(); }
    groupByCategory() { if (this.props.onGroupByCategory) this.props.onGroupByCategory(); }

    // ---- F111: category band strip ----
    _bandColor(group) {
        return { Inputs: "#0E7490", Earnings: "#4F46E5", Deductions: "#B45309", Totals: "#059669" }[group] || "#8B88A0";
    }
    bandStyle(c) { return "--band:" + this._bandColor(c.group); }
    get _bandStarts() {
        const starts = new Set();
        let prev = null;
        for (const c of this.ordered) {
            const cat = c.category_id || c.category || c.group;
            if (cat !== prev) starts.add(c.id);
            prev = cat;
        }
        return starts;
    }
    bandStart(c) { return this._bandStarts.has(c.id); }
    bandBoundaryClass(c) { return this._bandStarts.has(c.id) ? "g2-band g2-band-start" : "g2-band"; }

    _colNum(col) {
        let n = 0;
        for (const ch of String(col || "").toUpperCase()) {
            const v = ch.charCodeAt(0) - 64;
            if (v < 1 || v > 26) return 0;
            n = n * 26 + v;
        }
        return n;
    }

    // W4 — extra pinned value rows (display-only). They iterate the SAME
    // displayColumns as the active value row, so spacers/scenarios line up under
    // W109 windowing; base cells format via the parent's per-sample formatter.
    get extraPreviews() { return this.props.extraPreviews || []; }
    extraValue(ex, col) { return this.props.formatValueFor ? this.props.formatValueFor(col, ex.values) : "—"; }
    onUnpinExtra(sid) { if (this.props.onUnpinSample) this.props.onUnpinSample(sid); }

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
            const first = this.baseCols[0];   // W8: never seed focus on a folded column
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
        const ids = this.baseCols.map(c => c.id);   // W8: range spans visible columns only
        const a = ids.indexOf(this.ui.anchorId), b = ids.indexOf(colId);
        if (a === -1 || b === -1) return;
        const [lo, hi] = a < b ? [a, b] : [b, a];
        this.ui.selection = ids.slice(lo, hi + 1);
    }

    // ---- keyboard: ONE handler on the scroller (roving focus; cells are inert) ----
    onKeydown(ev) {
        if (this.ui.editing) return this._onEditorKeydown(ev); // editor has its own path
        if (this.ui.scenarioEdit) return;                      // a scenario editor owns the keyboard
        if ((ev.ctrlKey || ev.metaKey) && (ev.key === "z" || ev.key === "Z")) {
            ev.preventDefault(); ev.stopPropagation(); this._undo(); return;   // single-level undo (T2.9)
        }
        const cols = this.baseCols;   // W8: nav walks visible base columns only
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
                // printable char on an editable cell → open editor pre-seeded with the char.
                // "?" is EXCLUDED (W18/D-F1): it is not a legal formula-start token, and
                // leaving it unhandled lets it bubble to the window listener that opens the
                // shortcuts overlay while the grid scroller is focused.
                if (ev.key.length === 1 && ev.key !== "?" && !ev.ctrlKey && !ev.metaKey && !ev.altKey
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
        // W104 — snippet rows match on name/category and list AFTER component matches
        const snips = (this.props.snippets || [])
            .filter(s => (s.name || "").toLowerCase().includes(q) || (s.category || "").toLowerCase().includes(q))
            .slice(0, 4)
            .map(s => ({ id: "snip" + s.id, kind: "snippet", snippetId: s.id, code: s.name,
                         name: s.description || s.category || "", value: "snippet", body: s.body }));
        const comps = this.props.components
            .filter(c => (c.code || "").toLowerCase().startsWith(q) || (c.name || "").toLowerCase().includes(q))
            .sort((a, b) => this._colNum(a.col) - this._colNum(b.col))
            .slice(0, snips.length ? 6 : 8)
            .map(c => ({ id: c.id, col: c.col, code: c.code, name: c.name, value: this.props.formatValue(c.col) }));
        const items = [...comps, ...snips].slice(0, 8);
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
    // W104 — resolve ${CODE} placeholders to column-letter refs; an unknown code
    // is left AS-IS so live validation red-flags the cell (C7 — never silent 0).
    _resolveSnippetBody(body) {
        const row = this._refRow();
        return String(body || "").replace(/\$\{\s*([^}]+?)\s*\}/g, (m, codeRaw) => {
            const code = codeRaw.trim().toUpperCase();
            const comp = this.props.components.find(c => (c.code || "").toUpperCase() === code);
            return comp ? (comp.col + row) : m;
        });
    }
    _insertAutocomplete(item) {
        const ac = this.ui.autocomplete;
        const el = this.editorRef.el;
        if (!ac.open || !item || !el) return;
        const text = el.value;
        const ref = item.kind === "snippet"      // W104 — snippet expands to resolved body
            ? this._resolveSnippetBody(item.body)
            : item.col + this._refRow();          // e.g. "A2"
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
        // W8: never fill into a folded column — walk visible base columns only.
        return this.baseCols.filter(c =>
            c.type === "formula"
            && this._colNum(c.col) > this._colNum(src.col)
            && this._colNum(c.col) <= this._colNum(hover.col));
    }
    async _onFillMove(ev) {
        if (!this.ui.fill.active) return;
        this._fillPointerX = ev.clientX; this._fillPointerY = ev.clientY;
        this._edgeAutoScroll(ev.clientX);                // auto-scroll at the window edge (W109)
        await this._recomputeFillHover(ev.clientX, ev.clientY);
    }
    async _recomputeFillHover(x, y) {
        if (!this.ui.fill.active || x == null) return;
        const el = document.elementFromPoint(x, y);
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
        this._stopEdgeScroll();
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
        this._stopEdgeScroll();
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

    // ---- F14 scenario columns (ghost overlays next to their base) ----
    // Display units interleave each base column with its scenario ghost(s), so a
    // scenario renders immediately to the RIGHT of the component it overlays.
    // The roving keyboard/focus/drag-fill model still keys strictly on base
    // columns (this.ordered) — scenarios are mouse-interactive ghosts only.
    scenariosFor(ruleId) { return (this.props.scenarios || []).filter(s => s.rule_id === ruleId); }
    get hasScenarios() { return (this.props.scenarios || []).length > 0; }
    // Base column + its scenario ghosts, as display units (used by every row).
    _pushCol(units, c) {
        units.push({ kind: "base", comp: c, key: "b" + c.id });
        for (const s of this.scenariosFor(c.id)) units.push({ kind: "scenario", scenario: s, comp: c, key: "s" + s.id });
    }
    get displayColumns() {
        const units = [];
        const vord = this.viewOrdered;               // W8: base + summary units
        const pushUnit = (u) => {
            if (u.kind === "summary") units.push({ kind: "summary", summary: u, key: u.key });
            else this._pushCol(units, u.comp);        // base column + its scenario ghosts
        };
        if (!this.vcols.on) {                        // dormant: render everything, unchanged
            for (const u of vord) pushUnit(u);
            return units;
        }
        // Windowed: render [first..last] ∪ pinned, in order, bridging every run of
        // hidden units with one spacer <td> of width (gapCount × colW). A summary
        // and a (ghost-free, hence unpinned) hidden base each occupy exactly 1 colW,
        // so the spacer math stays exact. Pinning is a base-only concept (D-F5).
        const pin = this._pinnedIds;
        const w = this._colW || 168;
        let gap = 0;
        const flush = (tag) => { if (gap > 0) { units.push({ kind: "spacer", width: gap * w, key: "sp" + tag }); gap = 0; } };
        for (let i = 0; i < vord.length; i++) {
            const u = vord[i];
            const pinned = u.kind === "base" && pin.has(u.comp.id);
            if ((i >= this.vcols.first && i <= this.vcols.last) || pinned) {
                flush(i);
                pushUnit(u);
            } else {
                gap++;
            }
        }
        flush("end");
        return units;
    }
    canScenario(c) {
        return this.props.canEdit && !!this.props.onScenarioCreate && c && c.type === "formula";
    }
    async addScenario(ev, comp) {
        if (ev) ev.stopPropagation();
        if (!this.canScenario(comp)) return;
        await this.props.onScenarioCreate(comp.id);   // parent reloads props.scenarios; _sync evals it
    }
    _scenarioRuleId(sid) {
        const s = (this.props.scenarios || []).find(x => x.id === sid);
        return s ? s.rule_id : null;
    }
    isScenarioEditing(s) { return !!this.ui.scenarioEdit && this.ui.scenarioEdit.id === s.id; }
    startScenarioEdit(s) {
        if (!this.props.canEdit || !this.props.onScenarioSave) return;
        this._scEditorSeeded = false;
        this.ui.scenarioEdit = { id: s.id, buffer: s.override_formula || "", valid: null, message: "" };
    }
    onScenarioInput(ev) {
        if (!this.ui.scenarioEdit) return;
        this.ui.scenarioEdit.buffer = ev.target.value;
        this._scheduleScenarioValidate();
    }
    _scheduleScenarioValidate() {
        clearTimeout(this._scTimer);
        const mine = this.ui.scenarioEdit;
        if (!mine) return;
        const seq = ++this._scSeq;
        this._scTimer = setTimeout(async () => {
            const res = await this.props.onValidateLive(mine.buffer, this._scenarioRuleId(mine.id));
            if (this.ui.scenarioEdit === mine && seq === this._scSeq && res) {
                Object.assign(mine, { valid: res.valid, message: res.message || "" });
            }
        }, 260);
    }
    onScenarioEditorKeydown(ev) {
        if (ev.key === "Enter") { ev.preventDefault(); this._commitScenario(); }
        else if (ev.key === "Escape") { ev.preventDefault(); this.ui.scenarioEdit = null; }
        ev.stopPropagation();   // NEVER let scenario-editor keys reach the grid navigator
    }
    async _commitScenario() {
        const e = this.ui.scenarioEdit;
        if (!e) return;
        const res = await this.props.onValidateLive(e.buffer, this._scenarioRuleId(e.id));
        if (res && res.valid === false) { Object.assign(e, { valid: false, message: res.message || "Invalid formula" }); return; }
        this.ui.scenarioEdit = null;
        await this.props.onScenarioSave(e.id, e.buffer);
        const s = (this.props.scenarios || []).find(x => x.id === e.id);
        if (s) this._evalScenario(s);   // re-eval the value row with the new draft
        this.scrollerRef.el?.focus();
    }
    async promoteScenario(ev, s) {
        if (ev) ev.stopPropagation();
        if (!this.props.onScenarioPromote) return;
        if (s.valid === false) return;
        await this.props.onScenarioPromote(s.id);   // parent writes the rule (versioned) + refreshes
    }
    async discardScenario(ev, s) {
        if (ev) ev.stopPropagation();
        if (!this.props.onScenarioDiscard) return;
        delete this.scenarioValues[s.id];
        await this.props.onScenarioDiscard(s.id);
    }
    // value-row eval via the F8 overlay (guarded so onPatched can't loop)
    async _evalScenario(s) {
        if (!this.props.onScenarioEval) return;
        const sid = this.props.preview && this.props.preview.sample_id;
        this.scenarioValues[s.id] = { loading: true, forSample: sid };
        const r = await this.props.onScenarioEval(s.id, sid);
        if ((this.props.preview && this.props.preview.sample_id) === sid) {
            this.scenarioValues[s.id] = r && r.ok ? { ...r, forSample: sid } : { forSample: sid, ok: false };
        }
    }
    _syncScenarioValues() {
        if (!this.props.onScenarioEval) return;
        const sid = this.props.preview && this.props.preview.sample_id;
        const scenarios = this.props.scenarios || [];
        const ids = new Set(scenarios.map(s => s.id));
        for (const k of Object.keys(this.scenarioValues)) { if (!ids.has(+k)) delete this.scenarioValues[+k]; }
        for (const s of scenarios) {
            const cur = this.scenarioValues[s.id];
            if (!cur || cur.forSample !== sid) this._evalScenario(s);   // fires once per (scenario, sample)
        }
    }
    _fmtNum(v) { return Math.round(v || 0).toLocaleString("en-US"); }
    fmtSignedNum(v) {
        const n = Math.round(v || 0);
        return (n > 0 ? "+" : n < 0 ? "−" : "") + Math.abs(n).toLocaleString("en-US");
    }
    scenarioValue(s) {
        const v = this.scenarioValues[s.id];
        if (!v || v.loading) return "…";
        if (v.ok === false) return "—";
        return this._fmtNum(v.scenario_value);
    }
    scenarioDelta(s) {
        const v = this.scenarioValues[s.id];
        if (!v || v.loading || v.ok === false) return null;
        const d = (v.scenario_value || 0) - (v.base_value || 0);
        return Math.abs(d) < 0.5 ? null : d;
    }
    scenarioNetDelta(s) {
        const v = this.scenarioValues[s.id];
        if (!v || v.loading || v.ok === false || v.net_scenario === undefined) return null;
        const d = (v.net_scenario || 0) - (v.net_base || 0);
        return Math.abs(d) < 0.5 ? null : d;
    }
    scenarioStatus(s) {
        return s.valid === false ? { state: "error", message: s.message || "Invalid formula" } : { state: "ok", message: "Valid" };
    }

    // ---- post-render: seed the overlay input once, keep focus in view ----
    _afterPatch() {
        // W109: the component set may have been replaced (save/reorder/group) —
        // n can change, which flips or resizes the window and moves the spacers.
        // W8: folding a category also changes the unit count, so track viewOrdered
        // length (not ordered length). Only measure/recompute when it changed
        // (avoids a forced reflow on every unrelated patch).
        const n = this.viewOrdered.length;
        if (n !== this._lastN) {
            this._lastN = n;
            if (this._labelW == null && this.scrollerRef.el) {
                const lab = this.scrollerRef.el.querySelector(".g2-corner") || this.scrollerRef.el.querySelector(".g2-rlabel");
                this._labelW = lab ? lab.offsetWidth : 0;
            }
            this._recomputeWindow();
        }
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
        // seed the scenario editor overlay exactly once (mirrors the base editor)
        if (this.ui.scenarioEdit && this.scEditorRef.el && !this._scEditorSeeded) {
            this._scEditorSeeded = true;
            const el = this.scEditorRef.el;
            el.value = this.ui.scenarioEdit.buffer || "";
            el.focus();
            const n = el.value.length;
            try { el.setSelectionRange(n, n); } catch (e) { /* non-text */ }
        }
        if (!this.ui.scenarioEdit) this._scEditorSeeded = false;
        // keep scenario overlay values in sync with the current sample / scenario set
        this._syncScenarioValues();
        // W104 — a palette-queued snippet is inserted here (may span two patches:
        // one to open the editor, the next to insert once its <input> is mounted).
        this._consumePendingSnippet();
    }
    // Insert a snippet queued by the palette (D-F8 entry point b). Opens an editor
    // on the focused formula cell first if none is open.
    _consumePendingSnippet() {
        const sid = this.props.pendingSnippet;
        if (sid == null) return;
        const done = () => { if (this.props.onSnippetConsumed) this.props.onSnippetConsumed(); };
        const snip = (this.props.snippets || []).find(s => s.id === sid);
        if (!snip) return done();
        if (!this.ui.editing) {
            // prefer the focused formula cell; fall back to the first visible formula
            // column (e.g. when the palette was opened from another view, C3 remount)
            let f = this.focused;
            if (!f || f.type !== "formula") f = this.baseCols.find(c => c.type === "formula") || null;
            if (!f || !this.props.canEdit) return done();   // nowhere to insert
            this.setFocus(f.id, "formula");
            this._startEdit();          // editor <input> mounts on the next patch
            return;                     // wait for it, then this runs again
        }
        const el = this.editorRef.el;
        if (!el) return;                // editor not mounted yet — wait one more patch
        const text = el.value;
        const start = el.selectionStart ?? text.length, end = el.selectionEnd ?? start;
        const ins = this._resolveSnippetBody(snip.body);
        const newText = text.slice(0, start) + ins + text.slice(end);
        el.value = newText;
        const caret = start + ins.length;
        try { el.setSelectionRange(caret, caret); } catch (e) { /* non-text */ }
        this.ui.editing.buffer = newText;
        this._closeAutocomplete();
        el.focus();
        this._scheduleValidate();
        done();
    }
    _scrollFocusIntoView() {
        const root = this.scrollerRef.el;
        if (!root || this.ui.focus.colId == null) return;
        const el = root.querySelector(`[data-col-id="${this.ui.focus.colId}"][data-row="${this.ui.focus.row}"]`);
        if (el) el.scrollIntoView({ block: "nearest", inline: "nearest" });
    }
}
