/** @odoo-module **/

import { Component, useState, useRef, useEffect, useExternalListener, onWillStart, onMounted, onPatched } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const GROUPS = ["Inputs", "Earnings", "Deductions", "Totals"];
const CAT_COLOR = { info: "#0E7490", earn: "#4F46E5", ded: "#B45309", total: "#059669" };
const OPSYM = { "+": "+", "-": "−", "*": "×", "/": "÷", "^": "^" };

// Searchable many2one combobox (substring filter on name+code+col, keyboard nav).
// Menu is position:fixed so it escapes the .pbcfg scroll-container clipping.
export class CfgCombo extends Component {
    static template = "pb_formula_studio.CfgCombo";
    static props = {
        options: { type: Array },
        value: { optional: true },
        placeholder: { type: String, optional: true },
        onSelect: { type: Function },
    };
    setup() {
        this.state = useState({ open: false, q: "", active: 0, menuStyle: "" });
        this.root = useRef("root");
        this.search = useRef("search");
        useExternalListener(window, "mousedown", (ev) => {
            if (this.state.open && this.root.el && !this.root.el.contains(ev.target)) this.close();
        });
        useExternalListener(window, "scroll", () => { if (this.state.open) this.close(); }, { capture: true });
        useEffect(() => { if (this.state.open && this.search.el) this.search.el.focus(); }, () => [this.state.open]);
    }
    _txt(o) { return ((o.col ? o.col + " " : "") + (o.name || "") + " " + (o.code || "")).toLowerCase(); }
    label(o) { return o.col ? (o.col + " · " + (o.name || "")) : (o.name || ""); }
    get selected() { return this.props.options.find((o) => o.id === this.props.value) || null; }
    get displayLabel() { const s = this.selected; return s ? this.label(s) : ""; }
    get filtered() {
        const q = (this.state.q || "").trim().toLowerCase();
        return q ? this.props.options.filter((o) => this._txt(o).includes(q)) : this.props.options;
    }
    toggle() {
        if (this.state.open) { this.close(); return; }
        const ctrl = this.root.el && this.root.el.querySelector(".cfg-combo-control");
        if (ctrl) {
            const r = ctrl.getBoundingClientRect();
            const menuH = 320, below = window.innerHeight - r.bottom;
            const top = (below < menuH && r.top > below) ? Math.max(8, r.top - menuH - 4) : (r.bottom + 4);
            this.state.menuStyle = `position:fixed; left:${Math.round(r.left)}px; top:${Math.round(top)}px; width:${Math.round(r.width)}px; max-height:${menuH}px;`;
        }
        this.state.open = true; this.state.q = ""; this.state.active = 0;
    }
    close() { this.state.open = false; }
    onInput(ev) { this.state.q = ev.target.value; this.state.active = 0; }
    pick(id) { this.props.onSelect(id); this.close(); }
    onKey(ev) {
        const f = this.filtered;
        if (ev.key === "ArrowDown") { ev.preventDefault(); this.state.active = Math.min(this.state.active + 1, f.length - 1); this._scroll(); }
        else if (ev.key === "ArrowUp") { ev.preventDefault(); this.state.active = Math.max(this.state.active - 1, 0); this._scroll(); }
        else if (ev.key === "Enter") { ev.preventDefault(); const o = f[this.state.active]; if (o) this.pick(o.id); }
        else if (ev.key === "Escape") { ev.preventDefault(); this.close(); }
    }
    _scroll() {
        requestAnimationFrame(() => {
            const el = document.querySelector(".cfg-combo-menu .cfg-combo-opt.active");
            if (el) el.scrollIntoView({ block: "nearest" });
        });
    }
}

