/** @odoo-module **/

import { Component, useState, useRef, useEffect, useExternalListener, onWillStart, onMounted, onPatched, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { GridStudio } from "./grid/grid_studio";
import { MappingCanvas } from "./mapping/mapping_canvas";
import { FindReplace } from "./grid/find_replace";
import { CommandPalette } from "./palette/command_palette";
import { HoverCard } from "./hover_card";

const GROUPS = ["Inputs", "Earnings", "Deductions", "Totals"];
const CAT_COLOR = { info: "#0E7490", earn: "#4F46E5", ded: "#B45309", total: "#059669" };
const OPSYM = { "+": "+", "-": "−", "*": "×", "/": "÷", "^": "^" };

// W18 (D-F2) — keyboard-shortcut registry for the shortcuts overlay. The GRID rows
// are a static table living in this ONE file, right next to `paletteCommands` and
// `_setupCommandLayer` (which register the actual hotkeys), so W99 and W18 can never
// drift apart — one file to update. The "Command layer" section is derived from
// `paletteCommands` labels in `shortcutSections` (a binding-per-row), keeping the
// ⌘F row honest against the real Find command.
const SHORTCUT_GRID = [
    { title: "Grid navigation", rows: [
        { keys: ["←", "↑", "→", "↓"], label: "Move between cells" },
        { keys: ["Tab"], label: "Next column · Shift+Tab for previous" },
        { keys: ["Shift", "←/→"], label: "Extend the column selection" },
        { keys: ["Enter"], label: "Edit the focused formula cell" },
        { keys: ["F2"], label: "Edit the focused formula cell" },
    ] },
    { title: "Grid editing", rows: [
        { keys: ["A–Z", "0–9"], label: "Start typing to edit a formula cell" },
        { keys: ["Enter"], label: "Save the edit" },
        { keys: ["Esc"], label: "Cancel the edit · clear selection" },
        { keys: ["Ctrl", "Z"], label: "Undo the last saved formula" },
    ] },
    { title: "Drag-fill", rows: [
        { keys: ["Enter"], label: "Confirm the proposed fill" },
        { keys: ["Esc"], label: "Cancel the fill" },
    ] },
];

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
    static components = { CfgCombo, GridStudio, MappingCanvas, FindReplace, CommandPalette, HoverCard };
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
            // B3 — release bundles + sign-off
            releaseOpen: false,
            releaseBusy: false,
            releaseTab: "pending",
            releaseData: null,
            releaseNarrative: "",
            releaseList: [],
            releaseDetail: null,
            releaseExpandId: null,
            releaseLatestId: false,
            // W86 — one-action rollback (revert the latest release)
            rollbackOpen: false,
            rollbackBusy: false,
            rollbackData: null,        // rollback_preview payload
            rollbackConfirm: "",       // typed release-name confirmation
            rollbackSimBusy: false,
            rollbackSimProgress: 0,
            rollbackSimResult: null,
            rollbackSimId: null,
            rollbackApplying: false,
            // B6 — bureau cockpit
            bureauOpen: false,
            bureauBusy: false,
            bureauData: null,
            // B4 — legislation packs
            legisOpen: false,
            legisBusy: false,
            legisPacks: [],
            legisCanEdit: false,
            legisSel: null,
            legisDetail: null,
            legisCoverage: null,
            legisApplying: false,
            // B2 — config branches
            branchOpen: false,
            branchBusy: false,
            branchData: null,
            branchDiff: null,
            branchExpandId: null,
            branchNewName: "",
            branchNewNote: "",
            branchCreating: false,
            // B5 — scheme variants
            variantOpen: false,
            variantBusy: false,
            variantData: null,
            variantDiff: null,
            variantExpandId: null,
            variantNewName: "",
            variantCreating: false,
            variantSyncing: false,
            // B7 — client review shares
            shareOpen: false,
            shareBusy: false,
            shareData: null,
            shareNewClient: "",
            shareNewRelease: false,
            shareCreating: false,
            shareCopied: null,
            // B9 — dependency map (full-screen graph navigation)
            depOpen: false,
            depNodes: [],
            depEdges: [],
            depFocus: null,
            depHidden: [],
            depCritical: [],
            depCriticalOn: false,
            depZoom: 1,
            depPan: { x: 0, y: 0 },
            depDragging: false,
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
            // W97 — period comparison view (state.view === 'compare')
            cmpRuns: [],
            cmpA: null,
            cmpB: null,
            cmpCurrency: "",
            cmpBusy: false,
            cmpProgress: 0,
            cmpResult: null,
            cmpId: null,
            cmpSort: "delta",
            cmpSortDir: -1,
            cmpMoversOpen: false,
            // W48 — payrun anomaly narration over the compare fold
            cmpNarrate: null,        // {blocks, source, lang}
            cmpNarrateBusy: false,
            cmpNarrateLang: "en",
            // W82 — tests-on-save chip: the verdict from the last save RPC
            // ({has_tests,total,passed,failed,pending,failures:[]}), cleared on
            // config switch. null = no save yet this session.
            tests: null,
            testsFailOpen: false,        // failures popover under the chip
            // test & validate workbench
            test: { samples: [], inputComponents: [], currency: "" },
            testSampleId: null,
            testDetail: null,
            // W83 — coverage strip payload {pct, asserted, exercised, untested, orphan_inputs}
            testCoverage: null,
            coverageOpen: false,   // expandable untested list
            testGenOpen: false,
            // W84 — Generate dropdown sub-panels: null | 'boundary' | 'ai'
            genMode: null,
            boundaryCands: null,   // {candidates, reachable, unreachable}
            boundaryPicks: [],     // selected candidate keys
            boundaryBase: null,    // base sample id to clone inputs from
            boundaryBusy: false,
            boundaryResult: null,  // {created, skipped, capped}
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
            // WP-A — Studio Command Layer
            findOpen: false,        // W14 find & replace drawer
            paletteOpen: false,     // W99 command palette
            hoverCard: null,        // W100 hover card: {compId, x, y} | null
            // WP-F · W18 — keyboard-shortcuts overlay
            shortcutsOpen: false,
            // WP-F · W4 — pinned sample rows (client-session only; cleared on config
            // switch). `pinnedSamples` holds up to 2 extra sample ids (never the
            // active one, D-F4); `previewExtra` caches their computed value maps.
            pinnedSamples: [],
            previewExtra: {},
            // WP-F · W8 — collapse-by-category fold state {catKey: true}. Client-only
            // (D-F5); cleared on config switch. The grid owns the fold pipeline; the
            // parent just holds the flag map and relays toggles.
            folds: {},
            // WP-F · W104 — snippet library. Loaded once per load(); insertion +
            // ${CODE} resolution happen in the grid (D-F8).
            snippets: [],
            pendingSnippet: null,   // snippet id queued by the palette for the grid to insert
            snipManageOpen: false,  // manage-snippets scrim (managers only)
            snipEdit: null,         // {id, name, category, body, description} being edited | null
            snipBusy: false,
        });
        this.formulaRef = useRef("formulaInput");
        this.testFileRef = useRef("testFile");
        this.rawEditorRef = useRef("rawEditor");
        this.depCanvasRef = useRef("depCanvas");
        this._rawNeedsSeed = false;
        this._liveTimer = null;
        // Tools ▾ closes on any outside click; Esc closes the grid drawers.
        // Esc goes through the hotkey service — a plain window keydown listener
        // never fires because the service intercepts Escape at capture phase.
        useExternalListener(window, "mousedown", (ev) => {
            if (this.state.moreOpen && !ev.target.closest(".pbfs-more")) {
                this.state.moreOpen = false;
            }
            // W82 — the test-failures popover closes on any outside click.
            if (this.state.testsFailOpen && !ev.target.closest(".pbfs-testchip-wrap")) {
                this.state.testsFailOpen = false;
            }
        });
        useHotkey("escape", () => {
            if (this.state.shortcutsOpen) {          // W18 — front of the Escape ladder (D-F1)
                this.state.shortcutsOpen = false;
            } else if (this.state.snipManageOpen) {  // W104 — manage-snippets overlay
                this.closeSnipManage();
            } else if (this.state.paletteOpen) {
                this.state.paletteOpen = false;
            } else if (this.state.findOpen) {
                this.state.findOpen = false;
            } else if (this.state.testsFailOpen) {
                this.state.testsFailOpen = false;
            } else if (this.state.outlineDrawer || this.state.previewDrawer) {
                this.closeDrawers();
            } else if (this.state.moreOpen) {
                this.state.moreOpen = false;
            }
        }, { global: true, bypassEditableProtection: false });
        this._setupCommandLayer();   // WP-A: ⌘K palette, ⌘F find, hover-card listeners
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
        // Clear every pending debounce/open timer on unmount so a fired callback
        // never sets state on a destroyed component (W100 review finding — the
        // 350 ms hover-open timer was the reported case, but none of the studio's
        // debounce timers were being cleared).
        onWillUnmount(() => {
            for (const t of [this._hoverTimer, this._rawTimer, this._replayTimer,
                this._whatifTimer, this._liveTimer, this._testTimer, this._rateTimer]) {
                clearTimeout(t);
            }
        });
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
        // W82 — drop a stale test verdict when the user switches to another
        // config; a reload of the SAME config (after a save) keeps the chip.
        const prevCfgId = this.state.config && this.state.config.id;
        const d = await this.orm.call("pb.formula.studio", "get_studio_data", [configId || false]);
        this.state.empty = d.empty;
        this.state.configs = d.configs || [];
        this.state.canEdit = d.can_edit !== false;
        if (d.empty) { this.state.loaded = true; return; }
        if (prevCfgId && d.config && prevCfgId !== d.config.id) {
            this.state.tests = null;
            this.state.testsFailOpen = false;
            this.state.pinnedSamples = [];   // W4 — pins are per-config, client-session only
            this.state.previewExtra = {};
            this.state.folds = {};           // W8 — folds are per-config, client-session only
        }
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
        // W104 — snippet library (global; company-scoped server-side). Non-fatal.
        try {
            this.state.snippets = await this.orm.call("pb.formula.studio", "list_snippets", []);
        } catch (e) {
            this.state.snippets = [];
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
    // ---- W82 — tests-on-save chip -----------------------------------------
    // Fold a save RPC's `tests` payload into state; toast (danger) when tests
    // NEWLY fail (were clean/absent before, or the failure count grew). Called
    // AFTER load() so the config reload can't wipe the fresh verdict.
    _applyTests(tests) {
        if (!tests) return;
        const prev = this._lastTests || null;
        this.state.tests = tests;
        this._lastTests = tests;
        if (tests.has_tests && tests.failed > 0) {
            const wasClean = !prev || !prev.has_tests || !prev.failed;
            const grew = prev && prev.failed !== undefined && tests.failed > prev.failed;
            if (wasClean || grew) {
                const f = (tests.failures && tests.failures[0]) || null;
                const detail = f ? ` — ${f.sample}: ${f.code}` : "";
                this.notif.add(
                    `${tests.failed} sample test${tests.failed === 1 ? "" : "s"} failing${detail}`,
                    { type: "danger", title: "Tests failing" });
            }
        }
    }
    // Chip descriptor for the toolbar (null when no tests exist on this config).
    get testChip() {
        const t = this.state.tests;
        if (!t || !t.has_tests) return null;
        const kind = t.failed > 0 ? "fail" : "pass";
        return { kind, label: `${t.passed}/${t.total}`, failed: t.failed,
                 passed: t.passed, total: t.total };
    }
    toggleTestsFail() {
        const t = this.state.tests;
        if (!t || !t.failed) { this.openTests(); return; }
        this.state.testsFailOpen = !this.state.testsFailOpen;
    }
    // Jump from a failing chip/row into the Tests workbench for that sample.
    async openTestsFailure(sampleId) {
        this.state.testsFailOpen = false;
        await this.openTest();          // loads the Tests workbench + sets the view
        if (sampleId) this.state.testSampleId = sampleId;
    }
    async openTests() { this.state.testsFailOpen = false; await this.openTest(); }

    // ---- Grid Studio callbacks (T2.2/T2.3): save a formula and live-validate ----
    // Mirrors the inline editor's round-trip: save_formula → reload → recompute
    // the preview for the CURRENTLY selected sample (load() only computes sample[0]).
    async gridSaveFormula(ruleId, formula) {
        const cfgId = this.state.config.id;
        const sampleId = this.state.preview.sample_id;
        const r = await this.orm.call("pb.formula.studio", "save_formula", [ruleId, formula]);
        if (!r || !r.ok) { this.notif.add((r && r.msg) || "Could not save formula", { type: "warning" }); return; }
        await this.load(cfgId);
        this._applyTests(r.tests);
        if (sampleId) {
            this.state.preview = await this.orm.call("pb.formula.studio", "compute_preview", [cfgId, sampleId]);
        }
        await this._refreshPinned(cfgId);   // W4 — keep pinned sample rows in sync
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
        await this._refreshPinned(cfgId);   // W4
    }
    async gridTranslateFormula(ruleId, targetCols) {
        try { return await this.orm.call("pb.formula.studio", "translate_formula", [ruleId, targetCols]); }
        catch (e) { return []; }
    }
    // F111 — display-only reorder (letters frozen); refresh from the server so
    // the grid re-sorts by the new sequence.
    async gridReorder(dragId, beforeId) {
        if (this._lockedNotice()) return;
        const cfgId = this.state.config.id;
        try {
            const r = await this.orm.call("pb.formula.studio", "reorder_component", [cfgId, dragId, beforeId || false]);
            if (!r || !r.ok) { this.notif.add((r && r.msg) || "Reorder failed", { type: "warning" }); return; }
        } catch (e) { this.notif.add("Reorder failed", { type: "danger" }); return; }
        await this.load(cfgId);
    }
    async gridGroupByCategory() {
        if (this._lockedNotice()) return;
        const cfgId = this.state.config.id;
        try {
            const d = await this.orm.call("pb.formula.studio", "group_columns_by_category", [cfgId]);
            if (d && d.ok === false) { this.notif.add("Grouping failed", { type: "warning" }); return; }
            this.notif.add("Columns grouped by category", { type: "success" });
        } catch (e) { this.notif.add("Grouping failed", { type: "danger" }); return; }
        await this.load(cfgId);
    }
    async gridBulkSaveFormulas(items) {
        const cfgId = this.state.config.id;
        const sampleId = this.state.preview.sample_id;
        let r;
        try {
            r = await this.orm.call("pb.formula.studio", "bulk_save_formulas", [items]);
        } catch (e) { this.notif.add("Fill failed", { type: "warning" }); return; }
        this.notif.add(`Filled ${items.length} column${items.length === 1 ? "" : "s"}`, { type: "success" });
        await this.load(cfgId);
        this._applyTests(r && r.tests);
        if (sampleId) this.state.preview = await this.orm.call("pb.formula.studio", "compute_preview", [cfgId, sampleId]);
        await this._refreshPinned(cfgId);   // W4
    }

    // ==== WP-F · W4 — pinned sample rows ====================================
    // Extra display-only value rows in the grid: 2–3 samples side by side. Client
    // state only (D-F4); every formula save recomputes them alongside the active
    // preview via ONE Promise.all (C8 — per-save, never per-keystroke).
    _sampleNameOf(sid) { const s = this.state.samples.find(x => x.id === sid); return s ? s.name : "—"; }
    // Formatter used by the grid's extra rows — mirrors previewVal but reads a
    // supplied values map instead of state.preview.
    previewValFrom(col, values) {
        const v = values ? values[col] : undefined;
        return (v === undefined) ? "—" : this.fmtTyped(this.byCol(col), v);
    }
    // The prop the grid receives; excludes the active sample so it is never shown
    // twice (invariant: the active sample is never rendered as an extra).
    get extraPinnedPreviews() {
        const activeId = this.state.preview.sample_id;
        const out = [];
        for (const sid of this.state.pinnedSamples) {
            if (sid === activeId) continue;
            const ex = this.state.previewExtra[sid];
            out.push({ sample_id: sid, name: this._sampleNameOf(sid), values: (ex && ex.values) || {} });
        }
        return out;
    }
    // Can we pin the active sample? Need room (≤2) and a spare sample to keep
    // active afterwards (so active ∉ pinnedSamples stays true, D-F4).
    get canPinSample() {
        if (this.state.samples.length < 2 || this.state.pinnedSamples.length >= 2) return false;
        const sid = this.state.preview.sample_id;
        return this.state.samples.some(s => s.id !== sid && !this.state.pinnedSamples.includes(s.id));
    }
    // Pin the active sample and advance the active row to the next free sample, so
    // pinning gives immediate feedback (new pinned row + a fresh active row).
    async pinActiveSample() {
        const sid = this.state.preview.sample_id;
        if (!sid || this.state.pinnedSamples.includes(sid)) return;
        if (this.state.pinnedSamples.length >= 2) {
            this.notif.add("You can pin up to 2 extra sample rows", { type: "info" }); return;
        }
        const nextActive = this.state.samples.find(s => s.id !== sid && !this.state.pinnedSamples.includes(s.id));
        if (!nextActive) { this.notif.add("Add more sample data to pin another row", { type: "info" }); return; }
        const cfgId = this.state.config.id;
        // reuse the already-computed active values — no extra RPC for the pin itself
        this.state.pinnedSamples = [...this.state.pinnedSamples, sid];
        this.state.previewExtra = { ...this.state.previewExtra,
            [sid]: { sample_id: sid, values: { ...this.state.preview.values } } };
        this.state.preview = await this.orm.call("pb.formula.studio", "compute_preview", [cfgId, nextActive.id]);
    }
    unpinSample(sid) {
        this.state.pinnedSamples = this.state.pinnedSamples.filter(x => x !== sid);
        const ex = { ...this.state.previewExtra };
        delete ex[sid];
        this.state.previewExtra = ex;
    }
    // Recompute all pinned samples after a formula-changing save (D-F4). ONE
    // Promise.all; no-op when nothing is pinned.
    async _refreshPinned(cfgId) {
        const pins = this.state.pinnedSamples;
        if (!pins.length) return;
        const results = await Promise.all(pins.map(sid =>
            this.orm.call("pb.formula.studio", "compute_preview", [cfgId, sid])));
        const ex = {};
        pins.forEach((sid, i) => { ex[sid] = results[i]; });
        this.state.previewExtra = ex;
    }

    // ==== WP-F · W8 — collapse by category ==================================
    // The grid owns the fold pipeline + focus relocation; the parent just flips the
    // per-category flag (D-F5). formatSum below formats a summary Σ with vnd (D-F6).
    onToggleFold(catKey) {
        const folds = { ...this.state.folds };
        if (folds[catKey]) delete folds[catKey]; else folds[catKey] = true;
        this.state.folds = folds;
    }

    // ==== WP-F · W104 — snippet library =====================================
    // Insertion + ${CODE} resolution live in the grid (D-F8). From the palette we
    // just queue the snippet id and switch to the grid; the grid consumes it in
    // _afterPatch (starting an editor on the focused formula cell if needed).
    requestSnippetInsert(sid) {
        if (this.state.empty) return;
        if (this._lockedNotice()) return;   // read-only: say so, never a silent no-op
        if (this.state.view !== "grid") this.setView("grid");
        this.state.pendingSnippet = sid;
    }
    onSnippetConsumed() { this.state.pendingSnippet = null; }

    // ---- manage overlay (managers only) ----
    openSnipManage() {
        if (this._lockedNotice()) return;   // managers only (same guard as other writes)
        this.state.snipManageOpen = true;
        this.state.snipEdit = null;
    }
    closeSnipManage() { this.state.snipManageOpen = false; this.state.snipEdit = null; }
    newSnippet() { this.state.snipEdit = { id: null, name: "", category: "other", body: "", description: "" }; }
    editSnippet(s) { this.state.snipEdit = { id: s.id, name: s.name, category: s.category, body: s.body, description: s.description }; }
    cancelSnipEdit() { this.state.snipEdit = null; }
    onSnipField(field, ev) { if (this.state.snipEdit) this.state.snipEdit[field] = ev.target.value; }
    get snipCategories() {
        return [["proration", "Proration"], ["cap", "Cap / floor"], ["bracket", "Bracket / rate table"],
                ["rounding", "Rounding"], ["other", "Other"]];
    }
    async saveSnippet() {
        const e = this.state.snipEdit;
        if (!e || this.state.snipBusy) return;
        if (!(e.name || "").trim() || !(e.body || "").trim()) {
            this.notif.add("A snippet needs a name and a body", { type: "warning" }); return;
        }
        this.state.snipBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "save_snippet", [{
                id: e.id || false, name: e.name, category: e.category,
                body: e.body, description: e.description,
            }]);
            if (!r || !r.ok) { this.notif.add((r && r.msg) || "Could not save snippet", { type: "warning" }); return; }
            this.state.snippets = await this.orm.call("pb.formula.studio", "list_snippets", []);
            this.state.snipEdit = null;
            this.notif.add("Snippet saved", { type: "success" });
        } catch (err) {
            this.notif.add("Could not save snippet", { type: "danger" });
        } finally {
            this.state.snipBusy = false;
        }
    }
    async deleteSnippet(s) {
        if (this.state.snipBusy) return;
        this.state.snipBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "delete_snippet", [s.id]);
            if (!r || !r.ok) { this.notif.add((r && r.msg) || "Could not delete snippet", { type: "warning" }); return; }
            this.state.snippets = await this.orm.call("pb.formula.studio", "list_snippets", []);
            if (this.state.snipEdit && this.state.snipEdit.id === s.id) this.state.snipEdit = null;
        } catch (err) {
            this.notif.add("Could not delete snippet", { type: "danger" });
        } finally {
            this.state.snipBusy = false;
        }
    }

    // ==== WP-A — Studio Command Layer (W14 find · W99 palette · W100 hover) ====

    // D-A4 — one shared search index, rebuilt only when state.components is
    // replaced wholesale (identity compared by array reference, which load()
    // always swaps). W14 filters it, W99 fuzzy-scores it, W100 resolves against it.
    get searchIndex() {
        const comps = this.state.components;
        if (this._searchIndexSrc !== comps) {
            this._searchIndexSrc = comps;
            this._searchIndex = comps.map(c => {
                const formula = c.type === "formula" ? (c.excel_formula || "")
                    : c.type === "constant" ? String(c.constant_value ?? "") : "";
                return {
                    id: c.id, col: c.col, code: c.code || "", name: c.name || "",
                    category: c.category || "", type: c.type, formula,
                    is_valid: c.is_valid !== false,
                    _code: (c.code || "").toLowerCase(), _name: (c.name || "").toLowerCase(),
                    _cat: (c.category || "").toLowerCase(), _formula: formula.toLowerCase(),
                    _col: (c.col || "").toLowerCase(),
                };
            });
        }
        return this._searchIndex;
    }

    // ---- W14 find & replace ----
    openFind() { if (this.state.empty) return; this.state.paletteOpen = false; this.state.findOpen = true; }
    closeFind() { this.state.findOpen = false; }
    // Commit checked + valid hits through the extended bulk_save_formulas
    // (reason='bulk', note = the find/replace summary). One batch → N version rows.
    async findCommit(items, note) {
        if (!items || !items.length) return { ok: false, saved: 0 };
        if (this._lockedNotice()) return { ok: false };
        const cfgId = this.state.config.id;
        const sampleId = this.state.preview.sample_id;
        let r;
        try {
            r = await this.orm.call("pb.formula.studio", "bulk_save_formulas", [items, "bulk", note]);
        } catch (e) { this.notif.add("Replace failed", { type: "warning" }); return { ok: false }; }
        await this.load(cfgId);
        this._applyTests(r && r.tests);
        if (sampleId) this.state.preview = await this.orm.call("pb.formula.studio", "compute_preview", [cfgId, sampleId]);
        await this._refreshPinned(cfgId);   // W4
        return r || { ok: true };
    }
    // A code/name hit → jump to the component and open its rename flow. Codes are
    // referential identities (C5) — never string-replaced.
    findRename(id) {
        this.state.findOpen = false;
        this.setView("cards");
        this.selectComponent(id);
        requestAnimationFrame(() => this.startRename());
    }
    // A formula hit → reveal the component in the grid.
    findJump(id) {
        this.selectComponent(id);
        if (this.state.view !== "grid") this.setView("grid");
        requestAnimationFrame(() => this.selectComponent(id));   // re-run scroll after the view swap mounts
    }

    // ---- W99 command palette ----
    openPalette() { if (this.state.empty) return; this.state.findOpen = false; this.state.paletteOpen = true; }
    closePalette() { this.state.paletteOpen = false; }
    // Registry-driven descriptors; every run() calls an existing method (no new RPC).
    get paletteCommands() {
        const cmds = [];
        const add = (id, section, label, keywords, run, sublabel) => cmds.push({ id, section, label, keywords, run, sublabel });
        add("view.cards", "Views", "Cards view", "cards components overview", () => this.setView("cards"));
        add("view.grid", "Views", "Grid view", "grid spreadsheet table", () => this.setView("grid"));
        add("view.test", "Views", "Tests view", "tests samples validate check", () => this.setView("test"));
        add("view.compare", "Views", "Compare periods", "compare periods payrun delta difference month", () => this.openCompare());
        add("view.settings", "Views", "Settings", "settings configuration setup", () => this.setView("settings"));
        add("view.shortcuts", "Views", "Keyboard shortcuts", "keyboard shortcuts hotkeys keys help ?", () => this.openShortcuts());
        if (this.state.canEdit) add("act.new", "Actions", "New component", "add new create column", () => this.addComponentQuick());
        if (this.state.canEdit) add("act.import", "Actions", "Import from Excel…", "import excel upload spreadsheet workbook", () => this.importExcelInto());
        add("act.find", "Actions", "Find & replace", "find search replace formula", () => this.openFind());
        add("act.release", "Actions", "Release preview", "release sign-off bundle approve", () => this.openReleases());
        add("act.problems", "Actions", "Problems", "problems lint errors warnings", () => this.openProblems());
        add("act.ai", "Actions", "PayAI assistant", "ai assistant copilot chat", () => this.openAI());
        if (this.selected) add("act.explain", "Actions", "Explain " + this.selected.code, "explain formula describe", () => this.openExplain());
        if (this.state.canEdit) add("act.snipmanage", "Actions", "Manage snippets…", "snippet library manage create edit delete", () => this.openSnipManage());
        // W104 — Snippets section: insert a reusable fragment into the focused cell
        for (const s of this.state.snippets) {
            add("snip." + s.id, "Snippets", s.name, "snippet " + (s.category || "") + " " + (s.name || "").toLowerCase(),
                () => this.requestSnippetInsert(s.id), s.description || s.category);
        }
        for (const c of this.searchIndex) {
            add("cmp." + c.id, "Components", c.col + " · " + c.code, c._code + " " + c._name + " " + c._col,
                () => this.findJump(c.id), c.name);
        }
        for (const cfg of this.state.configs) {
            if (cfg.id === (this.state.config && this.state.config.id)) continue;
            add("cfg." + cfg.id, "Configs", cfg.name, "config switch " + (cfg.name || "").toLowerCase(), () => this.pickConfig(cfg.id));
        }
        return cmds;
    }

    // ---- W100 hover cards (pure client-side, zero RPC) ----
    _hoverTargetEl(el) {
        return el && el.closest && el.closest(
            "[data-hover-comp],[data-hover-col],.g2-chead[data-col-id],.g2-cell.g2-formula[data-col-id],.ol-item[data-col],.fchip.fref[data-hover-col]");
    }
    _onHoverMove(ev) {
        const t = this._hoverTargetEl(ev.target);
        if (!t) { this._killHover(); return; }
        let comp = null;
        const cid = t.getAttribute("data-hover-comp") || t.getAttribute("data-col-id");
        if (cid) comp = this.state.components.find(c => c.id === parseInt(cid, 10));
        if (!comp) {
            const col = t.getAttribute("data-hover-col") || t.getAttribute("data-col");
            if (col) comp = this.byCol(col);
        }
        if (!comp) { this._killHover(); return; }
        if (this.state.hoverCard && this.state.hoverCard.compId === comp.id) return;
        clearTimeout(this._hoverTimer);
        const r = t.getBoundingClientRect();
        this._hoverPending = { compId: comp.id, x: r.left, y: r.bottom + 6 };
        this._hoverTimer = setTimeout(() => {
            if (this._hoverPending) this.state.hoverCard = this._hoverPending;   // 350 ms open delay (D-A6)
        }, 350);
    }
    _killHover() {
        clearTimeout(this._hoverTimer);
        this._hoverPending = null;
        if (this.state.hoverCard) this.state.hoverCard = null;
    }
    get hoverCardData() {
        const h = this.state.hoverCard;
        if (!h) return null;
        const c = this.state.components.find(x => x.id === h.compId);
        if (!c) return null;
        return {
            name: c.name, code: c.code, col: c.col, category: c.category || "", type: c.type,
            tokens: c.type === "formula" ? this.chips(c.excel_formula || "") : [],
            constant: c.type === "constant" ? String(c.constant_value ?? "") : "",
            value: this.previewVal(c.col),
            valid: c.is_valid !== false,
            message: c.validation_message || "",
        };
    }
    get hoverCardStyle() {
        const h = this.state.hoverCard;
        if (!h) return "";
        const w = 320, x = Math.max(8, Math.min(h.x, window.innerWidth - w - 8));
        const y = Math.max(8, Math.min(h.y, window.innerHeight - 200));
        return `left:${Math.round(x)}px; top:${Math.round(y)}px;`;
    }

    // Registered once from setup() (hooks must run synchronously in setup).
    _setupCommandLayer() {
        useHotkey("control+k", () => this.openPalette(), { global: true, bypassEditableProtection: true });
        useHotkey("control+f", () => this.openFind(), { global: true, bypassEditableProtection: true });
        // Odoo folds Cmd(meta) into the "control" token on macOS (hotkey_service
        // lines 76-77), so a single registration covers ⌘K/⌘F and Ctrl+K/Ctrl+F.
        useExternalListener(window, "mouseover", (ev) => this._onHoverMove(ev));
        useExternalListener(window, "scroll", () => this._killHover(), { capture: true });
        useExternalListener(window, "keydown", () => this._killHover());
        // W18 (D-F1) — "?" opens the shortcuts overlay. A window keydown (not a
        // useHotkey token: shifted-punctuation parsing is layout-dependent) guarded
        // so it never fires while typing in any field or while another modal is up.
        useExternalListener(window, "keydown", (ev) => this._onGlobalHelpKey(ev));
        // Escape must close the overlay even when the grid scroller has focus: the
        // grid's navigator consumes Escape (clear-selection + stopPropagation,
        // grid_studio.js onKeydown), so the bubble-phase hotkey ladder never fires
        // on that path. Capture phase runs first; only intercept while the overlay
        // (always the topmost layer) is actually open.
        useExternalListener(window, "keydown", (ev) => {
            if (ev.key === "Escape" && this.state.shortcutsOpen) {
                ev.preventDefault();
                ev.stopPropagation();
                this.closeShortcuts();
            }
        }, { capture: true });
    }
    _onGlobalHelpKey(ev) {
        if (ev.key !== "?" || this.state.shortcutsOpen) return;
        const t = ev.target, tag = t && t.tagName;
        if (t && (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || t.isContentEditable)) return;
        if (this.state.paletteOpen || this.state.findOpen || this.state.aiOpen || this.state.snipManageOpen) return;
        ev.preventDefault();
        this.openShortcuts();
    }

    // ---- W18 shortcuts overlay ----
    openShortcuts() { this.state.paletteOpen = false; this.state.shortcutsOpen = true; }
    closeShortcuts() { this.state.shortcutsOpen = false; }
    // Command-layer rows are DERIVED from paletteCommands (binding-per-row, D-F2) so
    // the ⌘F row matches the real Find command; the grid rows are the static table.
    get shortcutSections() {
        const find = this.paletteCommands.find(c => c.id === "act.find");
        const cmd = [
            { keys: ["⌘/Ctrl", "K"], label: "Command palette" },
            { keys: ["⌘/Ctrl", "F"], label: (find && find.label) || "Find & replace" },
            { keys: ["?"], label: "Keyboard shortcuts (this panel)" },
            { keys: ["Esc"], label: "Close palette · find · drawers" },
        ];
        return [{ title: "Command layer", rows: cmd }, ...SHORTCUT_GRID];
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
        this._applyTests(r.tests);
        if (sampleId) this.state.preview = await this.orm.call("pb.formula.studio", "compute_preview", [cfgId, sampleId]);
        await this._refreshPinned(cfgId);   // W4
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

    // ---- Release bundles + sign-off (B3) ----
    openReleases() {
        this.state.releaseOpen = true;
        this.state.releaseTab = "pending";
        this.state.releaseData = null;
        this.state.releaseDetail = null;
        this.state.releaseExpandId = null;
        this._loadReleasePreview();
        this._loadReleaseList();
    }
    closeReleases() { this.state.releaseOpen = false; }
    setReleaseTab(t) { this.state.releaseTab = t; }
    async _loadReleasePreview() {
        this.state.releaseBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "release_preview", [this.state.config.id]);
            this.state.releaseData = r;
            this.state.releaseNarrative = (r && r.narrative) || "";
        } catch (e) { this.state.releaseData = { ok: false }; }
        finally { this.state.releaseBusy = false; }
    }
    async _loadReleaseList() {
        try {
            const r = await this.orm.call("pb.formula.studio", "list_releases", [this.state.config.id]);
            this.state.releaseList = (r && r.releases) || [];
            this.state.releaseLatestId = (r && r.latest_id) || false;
        } catch (e) { this.state.releaseList = []; this.state.releaseLatestId = false; }
    }
    onReleaseNarrative(ev) { this.state.releaseNarrative = ev.target.value; }
    reasonLabel(reason) {
        return { edit: "edited", bulk: "bulk edit", fill: "drag-fill", import: "import",
                 restore: "restored", rename: "renamed", lifecycle: "lifecycle" }[reason] || reason;
    }
    async approveRelease() {
        if (this._lockedNotice()) return;
        if (this.state.releaseBusy) return;
        this.state.releaseBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "release_approve",
                [this.state.config.id, this.state.releaseNarrative]);
            if (!r || !r.ok) { this.notif.add((r && r.msg) || "Could not sign off the release", { type: "warning" }); return; }
            this.notif.add(`Release sealed · ${r.change_count} component${r.change_count === 1 ? "" : "s"}`, { type: "success" });
            await this._loadReleasePreview();
            await this._loadReleaseList();
            this.state.releaseTab = "history";
        } catch (e) {
            this.notif.add("Sign-off failed", { type: "danger" });
        } finally {
            this.state.releaseBusy = false;
        }
    }
    async toggleReleaseDetail(rel) {
        if (this.state.releaseExpandId === rel.id) {
            this.state.releaseExpandId = null;
            this.state.releaseDetail = null;
            return;
        }
        this.state.releaseExpandId = rel.id;
        this.state.releaseDetail = null;
        try {
            const r = await this.orm.call("pb.formula.studio", "release_detail", [rel.id]);
            if (this.state.releaseExpandId === rel.id) this.state.releaseDetail = r;
        } catch (e) { this.state.releaseDetail = { changes: [] }; }
    }

    // ---- W86 — one-action rollback (revert the latest release atomically) ----
    async openRollback(rel) {
        if (this._lockedNotice()) return;
        this.state.rollbackOpen = true;
        this.state.rollbackData = null;
        this.state.rollbackConfirm = "";
        this.state.rollbackSimResult = null;
        this.state.rollbackSimId = null;
        this.state.rollbackBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "rollback_preview", [rel.id]);
            this.state.rollbackData = r;
        } catch (e) { this.state.rollbackData = { ok: false }; }
        finally { this.state.rollbackBusy = false; }
    }
    closeRollback() {
        this.state.rollbackOpen = false;
        const id = this.state.rollbackSimId;   // discard the transient sim — no residue
        this.state.rollbackSimId = null;
        this.state.rollbackSimResult = null;
        if (id) this.orm.call("pb.formula.studio", "simulate_drop", [id], {}, { silent: true }).catch(() => {});
    }
    onRollbackConfirm(ev) { this.state.rollbackConfirm = ev.target.value; }
    get rollbackConfirmOk() {
        const d = this.state.rollbackData;
        return !!(d && d.release && this.state.rollbackConfirm.trim() === d.release.name);
    }
    async runRollbackSim() {
        const d = this.state.rollbackData;
        if (!d || !d.release) return;
        const CHUNK = 100;
        this.state.rollbackSimBusy = true;
        this.state.rollbackSimProgress = 0;
        this.state.rollbackSimResult = null;
        try {
            const prep = await this.orm.call("pb.formula.studio", "rollback_simulate_prepare",
                [d.release.id, null], {}, { silent: true });
            if (!prep || prep.ok === false || !prep.sim_id) {
                this.notif.add((prep && prep.msg) || "No historical payslips to simulate against", { type: "warning" });
                return;
            }
            this.state.rollbackSimId = prep.sim_id;
            const ids = prep.payslip_ids || [];
            if (!ids.length) { this.state.rollbackSimResult = { empty: true }; return; }
            for (let i = 0; i < ids.length; i += CHUNK) {
                await this.orm.call("pb.formula.studio", "simulate_batch",
                    [{ sim_id: prep.sim_id, payslip_ids: ids.slice(i, i + CHUNK) }], {}, { silent: true });
                this.state.rollbackSimProgress = Math.round(100 * Math.min(i + CHUNK, ids.length) / ids.length);
                if (!this.state.rollbackOpen) return;   // user closed → abandon
            }
            const res = await this.orm.call("pb.formula.studio", "simulate_result", [prep.sim_id], {}, { silent: true });
            if (this.state.rollbackOpen) this.state.rollbackSimResult = (res && res.result) || null;
        } catch (e) {
            this.notif.add("Simulation failed", { type: "danger" });
        } finally { this.state.rollbackSimBusy = false; }
    }
    async applyRollback() {
        const d = this.state.rollbackData;
        if (!d || !d.release || !this.rollbackConfirmOk) return;
        if (this.state.rollbackApplying) return;
        this.state.rollbackApplying = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "rollback_apply", [d.release.id]);
            if (!r || !r.ok) { this.notif.add((r && r.msg) || "Rollback failed", { type: "danger" }); return; }
            this.notif.add(`Rolled back · ${r.restored} component${r.restored === 1 ? "" : "s"} restored`, { type: "success" });
            this.closeRollback();
            await this.load(this.state.config.id);   // formulas/constants changed everywhere
            this._applyTests(r.tests);
            await this._loadReleasePreview();
            await this._loadReleaseList();
        } catch (e) {
            this.notif.add("Rollback failed", { type: "danger" });
        } finally { this.state.rollbackApplying = false; }
    }

    // ---- Bureau cockpit (B6) ----
    openBureau() {
        this.state.bureauOpen = true;
        this.state.bureauData = null;
        this._loadBureau();
    }
    closeBureau() { this.state.bureauOpen = false; }
    async _loadBureau() {
        this.state.bureauBusy = true;
        try {
            this.state.bureauData = await this.orm.call("pb.formula.studio", "bureau_board", []);
        } catch (e) { this.state.bureauData = { ok: false, cards: [] }; }
        finally { this.state.bureauBusy = false; }
    }
    async bureauOpenConfig(card) {
        this.state.bureauOpen = false;
        await this.load(card.id);
        this.state.view = "cards";
    }
    async bureauClone(card) {
        if (this._lockedNotice()) return;
        const r = await this.orm.call("pb.formula.studio", "bureau_clone", [card.id]);
        if (!r || !r.ok) { this.notif.add((r && r.msg) || "Clone failed", { type: "warning" }); return; }
        this.notif.add(`Cloned as “${r.name}”`, { type: "success" });
        await this._loadBureau();
    }
    bureauCycleLabel(ct) {
        return { mid_cycle: "Mid-cycle", end_cycle: "End-cycle", full_final: "Full & Final", regular: "Regular" }[ct] || ct;
    }
    bureauStateLabel(s) {
        return { draft: "Draft", testing: "Testing", validated: "Validated", active: "Active", archived: "Archived" }[s] || s;
    }
    get bureauSummary() {
        const cards = (this.state.bureauData && this.state.bureauData.cards) || [];
        return {
            configs: cards.length,
            active: cards.filter(c => c.state === "active").length,
            withErrors: cards.filter(c => (c.problem_counts.error || 0) > 0).length,
            withPending: cards.filter(c => c.pending_changes > 0).length,
            employees: cards.reduce((a, c) => a + (c.employees || 0), 0),
        };
    }

    // ---- Legislation packs (B4) ----
    openLegislation() {
        this.state.legisOpen = true;
        this.state.legisSel = null;
        this.state.legisDetail = null;
        this.state.legisCoverage = null;
        this._loadLegisPacks();
    }
    closeLegislation() { this.state.legisOpen = false; }
    async _loadLegisPacks() {
        this.state.legisBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "legislation_packs", []);
            this.state.legisPacks = (r && r.packs) || [];
            this.state.legisCanEdit = !!(r && r.can_edit);
            // keep the current selection on refresh; on first open land on the
            // pack that needs a rollout, else the first one
            const cur = this.state.legisSel;
            const pick = (cur && this.state.legisPacks.find(p => p.id === cur))
                || this.state.legisPacks.find(p => p.drift > 0)
                || this.state.legisPacks[0];
            if (pick) await this.legisSelect(pick.id);
        } catch (e) { this.state.legisPacks = []; }
        finally { this.state.legisBusy = false; }
    }
    async legisSelect(packId) {
        this.state.legisSel = packId;
        this.state.legisDetail = null;
        this.state.legisCoverage = null;
        try {
            const [detail, cov] = await Promise.all([
                this.orm.call("pb.formula.studio", "legislation_detail", [packId]),
                this.orm.call("pb.formula.studio", "legislation_coverage", [packId]),
            ]);
            if (this.state.legisSel !== packId) return;   // superseded by a newer click
            this.state.legisDetail = detail;
            this.state.legisCoverage = cov;
        } catch (e) { /* keep the panes empty */ }
    }
    legisStateLabel(s) { return { draft: "Draft", published: "Published", superseded: "Superseded" }[s] || s; }
    // format a statutory value by its number_format (percentage ×100, else ₫)
    legisVal(fmt, v) {
        if (v === null || v === undefined || isNaN(v)) return "—";
        if (fmt === "percentage") return (Math.round(v * 10000) / 100).toLocaleString("en-US") + "%";
        if (fmt === "integer") return Math.round(v).toLocaleString("en-US");
        if (fmt === "number") return (Math.round(v * 100) / 100).toLocaleString("en-US");
        return "₫" + Math.round(v).toLocaleString("en-US");
    }
    get legisSelPack() {
        return (this.state.legisPacks || []).find(p => p.id === this.state.legisSel) || null;
    }
    get legisDriftConfigs() {
        const b = this.state.legisCoverage && this.state.legisCoverage.board;
        return (b || []).filter(x => x.status === "drift");
    }
    async legisApplyOne(configId) {
        if (this._lockedNotice()) return;
        if (this.state.legisApplying) return;
        this.state.legisApplying = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "legislation_apply",
                [this.state.legisSel, configId]);
            if (!r || !r.ok) { this.notif.add((r && r.msg) || "Apply failed", { type: "warning" }); return; }
            this.notif.add(`Applied · ${r.total_changed} value${r.total_changed === 1 ? "" : "s"} updated`, { type: "success" });
            await this.legisSelect(this.state.legisSel);
            await this._afterLegisApply(configId);
        } catch (e) { this.notif.add("Apply failed", { type: "danger" }); }
        finally { this.state.legisApplying = false; }
    }
    async legisApplyAll() {
        if (this._lockedNotice()) return;
        if (this.state.legisApplying) return;
        const ids = this.legisDriftConfigs.map(x => x.config_id);
        if (!ids.length) return;
        this.state.legisApplying = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "legislation_apply",
                [this.state.legisSel, false, ids]);
            if (!r || !r.ok) { this.notif.add((r && r.msg) || "Roll-out failed", { type: "warning" }); return; }
            this.notif.add(`Rolled out to ${r.configs_touched} config${r.configs_touched === 1 ? "" : "s"} · ${r.total_changed} values updated`, { type: "success" });
            await this.legisSelect(this.state.legisSel);
            await this._afterLegisApply(null);
        } catch (e) { this.notif.add("Roll-out failed", { type: "danger" }); }
        finally { this.state.legisApplying = false; }
    }
    async _afterLegisApply(configId) {
        // refresh the pack coverage roll-ups; reload the open config if it changed
        await this._loadLegisPacks();
        if (configId && this.state.config && this.state.config.id === configId) {
            await this.load(configId);
        }
    }

    // ---- Config branches (B2) ----
    openBranches() {
        this.state.branchOpen = true;
        this.state.branchDiff = null;
        this.state.branchExpandId = null;
        this.state.branchNewName = "";
        this.state.branchNewNote = "";
        this._loadBranches();
    }
    closeBranches() { this.state.branchOpen = false; }
    async _loadBranches() {
        this.state.branchBusy = true;
        try {
            this.state.branchData = await this.orm.call("pb.formula.studio", "list_branches", [this.state.config.id]);
        } catch (e) { this.state.branchData = { ok: false, branches: [] }; }
        finally { this.state.branchBusy = false; }
    }
    onBranchName(ev) { this.state.branchNewName = ev.target.value; }
    onBranchNote(ev) { this.state.branchNewNote = ev.target.value; }
    get branchParentId() {
        // branch the mainline: if we're viewing a branch, its parent is the target
        const cfg = this.state.branchData && this.state.branchData.config;
        return (cfg && cfg.is_branch) ? cfg.parent_id : (cfg ? cfg.id : this.state.config.id);
    }
    async createBranch() {
        if (this._lockedNotice()) return;
        if (this.state.branchCreating) return;
        this.state.branchCreating = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "branch_create",
                [this.branchParentId, this.state.branchNewName, this.state.branchNewNote]);
            if (!r || !r.ok) { this.notif.add((r && r.msg) || "Could not create branch", { type: "warning" }); return; }
            this.notif.add(`Branch “${r.name}” created`, { type: "success" });
            this.state.branchNewName = ""; this.state.branchNewNote = "";
            await this._loadBranches();
        } catch (e) { this.notif.add("Branch creation failed", { type: "danger" }); }
        finally { this.state.branchCreating = false; }
    }
    async toggleBranchDiff(b) {
        if (this.state.branchExpandId === b.id) {
            this.state.branchExpandId = null; this.state.branchDiff = null; return;
        }
        this.state.branchExpandId = b.id;
        this.state.branchDiff = null;
        try {
            const r = await this.orm.call("pb.formula.studio", "branch_diff", [b.id]);
            if (this.state.branchExpandId === b.id) this.state.branchDiff = r;
        } catch (e) { this.state.branchDiff = { ok: false }; }
    }
    async openBranchConfig(b) {
        this.state.branchOpen = false;
        await this.load(b.id);
        this.state.view = "cards";
    }
    async openParentConfig() {
        const cfg = this.state.branchData && this.state.branchData.config;
        if (!cfg || !cfg.parent_id) return;
        this.state.branchOpen = false;
        await this.load(cfg.parent_id);
        this.state.view = "cards";
    }
    async mergeBranch(b) {
        if (this._lockedNotice()) return;
        if (this.state.branchBusy) return;
        this.state.branchBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "branch_merge", [b.id]);
            if (!r || !r.ok) { this.notif.add((r && r.msg) || "Merge failed", { type: "warning" }); return; }
            let msg = `Merged ${r.merged} change${r.merged === 1 ? "" : "s"} into ${r.parent_name}`;
            if (r.conflicts) msg += ` · ${r.conflicts} conflict${r.conflicts === 1 ? "" : "s"} (branch won)`;
            this.notif.add(msg, { type: "success" });
            this.state.branchExpandId = null; this.state.branchDiff = null;
            await this._loadBranches();
        } catch (e) { this.notif.add("Merge failed", { type: "danger" }); }
        finally { this.state.branchBusy = false; }
    }
    async discardBranch(b) {
        if (this._lockedNotice()) return;
        const r = await this.orm.call("pb.formula.studio", "branch_discard", [b.id]);
        if (!r || !r.ok) { this.notif.add((r && r.msg) || "Discard failed", { type: "warning" }); return; }
        this.notif.add(`Branch “${b.name}” discarded`, { type: "info" });
        if (this.state.branchExpandId === b.id) { this.state.branchExpandId = null; this.state.branchDiff = null; }
        await this._loadBranches();
    }

    // ---- Scheme variants (B5) ----
    openVariants() {
        this.state.variantOpen = true;
        this.state.variantDiff = null;
        this.state.variantExpandId = null;
        this.state.variantNewName = "";
        this._loadVariants();
    }
    closeVariants() { this.state.variantOpen = false; }
    async _loadVariants() {
        this.state.variantBusy = true;
        try {
            this.state.variantData = await this.orm.call("pb.formula.studio", "list_variants", [this.state.config.id]);
        } catch (e) { this.state.variantData = { ok: false, variants: [] }; }
        finally { this.state.variantBusy = false; }
    }
    onVariantName(ev) { this.state.variantNewName = ev.target.value; }
    get variantMasterId() {
        const d = this.state.variantData;
        return (d && d.master) ? d.master.id : this.state.config.id;
    }
    async createVariant() {
        if (this._lockedNotice()) return;
        if (this.state.variantCreating) return;
        this.state.variantCreating = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "variant_create",
                [this.variantMasterId, this.state.variantNewName]);
            if (!r || !r.ok) { this.notif.add((r && r.msg) || "Could not create variant", { type: "warning" }); return; }
            this.notif.add(`Variant “${r.name}” created`, { type: "success" });
            this.state.variantNewName = "";
            await this._loadVariants();
        } catch (e) { this.notif.add("Variant creation failed", { type: "danger" }); }
        finally { this.state.variantCreating = false; }
    }
    async toggleVariantDiff(v) {
        if (this.state.variantExpandId === v.id) { this.state.variantExpandId = null; this.state.variantDiff = null; return; }
        this.state.variantExpandId = v.id;
        this.state.variantDiff = null;
        try {
            const r = await this.orm.call("pb.formula.studio", "variant_diff", [v.id]);
            if (this.state.variantExpandId === v.id) this.state.variantDiff = r;
        } catch (e) { this.state.variantDiff = { ok: false }; }
    }
    async _refreshVariantDiff(v) {
        if (this.state.variantExpandId === v.id) {
            this.state.variantDiff = await this.orm.call("pb.formula.studio", "variant_diff", [v.id]);
        }
    }
    async openVariantConfig(v) {
        this.state.variantOpen = false;
        await this.load(v.id);
        this.state.view = "cards";
    }
    async openMasterConfig() {
        const d = this.state.variantData;
        if (!d || !d.master) return;
        this.state.variantOpen = false;
        await this.load(d.master.id);
        this.state.view = "cards";
    }
    async syncVariant(v) {
        if (this._lockedNotice()) return;
        if (this.state.variantSyncing) return;
        this.state.variantSyncing = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "variant_sync", [v.id]);
            if (!r || !r.ok) { this.notif.add((r && r.msg) || "Sync failed", { type: "warning" }); return; }
            this.notif.add(`Synced ${r.synced} component${r.synced === 1 ? "" : "s"} · ${r.preserved} override${r.preserved === 1 ? "" : "s"} kept`, { type: "success" });
            await this._refreshVariantDiff(v);
            await this._loadVariants();
        } catch (e) { this.notif.add("Sync failed", { type: "danger" }); }
        finally { this.state.variantSyncing = false; }
    }
    async pushToVariants() {
        if (this._lockedNotice()) return;
        if (this.state.variantSyncing) return;
        this.state.variantSyncing = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "variant_push", [this.variantMasterId]);
            if (!r || !r.ok) { this.notif.add((r && r.msg) || "Push failed", { type: "warning" }); return; }
            this.notif.add(`Pushed to ${r.variants} variant${r.variants === 1 ? "" : "s"} · ${r.total_synced} update${r.total_synced === 1 ? "" : "s"}`, { type: "success" });
            this.state.variantExpandId = null; this.state.variantDiff = null;
            await this._loadVariants();
        } catch (e) { this.notif.add("Push failed", { type: "danger" }); }
        finally { this.state.variantSyncing = false; }
    }
    async toggleOverride(v, row) {
        if (this._lockedNotice()) return;
        const turnOn = !row.overridden;
        const r = await this.orm.call("pb.formula.studio", "variant_toggle_override", [v.id, row.code, turnOn]);
        if (!r || !r.ok) { this.notif.add((r && r.msg) || "Could not change override", { type: "warning" }); return; }
        this.notif.add(turnOn ? `“${row.name}” protected from sync` : `“${row.name}” now inherits from master`, { type: "info" });
        await this._refreshVariantDiff(v);
        await this._loadVariants();
    }
    async detachVariant(v) {
        if (this._lockedNotice()) return;
        const r = await this.orm.call("pb.formula.studio", "variant_detach", [v.id]);
        if (!r || !r.ok) { this.notif.add((r && r.msg) || "Detach failed", { type: "warning" }); return; }
        this.notif.add(`“${v.name}” detached — now a standalone config`, { type: "info" });
        if (this.state.variantExpandId === v.id) { this.state.variantExpandId = null; this.state.variantDiff = null; }
        await this._loadVariants();
    }

    // ---- Client review shares (B7) ----
    openShare() {
        this.state.shareOpen = true;
        this.state.shareNewClient = "";
        this.state.shareNewRelease = false;
        this.state.shareCopied = null;
        this._loadShares();
    }
    closeShare() { this.state.shareOpen = false; }
    async _loadShares() {
        this.state.shareBusy = true;
        try {
            this.state.shareData = await this.orm.call("pb.formula.studio", "list_review_shares", [this.state.config.id]);
        } catch (e) { this.state.shareData = { ok: false, shares: [] }; }
        finally { this.state.shareBusy = false; }
    }
    onShareClient(ev) { this.state.shareNewClient = ev.target.value; }
    onShareRelease(ev) { this.state.shareNewRelease = ev.target.value ? parseInt(ev.target.value) : false; }
    async createShare() {
        if (this._lockedNotice()) return;
        if (this.state.shareCreating) return;
        this.state.shareCreating = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "create_review_share",
                [this.state.config.id, this.state.shareNewRelease, this.state.shareNewClient, ""]);
            if (!r || !r.ok) { this.notif.add((r && r.msg) || "Could not create link", { type: "warning" }); return; }
            this.notif.add("Review link created", { type: "success" });
            this.state.shareNewClient = "";
            await this._loadShares();
            this._copyShare(r.share);
        } catch (e) { this.notif.add("Failed to create link", { type: "danger" }); }
        finally { this.state.shareCreating = false; }
    }
    async _copyShare(s) {
        try {
            await navigator.clipboard.writeText(s.url);
            this.state.shareCopied = s.token;
            this.notif.add("Link copied to clipboard", { type: "info" });
        } catch (e) { /* clipboard unavailable — the field is selectable */ }
    }
    copyShare(s) { this._copyShare(s); }
    async revokeShare(s) {
        if (this._lockedNotice()) return;
        const r = await this.orm.call("pb.formula.studio", "revoke_review_share", [s.id]);
        if (!r || !r.ok) { this.notif.add((r && r.msg) || "Revoke failed", { type: "warning" }); return; }
        this.notif.add("Link revoked", { type: "info" });
        await this._loadShares();
    }
    shareStatusLabel(st) {
        return { active: "Active", viewed: "Viewed", signed: "Signed off", revoked: "Revoked", expired: "Expired" }[st] || st;
    }

    // ---- Dependency map (B9) — full-screen graph navigation ----
    openDepMap() {
        this.state.depFocus = null;
        this.state.depHidden = [];
        this.state.depCriticalOn = false;
        this.state.depZoom = 1;
        this.state.depPan = { x: 0, y: 0 };
        this._depFocusSet = null;
        this._buildDepMap();
        this.state.depOpen = true;
        requestAnimationFrame(() => this.fitDepMap());
    }
    closeDepMap() { this.state.depOpen = false; }

    _buildDepMap() {
        const g = this.state.graph || {};
        const raw = g.nodes || [];
        const nodes = raw.map((n) => {
            const c = this.byCol(n.col);
            return {
                id: n.id, col: n.col, code: n.code, name: n.name,
                type: c ? c.type : "formula", group: c ? c.group : "Earnings",
                valid: n.is_valid, onslip: n.appears_on_payslip,
                x: 0, y: 0, w: 160, h: 46, layer: 0,
            };
        });
        const byCol = {};
        nodes.forEach((n) => (byCol[n.col] = n));
        const edges = (g.edges || []).filter((e) => byCol[e[0]] && byCol[e[1]]);
        const incoming = {};
        nodes.forEach((n) => (incoming[n.col] = []));
        edges.forEach(([a, b]) => incoming[b].push(a));
        // longest-path layering: inputs/constants at 0, formulas walk execution order
        const layer = {};
        nodes.forEach((n) => (layer[n.col] = 0));
        const order = (g.execution_order || []).filter((c) => byCol[c]);
        order.forEach((col) => {
            let mx = -1;
            incoming[col].forEach((dep) => (mx = Math.max(mx, layer[dep] || 0)));
            layer[col] = mx + 1;
        });
        // any formula left out of the topo order (cycle remnant) still gets placed
        nodes.forEach((n) => {
            if (n.type === "formula" && !order.includes(n.col)) {
                let mx = 0;
                incoming[n.col].forEach((dep) => (mx = Math.max(mx, (layer[dep] || 0) + 1)));
                layer[n.col] = Math.max(layer[n.col], mx);
            }
        });
        const NW = 160, NH = 46, GX = 78, GY = 16;
        const layerMap = {};
        nodes.forEach((n) => {
            n.layer = layer[n.col];
            (layerMap[n.layer] = layerMap[n.layer] || []).push(n);
        });
        const keys = Object.keys(layerMap).map(Number).sort((a, b) => a - b);
        let maxRows = 1;
        keys.forEach((k) => (maxRows = Math.max(maxRows, layerMap[k].length)));
        const fullH = maxRows * (NH + GY);
        keys.forEach((k, li) => {
            const col = layerMap[k].sort((a, b) => {
                const go = GROUPS.indexOf(a.group) - GROUPS.indexOf(b.group);
                return go !== 0 ? go : this.colToNum(a.col) - this.colToNum(b.col);
            });
            const h = col.length * (NH + GY);
            const oy = (fullH - h) / 2;
            col.forEach((n, ri) => {
                n.x = 32 + li * (NW + GX);
                n.y = 32 + oy + ri * (NH + GY);
                n.w = NW; n.h = NH;
            });
        });
        this._depW = 64 + Math.max(1, keys.length) * (NW + GX) - GX;
        this._depH = 64 + fullH;
        this._depByCol = byCol;
        this._depCycleCols = new Set((g.cycles || []).flatMap((cy) => cy.cols || []));
        this.state.depNodes = nodes;
        this.state.depEdges = edges;
        this.state.depCritical = this._criticalPath(nodes, incoming, layer);
    }

    _criticalPath(nodes, incoming, layer) {
        const ordered = [...nodes].sort((a, b) => layer[a.col] - layer[b.col]);
        const best = {}, prev = {};
        ordered.forEach((n) => {
            best[n.col] = 1; prev[n.col] = null;
            (incoming[n.col] || []).forEach((dep) => {
                if ((best[dep] || 0) + 1 > best[n.col]) { best[n.col] = best[dep] + 1; prev[n.col] = dep; }
            });
        });
        let end = null, mx = -1;
        // prefer a payslip output as the endpoint when tied
        nodes.forEach((n) => {
            const b = best[n.col] + (n.onslip ? 0.5 : 0);
            if (b > mx) { mx = b; end = n.col; }
        });
        const path = [];
        let cur = end;
        while (cur) { path.unshift(cur); cur = prev[cur]; }
        return path;
    }

    // ---- dep-map derived getters + classes ----
    get depStats() {
        const layers = new Set(this.state.depNodes.map((n) => n.layer));
        return {
            nodes: this.state.depNodes.length,
            edges: this.state.depEdges.length,
            depth: layers.size,
            critical: this.state.depCritical.length,
            cycles: (this.state.graph.cycles || []).length,
        };
    }
    get depGroupsPresent() {
        const seen = new Set(this.state.depNodes.map((n) => n.group));
        return GROUPS.filter((gname) => seen.has(gname));
    }
    depGroupCount(gname) { return this.state.depNodes.filter((n) => n.group === gname).length; }
    _depCritSet() { return new Set(this.state.depCritical); }
    _depCritEdge(a, b) {
        const p = this.state.depCritical;
        for (let i = 0; i < p.length - 1; i++) if (p[i] === a && p[i + 1] === b) return true;
        return false;
    }
    depHiddenGroup(gname) { return this.state.depHidden.includes(gname); }
    toggleDepGroup(gname) {
        const h = this.state.depHidden;
        this.state.depHidden = h.includes(gname) ? h.filter((x) => x !== gname) : [...h, gname];
    }
    toggleDepCritical() { this.state.depCriticalOn = !this.state.depCriticalOn; }
    setDepFocus(n) {
        if (this.state.depFocus === n.col) { this.state.depFocus = null; this._depFocusSet = null; return; }
        this.state.depFocus = n.col;
        this._depFocusSet = new Set([n.col, ...this.upstreamOf(n.col), ...this.downstreamOf(n.col)]);
    }
    clearDepFocus() { this.state.depFocus = null; this._depFocusSet = null; }
    openFromMap(n) {
        this.state.depOpen = false;
        if (this.byCol(n.col)) { this.state.view = "cards"; this.selectComponent(n.id); }
    }
    depNodeCls(n) {
        const cls = ["dep-node", "dg-" + this.catKey(n.group)];
        if (!n.valid) cls.push("invalid");
        if (this._depCycleCols && this._depCycleCols.has(n.col)) cls.push("cycle");
        if (this.state.depCriticalOn && this._depCritSet().has(n.col)) cls.push("crit");
        if (this.state.depHidden.includes(n.group)) cls.push("ghost");
        if (this.state.depFocus) {
            if (n.col === this.state.depFocus) cls.push("focus");
            else if (this._depFocusSet && this._depFocusSet.has(n.col)) cls.push("lit");
            else cls.push("dim");
        }
        return cls.join(" ");
    }
    depEdgeCls(e) {
        const cls = ["dep-edge"];
        const a = this._depByCol[e[0]], b = this._depByCol[e[1]];
        if (this._depCycleCols && this._depCycleCols.has(e[0]) && this._depCycleCols.has(e[1])) cls.push("cycle");
        if (this.state.depCriticalOn && this._depCritEdge(e[0], e[1])) cls.push("crit");
        if (this.state.depHidden.includes(a && a.group) || this.state.depHidden.includes(b && b.group)) cls.push("ghost");
        if (this.state.depFocus) {
            if (this._depFocusSet && this._depFocusSet.has(e[0]) && this._depFocusSet.has(e[1])) cls.push("lit");
            else cls.push("dim");
        }
        return cls.join(" ");
    }
    depEdgePath(e) {
        const a = this._depByCol[e[0]], b = this._depByCol[e[1]];
        if (!a || !b) return "";
        const x1 = a.x + a.w, y1 = a.y + a.h / 2;
        const x2 = b.x, y2 = b.y + b.h / 2;
        const dx = Math.max(28, Math.abs(x2 - x1) * 0.45);
        return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
    }
    depClip(name) { return (name && name.length > 20) ? name.slice(0, 19) + "…" : (name || ""); }
    get depViewBox() { return `0 0 ${this._depW || 100} ${this._depH || 100}`; }
    get depTransform() { return `translate(${this.state.depPan.x},${this.state.depPan.y}) scale(${this.state.depZoom})`; }

    // ---- pan / zoom ----
    fitDepMap() {
        const el = this.depCanvasRef && this.depCanvasRef.el;
        if (!el || !this._depW) return;
        const cw = el.clientWidth, ch = el.clientHeight;
        const s = Math.min(cw / this._depW, ch / this._depH, 1.4) * 0.94;
        this.state.depZoom = s;
        this.state.depPan = { x: (cw - this._depW * s) / 2, y: (ch - this._depH * s) / 2 };
    }
    depZoomBy(f) {
        const el = this.depCanvasRef && this.depCanvasRef.el;
        const cw = el ? el.clientWidth / 2 : 400, ch = el ? el.clientHeight / 2 : 300;
        const z0 = this.state.depZoom, z1 = Math.min(2.2, Math.max(0.15, z0 * f));
        // keep the viewport centre fixed
        this.state.depPan = {
            x: cw - (cw - this.state.depPan.x) * (z1 / z0),
            y: ch - (ch - this.state.depPan.y) * (z1 / z0),
        };
        this.state.depZoom = z1;
    }
    depZoomIn() { this.depZoomBy(1.2); }
    depZoomOut() { this.depZoomBy(1 / 1.2); }
    onDepWheel(ev) { this.depZoomBy(ev.deltaY < 0 ? 1.1 : 1 / 1.1); }
    onDepDown(ev) {
        if (ev.target.closest && ev.target.closest(".dep-node")) return; // let node clicks through
        this.state.depDragging = true;
        this._depPanStart = { x: ev.clientX - this.state.depPan.x, y: ev.clientY - this.state.depPan.y };
    }
    onDepMove(ev) {
        if (!this.state.depDragging) return;
        this.state.depPan = { x: ev.clientX - this._depPanStart.x, y: ev.clientY - this._depPanStart.y };
    }
    onDepUp() { this.state.depDragging = false; }

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
            this._applyTests(r.tests);
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
    // Cycle the active sample among the NON-pinned samples so a pinned sample is
    // never also the active one (W4 invariant, D-F4).
    async cycleSample() {
        const avail = this.state.samples.filter(s => !this.state.pinnedSamples.includes(s.id));
        if (avail.length < 2) return;
        const idx = avail.findIndex(s => s.id === this.state.preview.sample_id);
        const next = avail[(idx + 1) % avail.length];   // idx === -1 → first available
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
    // ---- W97 — period comparison view ----
    async openCompare() {
        if (this.state.empty) return;
        this.state.view = "compare";
        this.state.cmpResult = null;
        this.state.cmpId = null;
        this.state.cmpBusy = false;
        this.state.cmpProgress = 0;
        this.state.cmpMoversOpen = false;
        await this._loadCompareRuns();
    }
    async _loadCompareRuns() {
        try {
            const r = await this.orm.call("pb.formula.studio", "compare_runs", [this.state.config.id]);
            this.state.cmpRuns = (r && r.runs) || [];
            this.state.cmpCurrency = (r && r.currency) || "";
            if (this.state.cmpRuns.length >= 2) {
                this.state.cmpB = this.state.cmpRuns[0].id;    // newest period = B (the "after")
                this.state.cmpA = this.state.cmpRuns[1].id;    // prior period  = A (the "before")
            } else { this.state.cmpA = null; this.state.cmpB = null; }
        } catch (e) { this.state.cmpRuns = []; }
    }
    onCmpPick(side, ev) {
        const v = parseInt(ev.target.value, 10) || null;
        if (side === "a") this.state.cmpA = v; else this.state.cmpB = v;
    }
    async runCompare() {
        if (!this.state.cmpA || !this.state.cmpB) { this.notif.add("Pick two periods to compare", { type: "warning" }); return; }
        if (this.state.cmpA === this.state.cmpB) { this.notif.add("Pick two different periods", { type: "warning" }); return; }
        const CHUNK = 100;
        this.state.cmpBusy = true;
        this.state.cmpProgress = 0;
        this.state.cmpResult = null;
        this.state.cmpMoversOpen = false;
        this.state.cmpNarrate = null;
        try {
            const prep = await this.orm.call("pb.formula.studio", "compare_prepare",
                [this.state.config.id, this.state.cmpA, this.state.cmpB], {}, { silent: true });
            if (!prep || prep.ok === false || !prep.cmp_id) {
                this.notif.add((prep && prep.msg) || "Comparison failed", { type: "warning" });
                return;
            }
            this.state.cmpId = prep.cmp_id;
            const pairs = prep.pairs || [];
            if (!pairs.length) { this.state.cmpResult = { empty: true, matched: 0 }; return; }
            for (let i = 0; i < pairs.length; i += CHUNK) {
                await this.orm.call("pb.formula.studio", "compare_batch",
                    [{ cmp_id: prep.cmp_id, pairs: pairs.slice(i, i + CHUNK) }], {}, { silent: true });
                this.state.cmpProgress = Math.round(100 * Math.min(i + CHUNK, pairs.length) / pairs.length);
                if (this.state.view !== "compare") return;   // user navigated away → abandon
            }
            const res = await this.orm.call("pb.formula.studio", "compare_result",
                [prep.cmp_id], {}, { silent: true });
            if (this.state.view === "compare") this.state.cmpResult = (res && res.result) || null;
        } catch (e) {
            this.notif.add("Comparison failed", { type: "danger" });
        } finally { this.state.cmpBusy = false; }
    }
    cmpSetSort(key) {
        if (this.state.cmpSort === key) this.state.cmpSortDir = -this.state.cmpSortDir;
        else { this.state.cmpSort = key; this.state.cmpSortDir = -1; }
    }
    get cmpComponents() {
        const r = this.state.cmpResult;
        if (!r || !r.components) return [];
        const key = this.state.cmpSort || "delta";
        const dir = this.state.cmpSortDir || -1;
        const arr = r.components.slice();
        arr.sort((a, b) => {
            if (key === "code") return dir * String(a.code).localeCompare(String(b.code));
            return dir * (Math.abs(a[key] ?? 0) - Math.abs(b[key] ?? 0));
        });
        return arr;
    }
    get cmpMaxDelta() {
        const r = this.state.cmpResult;
        if (!r || !r.components) return 0;
        let m = 0;
        for (const c of r.components) m = Math.max(m, Math.abs(c.delta || 0));
        return m;
    }
    // delta-pct heat tint: 0..0.16 alpha green (up) / red (down)
    cmpHeat(delta) {
        const m = this.cmpMaxDelta;
        if (!m || !delta) return "";
        const a = Math.min(0.16, 0.16 * Math.abs(delta) / m).toFixed(3);
        return delta > 0 ? `background: rgba(15,138,99,${a});` : `background: rgba(220,38,38,${a});`;
    }
    toggleCmpMovers() { this.state.cmpMoversOpen = !this.state.cmpMoversOpen; }
    // W48 — narrate the finished comparison (deterministic floor, LLM polish when keyed)
    async openNarrate() {
        if (!this.state.cmpId || this.state.cmpNarrateBusy) return;
        this.state.cmpNarrateBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "narrate_comparison",
                [this.state.cmpId, this.state.cmpNarrateLang], {}, { silent: true });
            this.state.cmpNarrate = (r && r.ok) ? r : null;
            if (!this.state.cmpNarrate) this.notif.add("Could not narrate this comparison", { type: "warning" });
        } catch (e) {
            this.notif.add("Narration failed", { type: "warning" });
        } finally { this.state.cmpNarrateBusy = false; }
    }
    async setNarrateLang(lang) {
        if (this.state.cmpNarrateLang === lang) return;
        this.state.cmpNarrateLang = lang;
        if (this.state.cmpNarrate) await this.openNarrate();   // re-narrate in the new language
    }
    copyNarrate() {
        const t = ((this.state.cmpNarrate && this.state.cmpNarrate.blocks) || []).join("\n");
        if (t && navigator.clipboard) {
            navigator.clipboard.writeText(t).then(() => this.notif.add("Narrative copied", { type: "success" }));
        }
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
        // W83 — coverage strip: one extra RPC per load (not per-sample).
        this.state.testCoverage = await this.orm.call(
            "pb.formula.studio", "get_test_coverage", [this.state.config.id]);
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
    toggleTestGen() {
        this.state.testGenOpen = !this.state.testGenOpen;
        if (!this.state.testGenOpen) this.state.genMode = null;
    }
    // W83 — coverage strip
    toggleCoverage() { this.state.coverageOpen = !this.state.coverageOpen; }
    coverageJump(ruleId) { this.state.coverageOpen = false; this.findJump(ruleId); }
    // W84 — boundary-value generation panel (inside the Generate dropdown)
    backToGenMenu() { this.state.genMode = null; }
    async openBoundaryPanel() {
        this.state.genMode = "boundary";
        this.state.boundaryResult = null;
        this.state.boundaryBusy = true;
        this.state.boundaryCands = null;
        const r = await this.orm.call("pb.formula.studio", "boundary_candidates", [this.state.config.id]);
        this.state.boundaryBusy = false;
        this.state.boundaryCands = (r && r.ok) ? r : { candidates: [], reachable: 0, unreachable: 0 };
        // default: all reachable edges checked
        this.state.boundaryPicks = this.state.boundaryCands.candidates.filter(c => c.reachable).map(c => c.key);
        if (this.state.boundaryBase === null) {
            const first = this.state.test.samples[0];
            this.state.boundaryBase = first ? first.id : null;
        }
    }
    toggleBoundaryPick(key) {
        const p = this.state.boundaryPicks, i = p.indexOf(key);
        if (i >= 0) p.splice(i, 1); else p.push(key);
    }
    setBoundaryBase(ev) { const v = parseInt(ev.target.value, 10); this.state.boundaryBase = isNaN(v) ? null : v; }
    async runBoundaryGen() {
        const picks = (this.state.boundaryCands.candidates || [])
            .filter(c => c.reachable && this.state.boundaryPicks.includes(c.key));
        if (!picks.length) { this.notif.add("Select at least one reachable edge.", { type: "warning" }); return; }
        this.state.boundaryBusy = true;
        const r = await this.orm.call("pb.formula.studio", "generate_boundary_samples",
            [this.state.config.id, picks, this.state.boundaryBase]);
        this.state.boundaryBusy = false;
        if (!r || !r.ok) { this.notif.add((r && r.msg) || "Could not generate", { type: "warning" }); return; }
        this.state.boundaryResult = { created: r.created, skipped: r.skipped, capped: r.capped };
        const summary = `${r.created} created` + (r.skipped ? `, ${r.skipped} skipped` : "") + (r.capped ? `, ${r.capped} over cap` : "");
        this.notif.add(`Boundary samples: ${summary}`, { type: r.created ? "success" : "info" });
        await this.loadTestData(true);   // refresh samples + coverage strip
        if (r.created) {
            const gen = this.state.test.samples.filter(s => s.source_type === "generated");
            const last = gen[gen.length - 1];
            if (last) { this.state.testGenOpen = false; this.state.genMode = null; await this.selectSample(last.id); }
        }
    }
    // W84 — confirm characterization baselines (unconfirmed → chip-neutral until confirmed)
    get hasUnconfirmed() { return (this.state.test.samples || []).some(s => s.expected_confirmed === false); }
    async confirmBaseline(id) {
        const r = await this.orm.call("pb.formula.studio", "confirm_sample_expected", [id]);
        if (!r || !r.ok) { this.notif.add((r && r.msg) || "Could not confirm", { type: "warning" }); return; }
        this.state.testDetail = r; this._syncSampleVerdict(r); this._applyTests(r.tests);
        this.notif.add("Baseline confirmed", { type: "success" });
    }
    async confirmAllBaselines() {
        const r = await this.orm.call("pb.formula.studio", "confirm_all_samples", [this.state.config.id]);
        if (!r || !r.ok) { this.notif.add((r && r.msg) || "Could not confirm", { type: "warning" }); return; }
        this.state.test.samples = r.samples; this._applyTests(r.tests);
        if (this.state.testSampleId) await this.loadSampleDetail(this.state.testSampleId);
        this.notif.add(`${r.confirmed} baseline${r.confirmed === 1 ? "" : "s"} confirmed`, { type: "success" });
    }
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
        if (s) { s.verdict = detail.verdict; s.has_expected = detail.has_expected; s.expected_confirmed = detail.expected_confirmed; }
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
        // keep the W4 invariant (active ∉ pinnedSamples): jumping to a pinned sample unpins it
        this.state.pinnedSamples = this.state.pinnedSamples.filter(x => x !== this.state.testSampleId);
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
            this._applyTests(r.tests);
            await this._refreshPinned(this.state.config.id);   // W4
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
    pickTemplate(key) {
        this.state.wizardForm.template = key;
        // keep the config country in lock-step with the picked template — an
        // SG structure must never be created as a VN config (currency,
        // employee matching and legislation targeting all key off it)
        const t = this.state.wizardTemplates.find((x) => x.key === key);
        if (t && t.country) { this.state.wizardForm.country_code = t.country; }
    }
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
