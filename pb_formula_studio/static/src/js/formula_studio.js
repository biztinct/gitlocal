/** @odoo-module **/

import { Component, useState, useRef, useEffect, useExternalListener, onWillStart, onMounted, onPatched, onWillUnmount, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { loadPDFJSAssets } from "@web/core/utils/pdfjs";
import { GridStudio } from "./grid/grid_studio";
import { MappingCanvas } from "./mapping/mapping_canvas";
import { FindReplace } from "./grid/find_replace";
import { CommandPalette } from "./palette/command_palette";
import { HoverCard } from "./hover_card";
import { DocDrop } from "@biz_doc_ocr/js/doc_drop";
import {
    applyPayslipTableBorder,
    deletePayslipTable,
    deletePayslipTableColumn,
    deletePayslipTableRow,
    insertPayslipTableColumn,
    insertPayslipTableRow,
    mergePayslipTableCellDown,
    mergePayslipTableCellRight,
    payslipTableContext,
    splitPayslipTableCell,
} from "./payslip_table_tools";
// IA Cycle 4 — the ONE Studio change this cycle makes. Arriving here from the
// Settings hub's cog path used to be a one-way trip: the Studio renders no
// control panel, so there is no Odoo breadcrumb, and nothing in it said where
// the user had come from. `hubBack` reads the `pb_back` the caller wrote into
// the action context and returns null when nobody sent one — so the chip is
// ABSENT on every other route rather than inert (W5/W29), and nothing else in
// this file or its templates changes.
// `openHub` joins them in Integrations Cycle 2: the mapping overlay grows one
// quiet link OUT to the full-screen Mapping Studio, and a link that hands over
// a board has to hand over a return door with it (W5).
import { HubBackChip, hubBack, openHub } from "@pb_hub/js/hub_nav";
import { _t } from "@web/core/l10n/translation";

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
    static components = { CfgCombo, GridStudio, MappingCanvas, FindReplace, CommandPalette, HoverCard, HubBackChip, DocDrop };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.dialog = useService("dialog");
        // Read ONCE, from props, never written back — the arrival protocol's
        // rule since Cycle 1. Null unless a caller passed `pb_back`.
        this.back = hubBack(this.props);
        this.state = useState({
            loaded: false,
            empty: false,
            canEdit: true,
            view: "cards",
            config: {},
            configs: [],
            // Command Center — visual tool launcher ("Tools" button / ⌘K)
            cmdOpen: false, cmdQuery: "", cmdActive: 0,
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
            simplifyData: null,      // W54 — {ok, suggestions:[]}
            simplifyBusy: null,      // rule_id currently applying
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
            // W65 — mapping templates
            tmplMode: null,          // null | "save" | "apply"
            tmplName: "",            // save: template name
            tmplList: [],            // apply: visible templates
            tmplBusy: false,
            tmplResult: null,        // apply summary {applied, skipped_existing, unmatched_sources, unmatched_targets}
            // F9 — payslip studio
            psOpen: false,
            psBusy: false,
            psData: null,            // {ok, config, sections, tray, samples, sample_id, colors, can_edit}
            psLang: "en",            // en | vi label lens
            psDragId: null,          // rule id currently dragged
            psOverComp: null,        // rule id being hovered during a drag (insert-before)
            psOverZone: null,        // section id or 'tray' currently hovered
            psEditSec: null,         // section id whose title is inline-editing
            psThemeOpen: false,      // W73 — theme panel open
            psLogoV: 0,              // W73 — logo cache-buster (bumped on upload/clear)
            psImportOpen: false,     // uploaded payslip → reviewed layout draft
            psImportBusy: false,
            psImportDraft: null,
            psImportError: "",
            psImportApplyTheme: true,
            psImportApplyContent: true,
            psImportApplyLayout: true,
            psDeleteOpen: false,     // guarded removal of imported / section template
            psDeleteKind: null,      // imported | section
            psDeleteBusy: false,
            psRichOpen: false,       // header / section / footer rich-content editor
            psRichTarget: null,
            psRichTitle: "",
            psRichDraft: "",
            psRichBusy: false,
            psRichQuery: "",
            psRichMode: "both",     // label | value | both
            psRichUsedIds: [],
            psRichUsedMetaKeys: [],
            psRichTableActive: false,
            psRichTableLabel: "",
            psRichBorderScope: "table", // table | cell
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
            // Config Switcher — WOW gallery selector + health board
            // (supersedes both the old dropdown AND the Bureau cockpit)
            configSwitcherOpen: false,
            csBoard: null,       // {cards, can_edit, company} from bureau_board
            csBusy: false,
            csCloningId: null,
            csQuery: "",
            csCountry: "",
            csState: "",
            csCycle: "",
            csDivision: "",
            csSort: "attention",   // attention | recent | name | health
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
            // W95 (WP-H) — budget-vs-actual mode of the compare view
            cmpMode: "period",        // "period" | "budget"
            budgets: [],              // budgets for the picked config
            budgetSel: null,          // chosen budget id (side A in budget mode)
            budgetCanEdit: false,
            budgetEditOpen: false,
            budgetEdit: null,         // {id,name,period_label,note,rows[],orphans[]}
            budgetBusy: false,
            budgetSeedRun: null,      // run id chosen in the seed-from-run picker
            // W98 (WP-H) — offer calculator overlay
            offerOpen: false,
            offerInputs: [],          // [{code,col,name,value}]
            offerSamples: [],
            offerResult: null,        // {rows, net_code, net_value, subtotals}
            offerCurrency: "",
            offerBusy: false,
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
            // W49 — AI-proposed profiles
            aiProps: null,         // accepted proposals [{name, inputs, rationale}]
            aiPicks: [],           // selected proposal indices
            aiRejected: [],        // [{name, reason}]
            aiBusy: false,
            aiError: "",
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
        this._psRichNeedsSeed = false;
        this._psRichNativeRemoveClick = (ev) => this._psRichRemoveTokenFromEvent(ev);
        this._liveTimer = null;
        this._offerTimer = null;   // W98 — debounced offer recompute
        this._offerToken = 0;      // monotonic supersede token (C8)
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
            } else if (this.state.cmdOpen) {          // Command Center overlay
                this.closeCommand();
            } else if (this.state.offerOpen) {        // W98 — offer calculator overlay
                this.closeOfferCalc();
            } else if (this.state.budgetEditOpen) {  // W95 — budget editor overlay
                this.closeBudgetEditor();
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
        // Command Center — autofocus its search box whenever it opens
        this.cmdInputRef = useRef("cmdInput");
        useEffect(() => {
            if (this.state.cmdOpen && this.cmdInputRef.el) this.cmdInputRef.el.focus();
        }, () => [this.state.cmdOpen]);
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
            const openWiz = (a.params && a.params.open_wizard) || (a.context && a.context.open_wizard);
            if (cfgId) {
                if (!this.state.config || this.state.config.id !== cfgId) await this.load(cfgId);
                if ((a.params && a.params.open_settings) || (a.context && a.context.open_settings)) {
                    await this.openSettings();
                }
            } else if (!openWiz && !this.state.empty) {
                // Fresh entry (left-menu "Formula Engine" / dashboard) with no target
                // config → land on the Payroll-configurations picker so the user
                // chooses which scheme to open. Skip the option for the wizard flow
                // and when there are no configs yet (the build panel shows instead).
                this.openConfigSwitcher();
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
            // The contenteditable document is intentionally browser-owned.
            // Updating the reactive Used badges can nevertheless make OWL
            // reconcile its nominally empty editor node. Restore the captured
            // draft only when that reconciliation changed the live DOM; when it
            // did not, leave the nodes and current caret completely untouched.
            if (this._psRichNeedsSeed && this.state.psRichOpen) {
                const richEditor = this._psRichEditor();
                if (richEditor && richEditor.innerHTML !== this.state.psRichDraft) {
                    richEditor.innerHTML = this.state.psRichDraft || "";
                    this._psRichRange = null;
                    this._psRichCellEl = null;
                }
                if (richEditor) this._psRichBindTokenControls(richEditor);
                this._psRichNeedsSeed = false;
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

    // ==== WP-L · W17 — smart paste from Excel ==============================
    // The grid sends the raw pasted run; ONE server ladder normalizes each cell
    // to the canonical row-2 form AND validates it (D-L5). The ghost shows
    // exactly what a commit will store — no preview/commit divergence (S-I1).
    async gridStagePaste(entries) {
        // A thrown RPC must surface as an error, not as "n of n can't be
        // pasted" (C7) — rethrow so the grid's catch shows its danger toast.
        const r = await this.orm.call("pb.formula.studio", "stage_paste",
            [this.state.config.id, entries]);
        return (r && r.entries) || [];
    }
    // All-or-nothing commit through ONE bulk_save_formulas (reason='bulk',
    // note='smart paste') — N formulas → N version rows, one reason (C4/D-L6).
    async gridPasteCommit(items) {
        if (!items || !items.length) return;
        if (this._lockedNotice()) return;
        const cfgId = this.state.config.id;
        const sampleId = this.state.preview.sample_id;
        let r;
        try {
            r = await this.orm.call("pb.formula.studio", "bulk_save_formulas",
                [items, "bulk", "smart paste"]);
        } catch (e) { this.notif.add("Paste failed", { type: "warning" }); return; }
        const saved = (r && r.saved) != null ? r.saved : items.length;
        this.notif.add(`Pasted ${saved} formula${saved === 1 ? "" : "s"}`, { type: "success" });
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
        add("view.budget", "Views", "Compare vs budget", "budget variance vs actual target plan compare", () => this.openCompareBudget());
        add("act.offer", "Actions", "Offer calculator", "offer calculator hypothetical hire net breakdown simulate salary", () => this.openOfferCalc());
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

    // ---- Command Center (visual tool launcher; "Tools" button / ⌘K) ----
    openCommand() {
        if (this.state.empty) return;
        this.state.paletteOpen = false;
        this.state.findOpen = false;
        this.state.cmdQuery = "";
        this.state.cmdActive = 0;
        this.state.cmdOpen = true;
    }
    closeCommand() { this.state.cmdOpen = false; }
    setCmdQuery(ev) { this.state.cmdQuery = ev.target.value; this.state.cmdActive = 0; }
    // Run a tool then close. The run() is deferred to the next frame so the
    // Command Center overlay fully unmounts FIRST — launching in the same tick
    // raced the closing overlay against the tool's own overlay render, and some
    // tools set non-reactive instance state in their open* method (e.g. the
    // dep-map's _depByCol) that the combined render then read before it applied.
    // Deferring makes a card-launch behave exactly like a direct toolbar click.
    runCommand(tool) {
        this.closeCommand();
        if (tool && tool.run) requestAnimationFrame(() => tool.run());
    }
    // Hand off to the full text palette (components, configs, snippets…).
    cmdToPalette() { this.closeCommand(); this.openPalette(); }
    onCmdKey(ev) {
        const flat = this.commandView.flat;
        if (ev.key === "Enter") {
            ev.preventDefault();
            if (flat.length) this.runCommand(flat[Math.min(this.state.cmdActive, flat.length - 1)]);
            return;
        }
        if (!flat.length) return;
        if (ev.key === "ArrowDown" || ev.key === "ArrowRight") {
            ev.preventDefault();
            this.state.cmdActive = (this.state.cmdActive + 1) % flat.length;
        } else if (ev.key === "ArrowUp" || ev.key === "ArrowLeft") {
            ev.preventDefault();
            this.state.cmdActive = (this.state.cmdActive - 1 + flat.length) % flat.length;
        }
    }
    // Lanes of tools rendered as cards. Live stats come straight from state.
    get commandLanes() {
        const cfg = this.state.config || {};
        const T = (key, name, desc, icon, accent, run, stat) => ({ key, name, desc, icon, accent, run, stat: stat || null });
        return [
            { id: "analyze", label: "Analyze", tools: [
                T("replay", "Execution replay", "Watch a payslip compute step by step", "replay", "blue", () => this.openReplay()),
                T("whatif", "What-if", "Slide a rate and project the payroll cost", "whatif", "teal", () => this.openWhatif()),
                T("depmap", "Dependency map", "The whole configuration as a graph", "depmap", "blue", () => this.openDepMap()),
                T("offer", "Offer calculator", "Type hypothetical inputs, see the full breakdown", "offer", "green", () => this.openOfferCalc()),
            ] },
            { id: "design", label: "Design", tools: [
                T("payslip", "Payslip Studio", "Design the payslip layout", "payslip", "indigo", () => this.openPayslip()),
                T("mapping", "Mapping canvas", "Map cycle carryover, API, import and scheme fields onto your components", "mapping", "pink", () => this.openMapping()),
                T("rates", "Rate tables", "PIT brackets and other rate tables", "rates", "amber", () => this.openRates(), this.state.rateTables.length || null),
                T("export", "Export workbook", "Download the config as a living Excel file with real formulas", "export", "teal", () => this.exportLivingWorkbook()),
            ] },
            { id: "govern", label: "Govern", tools: [
                T("problems", "Problems", "Lint checks and rename-refactor", "problems", "rose", () => this.openProblems(), this.problemCount || null),
                T("branches", "Branches", "Fork this config, trial a change, merge back", "branches", "blue", () => this.openBranches(), cfg.branch_count || null),
                T("variants", "Variants", "One master scheme, many synced variants", "variants", "teal", () => this.openVariants(), cfg.variant_count || null),
                T("legislation", "Legislation", "Roll a statutory change across every configuration", "legislation", "amber", () => this.openLegislation()),
                T("releases", "Releases", "Review and sign off formula changes", "releases", "green", () => this.openReleases()),
            ] },
            { id: "collab", label: "Collaborate", tools: [
                T("share", "Share for review", "A read-only link for your client", "share", "blue", () => this.openShare()),
                T("payai", "Ask PayAI", "Describe a rule in plain English and let AI draft it", "payai", "indigo", () => this.openAI()),
            ] },
        ];
    }
    // Query-filtered lanes + a flat list carrying a global index (fi) for keyboard nav.
    get commandView() {
        const q = (this.state.cmdQuery || "").trim().toLowerCase();
        const lanes = [];
        let i = 0;
        for (const l of this.commandLanes) {
            const tools = (q ? l.tools.filter(t => (t.name + " " + t.desc).toLowerCase().includes(q)) : l.tools)
                .map(t => ({ ...t, fi: i++ }));
            if (tools.length) lanes.push({ ...l, tools });
        }
        const flat = [];
        lanes.forEach(l => l.tools.forEach(t => flat.push(t)));
        return { lanes, flat };
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
        useHotkey("control+k", () => this.openCommand(), { global: true, bypassEditableProtection: true });
        // ⌘⇧K keeps the full text palette (components, configs, snippets…) one chord away.
        useHotkey("control+shift+k", () => this.openPalette(), { global: true, bypassEditableProtection: true });
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

    // ---- Config Switcher health board (folds in the old Bureau cockpit) ----
    async _loadCsBoard() {
        this.state.csBusy = true;
        try {
            this.state.csBoard = await this.orm.call("pb.formula.studio", "bureau_board", []);
        } catch (e) { this.state.csBoard = { ok: false, cards: [], can_edit: false, company: "" }; }
        finally { this.state.csBusy = false; }
    }
    async csClone(card, ev) {
        if (ev) ev.stopPropagation();
        if (this._lockedNotice()) return;
        this.state.csCloningId = card.id;
        try {
            const r = await this.orm.call("pb.formula.studio", "bureau_clone", [card.id]);
            if (!r || !r.ok) { this.notif.add((r && r.msg) || "Clone failed", { type: "warning" }); return; }
            this.notif.add(`Cloned as “${r.name}”`, { type: "success" });
            await this._loadCsBoard();
        } finally { this.state.csCloningId = null; }
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
        const m = this._depByCol || {};
        const a = m[e[0]], b = m[e[1]];
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
        const m = this._depByCol;
        if (!m) return "";
        const a = m[e[0]], b = m[e[1]];
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
        if (this.state.cmpMode === "budget") await this._loadBudgets();
    }
    async openCompareBudget() {
        this.state.cmpMode = "budget";
        await this.openCompare();
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

    // ==== W95 (WP-H) — budget vs actual ====
    async setCmpMode(mode) {
        if (this.state.cmpMode === mode) return;
        this.state.cmpMode = mode;
        this.state.cmpResult = null;      // a mode switch invalidates the prior fold
        this.state.cmpNarrate = null;
        if (mode === "budget") await this._loadBudgets();
    }
    async _loadBudgets() {
        try {
            const r = await this.orm.call("pb.formula.studio", "budget_list", [this.state.config.id]);
            this.state.budgets = (r && r.budgets) || [];
            this.state.budgetCanEdit = !!(r && r.can_edit);
            if (this.state.budgets.length && !this.state.budgets.find((b) => b.id === this.state.budgetSel)) {
                this.state.budgetSel = this.state.budgets[0].id;
            } else if (!this.state.budgets.length) {
                this.state.budgetSel = null;
            }
        } catch (e) { this.state.budgets = []; }
    }
    onBudgetPick(ev) { this.state.budgetSel = parseInt(ev.target.value, 10) || null; }
    async runBudgetCompare() {
        if (!this.state.budgetSel) { this.notif.add("Pick or create a budget first", { type: "warning" }); return; }
        if (!this.state.cmpB) { this.notif.add("Pick a payrun to measure against", { type: "warning" }); return; }
        const CHUNK = 100;
        this.state.cmpBusy = true;
        this.state.cmpProgress = 0;
        this.state.cmpResult = null;
        this.state.cmpNarrate = null;
        try {
            const prep = await this.orm.call("pb.formula.studio", "budget_prepare",
                [this.state.config.id, this.state.budgetSel, this.state.cmpB], {}, { silent: true });
            if (!prep || prep.ok === false || !prep.cmp_id) {
                this.notif.add((prep && prep.msg) || "Budget comparison failed", { type: "warning" });
                return;
            }
            this.state.cmpId = prep.cmp_id;
            const pairs = prep.pairs || [];
            for (let i = 0; i < pairs.length; i += CHUNK) {
                await this.orm.call("pb.formula.studio", "compare_batch",
                    [{ cmp_id: prep.cmp_id, pairs: pairs.slice(i, i + CHUNK) }], {}, { silent: true });
                this.state.cmpProgress = pairs.length ? Math.round(100 * Math.min(i + CHUNK, pairs.length) / pairs.length) : 100;
                if (this.state.view !== "compare") return;
            }
            const res = await this.orm.call("pb.formula.studio", "compare_result",
                [prep.cmp_id], {}, { silent: true });
            if (this.state.view === "compare") this.state.cmpResult = (res && res.result) || null;
        } catch (e) {
            this.notif.add("Budget comparison failed", { type: "danger" });
        } finally { this.state.cmpBusy = false; }
    }
    // — editor overlay (manager-gated writes; reads open) —
    async openBudgetEditor(budgetId) {
        if (this._lockedNotice()) return;     // read-only: say so, never a silent no-op
        this.state.budgetBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "budget_get",
                [this.state.config.id, budgetId || false]);
            if (!r || !r.ok) { this.notif.add("Could not open the budget editor", { type: "warning" }); return; }
            const head = r.budget || {};
            this.state.budgetEdit = {
                id: head.id || null,
                name: head.name || "",
                period_label: head.period_label || "",
                note: head.note || "",
                rows: (r.components || []).map((c) => ({ ...c, amount: c.amount || 0 })),
                orphans: (r.orphans || []).map((o) => ({ ...o })),
            };
            this.state.budgetSeedRun = (this.state.cmpRuns[0] && this.state.cmpRuns[0].id) || null;
            this.state.budgetEditOpen = true;
        } catch (e) {
            this.notif.add("Could not open the budget editor", { type: "danger" });
        } finally { this.state.budgetBusy = false; }
    }
    newBudget() { this.openBudgetEditor(null); }
    closeBudgetEditor() { this.state.budgetEditOpen = false; this.state.budgetEdit = null; }
    onBudgetHead(field, ev) { if (this.state.budgetEdit) this.state.budgetEdit[field] = ev.target.value; }
    onBudgetAmount(code, ev) {
        const e = this.state.budgetEdit; if (!e) return;
        const row = e.rows.find((r) => r.code === code) || e.orphans.find((r) => r.code === code);
        if (row) row.amount = ev.target.value;
    }
    dropOrphan(code) {
        const e = this.state.budgetEdit; if (!e) return;
        e.orphans = e.orphans.filter((o) => o.code !== code);
    }
    onSeedRunPick(ev) { this.state.budgetSeedRun = parseInt(ev.target.value, 10) || null; }
    async seedBudgetFromRun() {
        const e = this.state.budgetEdit;
        if (!e || !this.state.budgetSeedRun) { this.notif.add("Pick a payrun to seed from", { type: "warning" }); return; }
        this.state.budgetBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "budget_seed_from_run",
                [this.state.config.id, this.state.budgetSeedRun], {}, { silent: true });
            const amounts = (r && r.amounts) || {};
            for (const row of e.rows) row.amount = amounts[row.code] != null ? amounts[row.code] : row.amount;
            this.notif.add("Amounts seeded from the payrun", { type: "success" });
        } catch (err) {
            this.notif.add("Could not seed from that payrun", { type: "warning" });
        } finally { this.state.budgetBusy = false; }
    }
    // seed from an on-screen PERIOD compare (client-side, no RPC) — uses the "after" sums
    get canSeedFromCompare() {
        const r = this.state.cmpResult;
        return !!(r && !r.empty && r.mode !== "budget" && r.components && r.components.length);
    }
    seedBudgetFromCompare() {
        const e = this.state.budgetEdit; const r = this.state.cmpResult;
        if (!e || !this.canSeedFromCompare) return;
        const bycode = {};
        for (const c of r.components) bycode[c.code] = c.sum_b;
        for (const row of e.rows) if (bycode[row.code] != null) row.amount = bycode[row.code];
        this.notif.add("Amounts seeded from the on-screen comparison", { type: "success" });
    }
    async saveBudget() {
        const e = this.state.budgetEdit;
        if (!e || this.state.budgetBusy) return;
        if (!(e.name || "").trim()) { this.notif.add("A budget needs a name", { type: "warning" }); return; }
        const lines = {};
        for (const row of e.rows) {
            const v = String(row.amount ?? "").trim();
            if (v !== "" && Number(v) !== 0) lines[row.code] = Number(v);
        }
        for (const o of e.orphans) {   // kept orphan lines persist unless dropped
            const v = String(o.amount ?? "").trim();
            if (v !== "") lines[o.code] = Number(v);
        }
        this.state.budgetBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "budget_save", [{
                id: e.id || false, config_id: this.state.config.id,
                name: e.name, period_label: e.period_label, note: e.note, lines,
            }]);
            if (!r || !r.ok) { this.notif.add((r && r.msg) || "Could not save budget", { type: "warning" }); return; }
            await this._loadBudgets();
            this.state.budgetSel = r.budget.id;
            this.state.budgetEditOpen = false;
            this.state.budgetEdit = null;
            this.notif.add("Budget saved", { type: "success" });
        } catch (err) {
            this.notif.add("Could not save budget", { type: "danger" });
        } finally { this.state.budgetBusy = false; }
    }
    async deleteBudget(b) {
        if (this._lockedNotice() || this.state.budgetBusy) return;
        this.state.budgetBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "budget_delete", [b.id]);
            if (!r || !r.ok) { this.notif.add((r && r.msg) || "Could not delete budget", { type: "warning" }); return; }
            if (this.state.budgetSel === b.id) this.state.budgetSel = null;
            if (this.state.budgetEdit && this.state.budgetEdit.id === b.id) this.closeBudgetEditor();
            await this._loadBudgets();
            this.notif.add("Budget deleted", { type: "success" });
        } catch (err) {
            this.notif.add("Could not delete budget", { type: "danger" });
        } finally { this.state.budgetBusy = false; }
    }
    get budgetEditByGroup() {
        const e = this.state.budgetEdit;
        if (!e) return [];
        const order = ["Earnings", "Deductions", "Totals", "Inputs"];
        const seen = {};
        const groups = [];
        for (const row of e.rows) {
            const g = row.group || "Earnings";
            if (!seen[g]) { seen[g] = { group: g, rows: [] }; groups.push(seen[g]); }
            seen[g].rows.push(row);
        }
        groups.sort((a, b) => (order.indexOf(a.group) + 99) - (order.indexOf(b.group) + 99) || a.group.localeCompare(b.group));
        return groups;
    }

    // ==== W98 (WP-H) — offer calculator (read-only, in-memory) ====
    async openOfferCalc() {
        if (this.state.empty) return;
        this.state.moreOpen = false;
        this.state.offerOpen = true;
        this.state.offerResult = null;
        try {
            const d = await this.orm.call("pb.formula.studio", "get_test_data", [this.state.config.id]);
            this.state.offerCurrency = (d && d.currency) || "";
            this.state.offerSamples = (d && d.samples) || [];
            this.state.offerInputs = ((d && d.input_components) || []).map((i) => ({
                code: i.code, col: i.col, name: i.name || i.code, value: i.default || 0,
            }));
        } catch (e) { this.state.offerInputs = []; }
        this._offerRun();
    }
    closeOfferCalc() { this.state.offerOpen = false; }
    onOfferInput(code, ev) {
        const row = this.state.offerInputs.find((i) => i.code === code);
        if (row) row.value = ev.target.value;
        this._offerSchedule();
    }
    _offerSchedule() {
        if (this._offerTimer) clearTimeout(this._offerTimer);
        this._offerTimer = setTimeout(() => this._offerRun(), 320);   // C8 — one RPC per pause
    }
    async _offerRun() {
        const token = ++this._offerToken;
        const inputs = {};
        for (const i of this.state.offerInputs) {
            const v = String(i.value ?? "").trim();
            // Send the raw value — the server coerces numeric strings and passes
            // text inputs (name/department columns) through to the evaluator.
            if (v !== "") inputs[i.code] = v;
        }
        this.state.offerBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "offer_calc",
                [this.state.config.id, inputs], {}, { silent: true });
            if (token !== this._offerToken) return;   // superseded by a newer keystroke
            if (!r || !r.ok) { this.state.offerResult = null; if (r && r.msg) this.notif.add(r.msg, { type: "warning" }); return; }
            this.state.offerResult = r;
        } catch (e) {
            if (token === this._offerToken) this.state.offerResult = null;
        } finally {
            if (token === this._offerToken) this.state.offerBusy = false;
        }
    }
    async offerFromSample(ev) {
        const sid = parseInt(ev.target.value, 10);
        if (!sid) return;
        try {
            const r = await this.orm.call("pb.formula.studio", "offer_sample_inputs", [sid]);
            const vals = (r && r.inputs) || {};
            for (const i of this.state.offerInputs) if (vals[i.code] != null) i.value = vals[i.code];
            this._offerRun();
        } catch (e) { this.notif.add("Could not load that sample", { type: "warning" }); }
    }
    get offerGroups() {
        const r = this.state.offerResult;
        if (!r || !r.rows) return [];
        const order = ["Earnings", "Deductions", "Totals", "Inputs"];
        const seen = {}, groups = [];
        for (const row of r.rows) {
            const g = row.group || "Earnings";
            if (!seen[g]) { seen[g] = { group: g, rows: [] }; groups.push(seen[g]); }
            seen[g].rows.push(row);
        }
        groups.sort((a, b) => (order.indexOf(a.group) + 99) - (order.indexOf(b.group) + 99));
        return groups;
    }
    copyOfferSummary() {
        const r = this.state.offerResult;
        if (!r) return;
        const cur = this.state.offerCurrency || "";
        const money = (v) => cur + Math.round(v || 0).toLocaleString("en-US");
        const lines = [];
        lines.push("Offer — " + (this.state.config.name || ""));
        lines.push(new Date().toLocaleDateString("en-GB"));
        lines.push("");
        lines.push("Inputs:");
        for (const i of this.state.offerInputs) lines.push("  " + (i.name || i.code) + ": " + i.value);
        lines.push("");
        lines.push("Breakdown (payslip components):");
        for (const row of r.rows) {
            if (row.appears_on_payslip) lines.push("  " + row.code + " (" + row.name + "): " + money(row.value));
        }
        if (r.net_code) { lines.push(""); lines.push("Net (" + r.net_code + "): " + money(r.net_value)); }
        const text = lines.join("\n");
        if (navigator.clipboard) navigator.clipboard.writeText(text).then(() => this.notif.add("Offer summary copied", { type: "success" }));
    }
    offerMoney(v) { return (this.state.offerCurrency || "") + Math.round(v || 0).toLocaleString("en-US"); }
    offerVal(row) {
        const n = row.value || 0;
        if (row.number_format === "percent") return Number(n).toLocaleString("en-US") + "%";
        return this.offerMoney(n);
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
    // W49 — AI-proposed profiles (LLM proposes inputs; engine computes the baseline)
    async openAiPanel() {
        this.state.genMode = "ai";
        this.state.aiBusy = true; this.state.aiError = "";
        this.state.aiProps = null; this.state.aiPicks = []; this.state.aiRejected = [];
        const r = await this.orm.call("pb.formula.studio", "ai_propose_samples", [this.state.config.id]);
        this.state.aiBusy = false;
        if (!r || !r.ok) { this.state.aiError = (r && r.reason) || "AI is unavailable."; this.state.aiProps = []; return; }
        this.state.aiProps = r.proposals || [];
        this.state.aiRejected = r.rejected || [];
        this.state.aiPicks = this.state.aiProps.map((_p, i) => i);   // all checked by default
    }
    toggleAiPick(i) {
        const p = this.state.aiPicks, k = p.indexOf(i);
        if (k >= 0) p.splice(k, 1); else p.push(i);
    }
    async acceptAiSamples() {
        const chosen = (this.state.aiProps || []).filter((_p, i) => this.state.aiPicks.includes(i));
        if (!chosen.length) { this.notif.add("Select at least one profile.", { type: "warning" }); return; }
        this.state.aiBusy = true;
        const r = await this.orm.call("pb.formula.studio", "create_ai_samples", [this.state.config.id, chosen]);
        this.state.aiBusy = false;
        if (!r || !r.ok) { this.notif.add((r && r.msg) || "Could not add samples", { type: "warning" }); return; }
        this.notif.add(`${r.created} AI profile${r.created === 1 ? "" : "s"} added`, { type: "success" });
        this.state.testGenOpen = false; this.state.genMode = null;
        await this.loadTestData(true);
        const gen = this.state.test.samples.filter(s => s.source_type === "generated");
        const last = gen[gen.length - 1];
        if (last) await this.selectSample(last.id);
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
    // W41 — export the whole config as a *living* .xlsx (real Excel formulas,
    // one row per sample, rate tables on a reference sheet). Clones the
    // exportTestTemplate blob-download path (D-L3).
    async exportLivingWorkbook() {
        if (this.state.empty) return;
        const r = await this.orm.call("pb.formula.studio", "export_living_workbook", [this.state.config.id]);
        if (!r || !r.ok) { this.notif.add((r && r.msg) || "Could not export workbook", { type: "warning" }); return; }
        const bin = atob(r.file_b64);
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        const url = URL.createObjectURL(new Blob([bytes], { type: r.mimetype }));
        const a = document.createElement("a");
        a.href = url; a.download = r.filename; a.click();
        URL.revokeObjectURL(url);
        this.notif.add(r.note || "Workbook downloaded", { type: r.note ? "info" : "success" });
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

    // ---- Config Switcher (gallery selector + health board with filters) ----
    openConfigSwitcher() {
        this.state.configPickerOpen = false;
        this.state.configSwitcherOpen = true;
        if (!this.state.csBoard) this._loadCsBoard();   // lazy — refetched on clone
    }
    closeConfigSwitcher() { this.state.configSwitcherOpen = false; }
    async refreshCsBoard() { await this._loadCsBoard(); }
    async chooseConfig(id) {
        this.state.configSwitcherOpen = false;
        if (id === (this.state.config && this.state.config.id)) return;
        this.state.selectedId = null;
        await this.load(id);
        this.state.view = "cards";
    }
    onCsSearch(ev) { this.state.csQuery = ev.target.value; }
    csClearQuery() { this.state.csQuery = ""; }
    csSetCountry(v) { this.state.csCountry = this.state.csCountry === v ? "" : v; }
    csSetState(v) { this.state.csState = this.state.csState === v ? "" : v; }
    csSetCycle(v) { this.state.csCycle = this.state.csCycle === v ? "" : v; }
    csSetDivision(v) { this.state.csDivision = this.state.csDivision === v ? "" : v; }
    csSetSort(v) { this.state.csSort = v; }
    csClearFilters() { this.state.csQuery = ""; this.state.csCountry = ""; this.state.csState = ""; this.state.csCycle = ""; this.state.csDivision = ""; }
    get csHasFilters() { return !!(this.state.csQuery || this.state.csCountry || this.state.csState || this.state.csCycle || this.state.csDivision); }
    get csCards() { return (this.state.csBoard && this.state.csBoard.cards) || []; }
    get csCanEdit() { return !!(this.state.csBoard && this.state.csBoard.can_edit); }
    csCountryLabel(cc) {
        return { VN: "Vietnam", ID: "Indonesia", IN: "India", SG: "Singapore",
                 MY: "Malaysia", TH: "Thailand", KH: "Cambodia", PH: "Philippines" }[cc] || cc;
    }
    csCycleLabel(ct) {
        return { regular: "Regular", mid_cycle: "Mid-cycle", end_cycle: "End-cycle",
                 full_final: "Full & Final" }[ct] || ct;
    }
    csStateLabel(s) {
        return { draft: "Draft", testing: "Testing", validated: "Validated",
                 active: "Active", archived: "Archived" }[s] || s;
    }
    csRingStroke(score) { return (score >= 80) ? "#059669" : (score >= 50 ? "#D97706" : (score > 0 ? "#DC2626" : "#CBD5E1")); }
    // a card wants attention if it has hard errors or unreleased changes
    csAttention(c) { return ((c.problem_counts && c.problem_counts.error) || 0) > 0 ? "err" : (c.pending_changes ? "warn" : ""); }
    _csFacet(key, labeler) {
        const m = {};
        for (const c of this.csCards) { const v = c[key] || ""; if (v) m[v] = (m[v] || 0) + 1; }
        return Object.keys(m).map(v => ({ v, n: m[v], label: labeler ? labeler.call(this, v) : v }))
                     .sort((a, b) => b.n - a.n || String(a.label).localeCompare(String(b.label)));
    }
    get csCountryFacets() { return this._csFacet("country", this.csCountryLabel); }
    get csStateFacets() { return this._csFacet("state", this.csStateLabel); }
    get csCycleFacets() { return this._csFacet("cycle_type", this.csCycleLabel); }
    get csDivisionFacets() { return this._csFacet("division"); }
    get csFiltered() {
        let cfgs = this.csCards.slice();
        const q = (this.state.csQuery || "").trim().toLowerCase();
        if (q) cfgs = cfgs.filter(c => (c.name || "").toLowerCase().includes(q) || (c.code || "").toLowerCase().includes(q) || (c.division || "").toLowerCase().includes(q));
        if (this.state.csCountry) cfgs = cfgs.filter(c => c.country === this.state.csCountry);
        if (this.state.csState) cfgs = cfgs.filter(c => c.state === this.state.csState);
        if (this.state.csCycle) cfgs = cfgs.filter(c => c.cycle_type === this.state.csCycle);
        if (this.state.csDivision) cfgs = cfgs.filter(c => c.division === this.state.csDivision);
        if (this.state.csSort === "name") cfgs.sort((a, b) => String(a.name).localeCompare(String(b.name)));
        else if (this.state.csSort === "health") cfgs.sort((a, b) => (b.score || 0) - (a.score || 0));
        else if (this.state.csSort === "attention") cfgs.sort((a, b) =>
            ((b.problem_counts && b.problem_counts.error || 0) - (a.problem_counts && a.problem_counts.error || 0))
            || (b.pending_changes - a.pending_changes) || (a.score - b.score));
        // "recent" keeps the server order
        return cfgs;
    }
    get csSummary() {
        const cfgs = this.csCards;
        return {
            total: cfgs.length,
            active: cfgs.filter(c => c.state === "active").length,
            withErrors: cfgs.filter(c => ((c.problem_counts && c.problem_counts.error) || 0) > 0).length,
            unreleased: cfgs.filter(c => c.pending_changes > 0).length,
            employees: cfgs.reduce((a, c) => a + (c.employees || 0), 0),
            shown: this.csFiltered.length,
        };
    }
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
        // W54 — simplification suggestions load in a second call (this one
        // evaluates, so it is deliberately off the eval-free get_problems path).
        try {
            this.state.simplifyData = await this.orm.call(
                "pb.formula.studio", "get_simplify_suggestions", [this.state.config.id]);
        } catch (e) { this.state.simplifyData = null; }
    }
    get simplifySuggestions() {
        return (this.state.simplifyData && this.state.simplifyData.suggestions) || [];
    }
    // split the changed span of a formula around a suggestion for a before/after
    // diff: [head, changed, tail]. `after` has no span, so highlight the BRACKET(...)
    // call by matching the head/tail against the before text.
    simplifyDiff(s, which) {
        const text = which === "after" ? (s.after || "") : (s.before || "");
        if (which === "before" && s.span) {
            return [text.slice(0, s.span[0]), text.slice(s.span[0], s.span[1]), text.slice(s.span[1])];
        }
        if (which === "after" && s.span) {
            const head = (s.before || "").slice(0, s.span[0]);
            const tail = (s.before || "").slice(s.span[1]);
            const changed = text.slice(head.length, text.length - tail.length);
            return [head, changed, tail];
        }
        return [text, "", ""];
    }
    async applySimplify(s) {
        if (!s || !s.can_apply || this.state.simplifyBusy) return;
        if (this._lockedNotice && this._lockedNotice()) return;
        this.state.simplifyBusy = s.rule_id;
        try {
            const r = await this.orm.call("pb.formula.studio", "simplify_apply", [s.rule_id]);
            if (!r || !r.ok) {
                this.notif.add((r && r.msg) || "Could not apply the rewrite", { type: "danger" });
                return;
            }
            const t = r.tests || {};
            const chip = t.has_tests ? ` · tests ${t.passed}/${t.total}` : "";
            this.notif.add(r.msg + chip, { type: "success" });
            await this.load(this.state.config.id);   // fresh formula + tables + problems
            await this._loadProblems();
        } catch (e) {
            this.notif.add("Could not apply the rewrite", { type: "danger" });
        } finally {
            this.state.simplifyBusy = null;
        }
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
            magic: "hash", offpayslip: "eye", dupe: "copy", simplify: "wand",
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
            { key: "employee", label: "Employee/Contract" },
        ];
    }
    // adapters that share the generic create/delete/draw dispatch; cycle is bespoke
    get _mapPrefix() { return { api: "api", import: "import", scheme: "scheme", employee: "employee" }[this.state.mapMode] || null; }
    // Employee/Contract tab: the RIGHT column shows a curated field set; this
    // autocomplete lets the user pick ANY writable employee/contract field and
    // append it (mapEmpExtras) so it becomes wireable. Once wired it persists and
    // the backend returns it in mapData.right on the next load.
    onMapEmpSearch(ev) {
        const q = ev.target.value || "";
        this.state.mapEmpQuery = q;
        clearTimeout(this._mapEmpTimer);
        if (q.trim().length < 2) { this.state.mapEmpResults = []; return; }
        this._mapEmpTimer = setTimeout(async () => {
            try {
                const r = await this.orm.call("pb.formula.studio", "ec_search_fields", [q, this.state.config.id]);
                this.state.mapEmpResults = (r && r.fields) || [];
            } catch (e) { this.state.mapEmpResults = []; }
        }, 220);
    }
    addEmpField(item) {
        const base = (this.state.mapData && this.state.mapData.right) || [];
        const extras = this.state.mapEmpExtras || [];
        if (!extras.some(x => x.id === item.id) && !base.some(x => x.id === item.id)) {
            this.state.mapEmpExtras = [...extras, item];
        }
        // if it had been session-hidden, un-hide it so the add takes effect
        this.state.mapEmpHidden = (this.state.mapEmpHidden || []).filter(x => x !== item.id);
        this.state.mapEmpQuery = "";
        this.state.mapEmpResults = [];
    }
    // Remove an UNWIRED field from the right column (session-scoped, per plan):
    // a pinned extra is dropped; a curated/base field is hidden until the tab
    // reloads. Mapped fields never reach here (the ✕/toggle are gated on wires).
    removeRightField(id) {
        const extras = this.state.mapEmpExtras || [];
        if (extras.some(x => x.id === id)) {
            this.state.mapEmpExtras = extras.filter(x => x.id !== id);
        } else if (!(this.state.mapEmpHidden || []).includes(id)) {
            this.state.mapEmpHidden = [...(this.state.mapEmpHidden || []), id];
        }
    }
    get mapEmpRight() {
        const base = (this.state.mapData && this.state.mapData.right) || [];
        const hidden = new Set(this.state.mapEmpHidden || []);
        const seen = new Set(base.map(i => i.id));
        return [
            ...base.filter(i => !hidden.has(i.id)),
            ...((this.state.mapEmpExtras || []).filter(i => !seen.has(i.id) && !hidden.has(i.id))),
        ];
    }
    // the canvas' RIGHT items: employee tab merges the pinned extras
    get mapRightItems() {
        return this.state.mapMode === "employee"
            ? this.mapEmpRight
            : ((this.state.mapData && this.state.mapData.right) || []);
    }
    // ---- Employee/Contract browse dropdowns (Employee ▾ / Contract ▾) --------
    // Toggle a per-model popover listing ALL writable scalar fields; lazy-load
    // once per model into mapEmpMenuAll.
    async toggleEmpMenu(model) {
        if (this.state.mapEmpMenu === model) { this.closeEmpMenu(); return; }
        this.state.mapEmpMenu = model;
        this.state.mapEmpMenuFilter = "";
        const cache = this.state.mapEmpMenuAll || {};
        if (!cache[model]) {
            try {
                const r = await this.orm.call("pb.formula.studio", "ec_model_fields", [model]);
                this.state.mapEmpMenuAll = { ...cache, [model]: (r && r.fields) || [] };
            } catch (e) { this.state.mapEmpMenuAll = { ...cache, [model]: [] }; }
        }
    }
    closeEmpMenu() { this.state.mapEmpMenu = null; this.state.mapEmpMenuFilter = ""; }
    onEmpMenuFilter(ev) { this.state.mapEmpMenuFilter = ev.target.value || ""; }
    get empMenuFields() {
        const model = this.state.mapEmpMenu;
        if (!model) return [];
        const all = (this.state.mapEmpMenuAll || {})[model] || [];
        const q = (this.state.mapEmpMenuFilter || "").trim().toLowerCase();
        if (!q) return all;
        return all.filter(f =>
            (f.label || "").toLowerCase().includes(q) ||
            ((f.meta && f.meta.field) || "").toLowerCase().includes(q));
    }
    get empMenuLabel() { return this.state.mapEmpMenu === "hr.contract" ? "Contract" : "Employee"; }
    isFieldAdded(id) { return this.mapRightItems.some(i => i.id === id); }
    isFieldMapped(id) {
        const wires = (this.state.mapData && this.state.mapData.wires) || [];
        return wires.some(w => w.rightId === id && w.state === "accepted");
    }
    // Row click in a browse dropdown: toggle add/remove for unmapped fields.
    pickEmpMenuField(f) {
        if (this.isFieldMapped(f.id)) return;           // locked — unwire first
        if (this.isFieldAdded(f.id)) this.removeRightField(f.id);
        else this.addEmpField(f);
    }
    _resetEmpPicker() {
        this.state.mapEmpQuery = "";
        this.state.mapEmpResults = [];
        this.state.mapEmpExtras = [];
        this.state.mapEmpHidden = [];
        this.state.mapEmpMenu = null;
        this.state.mapEmpMenuFilter = "";
        this.state.mapEmpMenuAll = {};
    }
    /**
     * "Open in Mapping Studio" — the overlay graduates to the full surface.
     *
     * The overlay stays exactly as it is (every scheme-centric flow reaches
     * mapping from inside a configuration, and taking that away would be a
     * regression dressed as a redesign). This is a one-way link that carries
     * what the overlay already knows — the configuration, the mode, and the
     * connector the API tab is on — so the studio opens on the same board
     * rather than on its own defaults. The registry probe is the same W29
     * rule everything else uses: no dead buttons.
     */
    get hasMappingStudio() {
        return registry.category("actions").contains("pb_mapping_studio");
    }
    openMappingStudio() {
        const ctx = {
            pb_config: this.state.config && this.state.config.id,
            pb_mode: this.state.mapMode || "api",
        };
        if (this.state.mapMode === "api" && this.state.mapContextId) {
            ctx.pb_connector = this.state.mapContextId;
        }
        openHub(this.action, {
            tag: "pb_mapping_studio",
            context: ctx,
            back: { label: _t("Formula Studio"),
                    xmlid: "pb_formula_studio.action_pb_formula_studio" },
        });
    }

    openMapping(mode) {
        this.state.mapMode = mode || this.state.mapMode || "cycle";
        this.state.mapOpen = true;
        this.state.mapData = null;
        this.state.mapContextId = null;
        this.state.mapDismissed = [];
        this._resetEmpPicker();
        this._loadMapping();
    }
    setMapMode(mode) {
        if (this.state.mapMode === mode) return;
        this.state.mapMode = mode;
        this.state.mapData = null;
        this.state.mapContextId = null;
        this.state.mapDismissed = [];
        this._resetEmpPicker();
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
    // W62 — transform preview/save (API adapter only). Preview never writes; save
    // is manager-gated + field-whitelisted server-side (never transformation_code).
    async mapTransformPreview(ref, draft) {
        try { return await this.orm.call("pb.formula.studio", "api_transform_preview", [ref, draft]); }
        catch (e) { return { ok: false, error: "Preview failed" }; }
    }
    async mapTransformSave(ref, vals) {
        const r = await this.orm.call("pb.formula.studio", "api_transform_save", [ref, vals]);
        if (r && r.ok) { await this._loadMapping(); }
        else if (r && r.msg) { this.notif.add(r.msg, { type: "warning" }); }
        return r;
    }
    // W65 — mapping templates (save a board / apply across configs). Both api + cycle.
    get mapTemplatable() { return ["api", "cycle"].includes(this.state.mapMode); }
    openTmplSave() { this.state.tmplMode = "save"; this.state.tmplName = ""; this.state.tmplResult = null; }
    async openTmplApply() {
        this.state.tmplMode = "apply";
        this.state.tmplResult = null;
        this.state.tmplBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "mapping_template_list", [this.state.mapMode]);
            this.state.tmplList = (r && r.templates) || [];
        } catch (e) { this.state.tmplList = []; }
        finally { this.state.tmplBusy = false; }
    }
    closeTmpl() { this.state.tmplMode = null; this.state.tmplResult = null; }
    onTmplName(ev) { this.state.tmplName = ev.target.value; }
    onTmplKey(ev) { if (ev.key === "Enter") this.saveTmpl(); }
    async saveTmpl() {
        const name = (this.state.tmplName || "").trim();
        if (!name) { this.notif.add("Give the template a name", { type: "warning" }); return; }
        this.state.tmplBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "mapping_template_save",
                [this.state.config.id, this.state.mapMode, name]);
            if (r && r.ok) {
                this.notif.add(`Saved "${name}" (${r.line_count} wire${r.line_count === 1 ? "" : "s"})`, { type: "success" });
                this.closeTmpl();
            } else { this.notif.add((r && r.msg) || "Could not save template", { type: "warning" }); }
        } finally { this.state.tmplBusy = false; }
    }
    async applyTmpl(id) {
        this.state.tmplBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "mapping_template_apply",
                [id, this.state.config.id, this.state.mapContextId || false]);
            if (r && r.ok) {
                this.state.tmplResult = r;
                await this._loadMapping();
            } else { this.notif.add((r && r.msg) || "Could not apply template", { type: "warning" }); }
        } finally { this.state.tmplBusy = false; }
    }
    async deleteTmpl(id) {
        const r = await this.orm.call("pb.formula.studio", "mapping_template_delete", [id]);
        if (r && r.ok === false) { this.notif.add(r.msg || "Could not delete", { type: "warning" }); return; }
        await this.openTmplApply();   // refresh the list in place
    }

    // ---- Payslip Studio (F9) ----
    openPayslip() {
        this.state.psOpen = true;
        this.state.psData = null;
        this.state.psEditSec = null;
        this.state.psImportOpen = false;
        this.state.psRichOpen = false;
        this.state.psDeleteOpen = false;
        this.state.psDeleteKind = null;
        this.state.psDeleteBusy = false;
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
    // Values passed here are either fields.Html (sanitized by Odoo on write)
    // or import text escaped server-side before its <p> wrapper is built.
    psHtml(value) { return markup(value || ""); }

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
        for (const c of (s.embedded_components || []).filter(c => this.psVisible(c))) {
            t += (c.is_deduction ? -1 : 1) * (c.value || 0);
        }
        return t;
    }
    get psNet() {
        if (!this.state.psData) return 0;
        let net = 0;
        for (const s of this.state.psData.sections) net += this.psSectionTotal(s);
        return net;
    }

    // ---- W73 payslip theme (accent / font / logo; preview + print share fields) ----
    get psTheme() {
        return (this.state.psData && this.state.psData.theme)
            || { accent: "slate", font: "system", show_logo: true, has_logo: false };
    }
    get psAccentHex() {
        const map = (this.state.psData && this.state.psData.accent_hex) || {};
        return map[this.psTheme.accent] || "#64748B";
    }
    get psFontStack() {
        return {
            system: "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
            serif: "Georgia, 'Times New Roman', Times, serif",
            mono: "'SF Mono', 'Cascadia Code', Consolas, monospace",
        }[this.psTheme.font] || "inherit";
    }
    // The .ps-slip preview reads the SAME four fields the print does (D-L7).
    get psSlipStyle() {
        return `--ps-accent: ${this.psAccentHex}; font-family: ${this.psFontStack};`;
    }
    get psLogoUrl() {
        if (!this.psTheme.show_logo || !this.psTheme.has_logo) return null;
        return `/web/image/hr.formula.config/${this.state.config.id}/theme_logo?v=${this.state.psLogoV}`;
    }
    get psAccentSwatches() { return (this.state.psData && this.state.psData.colors) || []; }
    async _saveTheme(vals) {
        if (!this.state.psData || !this.state.psData.can_edit) return;
        const r = await this.orm.call("pb.formula.studio", "save_payslip_theme",
            [this.state.config.id, vals]);
        if (r && r.ok && r.theme) this.state.psData.theme = r.theme;
        else if (r && r.msg) this.notif.add(r.msg, { type: "warning" });
    }
    psSetAccent(key) { this._saveTheme({ accent: key }); }
    psSetFont(ev) { this._saveTheme({ font: ev.target.value }); }
    psToggleLogo() { this._saveTheme({ show_logo: !this.psTheme.show_logo }); }
    togglePsTheme() { this.state.psThemeOpen = !this.state.psThemeOpen; }
    async psUploadLogo(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = async (e) => {
            const b64 = String(e.target.result).split(",")[1] || "";
            ev.target.value = "";
            await this._saveTheme({ logo: b64 });
            this.state.psLogoV++;             // bust the preview img cache
        };
        reader.readAsDataURL(file);
    }
    async psClearLogo() {
        await this._saveTheme({ logo: "" });
        this.state.psLogoV++;
    }
    psAskDeleteTemplate(kind) {
        if (!this.state.psData || !this.state.psData.can_edit) return;
        const activeKind = this.state.psData.layout_html ? "imported"
            : (this.state.psData.section_template_active ? "section" : null);
        if (kind !== activeKind) return;
        this.state.psDeleteKind = kind;
        this.state.psDeleteOpen = true;
        this.state.psDeleteBusy = false;
    }
    psCancelDeleteTemplate() {
        if (this.state.psDeleteBusy) return;
        this.state.psDeleteOpen = false;
        this.state.psDeleteKind = null;
    }
    async psConfirmDeleteTemplate() {
        if (!this.state.psDeleteOpen || this.state.psDeleteBusy || !this.state.psDeleteKind) return;
        const kind = this.state.psDeleteKind;
        this.state.psDeleteBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "delete_payslip_template",
                [this.state.config.id, kind]);
            if (r && r.ok) {
                this.state.psDeleteOpen = false;
                this.state.psDeleteKind = null;
                const message = kind === "imported"
                    ? _t("Imported template deleted. Your section template is now active.")
                    : _t("Section template deleted. Components are ready in the Unplaced tray.");
                this.notif.add(message, { type: "success" });
                await this._loadPayslip(this.state.psData.sample_id);
            } else {
                this.notif.add((r && r.msg) || _t("The template could not be deleted."),
                    { type: "warning" });
            }
        } finally {
            this.state.psDeleteBusy = false;
        }
    }

    // ---- uploaded payslip → reviewable layout draft ----
    openPsImport() {
        if (!this.state.psData || !this.state.psData.can_edit) return;
        this.state.psImportOpen = true;
        this.state.psImportBusy = false;
        this.state.psImportDraft = null;
        this.state.psImportError = "";
        this.state.psImportApplyTheme = true;
        this.state.psImportApplyContent = true;
        this.state.psImportApplyLayout = true;
    }
    closePsImport() {
        if (!this.state.psImportBusy) this.state.psImportOpen = false;
    }
    async psAnalyseTemplate(file) {
        if (this.state.psImportBusy) return;
        this.state.psImportBusy = true;
        this.state.psImportError = "";
        this.state.psImportDraft = null;
        try {
            if (file.mime === "application/pdf") {
                const extracted = await this._psExtractPdf(file.data);
                file = { ...file, extracted_text: extracted.text, pdf_layout: extracted.layout };
            }
            const r = await this.orm.call("pb.formula.studio", "analyse_payslip_template",
                [this.state.config.id, file]);
            if (r && r.ok) this.state.psImportDraft = r;
            else this.state.psImportError = (r && (r.msg || r.warning)) || _t("The payslip could not be analysed.");
        } catch (e) {
            this.state.psImportError = _t("The payslip could not be analysed. Check the Document OCR configuration and try again.");
        } finally {
            this.state.psImportBusy = false;
        }
    }
    async _psExtractPdf(data) {
        try {
            await loadPDFJSAssets();
            window.Util = window.pdfjsLib.Util;
            const binary = atob(data || "");
            const bytes = Uint8Array.from(binary, ch => ch.charCodeAt(0));
            const task = window.pdfjsLib.getDocument({ data: bytes });
            const pdf = await task.promise;
            const pageTexts = [];
            const layoutPages = [];
            let palette = [];
            for (let pageNo = 1; pageNo <= Math.min(pdf.numPages || 0, 8); pageNo++) {
                const page = await pdf.getPage(pageNo);
                const viewport = page.getViewport({ scale: 1 });
                if (pageNo === 1) {
                    const thumbViewport = page.getViewport({ scale: .45 });
                    const canvas = document.createElement("canvas");
                    canvas.width = Math.max(1, Math.round(thumbViewport.width));
                    canvas.height = Math.max(1, Math.round(thumbViewport.height));
                    const context = canvas.getContext("2d", { willReadFrequently: true });
                    if (context) {
                        await page.render({ canvasContext: context, viewport: thumbViewport }).promise;
                        const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
                        const counts = new Map();
                        for (let i = 0; i < pixels.length; i += 64) {
                            const r = pixels[i], g = pixels[i + 1], b = pixels[i + 2], a = pixels[i + 3];
                            if (a < 180 || (r > 242 && g > 242 && b > 242) || (r + g + b < 105)) continue;
                            if (Math.max(r, g, b) - Math.min(r, g, b) < 12) continue;
                            const key = [r, g, b].map(value => Math.round(value / 16) * 16)
                                .map(value => Math.min(255, value));
                            const hex = `#${key.map(value => value.toString(16).padStart(2, "0")).join("")}`;
                            counts.set(hex, (counts.get(hex) || 0) + 1);
                        }
                        palette = [...counts.entries()].sort((a, b) => b[1] - a[1])
                            .slice(0, 4).map(entry => entry[0]);
                    }
                }
                const content = await page.getTextContent();
                let text = "";
                const items = [];
                for (const item of content.items || []) {
                    text += (item.str || "") + (item.hasEOL ? "\n" : " ");
                    if (!item.str || !item.str.trim()) continue;
                    const tx = window.pdfjsLib.Util.transform(viewport.transform, item.transform);
                    const fontHeight = Math.max(1, Math.hypot(tx[2], tx[3]));
                    const style = (content.styles && content.styles[item.fontName]) || {};
                    const fontHint = `${item.fontName || ""} ${style.fontFamily || ""}`.toLowerCase();
                    items.push({
                        text: item.str.trim().slice(0, 240),
                        x: Math.max(0, Math.min(1000, tx[4] / viewport.width * 1000)),
                        y: Math.max(0, Math.min(1000, tx[5] / viewport.height * 1000)),
                        width: Math.max(0, Math.min(1000, (item.width || 0) / viewport.width * 1000)),
                        height: Math.max(1, Math.min(100, fontHeight / viewport.height * 1000)),
                        bold: /bold|black|heavy|semibold/.test(fontHint),
                        italic: /italic|oblique/.test(fontHint),
                    });
                }
                pageTexts.push(text.trim());
                layoutPages.push({ width: viewport.width, height: viewport.height, items });
            }
            if (pdf.destroy) await pdf.destroy();
            return {
                text: pageTexts.filter(Boolean).join("\n").slice(0, 80000),
                layout: { version: 1, pages: layoutPages.slice(0, 4), palette },
            };
        } catch (e) {
            // Scanned/password-protected PDFs continue to the configured OCR
            // provider; failure here must never block that stronger path.
            return { text: "", layout: { version: 1, pages: [] } };
        }
    }
    psImportToggle(sectionIndex, matchIndex, ev) {
        const match = this.state.psImportDraft.sections[sectionIndex].matches[matchIndex];
        match.selected = ev.target.checked;
    }
    psImportSetMatch(sectionIndex, matchIndex, ev) {
        const match = this.state.psImportDraft.sections[sectionIndex].matches[matchIndex];
        const ruleId = parseInt(ev.target.value, 10) || false;
        if (ruleId) {
            for (const section of this.state.psImportDraft.sections) {
                for (const other of section.matches) {
                    if (other !== match && other.rule_id === ruleId) other.selected = false;
                }
            }
        }
        const option = this.state.psImportDraft.options.find(o => o.id === ruleId);
        match.rule_id = ruleId;
        match.rule_name = option ? option.name : "";
        match.rule_code = option ? option.code : "";
        match.selected = Boolean(ruleId);
    }
    psImportToggleTheme(ev) { this.state.psImportApplyTheme = ev.target.checked; }
    psImportToggleContent(ev) { this.state.psImportApplyContent = ev.target.checked; }
    psImportToggleLayout(ev) { this.state.psImportApplyLayout = ev.target.checked; }
    get psImportSelectedCount() {
        const draft = this.state.psImportDraft;
        if (!draft) return 0;
        return draft.sections.reduce((n, s) => n + s.matches.filter(m => m.selected && m.rule_id).length, 0);
    }
    async psApplyTemplate() {
        if (!this.state.psImportDraft || this.state.psImportBusy || !this.psImportSelectedCount) return;
        this.state.psImportBusy = true;
        try {
            const payload = {
                ...this.state.psImportDraft,
                apply_theme: this.state.psImportApplyTheme,
                apply_content: this.state.psImportApplyContent,
                apply_layout: this.state.psImportApplyLayout,
            };
            const r = await this.orm.call("pb.formula.studio", "apply_payslip_template",
                [this.state.config.id, payload]);
            if (r && r.ok) {
                this.notif.add(_t("Template applied: %s fields placed, %s sections created.", r.placed, r.created_sections), { type: "success" });
                this.state.psImportOpen = false;
                await this._loadPayslip(this.state.psData.sample_id);
            } else {
                this.state.psImportError = (r && r.msg) || _t("The template could not be applied.");
            }
        } finally {
            this.state.psImportBusy = false;
        }
    }

    // ---- compact rich-content editor (stored HTML is sanitized server-side) ----
    psOpenRich(target, title, htmlValue) {
        if (!this.state.psData || !this.state.psData.can_edit) return;
        this.state.psRichTarget = target;
        this.state.psRichTitle = title;
        this.state.psRichQuery = "";
        this.state.psRichMode = "both";
        this.state.psRichUsedIds = this._psRichTokenIds(htmlValue || "");
        this.state.psRichUsedMetaKeys = this._psRichMetaKeys(htmlValue || "");
        this.state.psRichTableActive = false;
        this.state.psRichTableLabel = "";
        this.state.psRichBorderScope = "table";
        this.state.psRichDraft = this._psRichExpandTokens(htmlValue || "");
        this._psRichNeedsSeed = false;
        this._psRichRange = null;
        this._psRichCellEl = null;
        this.state.psRichOpen = true;
        // The contenteditable subtree is browser-owned once editing begins.
        // Seed it after OWL mounts the shell so VHtml never tries to reconcile
        // nodes inserted or removed by the selection/range APIs.
        const richTarget = this.state.psRichTarget;
        const draft = this.state.psRichDraft || "";
        const seedEditor = (attempt = 0) => {
            if (!this.state.psRichOpen || this.state.psRichTarget !== richTarget) return;
            const editor = this._psRichEditor();
            if (editor) {
                editor.innerHTML = draft;
                // The document body is deliberately outside OWL's child-node
                // reconciliation. Its injected controls therefore bind at the
                // same imperative boundary instead of relying on framework
                // delegation through a contenteditable island.
                this._psRichBindTokenControls(editor);
            }
            else if (attempt < 5) setTimeout(() => seedEditor(attempt + 1), 16);
        };
        setTimeout(seedEditor, 0);
    }
    closePsRich() {
        if (this.state.psRichBusy) return;
        this._psRichSelectCell(null);
        this.state.psRichOpen = false;
    }
    _psRichEditor() { return document.querySelector(".ps-rich-editor"); }
    _psRichEscape(value) {
        return String(value == null ? "" : value)
            .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;").replaceAll('"', "&quot;");
    }
    _psRichTokenIds(htmlValue) {
        const ids = [];
        const re = /\{\{pb_component:(\d+):(label|value|both)\}\}/g;
        for (const match of String(htmlValue || "").matchAll(re)) {
            const id = parseInt(match[1], 10);
            if (id && !ids.includes(id)) ids.push(id);
        }
        return ids;
    }
    _psRichMetaKeys(htmlValue) {
        const keys = [];
        const re = /\{\{pb_meta:(employee_name|employee_id|department|date_from|date_to|period)\}\}/g;
        for (const match of String(htmlValue || "").matchAll(re)) {
            if (!keys.includes(match[1])) keys.push(match[1]);
        }
        return keys;
    }
    _psRichComponent(ruleId) {
        return ((this.state.psData && this.state.psData.rich_components) || [])
            .find(c => c.id === parseInt(ruleId, 10));
    }
    _psRichTokenHtml(component, mode) {
        if (!component || !["label", "value", "both"].includes(mode)) return "";
        const name = this._psRichEscape(component.name || component.code || "Component");
        const value = this._psRichEscape(this.psVal(component));
        const code = this._psRichEscape(component.col || component.code || "");
        const modeLabel = mode === "label" ? "label" : mode === "value" ? "value" : "label and value";
        // Tokens must identify themselves while the document is being edited.
        // A value-only component often has no sample payslip value, so showing
        // only `— ×` made an inserted component indistinguishable from an empty
        // cell.  The identity below is editor chrome: serialization still
        // collapses the whole span to {{pb_component:id:mode}}, and the printed
        // payslip therefore contains only the requested label/value.
        const identity = `<span class="ps-component-token-identity">${code ? `<small>${code}</small>` : ""}<span>${name}</span></span>`;
        const preview = mode === "label" ? ""
            : `<span class="ps-component-token-preview"><small>Preview</small><span class="ps-component-token-value">${value}</span></span>`;
        return `<span class="ps-component-token mode-${mode}" contenteditable="false" data-ps-rule-id="${component.id}" data-ps-mode="${mode}" title="Live payroll component ${code}: ${name} · inserts ${modeLabel}">${identity}${preview}<button type="button" tabindex="-1" data-ps-remove-token="1" title="Remove ${name}">×</button></span>`;
    }
    _psRichMetaField(key) {
        return [
            { key: "employee_name", name: "Employee name", badge: "NAME", source: "Employee record" },
            { key: "employee_id", name: "Employee ID", badge: "ID", source: "Employee record" },
            { key: "department", name: "Department", badge: "DEPT", source: "Employee record" },
            { key: "period", name: "Pay period", badge: "PER", source: "Payslip period" },
            { key: "date_from", name: "Period start", badge: "FROM", source: "Payslip period" },
            { key: "date_to", name: "Period end", badge: "TO", source: "Payslip period" },
        ].find(field => field.key === key);
    }
    _psRichMetaTokenHtml(fieldOrKey) {
        const field = typeof fieldOrKey === "string" ? this._psRichMetaField(fieldOrKey) : fieldOrKey;
        if (!field) return "";
        const name = this._psRichEscape(field.name);
        return `<span class="ps-meta-token" contenteditable="false" data-ps-meta="${field.key}" title="Live ${name} — supplied by the employee or payslip period"><small>Employee detail</small><span>${name}</span><button type="button" tabindex="-1" data-ps-remove-token="1" title="Remove ${name}">×</button></span>`;
    }
    _psRichExpandTokens(htmlValue) {
        const components = String(htmlValue || "").replace(
            /\{\{pb_component:(\d+):(label|value|both)\}\}/g,
            (_token, ruleId, mode) => {
                const component = this._psRichComponent(ruleId);
                return component ? this._psRichTokenHtml(component, mode) : "";
            });
        return components.replace(
            /\{\{pb_meta:(employee_name|employee_id|department|date_from|date_to|period)\}\}/g,
            (_token, key) => this._psRichMetaTokenHtml(key));
    }
    get psRichMetaFields() {
        const fields = ["employee_name", "employee_id", "department", "period", "date_from", "date_to"]
            .map(key => this._psRichMetaField(key));
        const query = (this.state.psRichQuery || "").trim().toLowerCase();
        return query ? fields.filter(field =>
            [field.name, field.key, field.source].some(value =>
                String(value || "").toLowerCase().includes(query))) : fields;
    }
    get psRichComponents() {
        const all = (this.state.psData && this.state.psData.rich_components) || [];
        const query = (this.state.psRichQuery || "").trim().toLowerCase();
        const filtered = query ? all.filter(c =>
            [c.name, c.code, c.col, c.group].some(value =>
                String(value || "").toLowerCase().includes(query))) : all;
        return filtered.slice(0, 120);
    }
    psRichSearch(ev) { this.state.psRichQuery = ev.target.value || ""; }
    psRichSetMode(ev) { this.state.psRichMode = ev.target.value || "both"; }
    psRichIsUsed(component) { return this.state.psRichUsedIds.includes(component.id); }
    psRichMetaIsUsed(field) { return this.state.psRichUsedMetaKeys.includes(field.key); }
    _psRichBindTokenControls(editor) {
        if (!editor) return;
        for (const remove of editor.querySelectorAll("[data-ps-remove-token]")) {
            remove.removeEventListener("pointerdown", this._psRichNativeRemoveClick);
            remove.removeEventListener("click", this._psRichNativeRemoveClick);
            remove.addEventListener("pointerdown", this._psRichNativeRemoveClick);
            remove.addEventListener("click", this._psRichNativeRemoveClick);
        }
    }
    _psRichRefreshUsed() {
        const editor = this._psRichEditor();
        if (!editor) return;
        const ids = [...editor.querySelectorAll(".ps-component-token")]
            .map(node => parseInt(node.dataset.psRuleId, 10)).filter(Boolean);
        const metaKeys = [...editor.querySelectorAll(".ps-meta-token")]
            .map(node => node.dataset.psMeta).filter(key => this._psRichMetaField(key));
        // Capture user-owned DOM before changing reactive state. Without this,
        // the patch that refreshes the left-hand Used badges can restore the
        // pre-edit document and silently undo an insert or removal.
        this.state.psRichDraft = editor.innerHTML;
        this._psRichNeedsSeed = true;
        this.state.psRichUsedIds = [...new Set(ids)];
        this.state.psRichUsedMetaKeys = [...new Set(metaKeys)];
        this._psRichBindTokenControls(editor);
    }
    _psRichCellFromRange(range) {
        const editor = this._psRichEditor();
        if (!editor || !range) return null;
        let node = range.commonAncestorContainer;
        if (node && node.nodeType !== Node.ELEMENT_NODE) node = node.parentElement;
        const cell = node && node.closest && node.closest("td, th");
        return cell && editor.contains(cell) ? cell : null;
    }
    _psRichSelectCell(cell) {
        const editor = this._psRichEditor();
        if (this._psRichCellEl && this._psRichCellEl.isConnected) {
            this._psRichCellEl.classList.remove("ps-rich-cell-selected");
        }
        const context = cell && editor && editor.contains(cell)
            ? payslipTableContext(cell) : null;
        this._psRichCellEl = context ? cell : null;
        this.state.psRichTableActive = Boolean(context);
        this.state.psRichTableLabel = context
            ? `Row ${context.rowIndex + 1}, column ${context.cellIndex + 1} · ${context.rows.length} × ${context.columnCount}`
            : "";
        if (context) cell.classList.add("ps-rich-cell-selected");
    }
    _psRichActiveCell() {
        const editor = this._psRichEditor();
        if (this._psRichCellEl && this._psRichCellEl.isConnected
                && editor && editor.contains(this._psRichCellEl)) return this._psRichCellEl;
        return this._psRichCellFromRange(this._psRichRange);
    }
    _psRichPlaceCaret(cell) {
        const editor = this._psRichEditor();
        if (!cell || !editor || !editor.contains(cell)) {
            this._psRichSelectCell(null);
            return;
        }
        const range = document.createRange();
        range.selectNodeContents(cell);
        range.collapse(false);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        this._psRichRange = range.cloneRange();
        this._psRichSelectCell(cell);
        editor.focus();
    }
    psRichRememberSelection(ev) {
        const editor = this._psRichEditor();
        const selection = window.getSelection && window.getSelection();
        if (!editor || !selection || !selection.rangeCount) return;
        const range = selection.getRangeAt(0);
        if (!editor.contains(range.commonAncestorContainer)) return;
        this._psRichRange = range.cloneRange();
        const eventCell = ev && ev.target && ev.target.closest && ev.target.closest("td, th");
        this._psRichSelectCell(eventCell || this._psRichCellFromRange(range));
    }
    psRichCommand(command, value = null) {
        const editor = this._psRichEditor();
        if (!editor) return;
        editor.focus();
        const selection = window.getSelection();
        if (this._psRichRange && editor.contains(this._psRichRange.commonAncestorContainer)) {
            selection.removeAllRanges();
            selection.addRange(this._psRichRange);
        } else {
            const range = document.createRange();
            range.selectNodeContents(editor);
            range.collapse(false);
            selection.removeAllRanges();
            selection.addRange(range);
        }
        document.execCommand(command, false, value);
        this.psRichRememberSelection();
    }
    psRichToolbar(command, ev) {
        if (ev) ev.preventDefault();
        this.psRichCommand(command);
    }
    psRichBlock(ev) {
        const value = ev.target.value;
        if (value) this.psRichCommand("formatBlock", value);
        ev.target.value = "";
    }
    psRichFont(ev) {
        const value = ev.target.value;
        const editor = this._psRichEditor();
        const range = this._psRichRange;
        const cell = this._psRichActiveCell();
        const hasTextSelection = Boolean(editor && range && !range.collapsed
            && editor.contains(range.commonAncestorContainer));
        if (value && cell && !hasTextSelection) {
            if (value === "inherit") cell.style.removeProperty("font-family");
            else cell.style.fontFamily = value;
            if (!cell.getAttribute("style")) cell.removeAttribute("style");
            this._psRichSelectCell(cell);
        } else if (value) {
            this.psRichCommand("fontName", value);
        }
        ev.target.value = "";
    }
    psRichInsertTable() {
        this.psRichCommand("insertHTML", '<table><tbody><tr><th>Label</th><th>Value</th></tr><tr><td>Edit me</td><td>Edit me</td></tr></tbody></table><p><br></p>');
    }
    psRichInsertTableEvent(ev) {
        if (ev) ev.preventDefault();
        this.psRichInsertTable();
    }
    psRichTextColor(command, ev) {
        const value = ev && ev.target && ev.target.value;
        if (!/^#[0-9a-f]{6}$/i.test(value || "")) return;
        this.psRichCommand(command === "background" ? "hiliteColor" : "foreColor", value);
    }
    psRichTableAction(action, ev) {
        if (ev) ev.preventDefault();
        const cell = this._psRichActiveCell();
        if (!cell) { this._psRichSelectCell(null); return; }
        let next = cell;
        if (action === "row_above") next = insertPayslipTableRow(cell, false);
        else if (action === "row_below") next = insertPayslipTableRow(cell, true);
        else if (action === "column_before") next = insertPayslipTableColumn(cell, false);
        else if (action === "column_after") next = insertPayslipTableColumn(cell, true);
        else if (action === "merge_right") {
            next = mergePayslipTableCellRight(cell);
            if (!next) this.notif.add(_t("There is no compatible cell to merge on the right."), { type: "warning" });
            next = next || cell;
        } else if (action === "merge_down") {
            next = mergePayslipTableCellDown(cell);
            if (!next) this.notif.add(_t("There is no compatible cell to merge below."), { type: "warning" });
            next = next || cell;
        } else if (action === "split_cell") {
            next = splitPayslipTableCell(cell);
            if (!next) this.notif.add(_t("This cell is not merged."), { type: "warning" });
            next = next || cell;
        }
        else if (action === "delete_row") next = deletePayslipTableRow(cell);
        else if (action === "delete_column") next = deletePayslipTableColumn(cell);
        else if (action === "delete_table") {
            deletePayslipTable(cell);
            next = null;
        }
        this._psRichPlaceCaret(next);
    }
    psRichCellColor(kind, ev) {
        const value = ev && ev.target && ev.target.value;
        const cell = this._psRichActiveCell();
        if (!cell || !/^#[0-9a-f]{6}$/i.test(value || "")) return;
        if (kind === "background") cell.style.backgroundColor = value;
        else cell.style.color = value;
        this._psRichSelectCell(cell);
    }
    psRichClearCellColor(ev) {
        if (ev) ev.preventDefault();
        const cell = this._psRichActiveCell();
        if (!cell) return;
        cell.style.removeProperty("background-color");
        cell.style.removeProperty("color");
        if (!cell.getAttribute("style")) cell.removeAttribute("style");
        this._psRichSelectCell(cell);
    }
    psRichSetBorderScope(ev) {
        this.state.psRichBorderScope = ev.target.value === "cell" ? "cell" : "table";
    }
    psRichBorder(ev) {
        const preset = ev.target.value;
        const cell = this._psRichActiveCell();
        if (cell && preset) {
            applyPayslipTableBorder(cell, this.state.psRichBorderScope, preset);
            this._psRichSelectCell(cell);
        }
        ev.target.value = "";
    }
    _psRichInsertTokenHtml(token) {
        const editor = this._psRichEditor();
        if (!token || !editor) return;
        editor.focus();
        const selection = window.getSelection();
        let range = this._psRichRange;
        if (!range || !editor.contains(range.commonAncestorContainer)) {
            range = document.createRange();
            range.selectNodeContents(editor);
            range.collapse(false);
        } else {
            range = range.cloneRange();
        }
        // execCommand("insertHTML") unwraps contenteditable=false spans in some
        // table-cell contexts.  Insert the fragment through the live Range so
        // the component wrapper and its rule metadata survive serialization.
        const fragment = range.createContextualFragment(token + "\u200B");
        const last = fragment.lastChild;
        range.deleteContents();
        range.insertNode(fragment);
        if (last) {
            range.setStartAfter(last);
            range.collapse(true);
            selection.removeAllRanges();
            selection.addRange(range);
            this._psRichRange = range.cloneRange();
        }
        this._psRichRefreshUsed();
    }
    psRichInsertComponent(component, ev) {
        if (ev) ev.preventDefault();
        this._psRichInsertTokenHtml(this._psRichTokenHtml(component, this.state.psRichMode || "both"));
    }
    psRichInsertMeta(field, ev) {
        if (ev) ev.preventDefault();
        this._psRichInsertTokenHtml(this._psRichMetaTokenHtml(field));
    }
    psRichComponentDragStart(component, ev) {
        if (!ev || !ev.dataTransfer) return;
        ev.dataTransfer.effectAllowed = "copy";
        ev.dataTransfer.setData("application/x-pb-payslip-component", JSON.stringify({
            id: component.id, mode: this.state.psRichMode || "both",
        }));
    }
    psRichMetaDragStart(field, ev) {
        if (!ev || !ev.dataTransfer) return;
        ev.dataTransfer.effectAllowed = "copy";
        ev.dataTransfer.setData("application/x-pb-payslip-meta", JSON.stringify({ key: field.key }));
    }
    psRichEditorDragOver(ev) {
        const types = ev && ev.dataTransfer ? Array.from(ev.dataTransfer.types || []) : [];
        if (!types.includes("application/x-pb-payslip-component") && !types.includes("application/x-pb-payslip-meta")) return;
        ev.preventDefault();
        ev.dataTransfer.dropEffect = "copy";
    }
    psRichEditorDrop(ev) {
        if (!ev || !ev.dataTransfer) return;
        const rawMeta = ev.dataTransfer.getData("application/x-pb-payslip-meta");
        const raw = rawMeta || ev.dataTransfer.getData("application/x-pb-payslip-component");
        if (!raw) return;
        ev.preventDefault();
        let payload;
        try { payload = JSON.parse(raw); } catch (_e) { return; }
        const editor = this._psRichEditor();
        if (!editor) return;
        let range = null;
        if (document.caretRangeFromPoint) range = document.caretRangeFromPoint(ev.clientX, ev.clientY);
        else if (document.caretPositionFromPoint) {
            const pos = document.caretPositionFromPoint(ev.clientX, ev.clientY);
            if (pos) {
                range = document.createRange();
                range.setStart(pos.offsetNode, pos.offset);
                range.collapse(true);
            }
        }
        if (range && editor.contains(range.commonAncestorContainer)) this._psRichRange = range;
        if (rawMeta) {
            const field = this._psRichMetaField(payload.key);
            if (field) this.psRichInsertMeta(field);
            return;
        }
        const component = this._psRichComponent(payload.id);
        if (!component) return;
        const previousMode = this.state.psRichMode;
        this.state.psRichMode = payload.mode || "both";
        this.psRichInsertComponent(component);
        this.state.psRichMode = previousMode;
    }
    _psRichRemoveTokenFromEvent(ev) {
        const remove = ev.target && ev.target.closest && ev.target.closest("[data-ps-remove-token]");
        if (!remove) return false;
        ev.preventDefault();
        ev.stopPropagation();
        const token = remove.closest(".ps-component-token, .ps-meta-token");
        // pointerdown removes before Chromium's contenteditable selection
        // machinery can swallow the eventual click. The connected check keeps
        // the click fallback idempotent if the detached button later receives
        // the remainder of the same synthetic event sequence.
        if (token && token.isConnected) {
            token.remove();
            this._psRichRefreshUsed();
        }
        return true;
    }
    psRichEditorPointerDown(ev) {
        const remove = ev.target && ev.target.closest && ev.target.closest("[data-ps-remove-token]");
        if (remove) ev.preventDefault();
    }
    psRichEditorClick(ev) {
        if (this._psRichRemoveTokenFromEvent(ev)) return;
        this.psRichRememberSelection(ev);
    }
    _psRichSerializedHtml() {
        const editor = this._psRichEditor();
        if (!editor) return this.state.psRichDraft || "";
        const clone = editor.cloneNode(true);
        for (const token of clone.querySelectorAll(".ps-component-token")) {
            const ruleId = parseInt(token.dataset.psRuleId, 10);
            const mode = token.dataset.psMode;
            const marker = ruleId && ["label", "value", "both"].includes(mode)
                ? `{{pb_component:${ruleId}:${mode}}}` : "";
            token.replaceWith(document.createTextNode(marker));
        }
        for (const token of clone.querySelectorAll(".ps-meta-token")) {
            const key = token.dataset.psMeta || "";
            const marker = ["employee_name", "employee_id", "department", "date_from", "date_to", "period"].includes(key)
                ? `{{pb_meta:${key}}}` : "";
            token.replaceWith(document.createTextNode(marker));
        }
        // Browsers implement fontName with the legacy <font face="…"> tag.
        // Store a modern inline style instead: Odoo's sanitizer keeps the safe
        // font-family declaration and the same HTML works in preview and PDF.
        for (const font of clone.querySelectorAll("font[face]")) {
            const span = document.createElement("span");
            const existingStyle = font.getAttribute("style");
            const color = font.getAttribute("color");
            if (existingStyle) span.setAttribute("style", existingStyle);
            span.style.fontFamily = font.getAttribute("face") || "inherit";
            if (color) span.style.color = color;
            while (font.firstChild) span.appendChild(font.firstChild);
            font.replaceWith(span);
        }
        for (const cell of clone.querySelectorAll(".ps-rich-cell-selected")) {
            cell.classList.remove("ps-rich-cell-selected");
            if (!cell.className) cell.removeAttribute("class");
        }
        return clone.innerHTML;
    }
    async psSaveRich() {
        if (this.state.psRichBusy) return;
        const htmlValue = this._psRichSerializedHtml();
        this.state.psRichBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "save_payslip_content",
                [this.state.config.id, this.state.psRichTarget, htmlValue]);
            if (r && r.ok) {
                this.state.psRichOpen = false;
                await this._loadPayslip(this.state.psData.sample_id);
            } else this.notif.add((r && r.msg) || _t("Content could not be saved."), { type: "warning" });
        } finally {
            this.state.psRichBusy = false;
        }
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
        // Both config choosers can launch the wizard from their footer. Close
        // whichever is open, or its overlay keeps painting over the wizard and
        // the wizard only becomes visible once that one is dismissed.
        this.state.configPickerOpen = false;
        this.state.configSwitcherOpen = false;
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