export class PbFormulaStudio extends Component {
    static template = "pb_formula_studio.PbFormulaStudio";
    static components = { CfgCombo };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.state = useState({
            loaded: false,
            empty: false,
            view: "cards",
            config: {},
            configs: [],
            components: [],
            samples: [],
            preview: { sample_id: false, values: {} },
            selectedId: null,
            arrowsOn: true,
            formulaShort: false,
            flowOpen: false,
            flowStack: [],
            flowZoom: null,
            aiOpen: false,
            aiMsgs: [],
            aiProposal: null,
            aiLlm: false,
            aiModel: "",
            wizardOpen: false,
            wizardStep: 1,
            wizardForm: { name: "", country_code: "VN", cycle_type: "regular", template: "vn_standard" },
            wizardTemplates: [],
            wizardBusy: false,
            configPickerOpen: false,
            confirmDel: null,
            // config settings surface
            settings: null,
            setDraft: {},
            settingsTab: "setup",
            cfgAdvOpen: false,
            settingsBusy: false,
            settingsError: "",
            // test & validate workbench
            test: { samples: [], inputComponents: [], currency: "" },
            testSampleId: null,
            testDetail: null,
            testGenOpen: false,
            testInputsOpen: false,
            randomCount: 3,
            randomMin: 5000000,
            randomMax: 50000000,
            testBusy: false,
            // inline component editor
            editMode: false,
            editScope: "simple",
            editId: null,
            draft: {},
            editBusy: false,
            liveValid: null,
            editError: "",
            advOpen: false,
            fieldMeta: {},
        });
        this.formulaRef = useRef("formulaInput");
        this._liveTimer = null;
        onWillStart(async () => {
            await this.load();
            try {
                const s = await this.orm.call("pb.formula.studio", "ai_status", []);
                this.state.aiLlm = s.llm; this.state.aiModel = s.model;
            } catch (e) { /* non-fatal */ }
            // arriving from the native list's "New" → jump straight into the guided wizard
            const a = this.props.action || {};
            if ((a.params && a.params.open_wizard) || (a.context && a.context.open_wizard)) {
                await this.openWizard();
            }
            // arriving from a config row → open that config's Settings surface
            const cfgId = (a.params && a.params.config_id) || (a.context && a.context.config_id);
            if (cfgId) {
                if (!this.state.config || this.state.config.id !== cfgId) await this.load(cfgId);
                if ((a.params && a.params.open_settings) || (a.context && a.context.open_settings)) {
                    await this.openSettings();
                }
            }
        });
        onMounted(() => { this._bindArrowEvents(); this.redrawArrows(); });
        onPatched(() => { this.redrawArrows(); requestAnimationFrame(() => { this.applyZoom(); this.applyInlineFit(); }); });
    }

    async load(configId) {
        const d = await this.orm.call("pb.formula.studio", "get_studio_data", [configId || false]);
        this.state.empty = d.empty;
        this.state.configs = d.configs || [];
        if (d.empty) { this.state.loaded = true; return; }
        this.state.config = d.config;
        this.state.components = d.components;
        this.state.samples = d.samples;
        this.state.preview = d.preview || { sample_id: false, values: {} };
        if (d.field_meta) this.state.fieldMeta = d.field_meta;
        if (!this.state.selectedId || !d.components.some(c => c.id === this.state.selectedId)) {
            const firstFormula = d.components.find(c => c.type === "formula") || d.components[0];
            this.state.selectedId = firstFormula ? firstFormula.id : null;
        }
        this.state.loaded = true;
    }

    // ---- selectors ----
    get selected() { return this.state.components.find(c => c.id === this.state.selectedId) || null; }
    byCol(col) { return this.state.components.find(c => c.col === col); }
    colToNum(col) { let n = 0; for (const ch of String(col || "").toUpperCase()) { const c = ch.charCodeAt(0) - 64; if (c < 1 || c > 26) return 0; n = n * 26 + c; } return n; }
    // Excel range start:end -> the existing component column letters within the span (sorted).
    expandRange(start, end) {
        const a = this.colToNum(start), b = this.colToNum(end);
        const lo = Math.min(a, b), hi = Math.max(a, b);
        return this.state.components
            .map(c => c.col)
            .filter(col => { const n = this.colToNum(col); return n >= lo && n <= hi; })
            .sort((x, y) => this.colToNum(x) - this.colToNum(y));
    }
    groupItems(g) { return this.state.components.filter(c => c.group === g); }
    get visibleGroups() { return GROUPS.filter(g => this.groupItems(g).length); }
    get sampleName() {
        const s = this.state.samples.find(s => s.id === this.state.preview.sample_id);
        return s ? s.name : "—";
    }
    selectComponent(id) {
        this.state.selectedId = id;
        // reveal the outcome row in the live preview so the output arrow latches to it
        requestAnimationFrame(() => {
            const comp = this.state.components.find(x => x.id === id);
            if (comp) { const row = document.querySelector(`.pbfs-test .tp-row[data-col="${comp.col}"]`); if (row) row.scrollIntoView({ block: "nearest" }); }
            this.drawArrows();
        });
    }
    setView(v) { this.state.view = v; }

    // ---- formatting ----
    vnd(n) {
        if (n === null || n === undefined || isNaN(n)) return "—";
        const cur = this.state.config.currency || "₫";
        return cur + Math.round(n).toLocaleString("en-US");
    }
    previewVal(col) {
        const v = this.state.preview.values[col];
        return (v === undefined) ? "—" : this.vnd(v);
    }
    stageCls() { return { draft: "draft", testing: "testing", validated: "validated", active: "active", archived: "muted" }[this.state.config.state] || "muted"; }
    stageLabel() { return { draft: "Draft", testing: "Testing", validated: "Validated", active: "Active", archived: "Archived" }[this.state.config.state] || this.state.config.state; }
    nextLabel() { return { draft: "Start testing", testing: "Validate", validated: "Activate", active: "Active" }[this.state.config.state] || "Advance"; }
    isDeduction(c) { return c.group === "Deductions"; }
    ring(score) { const C = 2 * Math.PI * 19; return { dash: C, offset: C * (1 - (score || 0) / 100) }; }
    catKey(group) { return { Inputs: "info", Earnings: "earn", Deductions: "ded", Totals: "total" }[group] || "earn"; }
    colOf(c) { return c ? CAT_COLOR[this.catKey(c.group)] : "#4F46E5"; }

    // ---- dependency highlighting ----
    depColsOf(c) {
        if (!c || c.type !== "formula" || !c.excel_formula) return [];
        const out = [];
        const add = (col) => { if (this.byCol(col) && !out.includes(col)) out.push(col); };
        // expand A#:B# ranges first, blanking them so endpoints aren't re-counted as plain refs
        const rest = c.excel_formula.replace(/([A-Za-z]+)\d+:([A-Za-z]+)\d+/g, (full, s, e) => {
            this.expandRange(s.toUpperCase(), e.toUpperCase()).forEach(add); return " ";
        });
        (rest.match(/[A-Za-z]+\d+/g) || []).forEach(x => add(x.replace(/\d+$/, "").toUpperCase()));
        return out;
    }
    isDep(col) { return this.depColsOf(this.selected).includes(col); }
    isOutcome(col) { return this.selected && this.selected.col === col; }
    depStyle(c) { return this.isDep(c.col) ? ("--depc:" + this.colOf(c)) : ""; }

    // ---- formula chips (IF / function aware) ----
    setFormulaForm(short) { this.state.formulaShort = short; }

    // ---- inline component editor ----
    get editing() { return this.state.editMode && this.selected && this.selected.id === this.state.editId; }
    get draftType() { return this.state.draft.column_type || "formula"; }

    async enterEdit(id) {
        const rid = id || this.state.selectedId;
        if (!rid) return;
        const d = await this.orm.call("pb.formula.studio", "get_component_edit", [rid]);
        if (!d || !d.ok) { this.notif.add("Could not open the component.", { type: "warning" }); return; }
        delete d.ok;
        this.state.draft = d;
        this.state.editId = rid;
        this.state.editScope = "simple";
        this.state.advOpen = false;
        this.state.editError = "";
        this.state.editMode = true;
        this.state.liveValid = d.column_type === "formula"
            ? { valid: !!this.selected?.is_valid, message: this.selected?.validation_message || "" }
            : null;
    }
    cancelEdit() {
        this.state.editMode = false;
        this.state.editId = null;
        this.state.draft = {};
        this.state.liveValid = null;
        this.state.editError = "";
        if (this._liveTimer) { clearTimeout(this._liveTimer); this._liveTimer = null; }
    }
    setEditScope(scope) { this.state.editScope = scope; }
    toggleAdvanced() { this.state.advOpen = !this.state.advOpen; }
    setDraftField(field, ev) {
        const t = ev.target;
        let v = t.type === "checkbox" ? t.checked : t.value;
        if (t.type === "number") v = v === "" ? 0 : parseFloat(v);
        this.state.draft[field] = v;
    }
    setDraftType(type) {
        this.state.draft.column_type = type;
        if (type === "formula") this.scheduleLiveValidate();
        else this.state.liveValid = null;
    }

    // formula builder
    get paletteColumns() { return this.state.components.filter(c => c.id !== this.state.editId); }
    get paletteOps() { return [{ t: "+", g: "+" }, { t: "-", g: "−" }, { t: "*", g: "×" }, { t: "/", g: "÷" }, { t: "(", g: "(" }, { t: ")", g: ")" }]; }
    get paletteFns() { return ["IF", "SUM", "ROUND", "MIN", "MAX", "AND", "OR"]; }
    get draftChips() { return this.chips(this.state.draft.excel_formula || ""); }

    insertToken(text) {
        const inp = this.formulaRef.el;
        const cur = this.state.draft.excel_formula || "";
        let start = cur.length, end = cur.length;
        if (inp) { start = inp.selectionStart ?? cur.length; end = inp.selectionEnd ?? start; }
        const next = cur.slice(0, start) + text + cur.slice(end);
        this.state.draft.excel_formula = next;
        const caret = start + text.length;
        requestAnimationFrame(() => { if (this.formulaRef.el) { this.formulaRef.el.focus(); this.formulaRef.el.setSelectionRange(caret, caret); } });
        this.scheduleLiveValidate();
    }
    onFormulaInput(ev) {
        this.state.draft.excel_formula = ev.target.value;
        this.scheduleLiveValidate();
    }
    scheduleLiveValidate() {
        if (this._liveTimer) clearTimeout(this._liveTimer);
        this._liveTimer = setTimeout(() => this.runLiveValidate(), 260);
    }
    async runLiveValidate() {
        if (this.draftType !== "formula") { this.state.liveValid = null; return; }
        const f = this.state.draft.excel_formula || "";
        try {
            const r = await this.orm.call("pb.formula.studio", "validate_formula_live",
                [this.state.config.id, f, this.state.editId]);
            this.state.liveValid = { valid: r.valid, message: r.message };
        } catch (e) { /* non-fatal */ }
    }
    async saveComponent() {
        if (this.state.editBusy) return;
        this.state.editBusy = true;
        this.state.editError = "";
        try {
            const r = await this.orm.call("pb.formula.studio", "save_component",
                [this.state.editId, this.state.draft]);
            if (!r || !r.ok) {
                const msg = (r && r.msg) ? r.msg : "Could not save component";
                this.notif.add(msg, { type: "warning" });
                this.state.editError = msg;
                if (this.draftType === "formula") this.state.liveValid = { valid: false, message: msg };
                return;
            }
            this.notif.add("Component saved", { type: "success" });
            const cid = this.state.config.id;
            this.cancelEdit();
            await this.load(cid);
        } finally { this.state.editBusy = false; }
    }

    chips(formula) {
        if (!formula) return [{ kind: "src", text: "From contract / import" }];
        const re = /("[^"]*")|([A-Za-z_]+)(?=\()|([A-Za-z]+\d+:[A-Za-z]+\d+)|([A-Za-z]+\d+)|(\d+\.?\d*)|([+\-*/^])|([()])|(,)|(<=|>=|<>|[<>=])/g;
        const out = []; let m; const f = formula.replace(/^=/, "");
        while ((m = re.exec(f))) {
            if (m[1]) out.push({ kind: "num", text: m[1] });
            else if (m[2]) out.push({ kind: "func", text: m[2].toUpperCase() });
            else if (m[3]) {
                const [s, e] = m[3].split(":");
                const sc = s.replace(/\d+$/, "").toUpperCase(), ec = e.replace(/\d+$/, "").toUpperCase();
                const cols = this.expandRange(sc, ec);
                out.push({
                    kind: "range", start: sc, end: ec, count: cols.length,
                    startName: (this.byCol(sc) || {}).name || sc,
                    endName: (this.byCol(ec) || {}).name || ec,
                    names: cols.map(col => (this.byCol(col) || {}).name || col),
                });
            }
            else if (m[4]) { const col = m[4].replace(/\d+$/, "").toUpperCase(); const r = this.byCol(col); out.push({ kind: "ref", col, text: r ? r.name : col }); }
            else if (m[5]) out.push({ kind: "num", text: (+m[5]).toLocaleString("en-US") });
            else if (m[6]) out.push({ kind: "op", text: OPSYM[m[6]] || m[6] });
            else if (m[7]) out.push({ kind: "paren", text: m[7] });
            else if (m[8]) out.push({ kind: "comma", text: "," });
            else if (m[9]) out.push({ kind: "op", text: m[9] });
        }
        return out;
    }

    // ---- tiny Excel-ish parser (client-side; no backend change) ----
    parseFormula(formula) {
        const toks = [];
        const re = /\s*("[^"]*"|[A-Za-z_]+(?=\()|[A-Za-z]+\d+|\d+\.?\d*|<=|>=|<>|[-+*/^&(),:<>=])/g;
        let m; const f = (formula || "").replace(/^=/, "");
        while ((m = re.exec(f))) toks.push(m[1]);
        let p = 0;
        const peek = () => toks[p];
        const next = () => toks[p++];
        const parseExpr = () => parseCmp();
        const parseCmp = () => { let l = parseAdd(); while (["<", ">", "<=", ">=", "<>", "="].includes(peek())) { const op = next(); l = { t: "cmp", op, l, r: parseAdd() }; } return l; };
        const parseAdd = () => { let l = parseMul(); while (["+", "-"].includes(peek())) { const op = next(); l = { t: "op", op, l, r: parseMul() }; } return l; };
        const parseMul = () => { let l = parseUnary(); while (["*", "/"].includes(peek())) { const op = next(); l = { t: "op", op, l, r: parseUnary() }; } return l; };
        const parseUnary = () => { if (peek() === "-") { next(); return { t: "op", op: "-", l: { t: "num", v: 0 }, r: parseUnary() }; } return parsePrimary(); };
        const parsePrimary = () => {
            const tk = peek();
            // never consume a delimiter as a value (keeps IF arg lists intact)
            if (tk === undefined || tk === "," || tk === ")") return { t: "num", v: 0 };
            if (tk === "(") { next(); const e = parseExpr(); if (peek() === ")") next(); return e; }
            if (tk[0] === '"') { next(); return { t: "str", v: tk.slice(1, -1) }; }
            if (/^[A-Za-z]+\d+$/.test(tk)) {
                next(); const col = tk.replace(/\d+$/, "").toUpperCase();
                if (peek() === ":" && /^[A-Za-z]+\d+$/.test(toks[p + 1] || "")) {
                    next(); const end = next().replace(/\d+$/, "").toUpperCase();
                    return { t: "range", start: col, end };
                }
                return { t: "ref", col };
            }
            if (/^\d/.test(tk)) { next(); return { t: "num", v: parseFloat(tk) }; }
            if (/^[A-Za-z_]+$/.test(tk)) {
                const name = next().toUpperCase(); const args = [];
                if (peek() === "(") { next(); if (peek() !== ")") { args.push(parseExpr()); while (peek() === ",") { next(); args.push(parseExpr()); } } if (peek() === ")") next(); }
                return { t: "fn", name, args };
            }
            next(); return { t: "num", v: 0 };
        };
        try { return parseExpr(); } catch (e) { return null; }
    }
    evalNode(a) {
        try {
            if (!a) return 0;
            if (a.t === "num") return a.v;
            if (a.t === "str") return 0;
            if (a.t === "ref") return this.state.preview.values[a.col] || 0;
            if (a.t === "op") { const l = this.evalNode(a.l), r = this.evalNode(a.r); return a.op === "+" ? l + r : a.op === "-" ? l - r : a.op === "*" ? l * r : a.op === "/" ? (r ? l / r : 0) : a.op === "^" ? Math.pow(l, r) : 0; }
            if (a.t === "cmp") { const l = this.evalNode(a.l), r = this.evalNode(a.r), o = a.op; return (o === ">" ? l > r : o === "<" ? l < r : o === ">=" ? l >= r : o === "<=" ? l <= r : o === "<>" ? l !== r : l === r) ? 1 : 0; }
            if (a.t === "range") return this.expandRange(a.start, a.end).reduce((s, col) => s + (this.state.preview.values[col] || 0), 0);
            if (a.t === "fn") {
                const g = (a.args || []).flatMap(x => x.t === "range" ? this.expandRange(x.start, x.end).map(col => ({ t: "ref", col })) : [x]);
                const n = a.name;
                if (n === "IF") return this.evalNode(g[0]) ? this.evalNode(g[1]) : this.evalNode(g[2] || { t: "num", v: 0 });
                if (n === "SUM") return g.reduce((s, x) => s + this.evalNode(x), 0);
                if (n === "MAX") return Math.max(...g.map(x => this.evalNode(x)));
                if (n === "MIN") return Math.min(...g.map(x => this.evalNode(x)));
                if (n === "ROUND") { const v = this.evalNode(g[0]), d = g[1] ? this.evalNode(g[1]) : 0, f = Math.pow(10, d); return Math.round(v * f) / f; }
                if (n === "IFERROR") { const v = this.evalNode(g[0]); return isFinite(v) ? v : this.evalNode(g[1] || { t: "num", v: 0 }); }
                return this.evalNode(g[0] || { t: "num", v: 0 });
            }
            return 0;
        } catch (e) { return 0; }
    }
    fmtNum(v) { return (Number.isInteger(v) ? v.toString() : String(v)); }

    // ---- flowchart model (result at bottom, leaves at top) ----
    dnode(a) {
        if (!a) return { kind: "num", label: "?", value: 0, children: [] };
        if (a.t === "num") return { kind: "num", label: this.fmtNum(a.v), value: a.v, children: [] };
        if (a.t === "str") return { kind: "num", label: '"' + a.v + '"', value: 0, children: [] };
        if (a.t === "ref") { const c = this.byCol(a.col) || {}; return { kind: "ref", col: a.col, label: c.name || a.col, sub: "Col " + a.col, value: this.state.preview.values[a.col], formula: c.type === "formula", children: [] }; }
        if (a.t === "op") return { kind: "op", label: OPSYM[a.op] || a.op, value: this.evalNode(a), children: [this.dnode(a.l), this.dnode(a.r)] };
        if (a.t === "cmp") return { kind: "op", label: a.op, value: this.evalNode(a), children: [this.dnode(a.l), this.dnode(a.r)] };
        if (a.t === "range") { const cols = this.expandRange(a.start, a.end); return { kind: "fn", label: a.start + ":" + a.end, value: this.evalNode(a), children: cols.map(col => this.dnode({ t: "ref", col })) }; }
        if (a.t === "fn") {
            if (a.name === "IF") { const g = a.args; return { kind: "if", label: "IF", value: this.evalNode(a), children: [this.dnode(g[0]), this.dnode(g[1] || { t: "num", v: 0 }), this.dnode(g[2] || { t: "num", v: 0 })] }; }
            const kids = (a.args || []).flatMap(x => x.t === "range" ? this.expandRange(x.start, x.end).map(col => this.dnode({ t: "ref", col })) : [this.dnode(x)]);
            return { kind: "fn", label: a.name, value: this.evalNode(a), children: kids };
        }
        return { kind: "num", label: "?", value: 0, children: [] };
    }
    nodeColor(n) {
        if (n.kind === "ref") { const c = this.byCol(n.col); return CAT_COLOR[this.catKey(c ? c.group : "Earnings")]; }
        if (n.kind === "num") return "#64748B";
        if (n.kind === "if") return "#B45309";
        if (n.kind === "result") return "#312E81";
        return "#4F46E5";
    }
    fmtNode(n) { return n.kind === "num" ? n.label : this.vnd(n.value); }
    buildFlow(comp) {
        if (!comp || comp.type !== "formula") return null;
        const ast = this.parseFormula(comp.excel_formula);
        const root = { kind: "result", label: comp.name, col: comp.col, value: this.evalNode(ast), children: [this.dnode(ast)] };
        const slotW = 188, boxH = 52, diaH = 92, levelGap = 124, padX = 28, padY = 72;
        let leaf = 0, maxDepth = 0;
        const place = (n, depth) => {
            n.depth = depth; if (depth > maxDepth) maxDepth = depth;
            if (!n.children || !n.children.length) { n.x = leaf * slotW + slotW / 2 + padX; leaf++; }
            else { n.children.forEach(c => place(c, depth + 1)); n.x = n.children.reduce((s, c) => s + c.x, 0) / n.children.length; }
        };
        place(root, 0);
        const width = Math.max(leaf * slotW + padX * 2, 360);
        const height = (maxDepth + 1) * levelGap + padY * 2;
        const yOf = n => (maxDepth - n.depth) * levelGap + padY + (n.kind === "if" ? 20 : 26);
        const nodes = [], edges = [], labels = [];
        let idc = 0;
        const OPCLS = { "+": "op-add", "−": "op-sub", "×": "op-mul", "÷": "op-div", "%": "op-pct", "^": "op-pow",
            "=": "op-cmp", "<": "op-cmp", ">": "op-cmp", "<=": "op-cmp", ">=": "op-cmp", "<>": "op-cmp" };
        const collect = (n) => {
            n.y = yOf(n); n._id = "n" + (idc++);
            nodes.push({ id: n._id, x: n.x, y: n.y, kind: n.kind, label: n.label, value: this.fmtNode(n), sub: n.sub || "", color: this.nodeColor(n), ref: n.col, formula: !!n.formula, opCls: (n.kind === "op" ? (OPCLS[n.label] || "op-mul") : "") });
            (n.children || []).forEach(collect);
        };
        collect(root);
        const eWalk = (n) => {
            const ph = (n.kind === "if" ? diaH : boxH);
            (n.children || []).forEach((c, ci) => {
                const chh = (c.kind === "if" ? diaH : boxH);
                const ay = c.y + chh / 2, by = n.y - ph / 2, ax = c.x, bx = n.x;
                const d = `M ${ax} ${ay} C ${ax} ${(ay + by) / 2} ${bx} ${(ay + by) / 2} ${bx} ${by}`;
                edges.push({ d, color: this.nodeColor(c) });
                if (n.kind === "if") { const lab = ci === 0 ? "if" : (ci === 1 ? "Yes" : "No"); labels.push({ text: lab, cls: ci === 1 ? "yes" : (ci === 2 ? "no" : ""), x: (ax + bx) / 2, y: (ay + by) / 2 }); }
                eWalk(c);
            });
        };
        eWalk(root);
        return { nodes, edges, labels, width, height };
    }
    get inlineFlow() { return this.buildFlow(this.selected); }
    get modalComp() { const col = this.state.flowStack[this.state.flowStack.length - 1]; return this.byCol(col); }
    get modalFlow() { return this.modalComp ? this.buildFlow(this.modalComp) : null; }
    get modalCrumbs() { return this.state.flowStack.map(c => ({ col: c, name: (this.byCol(c) || {}).name || c })); }

    openExpand() { if (this.selected && this.selected.type === "formula") { this.state.flowStack = [this.selected.col]; this.state.flowZoom = null; this.state.flowOpen = true; } }
    flowDrill(col) {
        if (!this.byCol(col)) return;
        this.state.flowZoom = null;
        if (this.state.flowOpen) {
            if (this.state.flowStack[this.state.flowStack.length - 1] !== col) this.state.flowStack = [...this.state.flowStack, col];
        } else { this.state.flowStack = [col]; this.state.flowOpen = true; }
    }
    crumbTo(i) { this.state.flowZoom = null; this.state.flowStack = this.state.flowStack.slice(0, i + 1); }
    closeFlow() { this.state.flowOpen = false; }
    flowNodeClick(ev, n) { if (ev) ev.stopPropagation(); if (n && n.formula) this.flowDrill(n.ref); }

    // ---- expand-modal zoom (fit by default, +/- to blow up/down) ----
    _fitZoom() {
        const canvas = document.querySelector(".fc-modal .fc-canvas");
        const flow = this.modalFlow;
        if (!canvas || !flow) return 1;
        const pad = 28;
        return Math.min((canvas.clientWidth - pad) / flow.width, (canvas.clientHeight - pad) / flow.height, 1.5);
    }
    applyZoom() {
        if (!this.state.flowOpen) return;
        const canvas = document.querySelector(".fc-modal .fc-canvas");
        const wrap = canvas && canvas.querySelector(".fc-zoomwrap");
        const stage = wrap && wrap.querySelector(".fc-stage");
        const flow = this.modalFlow;
        if (!canvas || !wrap || !stage || !flow) return;
        const fit = this._fitZoom();
        const z = (this.state.flowZoom != null ? this.state.flowZoom : fit);
        this._curZoom = z;
        stage.style.transformOrigin = "top left";
        stage.style.transform = "scale(" + z + ")";
        wrap.style.width = (flow.width * z) + "px";
        wrap.style.height = (flow.height * z) + "px";
        wrap.style.margin = "0 auto";        // centre horizontally; scrolls when zoomed in
        const lbl = document.querySelector(".fc-zoom .zlabel");
        if (lbl) lbl.textContent = Math.round(z * 100) + "%";
    }
    zoomIn() { this.state.flowZoom = (this._curZoom || this._fitZoom()) * 1.2; this.applyZoom(); }
    zoomOut() { this.state.flowZoom = Math.max(0.15, (this._curZoom || this._fitZoom()) / 1.2); this.applyZoom(); }
    zoomFit() { this.state.flowZoom = null; this.applyZoom(); }
    // inline flow always fits its window (Expand to see complex ones bigger)
    applyInlineFit() {
        const container = document.querySelector(".pbfs-editor .fc-inline");
        const wrap = container && container.querySelector(".fc-zoomwrap");
        const stage = wrap && wrap.querySelector(".fc-stage");
        const flow = this.inlineFlow;
        if (!container || !wrap || !stage || !flow) return;
        const pad = 18;
        const z = Math.min((container.clientWidth - pad) / flow.width, (container.clientHeight - pad) / flow.height, 1);
        stage.style.transformOrigin = "top left";
        stage.style.transform = "scale(" + z + ")";
        wrap.style.width = (flow.width * z) + "px";
        wrap.style.height = (flow.height * z) + "px";
    }

    // ---- dependency arrows (imperative SVG over the two left panes) ----
    toggleArrows() { this.state.arrowsOn = !this.state.arrowsOn; this.redrawArrows(); }
    redrawArrows() { requestAnimationFrame(() => requestAnimationFrame(() => this.drawArrows())); }
    _bindArrowEvents() {
        const ol = document.querySelector(".pbfs-outline");
        if (ol) ol.addEventListener("scroll", () => this.redrawArrows());
        const ed = document.querySelector(".pbfs-editor");
        if (ed) ed.addEventListener("scroll", () => this.redrawArrows());
        const pv = document.querySelector(".pbfs-test");
        if (pv) pv.addEventListener("scroll", () => this.redrawArrows());
        window.addEventListener("resize", () => this.redrawArrows());
    }
    scrollToCol(col) {
        const row = document.querySelector(`.pbfs-outline .ol-item[data-col="${col}"]`);
        if (!row) return;
        row.scrollIntoView({ behavior: "smooth", block: "center" });
        row.classList.add("pulse"); setTimeout(() => row.classList.remove("pulse"), 950);
    }
    _arrow(layer, sx, sy, tipx, ty, color, onClick, dur, clampPt) {
        const NS = "http://www.w3.org/2000/svg";
        const rtl = tipx < sx;                       // pointing left?
        const basex = tipx + (rtl ? 14 : -14);
        const dx = basex - sx, c1 = sx + dx * 0.45, c2 = sx + dx * 0.55;
        const d = `M ${sx} ${sy} C ${c1} ${sy} ${c2} ${ty} ${basex} ${ty}`;
        const p = document.createElementNS(NS, "path");
        p.setAttribute("d", d); p.setAttribute("fill", "none"); p.setAttribute("stroke", color);
        p.setAttribute("stroke-width", "2.6"); p.setAttribute("stroke-linecap", "round");
        p.style.pointerEvents = "stroke";
        if (onClick) { p.style.cursor = "pointer"; p.addEventListener("click", onClick); }
        layer.appendChild(p);
        const dot = document.createElementNS(NS, "circle");
        dot.setAttribute("r", "3.6"); dot.setAttribute("fill", color); dot.style.pointerEvents = "none";
        const am = document.createElementNS(NS, "animateMotion");
        am.setAttribute("dur", dur + "s"); am.setAttribute("repeatCount", "indefinite"); am.setAttribute("path", d);
        dot.appendChild(am); layer.appendChild(dot);
        const head = document.createElementNS(NS, "polygon");
        head.setAttribute("points", `${tipx},${ty} ${basex},${ty - 7} ${basex},${ty + 7}`);
        head.setAttribute("fill", color);
        if (onClick) { head.style.cursor = "pointer"; head.style.pointerEvents = "auto"; head.addEventListener("click", onClick); }
        layer.appendChild(head);
        if (clampPt) { const t = document.createElementNS(NS, "circle"); t.setAttribute("cx", clampPt[0]); t.setAttribute("cy", clampPt[1]); t.setAttribute("r", "4"); t.setAttribute("fill", color); layer.appendChild(t); }
    }
    drawArrows() {
        const layer = document.getElementById("pbfsArrows");
        const work = document.querySelector(".pbfs-work");
        if (!layer || !work) return;
        const card = document.querySelector(".pbfs-editor .ed-card");
        const outline = document.querySelector(".pbfs-outline");
        const editor = document.querySelector(".pbfs-editor");
        const preview = document.querySelector(".pbfs-test");
        layer.innerHTML = "";
        const wr = work.getBoundingClientRect();
        layer.setAttribute("width", wr.width); layer.setAttribute("height", wr.height);
        layer.style.width = wr.width + "px"; layer.style.height = wr.height + "px";
        const c = this.selected;
        if (!this.state.arrowsOn || !card || !outline || !editor || !c || c.type !== "formula") return;
        const deps = this.depColsOf(c);
        const cardR = card.getBoundingClientRect(), olR = outline.getBoundingClientRect(), edR = editor.getBoundingClientRect();
        // anchor arrowheads near the editor's vertical centre so they stay visible while scrolling
        const centerY = edR.top + edR.height / 2 - wr.top;
        const edTop = edR.top - wr.top + 34, edBot = edR.bottom - wr.top - 34;
        const gap = 34, n = deps.length;
        // ---- input arrows: dependency rows -> left edge of the card ----
        deps.forEach((col, i) => {
            const row = outline.querySelector(`.ol-item[data-col="${col}"]`);
            if (!row) return;
            const rr = row.getBoundingClientRect();
            let sy = rr.top + rr.height / 2 - wr.top;
            const bandTop = olR.top - wr.top + 8, bandBot = olR.bottom - wr.top - 8;
            const clamped = sy < bandTop || sy > bandBot;
            sy = Math.max(bandTop, Math.min(bandBot, sy));
            const sx = olR.right - wr.left - 6;
            const tipx = cardR.left - wr.left + 6;
            let ty = centerY - (n - 1) * gap / 2 + i * gap;
            ty = Math.max(edTop, Math.min(edBot, ty));
            const color = this.colOf(this.byCol(col));
            this._arrow(layer, sx, sy, tipx, ty, color, () => this.scrollToCol(col), (7.5 + i * 0.7), clamped ? [sx, sy] : null);
        });
        // ---- output arrow: right edge of the card -> outcome row in the live preview ----
        if (preview) {
            const outRow = preview.querySelector(`.tp-row[data-col="${c.col}"]`);
            const pvR = preview.getBoundingClientRect();
            const sx = cardR.right - wr.left + 4;
            const sy = Math.max(edTop, Math.min(edBot, centerY));
            const tipx = pvR.left - wr.left + 4;
            let ty = sy, clampedOut = false;
            if (outRow) {
                const orr = outRow.getBoundingClientRect();
                ty = orr.top + orr.height / 2 - wr.top;
                const pT = pvR.top - wr.top + 8, pB = pvR.bottom - wr.top - 8;
                clampedOut = ty < pT || ty > pB;
                ty = Math.max(pT, Math.min(pB, ty));
            }
            this._arrow(layer, sx, sy, tipx, ty, this.colOf(c), () => this.scrollToPreviewCol(c.col), 8.5, clampedOut ? [tipx, ty] : null);
        }
    }
    scrollToPreviewCol(col) {
        const row = document.querySelector(`.pbfs-test .tp-row[data-col="${col}"]`);
        if (!row) return;
        row.scrollIntoView({ behavior: "smooth", block: "center" });
        row.classList.add("pulse"); setTimeout(() => row.classList.remove("pulse"), 950);
    }

    // ---- sample switching ----
    async cycleSample() {
        if (this.state.samples.length < 2) return;
        const idx = this.state.samples.findIndex(s => s.id === this.state.preview.sample_id);
        const next = this.state.samples[(idx + 1) % this.state.samples.length];
        this.state.preview = await this.orm.call("pb.formula.studio", "compute_preview", [this.state.config.id, next.id]);
    }

    // ---- lifecycle ----
    async advance() {
        const r = await this.orm.call("pb.formula.studio", "advance", [this.state.config.id]);
        if (!r.ok) { this.notif.add(r.message || "Action blocked", { type: "warning" }); }
        else { this.notif.add("Now " + (r.state || ""), { type: "success" }); }
        await this.load(this.state.config.id);
    }
    async runValidate() {
        const r = await this.orm.call("pb.formula.studio", "validate", [this.state.config.id]);
        this.notif.add(r.ok ? "Validation complete" : (r.message || "Validation failed"), { type: r.ok ? "success" : "warning" });
        await this.load(this.state.config.id);
    }
    async runTests() {
        const r = await this.orm.call("pb.formula.studio", "run_tests", [this.state.config.id]);
        if (r.ok) this.notif.add(`${r.passed}/${r.total} tests passed`, { type: r.failed ? "warning" : "success" });
        else this.notif.add(r.message || "Test run failed", { type: "danger" });
        await this.load(this.state.config.id);
    }

    // ---- config settings surface ----
    async openSettings() {
        if (!this.state.config || !this.state.config.id) return;
        await this.loadSettings();
        this.state.settingsTab = "setup";
        this.state.cfgAdvOpen = false;
        this.state.settingsError = "";
        this.state.view = "settings";
    }
    async loadSettings() {
        const d = await this.orm.call("pb.formula.studio", "get_config_settings", [this.state.config.id]);
        if (!d || !d.ok) { this.notif.add("Could not load settings.", { type: "warning" }); return; }
        this.state.settings = d;
        this.state.setDraft = Object.assign({}, d.values);
    }
    setSettingsTab(tab) { this.state.settingsTab = tab; }
    toggleCfgAdv() { this.state.cfgAdvOpen = !this.state.cfgAdvOpen; }
    async generateSampleData() {
        const r = await this.orm.call("pb.formula.studio", "cfg_generate_sample_data", [this.state.config.id]);
        if (!r || !r.ok) { this.notif.add((r && r.msg) || "Could not generate sample", { type: "warning" }); return; }
        this.notif.add(r.notif || "Sample data generated", { type: "success" });
        if (r.settings && this.state.settings) { this.state.settings = r.settings; this.state.setDraft = Object.assign({}, r.settings.values); }
        await this.load(this.state.config.id);
    }
    // ---- Test & Validate workbench ----
    async openTest() {
        await this.loadTestData();
        this.state.view = "test";
    }
    async loadTestData(keepSel) {
        const d = await this.orm.call("pb.formula.studio", "get_test_data", [this.state.config.id]);
        if (!d || !d.ok) return;
        this.state.test = d;
        if (!keepSel || !d.samples.some(s => s.id === this.state.testSampleId)) {
            const first = d.samples[0];
            if (first) { await this.selectSample(first.id); } else { this.state.testSampleId = null; this.state.testDetail = null; }
        } else {
            await this.loadSampleDetail(this.state.testSampleId);
        }
    }
    async selectSample(id) { this.state.testSampleId = id; await this.loadSampleDetail(id); }
    async loadSampleDetail(id) {
        const d = await this.orm.call("pb.formula.studio", "get_sample_detail", [id]);
        this.state.testDetail = (d && d.ok) ? d : null;
    }
    get testSample() { return this.state.test.samples.find(s => s.id === this.state.testSampleId) || null; }
    tcell(v) { return (v === null || v === undefined || v === "") ? "—" : this.vnd(v); }
    toggleTestGen() { this.state.testGenOpen = !this.state.testGenOpen; }
    toggleTestInputs() { this.state.testInputsOpen = !this.state.testInputsOpen; }
    setRandomField(field, ev) { const v = parseFloat(ev.target.value); this.state[field] = isNaN(v) ? 0 : v; }
    onTestInput(code, ev) {
        const val = ev.target.value;
        if (this._testTimer) clearTimeout(this._testTimer);
        this._testTimer = setTimeout(async () => {
            const r = await this.orm.call("pb.formula.studio", "save_sample_inputs", [this.state.testSampleId, { [code]: val }]);
            if (r && r.ok) { this.state.testDetail = r; this._syncSampleVerdict(r); }
        }, 320);
    }
    _syncSampleVerdict(detail) {
        const s = this.state.test.samples.find(x => x.id === detail.id);
        if (s) { s.verdict = detail.verdict; s.has_expected = detail.has_expected; }
    }
    async addManualSample() {
        this.state.testGenOpen = false;
        const r = await this.orm.call("pb.formula.studio", "add_manual_sample", [this.state.config.id]);
        if (!r || !r.ok) { this.notif.add("Could not add sample", { type: "warning" }); return; }
        this.state.test.samples = r.samples;
        await this.selectSample(r.sample_id);
        this.state.testInputsOpen = true;  // manual samples are about editing inputs
    }
    async generateRandom() {
        this.state.testGenOpen = false;
        const r = await this.orm.call("pb.formula.studio", "generate_random_samples",
            [this.state.config.id, this.state.randomCount, this.state.randomMin, this.state.randomMax]);
        if (!r || !r.ok) { this.notif.add((r && r.msg) || "Could not generate", { type: "warning" }); return; }
        this.notif.add(`${this.state.randomCount} random samples added`, { type: "success" });
        this.state.test.samples = r.samples;
        const last = r.samples[r.samples.length - 1];
        if (last) await this.selectSample(last.id);
    }
    async generateFromWizard(source) {
        this.state.testGenOpen = false;
        const r = await this.orm.call("pb.formula.studio", "cfg_generate_wizard", [this.state.config.id, source]);
        if (r && r.ok && r.action) {
            this.action.doAction(r.action, { onClose: () => this.loadTestData(true) });
        }
    }
    async snapshotExpected() {
        const r = await this.orm.call("pb.formula.studio", "snapshot_expected", [this.state.testSampleId]);
        if (r && r.ok) { this.state.testDetail = r; this._syncSampleVerdict(r); this.notif.add("Baseline saved", { type: "success" }); }
    }
    async clearExpected() {
        const r = await this.orm.call("pb.formula.studio", "clear_expected", [this.state.testSampleId]);
        if (r && r.ok) { this.state.testDetail = r; this._syncSampleVerdict(r); }
    }
    async deleteSample(id) {
        const s = this.state.test.samples.find(x => x.id === id);
        if (!window.confirm(`Delete ${s ? s.name : "this sample"}?`)) return;
        const r = await this.orm.call("pb.formula.studio", "delete_sample", [id]);
        if (r && r.ok) {
            this.state.test.samples = r.samples;
            if (this.state.testSampleId === id) {
                const first = r.samples[0];
                if (first) await this.selectSample(first.id); else { this.state.testSampleId = null; this.state.testDetail = null; }
            }
        }
    }
    async renameSample(ev) {
        const name = ev.target.value;
        await this.orm.call("pb.formula.studio", "rename_sample", [this.state.testSampleId, name]);
        const s = this.state.test.samples.find(x => x.id === this.state.testSampleId);
        if (s) s.name = name;
    }
    async runAllTests() {
        const r = await this.orm.call("pb.formula.studio", "cfg_run_tests", [this.state.config.id]);
        this.notif.add((r && r.notif) || "Tests run", { type: "success" });
        await this.loadTestData(true);
    }

    get cfgState() { return (this.state.settings && this.state.settings.status.state) || "draft"; }
    cfgStageCls(stage) {
        const order = ["draft", "testing", "validated", "active"];
        if (this.cfgState === "archived") return "muted";
        const cur = order.indexOf(this.cfgState), i = order.indexOf(stage);
        return i < cur ? "done" : (i === cur ? "current" : "todo");
    }
    cfgMeta(key) { return (this.state.settings && this.state.settings.meta && this.state.settings.meta[key]) || []; }
    setCfgField(field, ev) {
        const t = ev.target;
        let v = t.type === "checkbox" ? t.checked : t.value;
        if (t.type === "number") v = v === "" ? 0 : parseFloat(v);
        this.state.setDraft[field] = v;
    }
    setCfgM2O(field, ev) { const v = ev.target.value; this.state.setDraft[field] = v ? parseInt(v) : false; }
    pickCfgM2O(field, id) { this.state.setDraft[field] = id || false; }
    cfgM2MHas(field, id) { return (this.state.setDraft[field] || []).includes(id); }
    toggleCfgM2M(field, id) {
        const cur = (this.state.setDraft[field] || []).slice();
        const i = cur.indexOf(id);
        if (i >= 0) cur.splice(i, 1); else cur.push(id);
        this.state.setDraft[field] = cur;
    }
    async saveSettings() {
        if (this.state.settingsBusy) return;
        this.state.settingsBusy = true;
        this.state.settingsError = "";
        try {
            const r = await this.orm.call("pb.formula.studio", "save_config_settings", [this.state.config.id, this.state.setDraft]);
            if (!r || !r.ok) {
                const msg = (r && r.msg) ? r.msg : "Could not save settings";
                this.state.settingsError = msg; this.notif.add(msg, { type: "warning" });
                return;
            }
            if (this.state.settings) this.state.settings.status = r.status;
            this.notif.add("Settings saved", { type: "success" });
            await this.load(this.state.config.id);   // sync top bar / score / name
        } finally { this.state.settingsBusy = false; }
    }
    revertSettings() {
        if (this.state.settings) this.state.setDraft = Object.assign({}, this.state.settings.values);
        this.state.settingsError = "";
    }
    async _cfgLifecycle(method, okMsg) {
        const r = await this.orm.call("pb.formula.studio", method, [this.state.config.id]);
        if (!r || !r.ok) { this.notif.add((r && r.msg) || "Action blocked", { type: "warning" }); }
        else { this.notif.add(r.notif || okMsg, { type: "success" }); }
        if (r && r.settings) { this.state.settings = r.settings; this.state.setDraft = Object.assign({}, r.settings.values); }
        else if (r && r.status && this.state.settings) { this.state.settings.status = r.status; }
        await this.load(this.state.config.id);
    }
    startTesting() { return this._cfgLifecycle("cfg_start_testing", "Testing started"); }
    validateCfg() { return this._cfgLifecycle("cfg_validate", "Validated"); }
    activateCfg() { return this._cfgLifecycle("cfg_activate", "Activated"); }
    setDraftCfg() { return this._cfgLifecycle("cfg_set_draft", "Back to draft"); }
    archiveCfg() { if (!window.confirm("Archive this configuration?")) return; return this._cfgLifecycle("cfg_archive", "Archived"); }
    regenerateFormulas() { return this._cfgLifecycle("cfg_regenerate_formulas", "Formulas regenerated"); }
    generateSamples() { return this._cfgLifecycle("cfg_generate_sample_data", "Sample data generated"); }
    runTestsCfg() { return this._cfgLifecycle("cfg_run_tests", "Tests run"); }
    async importExcelCfg() {
        const r = await this.orm.call("pb.formula.studio", "cfg_import_excel", [this.state.config.id]);
        if (r && r.ok && r.action) {
            this.action.doAction(r.action, { onClose: () => { this.loadSettings(); this.load(this.state.config.id); } });
        }
    }

    // ---- config picker ----
    toggleConfigPicker() { this.state.configPickerOpen = !this.state.configPickerOpen; }
    async pickConfig(id) { this.state.configPickerOpen = false; this.state.selectedId = null; await this.load(id); }
    async openConfigSettings(id, ev) {
        if (ev) ev.stopPropagation();
        this.state.configPickerOpen = false;
        if (id !== (this.state.config && this.state.config.id)) { this.state.selectedId = null; await this.load(id); }
        await this.openSettings();
    }

    // ---- PayAI ----
    openAI() { this.state.aiOpen = true; }
    closeAI() { this.state.aiOpen = false; }
    async aiAsk(text) {
        if (!text || !text.trim()) return;
        this.state.aiMsgs.push({ who: "you", text });
        this.state.aiProposal = null;
        const r = await this.orm.call("pb.formula.studio", "ai_propose", [this.state.config.id, text]);
        this.state.aiMsgs.push({ who: "ai", text: r.reply || "" });
        if (r.ok && r.kind === "formula") this.state.aiProposal = r;
        const inp = document.querySelector(".pbfs-ai-input input");
        if (inp) inp.value = "";
    }
    aiAskInput(ev) { if (ev.key === "Enter") this.aiAsk(ev.target.value); }
    aiAskChip(text) { this.aiAsk(text); }
    async applyProposal() {
        const p = this.state.aiProposal;
        if (!p) return;
        if (p.target_id) {
            const r = await this.orm.call("pb.formula.studio", "apply_ai_formula", [p.target_id, p.formula]);
            if (r.ok) { this.notif.add("Formula applied to " + (p.target_name || ""), { type: "success" }); }
            else { this.notif.add(r.msg || "Could not apply", { type: "warning" }); }
        } else {
            this.notif.add("That would create a new component — open the editor to confirm name & code.", { type: "info" });
        }
        this.state.aiProposal = null;
        this.state.aiOpen = false;
        await this.load(this.state.config.id);
    }
    discardProposal() { this.state.aiProposal = null; }

    // ---- guided first-setup wizard ----
    async openWizard() {
        this.state.configPickerOpen = false;
        this.state.wizardStep = 1;
        this.state.wizardForm = { name: "", country_code: "VN", cycle_type: "regular", template: "vn_standard" };
        if (!this.state.wizardTemplates.length) {
            this.state.wizardTemplates = await this.orm.call("pb.formula.studio", "wizard_templates", []);
        }
        this.state.wizardOpen = true;
    }
    closeWizard() { this.state.wizardOpen = false; }
    wizardSet(field, ev) { this.state.wizardForm[field] = ev.target.value; }
    pickTemplate(key) { this.state.wizardForm.template = key; }
    get wizardTpl() { return this.state.wizardTemplates.find(t => t.key === this.state.wizardForm.template) || {}; }
    wizardBack() { if (this.state.wizardStep > 1) this.state.wizardStep--; }
    wizardNext() {
        if (this.state.wizardStep === 1 && !this.state.wizardForm.name.trim()) { this.notif.add("Give the configuration a name first.", { type: "warning" }); return; }
        if (this.state.wizardStep < 5) this.state.wizardStep++;
    }
    async wizardCreate() {
        if (this.state.wizardBusy) return;
        this.state.wizardBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "create_config", [this.state.wizardForm]);
            if (r.ok) {
                this.notif.add(`Created “${this.state.wizardForm.name}” with ${r.rule_count} components`, { type: "success" });
                this.state.wizardOpen = false; this.state.selectedId = null; await this.load(r.config_id);
            } else { this.notif.add("Could not create configuration", { type: "danger" }); }
        } finally { this.state.wizardBusy = false; }
    }
    async importExcel() {
        if (!this.state.wizardForm.name.trim()) { this.notif.add("Give the configuration a name first.", { type: "warning" }); this.state.wizardStep = 1; return; }
        if (this.state.wizardBusy) return;
        this.state.wizardBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "create_config", [{ ...this.state.wizardForm, template: "blank" }]);
            if (!r.ok) { this.notif.add("Could not create configuration", { type: "danger" }); return; }
            this.state.wizardOpen = false;
            this.action.doAction(
                { type: "ir.actions.act_window", name: "Import from Excel", res_model: "hr.formula.multisheet.import.wizard",
                  view_mode: "form", views: [[false, "form"]], target: "new", context: { default_config_id: r.config_id } },
                { onClose: () => this.load(r.config_id) });
        } finally { this.state.wizardBusy = false; }
    }

    // ----- "finish setup" resume CTAs (shown when the loaded config is empty) -----
    importExcelInto() {
        const cid = this.state.config.id;
        if (!cid) return;
        this.action.doAction(
            { type: "ir.actions.act_window", name: "Import from Excel", res_model: "hr.formula.multisheet.import.wizard",
              view_mode: "form", views: [[false, "form"]], target: "new", context: { default_config_id: cid } },
            { onClose: () => this.load(cid) });
    }
    async applyStarter(key) {
        if (this.state.wizardBusy) return;
        this.state.wizardBusy = true;
        try {
            const cid = this.state.config.id;
            const r = await this.orm.call("pb.formula.studio", "apply_starter", [cid, key || "vn_standard"]);
            if (r.ok) { this.notif.add(`Added ${r.rule_count} components`, { type: "success" }); await this.load(cid); }
            else if (r.error === "not_empty") { this.notif.add("This configuration already has components.", { type: "warning" }); }
            else { this.notif.add("Could not apply the starter.", { type: "danger" }); }
        } finally { this.state.wizardBusy = false; }
    }
    async addComponentQuick() {
        if (this.state.wizardBusy) return;
        this.state.wizardBusy = true;
        try {
            const cid = this.state.config.id;
            const r = await this.orm.call("pb.formula.studio", "add_component", [cid, {}]);
            if (r.ok) { await this.load(cid); this.state.selectedId = r.rule_id; }
            else { this.notif.add("Could not add a component.", { type: "danger" }); }
        } finally { this.state.wizardBusy = false; }
    }
    // ----- delete a whole configuration (picker trash + build-panel discard) -----
    askDeleteConfig(cfg, ev) {
        if (ev) ev.stopPropagation();
        if (!cfg || !cfg.id) return;
        this.state.confirmDel = {
            id: cfg.id,
            name: cfg.name || "this configuration",
            count: (cfg.rule_count != null ? cfg.rule_count : (cfg.count || 0)),
            state: cfg.state || "draft",
        };
    }
    cancelDeleteConfig() { this.state.confirmDel = null; }
    async confirmDeleteConfig() {
        const d = this.state.confirmDel;
        if (!d) return;
        const wasCurrent = d.id === this.state.config.id;
        const r = await this.orm.call("pb.formula.studio", "delete_config", [d.id]);
        if (!r || !r.ok) {
            this.notif.add(r && r.msg ? r.msg : "Could not delete configuration", { type: "warning" });
            this.state.confirmDel = null;
            return;
        }
        this.notif.add(`Deleted “${d.name}”`, { type: "success" });
        this.state.confirmDel = null;
        this.state.configPickerOpen = false;
        this.state.selectedId = null;
        await this.load(wasCurrent ? undefined : this.state.config.id);
    }
    discardConfig() {
        const c = this.state.config;
        if (c && c.id) this.askDeleteConfig({ id: c.id, name: c.name, rule_count: c.rule_count, state: c.state });
    }

    // ----- component management (available in the normal 3-pane too) -----
    openComponentForm(id) {
        const rid = id || this.state.selectedId;
        const cid = this.state.config.id;
        if (!rid) return;
        this.action.doAction(
            { type: "ir.actions.act_window", name: "Edit component", res_model: "hr.formula.rule",
              res_id: rid, views: [[false, "form"]], target: "new" },
            { onClose: () => this.load(cid) });
    }
    async deleteComponent(id) {
        const rid = id || this.state.selectedId;
        const cid = this.state.config.id;
        if (!rid) return;
        const comp = this.state.components.find(c => c.id === rid);
        if (!window.confirm(`Delete component “${comp ? comp.name : rid}”?`)) return;
        await this.orm.call("pb.formula.studio", "delete_component", [rid]);
        this.notif.add("Component deleted", { type: "success" });
        if (this.state.selectedId === rid) this.state.selectedId = null;
        await this.load(cid);
    }
}

registry.category("actions").add("pb_formula_studio", PbFormulaStudio);
