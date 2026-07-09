/** @odoo-module **/

import { Component, useState, useRef, useEffect, useExternalListener, onWillStart, onMounted, onPatched } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { GridStudio } from "./grid/grid_studio";
import { MappingCanvas } from "./mapping/mapping_canvas";

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
    static components = { CfgCombo, GridStudio, MappingCanvas };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.state = useState({
            loaded: false,
            empty: false,
            canEdit: true,
            view: "cards",
            config: {},
            configs: [],
            components: [],
            samples: [],
            scenarios: [],              // F14 — what-if overlays per component
            preview: { sample_id: false, values: {} },
            // dependency-graph payload from get_intelligence (Feature 1); the
            // grid-highlight primitives (Feature 2) walk state.graph.edges.
            graph: { nodes: [], edges: [], execution_order: [], unused: [], cycles: [] },
            insightsOpen: false,        // T1.4: downstream list expander
            cycleHighlight: [],         // T1.6: cols to flash in the outline
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
            // T5.3 — Explain modal (progressive: deterministic floor first, LLM replaces)
            explainOpen: false,
            explainLang: "en",
            explainText: "",
            explainSource: "deterministic",
            explainBusy: false,
            // F7 — version history rail
            historyOpen: false,
            historyBusy: false,
            historyData: null,       // {code, name, config_name, current, versions:[]}
            historyDiffSeq: null,    // which version's diff-vs-current is expanded
            historyDiffRuns: null,
            // F8 — simulate-before-activate
            simOpen: false,
            simBusy: false,
            simProgress: 0,          // 0..100 during the chunked drive
            simResult: null,         // folded distribution payload
            simId: null,
            // F13 — Problems rail + lint + rename-refactor
            probOpen: false,
            probData: null,          // {ok, count, counts, problems:[]}
            probBusy: false,
            renameId: null,          // rule being renamed inline on the card
            renameVal: "",
            renameBusy: false,
            renameErr: "",
            // F11 — rate (bracket) tables
            rateTables: [],
            ratesOpen: false,
            rateEdit: null,          // {id, code, name, note, brackets:[{lower, rate}]}
            rateBusy: false,
            rateErr: "",
            ratePreviewIncome: 40000000,
            ratePreview: null,       // {value, result, compiled}
            // F10 — mapping canvas (multi-adapter)
            mapOpen: false,
            mapBusy: false,
            mapMode: "cycle",        // cycle | api
            mapContextId: null,      // adapter context (e.g. connector id for api)
            mapDismissed: [],        // client-side-dismissed suggestion wire ids
            mapData: null,           // {ok, left, right, wires, left_title, right_title, supports_suggest, contexts, ...}
            // F9 — payslip studio
            psOpen: false,
            psBusy: false,
            psData: null,            // {ok, config, sections, tray, samples, sample_id, colors, can_edit}
            psLang: "en",            // en | vi label lens
            psDragId: null,          // rule id currently dragged
            psOverComp: null,        // rule id being hovered during a drag (insert-before)
            psOverZone: null,        // section id or 'tray' currently hovered
            psEditSec: null,         // section id whose title is inline-editing
            // F12 — raw-Excel mode on the card (per-user preference)
            rawMode: (typeof localStorage !== "undefined" && localStorage.getItem("pbfs_raw_mode") === "1"),
            rawBuffer: "",
            rawFor: null,            // component id the current buffer belongs to
            rawValid: null,          // {valid, message} from validate_formula_live
            rawDirty: false,
            rawBusy: false,
            // B8 — what-if sliders + cost projection
            whatifOpen: false,
            whatifBusy: false,
            whatifData: null,        // {components, currency}
            whatifTarget: null,      // selected constant code
            whatifBase: 0,           // its current value
            whatifMult: 1,           // slider 0..2 (×)
            whatifResult: null,      // sim result (sampled or full)
            whatifHeadlineName: "",
            // B1 — execution replay
            replayOpen: false,
            replayBusy: false,
            replayData: null,        // {seeded, steps, config, samples, sample_id}
            replayStep: -1,          // -1 = only inputs seeded; k = steps[0..k] computed
            replayPlaying: false,
            // F15 — comments & annotations
            notesOpen: false,
            notesBusy: false,
            notesData: null,         // {ok, notes:[], open_reviews}
            noteDraft: "",
            noteReview: false,
            aiModel: "",
            wizardOpen: false,
            wizardStep: 1,
            wizardForm: { name: "", country_code: "VN", cycle_type: "regular", template: "vn_standard" },
            wizardTemplates: [],
            wizardBusy: false,
            configPickerOpen: false,
            confirmDel: null,
            // responsive header: Tools ▾ overflow (visible ≤1280 via CSS)
            moreOpen: false,
            // grid workbench: slide-in drawers over the full-width spreadsheet
            outlineDrawer: false,
            previewDrawer: false,
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
            testInputsOpen: true,
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
        this.testFileRef = useRef("testFile");
        this.rawEditorRef = useRef("rawEditor");
        this._rawNeedsSeed = false;
        this._liveTimer = null;
        // Tools ▾ closes on any outside click; Esc closes the grid drawers.
        // Esc goes through the hotkey service — a plain window keydown listener
        // never fires because the service intercepts Escape at capture phase.
        useExternalListener(window, "mousedown", (ev) => {
            if (this.state.moreOpen && !ev.target.closest(".pbfs-more")) {
                this.state.moreOpen = false;
            }
        });
        useHotkey("escape", () => {
            if (this.state.outlineDrawer || this.state.previewDrawer) {
                this.closeDrawers();
            } else if (this.state.moreOpen) {
                this.state.moreOpen = false;
            }
        }, { global: true, bypassEditableProtection: false });
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
        onPatched(() => {
            this.redrawArrows();
            // F12 — seed the raw textarea imperatively (uncontrolled, so the caret
            // never jumps mid-edit); only when a re-seed was requested.
            if (this._rawNeedsSeed && this.rawEditorRef.el) {
                this.rawEditorRef.el.value = this.state.rawBuffer;
                this._rawNeedsSeed = false;
            }
            requestAnimationFrame(() => { this.applyZoom(); this.applyInlineFit(); });
        });
    }

    async load(configId) {
        const d = await this.orm.call("pb.formula.studio", "get_studio_data", [configId || false]);
        this.state.empty = d.empty;
        this.state.configs = d.configs || [];
        this.state.canEdit = d.can_edit !== false;
        if (d.empty) { this.state.loaded = true; return; }
        this.state.config = d.config;
        this.state.components = d.components;
        this.state.samples = d.samples;
        this.state.scenarios = d.scenarios || [];
        this.state.rateTables = d.rate_tables || [];
        this.state.preview = d.preview || { sample_id: false, values: {} };
        if (d.field_meta) this.state.fieldMeta = d.field_meta;
        if (!this.state.selectedId || !d.components.some(c => c.id === this.state.selectedId)) {
            const firstFormula = d.components.find(c => c.type === "formula") || d.components[0];
            this.state.selectedId = firstFormula ? firstFormula.id : null;
        }
        // Dependency graph in a second call — keeps get_studio_data untouched and
        // the client BFS helpers (upstreamOf/downstreamOf) run off state.graph.edges.
        try {
            this.state.graph = await this.orm.call("pb.formula.studio", "get_intelligence", [d.config.id]);
        } catch (e) {
            this.state.graph = { nodes: [], edges: [], execution_order: [], unused: [], cycles: [] };
        }
        this.state.cycleHighlight = [];
        // F13 — problems tally in a third call (pure metadata; feeds the
        // toolbar badge and the Problems rail). Non-fatal if it fails.
        try {
            this.state.probData = await this.orm.call("pb.formula.studio", "get_problems", [d.config.id]);
        } catch (e) {
            this.state.probData = null;
        }
        this.state.loaded = true;
    }

    // ---- dependency-graph BFS (pure; over state.graph.edges [fromCol,toCol]) ----
    // edges point in data-flow direction (dependency -> consumer), so a column's
    // upstream = follow edges backward, downstream = follow edges forward.
    _bfsGraph(startCol, dir) {
        const edges = (this.state.graph && this.state.graph.edges) || [];
        const seen = new Set();
        const queue = [startCol];
        const out = [];
        while (queue.length) {
            const cur = queue.shift();
            for (const e of edges) {
                const from = e[0], to = e[1];
                let next = null;
                if (dir === "down" && from === cur) next = to;
                else if (dir === "up" && to === cur) next = from;
                if (next && next !== startCol && !seen.has(next)) {
                    seen.add(next);
                    out.push(next);
                    queue.push(next);
                }
            }
        }
        return out;
    }
    // transitive inputs feeding `col`
    upstreamOf(col) { return this._bfsGraph(col, "up"); }
    // transitive dependents fed by `col`
    downstreamOf(col) { return this._bfsGraph(col, "down"); }

    // ---- Feature 1 intelligence: derived views over state.graph ----------
    _colsToComps(cols) {
        return cols.map(col => this.byCol(col)).filter(Boolean)
            .sort((a, b) => this.colToNum(a.col) - this.colToNum(b.col));
    }
    // T1.4 — impact of the selected component (client BFS; instant, no RPC).
    get selectedImpact() {
        const c = this.selected;
        if (!c) return { down: [], payvis: [], up: [] };
        const down = this._colsToComps(this.downstreamOf(c.col));
        return {
            down,
            payvis: down.filter(x => x.appears_on_payslip),
            up: this._colsToComps(this.upstreamOf(c.col)),
        };
    }
    toggleInsights() { this.state.insightsOpen = !this.state.insightsOpen; }

    // T1.5 — execution order + unused panels (map graph cols -> live components).
    get execOrderItems() {
        return (this.state.graph.execution_order || []).map(col => {
            const c = this.byCol(col);
            return c ? { id: c.id, col, name: c.name, is_valid: c.is_valid }
                     : { id: "x" + col, col, name: col, is_valid: true };
        });
    }
    get unusedItems() {
        return (this.state.graph.unused || [])
            .map(col => { const c = this.byCol(col); return c ? { id: c.id, col, name: c.name, type: c.type } : null; })
            .filter(Boolean);
    }

    // T1.6 — circular-reference explainer (cycles come from get_intelligence).
    get graphCycles() { return this.state.graph.cycles || []; }
    // the cycle the selected component participates in, or null
    get selectedCycle() {
        const c = this.selected;
        if (!c) return null;
        return this.graphCycles.find(cy => (cy.cols || []).includes(c.col)) || null;
    }
    // ---- Grid Studio callbacks (T2.2/T2.3): save a formula and live-validate ----
    // Mirrors the inline editor's round-trip: save_formula → reload → recompute
    // the preview for the CURRENTLY selected sample (load() only computes sample[0]).
    async gridSaveFormula(ruleId, formula) {
        const cfgId = this.state.config.id;
        const sampleId = this.state.preview.sample_id;
        const r = await this.orm.call("pb.formula.studio", "save_formula", [ruleId, formula]);
        if (!r || !r.ok) { this.notif.add((r && r.msg) || "Could not save formula", { type: "warning" }); return; }
        await this.load(cfgId);
        if (sampleId) {
            this.state.preview = await this.orm.call("pb.formula.studio", "compute_preview", [cfgId, sampleId]);
        }
    }
    async gridValidateLive(formula, excludeRuleId) {
        try {
            return await this.orm.call("pb.formula.studio", "validate_formula_live",
                [this.state.config.id, formula, excludeRuleId]);
        } catch (e) { return { valid: true, message: "" }; }
    }
    async gridBulkUpdate(ruleIds, vals) {
        const cfgId = this.state.config.id;
        const sampleId = this.state.preview.sample_id;
        try {
            const r = await this.orm.call("pb.formula.studio", "bulk_update_components", [ruleIds, vals]);
            if (r && r.ok === false) { this.notif.add(r.msg || "Bulk update failed", { type: "warning" }); return; }
            this.notif.add(`Updated ${(r && r.updated) || ruleIds.length} components`, { type: "success" });
        } catch (e) {
            this.notif.add("Bulk update failed", { type: "warning" });
            return;
        }
        await this.load(cfgId);
        if (sampleId) this.state.preview = await this.orm.call("pb.formula.studio", "compute_preview", [cfgId, sampleId]);
    }
    async gridTranslateFormula(ruleId, targetCols) {
        try { return await this.orm.call("pb.formula.studio", "translate_formula", [ruleId, targetCols]); }
        catch (e) { return []; }
    }
    async gridBulkSaveFormulas(items) {
        const cfgId = this.state.config.id;
        const sampleId = this.state.preview.sample_id;
        try {
            await this.orm.call("pb.formula.studio", "bulk_save_formulas", [items]);
        } catch (e) { this.notif.add("Fill failed", { type: "warning" }); return; }
        this.notif.add(`Filled ${items.length} column${items.length === 1 ? "" : "s"}`, { type: "success" });
        await this.load(cfgId);
        if (sampleId) this.state.preview = await this.orm.call("pb.formula.studio", "compute_preview", [cfgId, sampleId]);
    }

    // ---- F14 scenario columns (what-if overlays) ----
    async reloadScenarios() {
        const r = await this.orm.call("pb.formula.studio", "list_scenarios", [this.state.config.id]);
        this.state.scenarios = (r && r.scenarios) || [];
    }
    async gridScenarioCreate(ruleId) {
        if (this._lockedNotice()) return null;
        const r = await this.orm.call("pb.formula.studio", "create_scenario", [ruleId]);
        if (!r || !r.ok) { this.notif.add((r && r.msg) || "Could not create scenario", { type: "warning" }); return null; }
        await this.reloadScenarios();
        return r.scenario;
    }
    async gridScenarioSave(sid, formula) {
        const r = await this.orm.call("pb.formula.studio", "save_scenario_formula", [sid, formula]);
        const sc = this.state.scenarios.find(s => s.id === sid);
        if (sc) { sc.override_formula = formula; if (r) { sc.valid = r.valid; sc.message = r.message; } }
        return r || { ok: true };
    }
    async gridScenarioEval(sid, sampleId) {
        try { return await this.orm.call("pb.formula.studio", "eval_scenario", [sid, sampleId]); }
        catch (e) { return { ok: false }; }
    }
    async gridScenarioPromote(sid) {
        if (this._lockedNotice()) return { ok: false };
        const cfgId = this.state.config.id;
        const sampleId = this.state.preview.sample_id;
        const r = await this.orm.call("pb.formula.studio", "promote_scenario", [sid]);
        if (!r || !r.ok) { this.notif.add((r && r.msg) || "Promote failed", { type: "warning" }); return { ok: false }; }
        this.notif.add(`Promoted into ${r.code}`, { type: "success" });
        await this.load(cfgId);   // the rule changed → refresh grid + scenarios + version history
        if (sampleId) this.state.preview = await this.orm.call("pb.formula.studio", "compute_preview", [cfgId, sampleId]);
        return r;
    }
    async gridScenarioDiscard(sid) {
        await this.orm.call("pb.formula.studio", "discard_scenario", [sid]);
        this.state.scenarios = this.state.scenarios.filter(s => s.id !== sid);
        return { ok: true };
    }

    isCycleMember(col) { return this.state.cycleHighlight.includes(col); }
    showCyclePath(cycle) {
        this.state.cycleHighlight = (cycle && cycle.cols) ? cycle.cols.slice() : [];
        // reveal the first member in the outline
        const first = this.state.cycleHighlight[0];
        if (first) this.scrollToCol(first);
    }
    clearCycleHighlight() { this.state.cycleHighlight = []; }

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
        if (this.state.rawMode) this._seedRaw();   // F12 — re-seed the text editor
        // reveal the outcome row in the live preview so the output arrow latches to it
        requestAnimationFrame(() => {
            const comp = this.state.components.find(x => x.id === id);
            const pv = comp && this._panelOnCanvas(".pbfs-test");
            if (pv) { const row = pv.querySelector(`.tp-row[data-col="${comp.col}"]`); if (row) row.scrollIntoView({ block: "nearest" }); }
            this.drawArrows();
            // grid workbench: jump the spreadsheet to the picked column + flash it
            if (this.state.view === "grid") {
                const th = document.querySelector(`.g2-table th[data-col-id="${id}"]`);
                if (th) {
                    th.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
                    th.classList.add("g2-jump");
                    setTimeout(() => th.classList.remove("g2-jump"), 1200);
                }
            }
        });
    }
    setView(v) {
        this.state.view = v;
        // grid = full-width workbench; drawers start closed on every switch
        this.state.outlineDrawer = false;
        this.state.previewDrawer = false;
        this.state.moreOpen = false;
    }

    // ---- responsive header: Tools ▾ overflow ----
    toggleMore() { this.state.moreOpen = !this.state.moreOpen; }
    pickTool(tool) {
        this.state.moreOpen = false;
        if (tool === "replay") this.openReplay();
        else if (tool === "whatif") this.openWhatif();
        else if (tool === "payslip") this.openPayslip();
        else if (tool === "mapping") this.openMapping();
        else if (tool === "rates") this.openRates();
    }

    // ---- grid workbench drawers ----
    toggleDrawer(which) {
        if (which === "outline") this.state.outlineDrawer = !this.state.outlineDrawer;
        else this.state.previewDrawer = !this.state.previewDrawer;
    }
    closeDrawers() { this.state.outlineDrawer = false; this.state.previewDrawer = false; }

    // ---- formatting ----
    vnd(n) {
        if (n === null || n === undefined || isNaN(n)) return "—";
        const cur = this.state.config.currency || "₫";
        return cur + Math.round(n).toLocaleString("en-US");
    }
    // F11 — typed cell display: format a value by its component's number_format
    // (percentage shows ×100 with %, integer/number drop the currency symbol).
    fmtTyped(comp, v) {
        if (v === null || v === undefined || isNaN(v)) return "—";
        const nf = comp && comp.number_format;
        if (nf === "percentage") return (Math.round(v * 10000) / 100).toLocaleString("en-US") + "%";
        if (nf === "integer") return Math.round(v).toLocaleString("en-US");
        if (nf === "number") return (Math.round(v * 100) / 100).toLocaleString("en-US");
        return this.vnd(v);   // currency (default)
    }
    previewVal(col) {
        const v = this.state.preview.values[col];
        return (v === undefined) ? "—" : this.fmtTyped(this.byCol(col), v);
    }
    stageCls() { return { draft: "draft", testing: "testing", validated: "validated", active: "active", archived: "muted" }[this.state.config.state] || "muted"; }
    stageLabel() { return { draft: "Draft", testing: "Testing", validated: "Validated", active: "Active", archived: "Archived" }[this.state.config.state] || this.state.config.state; }
    nextLabel() { return { draft: "Start testing", testing: "Validate", validated: "Activate", active: "Active" }[this.state.config.state] || "Advance"; }
    isDeduction(c) { return c.group === "Deductions"; }
    // A component that reduces the total: grouped as a Deduction OR whose own
    // formula is defined as a negative value (e.g. Loan Repayment = "=-F2", which
    // the name/group heuristic misses). Used to render "+deduction" as "−".
    isNegativeComponent(c) {
        if (!c) return false;
        if (this.isDeduction(c)) return true;
        return (c.excel_formula || "").replace(/^=/, "").trim().startsWith("-");
    }
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

    // ---- raw-Excel mode on the card (F12) ----
    // Same excel_formula + validate_formula_live + save_formula path the grid
    // uses, so both the chip editor and raw text write identical formulas.
    get rawActive() {
        return this.state.rawMode && this.selected && this.selected.type === "formula" && this.state.canEdit;
    }
    setRawMode(on) {
        if (this.state.rawMode === on) return;
        this.state.rawMode = on;
        try { localStorage.setItem("pbfs_raw_mode", on ? "1" : "0"); } catch (e) { /* private mode */ }
        if (on) {
            // preserve an in-progress edit for the SAME component across a
            // Chips↔Text round-trip; only seed fresh for a different component.
            const cid = this.selected ? this.selected.id : null;
            if (this.state.rawFor !== cid) this._seedRaw();
            else this._rawNeedsSeed = true;   // just re-push the buffer into the remounted textarea
        }
    }
    _seedRaw() {
        const c = this.selected;
        this.state.rawBuffer = (c && c.excel_formula) || "";
        this.state.rawFor = c ? c.id : null;
        this.state.rawValid = null;
        this.state.rawDirty = false;
        this._rawNeedsSeed = true;   // onPatched pushes it into the textarea
    }
    onRawInput(ev) {
        this.state.rawBuffer = ev.target.value;
        this.state.rawDirty = this.selected ? (ev.target.value !== (this.selected.excel_formula || "")) : false;
        if (this._rawTimer) clearTimeout(this._rawTimer);
        this._rawTimer = setTimeout(() => this._rawValidate(), 260);
    }
    async _rawValidate() {
        if (!this.selected) return;
        this.state.rawValid = await this.gridValidateLive(this.state.rawBuffer, this.selected.id);
    }
    onRawKeydown(ev) {
        // Ctrl/Cmd+Enter saves; plain Enter inserts a newline (formulas can be long)
        if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); this.saveRaw(); }
    }
    async saveRaw() {
        const c = this.selected;
        if (!c || this.state.rawBusy || !this.state.rawDirty) return;
        if (this._lockedNotice()) return;
        this.state.rawBusy = true;
        try {
            await this.gridSaveFormula(c.id, this.state.rawBuffer);   // save + full reload + recompute
            this.state.rawDirty = false;
            this.state.rawValid = { valid: true, message: "" };
            this._seedRaw();   // re-seed from the refreshed component
        } finally {
            this.state.rawBusy = false;
        }
    }
    revertRaw() { this._seedRaw(); }

    // ---- comments & annotations (F15) ----
    openNotes() {
        const c = this.selected;
        if (!c) return;
        this.state.notesOpen = true;
        this.state.notesData = null;
        this.state.noteDraft = "";
        this.state.noteReview = false;
        this._loadNotes(c.id);
    }
    closeNotes() { this.state.notesOpen = false; }
    async _loadNotes(ruleId) {
        this.state.notesBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "list_notes", [ruleId]);
            if (this.state.notesOpen && this.selected && this.selected.id === ruleId) {
                this.state.notesData = r;
            }
        } catch (e) { this.state.notesData = { ok: false, notes: [] }; }
        finally { this.state.notesBusy = false; }
    }
    onNoteInput(ev) { this.state.noteDraft = ev.target.value; }
    toggleNoteReview() { this.state.noteReview = !this.state.noteReview; }
    onNoteKeydown(ev) {
        if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); this.postNote(); }
    }
    async postNote() {
        const c = this.selected;
        const body = (this.state.noteDraft || "").trim();
        if (!c || !body) return;
        const r = await this.orm.call("pb.formula.studio", "post_note", [c.id, body, this.state.noteReview]);
        if (r && r.ok) {
            this.state.notesData = r;
            this.state.noteDraft = "";
            this.state.noteReview = false;
            await this.load(this.state.config.id);   // refresh card badge + problems tally
            this.state.notesOpen = true;              // keep the rail open after reload
        }
    }
    async resolveNote(n) {
        await this.orm.call("pb.formula.studio", n.resolved ? "reopen_note" : "resolve_note", [n.id]);
        await this._loadNotes(this.selected.id);
        await this.load(this.state.config.id);
        this.state.notesOpen = true;
    }
    async deleteNote(n) {
        await this.orm.call("pb.formula.studio", "delete_note", [n.id]);
        await this._loadNotes(this.selected.id);
        await this.load(this.state.config.id);
        this.state.notesOpen = true;
    }
    // resolve a review note directly from the Problems rail
    async resolveProblemNote(p) {
        if (!p.note_id) return;
        await this.orm.call("pb.formula.studio", "resolve_note", [p.note_id]);
        await this._loadProblems();
        await this.load(this.state.config.id);
        this.state.probOpen = true;
    }

    // ---- Execution replay (B1) ----
    openReplay() {
        this.state.replayOpen = true;
        this.state.replayData = null;
        this.state.replayStep = -1;
        this.state.replayPlaying = false;
        this._loadReplay(this.state.preview.sample_id);
    }
    closeReplay() {
        this.state.replayPlaying = false;
        if (this._replayTimer) { clearTimeout(this._replayTimer); this._replayTimer = null; }
        this.state.replayOpen = false;
    }
    async _loadReplay(sampleId) {
        this.state.replayBusy = true;
        try {
            this.state.replayData = await this.orm.call("pb.formula.studio", "replay_trace",
                [this.state.config.id, sampleId || false]);
            this.state.replayStep = -1;
        } catch (e) {
            this.state.replayData = { ok: false };
        } finally {
            this.state.replayBusy = false;
        }
    }
    replaySetSample(ev) {
        this.state.replayPlaying = false;
        this._loadReplay(parseInt(ev.target.value, 10));
    }
    get replaySteps() { return (this.state.replayData && this.state.replayData.steps) || []; }
    get replayCurrent() {
        const k = this.state.replayStep;
        return (k >= 0 && k < this.replaySteps.length) ? this.replaySteps[k] : null;
    }
    get replayDone() { return this.state.replayStep >= this.replaySteps.length - 1; }
    // value computed for a step index (visible once we've stepped past it)
    replayStepComputed(idx) { return idx <= this.state.replayStep; }
    replayFmt(item) { return this.fmtTyped({ number_format: item.number_format }, item.value); }
    replayProgressPct() {
        const n = this.replaySteps.length;
        return n ? Math.round(100 * (this.state.replayStep + 1) / n) : 0;
    }
    replayNext() {
        if (this.state.replayStep < this.replaySteps.length - 1) this.state.replayStep++;
        else this.state.replayPlaying = false;
    }
    replayPrev() { if (this.state.replayStep >= 0) this.state.replayStep--; }
    replayReset() { this.state.replayPlaying = false; this.state.replayStep = -1; }
    replayPlayPause() {
        if (this.state.replayPlaying) { this.state.replayPlaying = false; return; }
        if (this.replayDone) this.state.replayStep = -1;   // restart from the top
        this.state.replayPlaying = true;
        this._replayTick();
    }
    _replayTick() {
        if (!this.state.replayPlaying || !this.state.replayOpen) return;
        if (this.state.replayStep >= this.replaySteps.length - 1) { this.state.replayPlaying = false; return; }
        this.state.replayStep++;
        this._replayTimer = setTimeout(() => this._replayTick(), 650);
    }
    replaySeekPct(ev) {
        const n = this.replaySteps.length;
        if (!n) return;
        const pct = parseInt(ev.target.value, 10) / 100;
        this.state.replayStep = Math.min(n - 1, Math.max(-1, Math.round(pct * n) - 1));
    }

    // ---- What-if sliders + cost projection (B8) ----
    async openWhatif() {
        this.state.whatifOpen = true;
        this.state.whatifResult = null;
        this.state.whatifTarget = null;
        this.state.whatifData = await this.orm.call("pb.formula.studio", "whatif_components", [this.state.config.id]);
        // default to the first slidable constant with a non-zero value
        const first = (this.state.whatifData.components || []).find(c => c.value) || (this.state.whatifData.components || [])[0];
        if (first) this.whatifSelectTarget(first.code);
    }
    closeWhatif() {
        this._whatifToken = (this._whatifToken || 0) + 1;   // cancel any in-flight run
        this.state.whatifOpen = false;
    }
    get whatifComp() {
        return (this.state.whatifData && this.state.whatifData.components || []).find(c => c.code === this.state.whatifTarget) || null;
    }
    get whatifCandidate() { return (this.state.whatifBase || 0) * this.state.whatifMult; }
    whatifSelectTarget(code) {
        const c = (this.state.whatifData.components || []).find(x => x.code === code);
        if (!c) return;
        this.state.whatifTarget = code;
        this.state.whatifBase = c.value || 0;
        this.state.whatifMult = 1;
        this.state.whatifResult = null;
        this._runWhatif(200);
    }
    onWhatifTargetChange(ev) { this.whatifSelectTarget(ev.target.value); }
    onWhatifSlide(ev) {
        this.state.whatifMult = parseInt(ev.target.value, 10) / 100;   // 0..200 → 0..2×
        if (this._whatifTimer) clearTimeout(this._whatifTimer);
        this._whatifTimer = setTimeout(() => this._runWhatif(200), 300);   // sampled, debounced
    }
    whatifRunFull() { this._runWhatif(null); }   // exhaustive commit run
    whatifFmtVal(v) {
        const c = this.whatifComp;
        return this.fmtTyped({ number_format: c ? c.number_format : "number" }, v);
    }
    whatifPctChange() {
        const b = this.state.whatifBase;
        return b ? Math.round((this.state.whatifMult - 1) * 1000) / 10 : 0;
    }
    async _runWhatif(limit) {
        if (!this.state.whatifTarget) return;
        const code = this.state.whatifTarget, val = this.whatifCandidate;
        this.state.whatifBusy = true;
        const token = this._whatifToken = (this._whatifToken || 0) + 1;
        try {
            const prep = await this.orm.call("pb.formula.studio", "whatif_prepare",
                [this.state.config.id, code, val, limit || false], {}, { silent: true });
            if (token !== this._whatifToken) { if (prep && prep.sim_id) this.orm.call("pb.formula.studio", "whatif_drop", [prep.sim_id], {}, { silent: true }); return; }
            if (!prep || prep.ok === false || !prep.sim_id) { this.state.whatifResult = { empty: true }; return; }
            this.state.whatifHeadlineName = prep.headline_name || "";
            const ids = prep.payslip_ids || [];
            const CH = 120;
            for (let i = 0; i < ids.length; i += CH) {
                await this.orm.call("pb.formula.studio", "whatif_batch",
                    [{ sim_id: prep.sim_id, payslip_ids: ids.slice(i, i + CH) }], {}, { silent: true });
                if (token !== this._whatifToken) { this.orm.call("pb.formula.studio", "whatif_drop", [prep.sim_id], {}, { silent: true }); return; }
            }
            const res = await this.orm.call("pb.formula.studio", "whatif_result", [prep.sim_id], {}, { silent: true });
            if (token === this._whatifToken) {
                const r = (res && res.result) || null;
                if (r) r.sampled = !!limit;
                this.state.whatifResult = r;
            }
            this.orm.call("pb.formula.studio", "whatif_drop", [prep.sim_id], {}, { silent: true }).catch(() => {});
        } catch (e) { /* transient — keep last result */ }
        finally { if (token === this._whatifToken) this.state.whatifBusy = false; }
    }
    // histogram bar geometry (reuse the F8 idea)
    whatifBarPct(n) {
        const r = this.state.whatifResult;
        if (!r || !r.histogram) return 0;
        let mx = 0;
        for (const b of r.histogram) mx = Math.max(mx, b.neg, b.pos);
        return mx ? Math.round(100 * n / mx) : 0;
    }
    get whatifHistLabels() {
        return { lt10k: "< ₫10k", lt100k: "< ₫100k", lt1m: "< ₫1M", lt10m: "< ₫10M", ge10m: "≥ ₫10M" };
    }

    // ---- inline component editor ----
    get editing() { return this.state.editMode && this.selected && this.selected.id === this.state.editId; }
    get draftType() { return this.state.draft.column_type || "formula"; }

    async enterEdit(id) {
        if (this._lockedNotice()) return;
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
        // Deduction components (Social/Health/Unemployment Insurance, PIT, Loan…)
        // are stored as NEGATIVE values, so a "full net" formula adds them with a
        // "+". Rendering that as a uniform "+" is misleading — it reads as if
        // deductions are added. When a "+" operator sits directly before a
        // deduction chip, display it as "−" (and flag it so we can tint it) so the
        // line reads "Gross − SI − HI − … − PIT" — matching the real arithmetic.
        // Display-only: the stored formula is untouched.
        for (let i = 0; i < out.length - 1; i++) {
            const t = out[i], nxt = out[i + 1];
            if (t.kind === "op" && t.text === "+" && nxt.kind === "ref") {
                const comp = this.byCol(nxt.col);
                if (this.isNegativeComponent(comp)) { t.text = "−"; t.ded = true; }
            }
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

    // ---- Grab-to-pan the flow canvas (drag empty space to move the diagram) ----
    onPanStart(ev) {
        // left button only; don't hijack clicks on nodes / buttons (drill-in must work)
        if (ev.button !== 0 || ev.target.closest(".node-box, .node-diamond, button, a")) return;
        const el = ev.currentTarget;
        this._pan = { el, x: ev.clientX, y: ev.clientY, sl: el.scrollLeft, st: el.scrollTop, id: ev.pointerId };
        try { el.setPointerCapture(ev.pointerId); } catch (e) { /* ignore */ }
        el.classList.add("grabbing");
    }
    onPanMove(ev) {
        const p = this._pan;
        if (!p) return;
        p.el.scrollLeft = p.sl - (ev.clientX - p.x);
        p.el.scrollTop = p.st - (ev.clientY - p.y);
    }
    onPanEnd() {
        const p = this._pan;
        if (!p) return;
        try { p.el.releasePointerCapture(p.id); } catch (e) { /* ignore */ }
        p.el.classList.remove("grabbing");
        this._pan = null;
    }

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
    // Mouse-wheel zoom, anchored on the cursor (point under the pointer stays put).
    onWheel(ev) {
        if (!this.state.flowOpen) return;
        ev.preventDefault();
        const canvas = ev.currentTarget;
        const prev = this._curZoom || this._fitZoom();
        const next = Math.max(0.15, Math.min(prev * (ev.deltaY < 0 ? 1.1 : 1 / 1.1), 4));
        if (next === prev) return;
        const rect = canvas.getBoundingClientRect();
        const ox = canvas.scrollLeft + (ev.clientX - rect.left);
        const oy = canvas.scrollTop + (ev.clientY - rect.top);
        const ratio = next / prev;
        this.state.flowZoom = next;
        this.applyZoom();
        canvas.scrollLeft = ox * ratio - (ev.clientX - rect.left);
        canvas.scrollTop = oy * ratio - (ev.clientY - rect.top);
    }
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
    // scrollIntoView on an element inside a closed drawer scrolls the action
    // container horizontally to "reveal" the off-canvas panel, displacing the
    // whole workspace — only ever scroll to rows inside an on-canvas panel.
    _panelOnCanvas(sel) {
        const el = document.querySelector(sel);
        if (!el) return null;
        const st = getComputedStyle(el);
        return st.display !== "none" && st.visibility !== "hidden" ? el : null;
    }
    scrollToCol(col) {
        const panel = this._panelOnCanvas(".pbfs-outline");
        const row = panel && panel.querySelector(`.ol-item[data-col="${col}"]`);
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
        // a hidden or off-canvas panel (display:none, drawer mode) has a useless
        // rect — drawing to it produces a line sweeping across the screen
        const anchorable = (el) => {
            if (!el) return false;
            const r = el.getBoundingClientRect();
            const st = getComputedStyle(el);
            return r.width > 5 && st.visibility !== "hidden" && st.position !== "absolute";
        };
        if (!anchorable(outline)) return;
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
        if (preview && anchorable(preview)) {
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
        const panel = this._panelOnCanvas(".pbfs-test");
        const row = panel && panel.querySelector(`.tp-row[data-col="${col}"]`);
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
    // ---- jump from a test sample into the Cards (formula) view ----
    async openInFormulaView() {
        if (!this.state.testSampleId) return;
        await this.load(this.state.config.id);  // refresh cards sample list so the preview header resolves
        this.state.preview = await this.orm.call("pb.formula.studio", "compute_preview",
            [this.state.config.id, this.state.testSampleId]);
        this.state.view = "cards";
    }
    // ---- Excel template export / import ----
    async exportTestTemplate() {
        const r = await this.orm.call("pb.formula.studio", "export_test_template", [this.state.config.id]);
        if (!r || !r.ok) { this.notif.add((r && r.msg) || "Could not export template", { type: "warning" }); return; }
        const bin = atob(r.file_b64);
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        const url = URL.createObjectURL(new Blob([bytes], { type: r.mimetype }));
        const a = document.createElement("a");
        a.href = url; a.download = r.filename; a.click();
        URL.revokeObjectURL(url);
        this.notif.add("Template downloaded", { type: "success" });
    }
    triggerImport() { if (this.testFileRef.el) this.testFileRef.el.click(); }
    async onImportFile(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = async (e) => {
            const b64 = String(e.target.result).split(",")[1] || "";
            const r = await this.orm.call("pb.formula.studio", "import_test_samples",
                [this.state.config.id, b64, file.name]);
            ev.target.value = "";  // allow re-importing the same file
            if (!r || !r.ok) { this.notif.add((r && r.msg) || "Could not import", { type: "warning" }); return; }
            this.notif.add(`${r.count} sample${r.count === 1 ? "" : "s"} imported`, { type: "success" });
            this.state.test.samples = r.samples;
            if (r.first_id) await this.selectSample(r.first_id);
        };
        reader.readAsDataURL(file);
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
    // Read-only (Formula User) gate: buttons stay visible, but acting on them
    // shows the upsell dialog instead of performing the write.
    _lockedNotice() {
        if (this.state.canEdit) return false;
        this.dialog.add(AlertDialog, {
            title: "Available in the full platform",
            body: "This functionality is available in the full Payobook platform. " +
                "Please contact Payobook to arrange a personalised demonstration.",
            confirmLabel: "Got it",
        });
        return true;
    }
    openAI() { if (this._lockedNotice()) return; this.state.aiOpen = true; }
    closeAI() { this.state.aiOpen = false; }

    // ---- Explain modal (T5.3) ----
    openExplain() {
        const c = this.selected;
        if (!c) return;
        this.state.explainOpen = true;
        this.state.explainLang = "en";
        // deterministic floor is already in the payload → shows instantly (<200ms)
        this.state.explainText = c.explain || "";
        this.state.explainSource = "deterministic";
        this._fetchExplain();
    }
    closeExplain() { this.state.explainOpen = false; }
    setExplainLang(lang) {
        if (this.state.explainLang === lang) return;
        this.state.explainLang = lang;
        // keep the current floor visible while the new-language text loads
        if (lang === "en" && this.selected) this.state.explainText = this.selected.explain || this.state.explainText;
        this.state.explainSource = "deterministic";
        this._fetchExplain();
    }
    async _fetchExplain() {
        const c = this.selected;
        if (!c) return;
        const lang = this.state.explainLang, ruleId = c.id;
        this.state.explainBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "explain_formula_ai", [ruleId, lang]);
            // ignore stale responses (user switched lang / component / closed)
            if (this.state.explainOpen && this.state.explainLang === lang && this.selected && this.selected.id === ruleId) {
                this.state.explainText = (r && r.text) || this.state.explainText;
                this.state.explainSource = (r && r.source) || "deterministic";
            }
        } catch (e) { /* keep the floor */ }
        finally { if (this.state.explainLang === lang) this.state.explainBusy = false; }
    }

    // ---- Version history rail (F7) ----
    openHistory() {
        const c = this.selected;
        if (!c) return;
        this.state.historyOpen = true;
        this.state.historyData = null;
        this.state.historyDiffSeq = null;
        this.state.historyDiffRuns = null;
        this._loadHistory(c.id);
    }
    closeHistory() { this.state.historyOpen = false; }
    async _loadHistory(ruleId) {
        this.state.historyBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "get_rule_history", [ruleId]);
            // ignore if the user closed or switched component meanwhile
            if (this.state.historyOpen && this.selected && this.selected.id === ruleId) {
                this.state.historyData = r && r.ok ? r : null;
            }
        } catch (e) { this.state.historyData = null; }
        finally { this.state.historyBusy = false; }
    }
    async toggleDiff(seq) {
        if (this.state.historyDiffSeq === seq) {
            this.state.historyDiffSeq = null;
            this.state.historyDiffRuns = null;
            return;
        }
        const ruleId = this.selected && this.selected.id;
        if (!ruleId) return;
        this.state.historyDiffSeq = seq;
        this.state.historyDiffRuns = null;
        try {
            // diff this version (older, A) against the live head (newer, B)
            const r = await this.orm.call("pb.formula.studio", "diff_versions", [ruleId, seq, null]);
            if (this.state.historyDiffSeq === seq) this.state.historyDiffRuns = (r && r.runs) || [];
        } catch (e) { this.state.historyDiffRuns = []; }
    }
    async restoreVersion(seq) {
        const ruleId = this.selected && this.selected.id;
        if (!ruleId) return;
        if (this._lockedNotice()) return;
        try {
            const r = await this.orm.call("pb.formula.studio", "restore_version", [ruleId, seq]);
            if (!r || !r.ok) {
                this.notif.add((r && r.msg) || "Restore failed", { type: "danger" });
                return;
            }
            this.notif.add("Restored v" + seq, { type: "success" });
            // reflect the new formula everywhere, then refresh the rail (the
            // restore itself is a new 'restore' version — history never rewrites)
            await this.load(this.state.config.id);
            this.state.historyDiffSeq = null;
            this.state.historyDiffRuns = null;
            await this._loadHistory(ruleId);
        } catch (e) {
            this.notif.add("Restore failed", { type: "danger" });
        }
    }

    // ---- Simulate-before-activate (F8) ----
    // Drives the chunked simulation over SILENT RPC so the global loading
    // indicator stays hidden and the modal's own progress bar is the only
    // signal (same cadence as the Shadow cockpit).
    openSimulate() {
        if (this._lockedNotice()) return;
        if (!this.state.config || !this.state.config.id) return;
        this.state.simOpen = true;
        this.state.simResult = null;
        this.state.simProgress = 0;
        this.state.simId = null;
        this._runSimulate({});   // whole draft config vs the last actual payrun
    }
    closeSimulate() {
        this.state.simOpen = false;
        // discard the transient run — no residue (D8.2)
        const id = this.state.simId;
        this.state.simId = null;
        this.state.simResult = null;
        if (id) this.orm.call("pb.formula.studio", "simulate_drop", [id], {}, { silent: true }).catch(() => {});
    }
    async _runSimulate(overrides) {
        const SIM_CHUNK = 100;
        this.state.simBusy = true;
        this.state.simProgress = 0;
        try {
            const prep = await this.orm.call("pb.formula.studio", "simulate_prepare",
                [this.state.config.id, overrides || {}, null], {}, { silent: true });
            if (!prep || prep.ok === false || !prep.sim_id) {
                this.notif.add((prep && prep.msg) || "No historical payslips to simulate against", { type: "warning" });
                this.state.simOpen = false;
                return;
            }
            this.state.simId = prep.sim_id;
            const ids = prep.payslip_ids || [];
            if (!ids.length) {
                this.notif.add("No historical payslips to simulate against", { type: "warning" });
                this.state.simResult = { empty: true };
                return;
            }
            for (let i = 0; i < ids.length; i += SIM_CHUNK) {
                await this.orm.call("pb.formula.studio", "simulate_batch",
                    [{ sim_id: prep.sim_id, payslip_ids: ids.slice(i, i + SIM_CHUNK) }], {}, { silent: true });
                this.state.simProgress = Math.round(100 * Math.min(i + SIM_CHUNK, ids.length) / ids.length);
                if (!this.state.simOpen) return;   // user closed → abandon
            }
            const res = await this.orm.call("pb.formula.studio", "simulate_result",
                [prep.sim_id], {}, { silent: true });
            if (this.state.simOpen) this.state.simResult = (res && res.result) || null;
        } catch (e) {
            this.notif.add("Simulation failed", { type: "danger" });
            this.state.simOpen = false;
        } finally {
            this.state.simBusy = false;
        }
    }
    // histogram bar geometry: share of the tallest bucket, 0..100 (%)
    simBarPct(n) {
        const r = this.state.simResult;
        if (!r || !r.histogram) return 0;
        let mx = 0;
        for (const b of r.histogram) mx = Math.max(mx, b.neg, b.pos);
        return mx ? Math.round(100 * n / mx) : 0;
    }
    get simHistLabels() {
        return { lt10k: "< ₫10k", lt100k: "< ₫100k", lt1m: "< ₫1M", lt10m: "< ₫10M", ge10m: "≥ ₫10M" };
    }
    fmtSigned(v) {
        const n = Math.round(v || 0);
        const s = Math.abs(n).toLocaleString("en-US");
        return (n > 0 ? "+" : n < 0 ? "−" : "") + s;
    }

    // ---- Problems rail + lint + rename-refactor (F13) ----
    get problemCount() { return (this.state.probData && this.state.probData.count) || 0; }
    // worst severity present -> drives the toolbar badge colour ('' when clean)
    get problemLevel() {
        const c = (this.state.probData && this.state.probData.counts) || {};
        if (c.error) return "error";
        if (c.warning) return "warning";
        if (c.hint) return "hint";
        return "";
    }
    get problems() { return (this.state.probData && this.state.probData.problems) || []; }
    problemsOf(sev) { return this.problems.filter(p => p.severity === sev); }
    openProblems() {
        this.state.probOpen = true;
        this._loadProblems();
    }
    closeProblems() { this.state.probOpen = false; }
    async _loadProblems() {
        if (!this.state.config || !this.state.config.id) return;
        this.state.probBusy = true;
        try {
            this.state.probData = await this.orm.call("pb.formula.studio", "get_problems", [this.state.config.id]);
        } catch (e) { /* keep last */ }
        finally { this.state.probBusy = false; }
    }
    // jump to the component a problem points at (switch to Cards, select, scroll)
    gotoProblem(p) {
        if (!p || !p.rule_id) return;
        this.state.probOpen = false;
        if (this.state.view !== "cards" && this.state.view !== "grid") this.state.view = "cards";
        this.selectComponent(p.rule_id);
        if (p.col) requestAnimationFrame(() => this.scrollToCol(p.col));
    }
    probIcon(kind) {
        return {
            invalid: "alert", empty: "alert", cycle: "cycle", unused: "unplug",
            magic: "hash", offpayslip: "eye",
        }[kind] || "dot";
    }

    // inline code rename on the component card
    tryRename() {
        if (!this.state.canEdit) return;
        this.startRename();
    }
    startRename() {
        if (this._lockedNotice()) return;
        const c = this.selected;
        if (!c) return;
        this.state.renameId = c.id;
        this.state.renameVal = c.code || "";
        this.state.renameErr = "";
    }
    cancelRename() {
        this.state.renameId = null;
        this.state.renameVal = "";
        this.state.renameErr = "";
    }
    onRenameInput(ev) {
        // keep the input to plain identifier characters, uppercased
        this.state.renameVal = (ev.target.value || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
        this.state.renameErr = "";
    }
    onRenameKey(ev) {
        if (ev.key === "Enter") { ev.preventDefault(); this.commitRename(); }
        else if (ev.key === "Escape") { ev.preventDefault(); this.cancelRename(); }
    }
    async commitRename() {
        const id = this.state.renameId;
        if (!id) return;
        const code = (this.state.renameVal || "").trim();
        if (this.state.renameBusy) return;
        this.state.renameBusy = true;
        this.state.renameErr = "";
        try {
            const r = await this.orm.call("pb.formula.studio", "rename_component", [id, code]);
            if (!r || !r.ok) { this.state.renameErr = (r && r.msg) || "Rename failed"; return; }
            const n = (r.rewritten || []).length;
            this.notif.add(
                r.msg + (n ? " · " + n + (n === 1 ? " formula" : " formulas") + " updated" : ""),
                { type: "success" });
            this.cancelRename();
            await this.load(this.state.config.id);   // reflect new code + rewritten refs + fresh problems
        } catch (e) {
            this.state.renameErr = "Rename failed";
        } finally {
            this.state.renameBusy = false;
        }
    }

    // ---- Rate (bracket) tables (F11) ----
    openRates() {
        this.state.ratesOpen = true;
        this.state.rateEdit = null;
        this.state.rateErr = "";
        this.reloadRates();
    }
    closeRates() { this.state.ratesOpen = false; this.state.rateEdit = null; }
    cancelRateEdit() { this.state.rateEdit = null; this.state.rateErr = ""; }
    async reloadRates() {
        const r = await this.orm.call("pb.formula.studio", "list_rate_tables", [this.state.config.id]);
        this.state.rateTables = (r && r.tables) || [];
    }
    newRateTable() {
        if (this._lockedNotice()) return;
        this.state.rateEdit = { id: null, code: "", name: "", note: "",
            brackets: [{ lower: 0, rate: 0.05 }] };
        this.state.rateErr = "";
        this.state.ratePreview = null;
    }
    editRateTable(t) {
        if (this._lockedNotice()) return;
        this.state.rateEdit = {
            id: t.id, code: t.code, name: t.name, note: t.note,
            brackets: (t.brackets || []).map(b => ({ lower: b.lower, rate: b.rate })),
        };
        this.state.rateErr = "";
        this.state.ratePreview = null;
        this._previewBracketLater();
    }
    addBracket() {
        if (!this.state.rateEdit) return;
        const bs = this.state.rateEdit.brackets;
        const last = bs[bs.length - 1];
        bs.push({ lower: last ? Number(last.lower) + 5000000 : 0, rate: last ? last.rate : 0.05 });
    }
    removeBracket(i) {
        if (!this.state.rateEdit) return;
        this.state.rateEdit.brackets.splice(i, 1);
    }
    onBracketLower(i, ev) {
        const v = parseFloat((ev.target.value || "").replace(/[^0-9.\-]/g, ""));
        this.state.rateEdit.brackets[i].lower = isNaN(v) ? 0 : v;
        this._previewBracketLater();
    }
    // percent-typed: the input shows rate×100 with a %, we store the fraction
    onBracketRate(i, ev) {
        const v = parseFloat((ev.target.value || "").replace(/[^0-9.\-]/g, ""));
        this.state.rateEdit.brackets[i].rate = isNaN(v) ? 0 : v / 100;
        this._previewBracketLater();
    }
    ratePct(rate) {
        const n = (rate || 0) * 100;
        return (Math.round(n * 100) / 100);
    }
    setRateField(field, ev) {
        this.state.rateEdit[field] = field === "code"
            ? (ev.target.value || "").toUpperCase().replace(/[^A-Z0-9]/g, "")
            : ev.target.value;
        this.state.rateErr = "";
    }
    async saveRateTable() {
        if (this.state.rateBusy || !this.state.rateEdit) return;
        this.state.rateBusy = true;
        this.state.rateErr = "";
        try {
            const r = await this.orm.call("pb.formula.studio", "save_rate_table",
                [this.state.config.id, this.state.rateEdit]);
            if (!r || !r.ok) { this.state.rateErr = (r && r.msg) || "Save failed"; return; }
            this.notif.add("Rate table saved", { type: "success" });
            await this.reloadRates();
            this.state.rateEdit = null;
            // BRACKET recompiles at compute — refresh preview so the grid/card reflect it
            await this.load(this.state.config.id);
        } catch (e) {
            this.state.rateErr = "Save failed";
        } finally {
            this.state.rateBusy = false;
        }
    }
    async deleteRateTable(t) {
        if (this._lockedNotice()) return;
        const r = await this.orm.call("pb.formula.studio", "delete_rate_table", [t.id]);
        if (!r || !r.ok) { this.notif.add((r && r.msg) || "Delete failed", { type: "warning" }); return; }
        this.notif.add("Rate table deleted", { type: "success" });
        await this.reloadRates();
    }
    setPreviewIncome(ev) {
        const v = parseFloat((ev.target.value || "").replace(/[^0-9.\-]/g, ""));
        this.state.ratePreviewIncome = isNaN(v) ? 0 : v;
        this._previewBracketLater();
    }
    _previewBracketLater() {
        if (this._rateTimer) clearTimeout(this._rateTimer);
        this._rateTimer = setTimeout(() => this._previewBracket(), 220);
    }
    async _previewBracket() {
        const e = this.state.rateEdit;
        if (!e || !e.id) { this.state.ratePreview = this._localBracketEval(); return; }
        // saved table → server truth; unsaved edits → local eval for instant feedback
        this.state.ratePreview = this._localBracketEval();
    }
    // client-side progressive eval mirroring the server (instant, no round-trip)
    _localBracketEval() {
        const e = this.state.rateEdit;
        if (!e) return null;
        const bs = [...e.brackets].map(b => ({ lower: Number(b.lower) || 0, rate: Number(b.rate) || 0 }))
            .sort((a, b) => a.lower - b.lower);
        const x = Number(this.state.ratePreviewIncome) || 0;
        let base = 0, result = 0;
        for (let i = 0; i < bs.length; i++) {
            const upper = i + 1 < bs.length ? bs[i + 1].lower : null;
            if (x > bs[i].lower) {
                const top = upper === null ? x : Math.min(x, upper);
                result = base + bs[i].rate * (top - bs[i].lower);
            }
            base += bs[i].rate * (upper === null ? 0 : (upper - bs[i].lower));
        }
        return { value: x, result: Math.max(0, result) };
    }
    rateTableUsage(t) {
        const u = (t.used_by || []);
        return u.length ? u.join(", ") : "";
    }

    // ---- Mapping canvas (F10, multi-adapter) ----
    get mapTabs() {
        return [
            { key: "cycle", label: "Cycle carryover" },
            { key: "api", label: "API fields" },
            { key: "import", label: "Import columns" },
            { key: "scheme", label: "Schemes" },
        ];
    }
    // adapters that share the generic create/delete/draw dispatch; cycle is bespoke
    get _mapPrefix() { return { api: "api", import: "import", scheme: "scheme" }[this.state.mapMode] || null; }
    openMapping(mode) {
        this.state.mapMode = mode || this.state.mapMode || "cycle";
        this.state.mapOpen = true;
        this.state.mapData = null;
        this.state.mapContextId = null;
        this.state.mapDismissed = [];
        this._loadMapping();
    }
    setMapMode(mode) {
        if (this.state.mapMode === mode) return;
        this.state.mapMode = mode;
        this.state.mapData = null;
        this.state.mapContextId = null;
        this.state.mapDismissed = [];
        this._loadMapping();
    }
    setMapContext(ev) {
        this.state.mapContextId = parseInt(ev.target.value, 10);
        this.state.mapDismissed = [];
        this._loadMapping();
    }
    closeMapping() { this.state.mapOpen = false; }
    async _loadMapping() {
        this.state.mapBusy = true;
        const cfg = this.state.config.id, ctx = this.state.mapContextId, p = this._mapPrefix;
        try {
            const r = p
                ? await this.orm.call("pb.formula.studio", `${p}_mapping_data`, [cfg, ctx || false])
                : await this.orm.call("pb.formula.studio", "mapping_canvas_data", [cfg]);
            this.state.mapData = r;
            if (r && r.context_id) this.state.mapContextId = r.context_id;
        } catch (e) {
            this.state.mapData = { ok: false, reason: "error" };
        } finally {
            this.state.mapBusy = false;
        }
    }
    // wires passed to the canvas (drop client-side-dismissed api suggestions)
    get mapWires() {
        const w = (this.state.mapData && this.state.mapData.wires) || [];
        const d = this.state.mapDismissed || [];
        return d.length ? w.filter(x => !d.includes(x.id)) : w;
    }
    get mapAcceptedCount() { return this.mapWires.filter(x => x.state === "accepted").length; }
    get mapSuggestedCount() { return this.mapWires.filter(x => x.state === "suggested").length; }
    async mapAccept(wire) {
        const p = this._mapPrefix;
        if (p) {
            await this.orm.call("pb.formula.studio", `${p}_mapping_create`,
                [this.state.config.id, this.state.mapContextId, wire.source || wire.leftId, wire.rightId]);
        } else {
            await this.orm.call("pb.formula.studio", "mapping_accept", [wire.ref]);
        }
        await this._loadMapping();
    }
    async mapReject(wire) {
        if (this._mapPrefix) {
            // api/import suggestions are computed live, not persisted — dismiss client-side
            this.state.mapDismissed = [...(this.state.mapDismissed || []), wire.id];
            return;
        }
        await this.orm.call("pb.formula.studio", "mapping_reject", [wire.ref]);
        await this._loadMapping();
    }
    async mapDelete(wire) {
        const p = this._mapPrefix;
        await this.orm.call("pb.formula.studio", p ? `${p}_mapping_delete` : "mapping_delete", [wire.ref]);
        await this._loadMapping();
    }
    async mapDraw(leftId, rightId) {
        const p = this._mapPrefix;
        const r = p
            ? await this.orm.call("pb.formula.studio", `${p}_mapping_create`,
                [this.state.config.id, this.state.mapContextId, leftId, rightId])
            : await this.orm.call("pb.formula.studio", "mapping_create", [this.state.config.id, leftId, rightId]);
        if (r && r.ok === false) { this.notif.add(r.msg || "Could not connect", { type: "warning" }); return; }
        await this._loadMapping();
    }
    async mapSuggest() {
        this.state.mapBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "mapping_suggest", [this.state.config.id]);
            if (r && r.ok) this.state.mapData = r;
            const n = this.mapSuggestedCount;
            this.notif.add(n ? `${n} suggestion${n === 1 ? "" : "s"} found` : "No new suggestions", { type: "success" });
        } catch (e) {
            this.notif.add("Suggest failed", { type: "danger" });
        } finally {
            this.state.mapBusy = false;
        }
    }
    async mapAcceptAll() {
        const sugs = this.mapWires.filter(w => w.state === "suggested" && w.confidence >= 0.9);
        for (const w of sugs) await this.mapAccept(w);
        await this._loadMapping();
        this.notif.add(`Accepted ${sugs.length} high-confidence mapping${sugs.length === 1 ? "" : "s"}`, { type: "success" });
    }

    // ---- Payslip Studio (F9) ----
    openPayslip() {
        this.state.psOpen = true;
        this.state.psData = null;
        this.state.psEditSec = null;
        this._loadPayslip();
    }
    closePayslip() { this.state.psOpen = false; }
    async _loadPayslip(sampleId) {
        this.state.psBusy = true;
        try {
            this.state.psData = await this.orm.call("pb.formula.studio", "payslip_studio_data",
                [this.state.config.id, sampleId || false]);
        } catch (e) {
            this.state.psData = { ok: false };
        } finally {
            this.state.psBusy = false;
        }
    }
    psSetSample(ev) { this._loadPayslip(parseInt(ev.target.value, 10)); }
    psToggleLang() { this.state.psLang = this.state.psLang === "en" ? "vi" : "en"; }
    psSectionTitle(s) {
        return (this.state.psLang === "vi" && s.label_vi) ? s.label_vi : (s.label || s.identifier);
    }

    // component value formatting (typed, reusing fmtTyped)
    psVal(c) { return this.fmtTyped(c, c.value); }
    // is a line visible on the printed slip?
    psVisible(c) {
        if (c.visibility === "never") return false;
        if (c.visibility === "when_nonzero") return Math.abs(c.value || 0) > 0.0001;
        return true;
    }
    psSectionVisibleComps(s) { return s.components.filter(c => this.psVisible(c)); }
    psSectionShown(s) {
        if (!s.collapse_when_empty) return true;
        return this.psSectionVisibleComps(s).length > 0;
    }
    psSectionTotal(s) {
        let t = 0;
        for (const c of this.psSectionVisibleComps(s)) t += (c.is_deduction ? -1 : 1) * (c.value || 0);
        return t;
    }
    get psNet() {
        if (!this.state.psData) return 0;
        let net = 0;
        for (const s of this.state.psData.sections) net += this.psSectionTotal(s);
        return net;
    }

    // ---- drag & drop (native HTML5) ----
    psDragStart(comp, ev) {
        if (!this.state.psData.can_edit) { ev.preventDefault(); return; }
        this.state.psDragId = comp.id;
        ev.dataTransfer.effectAllowed = "move";
        try { ev.dataTransfer.setData("text/plain", String(comp.id)); } catch (e) { /* firefox */ }
    }
    psDragEnd() { this.state.psDragId = null; this.state.psOverComp = null; this.state.psOverZone = null; }
    psDragOverComp(comp, ev) {
        if (this.state.psDragId == null) return;
        ev.preventDefault(); ev.stopPropagation();
        this.state.psOverComp = comp.id;
    }
    psDragOverZone(zone, ev) {
        if (this.state.psDragId == null) return;
        ev.preventDefault();
        this.state.psOverZone = zone;
    }
    async psDrop(sectionId, ev) {
        if (ev) ev.preventDefault();
        const dragId = this.state.psDragId;
        this.state.psOverZone = null;
        if (dragId == null) return;
        const target = sectionId ? this.state.psData.sections.find(s => s.id === sectionId) : null;
        const list = (target ? target.components : this.state.psData.tray)
            .map(c => c.id).filter(id => id !== dragId);
        let idx = list.indexOf(this.state.psOverComp);
        if (idx === -1) idx = list.length;
        list.splice(idx, 0, dragId);
        this.state.psDragId = null; this.state.psOverComp = null;
        await this.orm.call("pb.formula.studio", "move_component", [dragId, sectionId || false, list]);
        await this._loadPayslip(this.state.psData.sample_id);
    }

    // ---- section ops ----
    async psCreateSection() {
        if (this._lockedNotice()) return;
        const r = await this.orm.call("pb.formula.studio", "create_section", [this.state.config.id, "New section"]);
        if (r && r.ok) { await this._loadPayslip(this.state.psData.sample_id); this.state.psEditSec = r.section_id; }
    }
    startSectionEdit(s) { if (this.state.psData.can_edit) this.state.psEditSec = s.id; }
    async psRenameSection(s, ev) {
        const label = (ev.target.value || "").trim();
        this.state.psEditSec = null;
        if (label && label !== s.label) {
            await this.orm.call("pb.formula.studio", "update_section", [s.id, { label }]);
            await this._loadPayslip(this.state.psData.sample_id);
        }
    }
    psRenameKey(s, ev) { if (ev.key === "Enter") ev.target.blur(); else if (ev.key === "Escape") this.state.psEditSec = null; }
    async psSetSectionColor(s, color) {
        await this.orm.call("pb.formula.studio", "update_section", [s.id, { color_key: color }]);
        await this._loadPayslip(this.state.psData.sample_id);
    }
    async psToggleCollapse(s) {
        await this.orm.call("pb.formula.studio", "update_section", [s.id, { collapse_when_empty: !s.collapse_when_empty }]);
        await this._loadPayslip(this.state.psData.sample_id);
    }
    async psDeleteSection(s) {
        await this.orm.call("pb.formula.studio", "delete_section", [s.id]);
        await this._loadPayslip(this.state.psData.sample_id);
    }
    async psCycleVisibility(c) {
        if (!this.state.psData.can_edit) return;
        const next = { always: "when_nonzero", when_nonzero: "never", never: "always" }[c.visibility] || "always";
        await this.orm.call("pb.formula.studio", "set_component_visibility", [c.id, next]);
        await this._loadPayslip(this.state.psData.sample_id);
    }
    psVisIcon(c) { return c.visibility; }   // used for CSS class

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
        if (this._lockedNotice()) return;
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
