# PHASE 5 — Formula Engine Design: the Not-Built Backlog, High-Priority First

**Source of sequence:** `docs/FORMULA_ENGINE_VISION.html` §11 catalogue, filtered **Not built**, sorted
**High priority first**, Moonshot tier excluded. Feature IDs below are the catalogue numbers (W14 = row #14),
so this doc maps 1:1 to the vision table.

**Conventions:** every rule in `docs/FORMULA_ENGINE_CONVENTIONS.md` (C1–C11) is binding. Read it first.
Do not re-derive any plumbing fact marked ✅ — each was personally verified against the live code on 2026-07-12.

**Packaging:** four work packages, built in order **WP-A → WP-B → WP-C → WP-D**, one Opus session each.
After each package the user reports "opus done", Fable reviews, then the next kickoff line is used.
Part II holds design briefs for the 24 Medium features (designed fully in a later cycle); Part III is the
Low-priority backlog.

**Binding non-goals for all packages**
- No Moonshot features (M-tier). No re-design of features an existing doc already covers (cross-refs in Part II).
- Engine/wizard server code stays in `pb_hr_payroll_formula` (headless); all UI + studio RPCs in
  `pb_formula_studio` (C1). AI always has a deterministic fallback (C1).
- No schema migrations of existing tables beyond additive fields; no changes to the evaluator's semantics.
- Manifest `version` bumped in every commit that touches assets (C2). One feature-scoped commit per W-feature (C10).

---

## Verified infrastructure the packages build on

| Fact | Where (verified) |
|---|---|
| Grid renders ALL columns — no virtualization; components are columns, 6 fixed property rows | `grid_studio.js:7` (`ROWS`), full `<table class="g2-table">` in `grid_studio.xml` |
| Grid UI state id-keyed (focus/selection/editing/fill), survives wholesale prop refresh | `grid_studio.js:46-84` |
| Display order = `sequence`; letters frozen with high-water mark | `grid_studio.js:90-93`, `formula_rule.py:1129-1154` |
| Client has full component list + dependency graph + preview values in memory | `formula_studio.js` state: `components`, `graph {nodes,edges,execution_order,unused,cycles}`, `preview.values` |
| Client BFS tint primitives, memoized | `grid_studio.js:221-242` (`_bfsCols`, `_ensureTint`) |
| `useHotkey` already wired in the studio root | `formula_studio.js:6`, usage `:300-306` |
| Fixed-position overlay primitives: `.g2-ac` autocomplete, `.g2-bulkpop` + scrim | `grid_studio.xml:200-232`, `grid.scss:170-182` |
| Studio RPC facade `pb.formula.studio` (AbstractModel, 4,568 lines) | `pb_formula_studio/models/pb_formula_studio.py` |
| `save_formula` `:729` returns bare `{ok}`; `bulk_save_formulas` `:705` hardcodes `reason='fill'` `:717` | verified |
| F7 write funnel: outgoing snapshots, context contract (`formula_version_reason/_note/_seen`, `skip_formula_version`) | `formula_rule.py:1157-1194`, `VERSIONED_FIELDS :14-20` |
| `_formula_at(rule, when)` = formula live at time T (earliest version at-or-after T, else current) | `pb_formula_studio.py:1027-1034` |
| `compare_to_milestone` / `_changes_between` produce per-rule old/new + token-diff runs | `pb_formula_studio.py:1036-1110` |
| `restore_version(rule_id, seq)` restores ONE rule, reason='restore', recomputes python + validity | `pb_formula_studio.py:988-1014` |
| Releases = query over F7 versions between two milestones; `release_approve` seals milestone `Release vN` | `formula_release.py`, `pb_formula_studio.py:1140-1194` |
| Chunked simulation engine: `hr.formula.simulation` via `simulate_prepare/batch/result/drop`, `overrides={code: draft_formula}`, ~50-slip chunks | `pb_formula_studio.py:2068-2098` |
| Test cases: `hr.formula.sample.data`; `_compute_results` depends ONLY on `input_values_json` + `config_id.rule_ids` (membership) → **formula edits do NOT rerun tests today** | `formula_sample_data.py:164-181`; validation `:183-230` (uses `coerce_number`) |
| Payslips store `formula_computed_values` (full `{code: value}` JSON) + `formula_input_values`, `calculation_method='formula'`, `formula_config_id` | `hr_payslip_formula.py:21-60` |
| Payrun batch recompute exists (regression anchor) | `hr_payslip_run.py:10` |
| Import preview mixin: capture-in-context, confidence 40/25/20/15 (15% = sheets with a primary key, **binary**), `_diagnose`, fix actions; `issue_type` enum already contains `primary_key_miss` (unused: "later tasks", `:344`) | `multisheet_import_preview.py:41-151, 321-345, 371-377` |
| Import execute already supports updating existing rules: `update_existing` flag, match by code | `multisheet_import_wizard.py:2686, 2721, 2765-2770` |
| Primary-key resolution per sheet | `multisheet_import_wizard.py:124-167` (`primary_key_column_name` on sheet lines) |
| Studio LLM entry: `_llm_chat(messages, json_mode=False)` `:4179`; engine reaches it only guarded (`multisheet_import_preview.py:206-213`) | verified |
| AI pulse (cron anomalies + `provider.generate_text` summaries) exists but is global/cron, not per-payrun | `payroll_ai_pulse.py:72-106, 328-361` |
| Manifest versions at design time: studio `19.0.1.38.0`, engine `19.0.1.23.0` | both `__manifest__.py` |
| Studio problems/rename/mapping surfaces (reused, not rebuilt): `get_problems :2303`, `rename_component :2432`, `mapping_canvas_data :2562`, `get_component_edit :771` | verified |

Effort summary: WP-A ≈ 3.5 wks · WP-B ≈ 2 wks · WP-C ≈ 3 wks · WP-D ≈ 4 days. Total ≈ 9–10 dev-weeks.

---

# WP-A — Studio Command Layer (`pb_formula_studio` only) — W109 → W14 → W99 → W100

Build in that order: W109 changes how grid cells materialize, so the find/palette/hover layers land on
the final DOM contract. W14/W99/W100 share one client-side search index (D-A4).

## Locked decisions

- **D-A1 (W109)** Virtualize **columns only** (rows are a fixed 6-property vocabulary). Keep the real
  `<table>`: window = `[first..last]` visible columns ± 8 overscan, with two spacer `<td>`s (left/right)
  of computed width per row. Activate only when `ordered.length > 60`; below that render everything
  (zero regression risk for typical configs). Column width becomes a fixed constant `--g2-colw`
  (set it to the current rendered width; read it once via `getComputedStyle`).
- **D-A2 (W109)** The render set is `window ∪ pinned`, where pinned = focus column, editing column,
  fill source + targets, tint anchor, scenario-ghost bases, drag column. A cell that owns transient UI
  never unmounts mid-interaction. Keyboard nav to an off-window column: set focus id first, then
  `scrollIntoView`; the scroll handler (rAF-throttled) recomputes the window; id-keyed focus survives (C3).
- **D-A3 (W14)** Find & replace is **client-side search** (all formulas/names/codes are already in
  `state.components`), **server-side commit** through `bulk_save_formulas` extended with
  `reason='bulk'`, `note='find/replace: <q> → <r>'`. Replace mutates **formula text only**. A hit on a
  component *code or name* offers "Rename component…" (jumps to the existing `rename_component` flow)
  instead of text replacement — codes are referential identities (C5), never string-replaced.
- **D-A4 (shared)** One memoized search index in `formula_studio.js`:
  `[{id, col, code, name, category, formula}]` lowercased, rebuilt when `state.components` is replaced.
  W14 filters it with match options; W99 fuzzy-scores it; W100 resolves hover targets against it.
- **D-A5 (W99)** Command palette is registry-driven: a static array of command descriptors
  `{id, section, label, keywords, run()}` + dynamic sections (components, configs). No new RPCs — every
  action calls an existing `formula_studio.js` method (view switches, selectComponent, open import/release/
  shadow/AI drawers). `Ctrl/Cmd+K` via `useHotkey`, global within the studio action.
- **D-A6 (W100)** Hover cards are **pure client-side** (name, code, col, category, token chips, live
  preview value from `state.preview.values[col]`, validity) — zero RPC, zero latency. 350 ms open delay,
  `pointer-events: none` (no hover-trap), dismiss on scroll/keydown/mouseleave. One reusable
  `<HoverCard/>` OWL component positioned fixed like `.g2-ac`.
- **D-A7 (W14)** Replace validates before committing: run each proposed formula through
  `validate_formula_live` in a batched loop client-side (reuse debounce token pattern, C8) and show
  per-hit validity in the preview; invalid proposals are excluded from commit by default.

## Tasks

**TA.1 — W109 column window (core)** — new `useVirtualCols()` helper inside `grid_studio.js` (no new file):
computes `{first, last, leftPad, rightPad}` from `scrollLeft`, `clientWidth`, `--g2-colw`, `ordered.length`;
rAF-throttled scroll listener on `scrollerRef`. `ordered` slicing goes through one `visibleCols` getter used
by the template's `t-foreach` (all six rows + header). Spacer cells carry `colspan=1` fixed widths via style.
AC: with the 2 VN demo configs (<60 components) DOM is byte-identical to today (feature dormant); with a
synthetic 250-component config (create via shell loop, keep for the demo library) the grid mounts < 300 ms,
scroll is smooth, and total rendered `<td>`s ≤ (window+overscan+pinned) × 6.

**TA.2 — W109 interaction survival** — pinned-set logic (D-A2); drag-fill auto-scroll at window edges;
autocomplete/editor overlay positions computed from the rendered cell rect (unchanged code path — verify).
AC: on the 250-component config: (1) F2-edit column 200 via keyboard-only from column 5 — focus, editor,
autocomplete all work; (2) drag-fill from col 40 to col 90 crossing the window edge auto-scrolls and commits
N version rows reason='fill' (C4); (3) dependency tint on a hub component tints off-window columns correctly
once scrolled into view (BFS is data-level, `grid.scss` classes apply on render).

**TA.3 — W109 scenario/reorder compatibility** — scenario ghost columns and F111 drag-reorder work with
windowing (ghosts pin with their base; dragOver targets only rendered columns — dropping past the window
edge auto-scrolls). AC: scenario create/eval/promote and a reorder from col 3 to col 120 both work on the
250-component config.

**TA.4 — W14 find panel** — new `static/src/js/grid/find_replace.js` + template + `find.scss` (manifest
bump, C2). Drawer-style panel (reuse drawer pattern `formula_studio.js:256-257`): query, replace-with,
options (match case, whole token — default ON for replace), scope chips (Formulas / Names / Codes).
Hit list grouped by component: col+code chip, formula with `<mark>`ed match, per-hit checkbox, validity
pill after dry-run (D-A7). `Ctrl/Cmd+F` opens it when focus is inside the studio; `Escape` closes (existing
hotkey pattern). Enter in query = find; the panel is also openable from W99 palette.
AC: searching `VLOOKUP` on VN demo config lists every formula containing it with correct counts; searching
a code like `BHXH` shows formula refs AND a "rename" affordance for the component itself, which opens the
existing rename flow (no text replace of codes).

**TA.5 — W14 replace commit** — extend `bulk_save_formulas(items, reason='fill', note=False)`
(`pb_formula_studio.py:705`): validate `reason` against `_VALID_VERSION_REASONS`-compatible subset
(`fill`,`bulk`), pass `formula_version_note`; drag-fill callers unchanged (default keeps 'fill').
Find&replace commits checked+valid hits with `reason='bulk'`. After commit: refresh + `compute_preview`
(existing save pipeline), toast "Replaced N occurrence(s) in M component(s)".
AC: replacing `0.105` → `SIRATE` across 6 formulas creates exactly 6 version rows, all reason='bulk' with
the find/replace note (C4 batch rule); history view shows them; an invalid proposal (syntax break) is
excluded and reported, not committed.

**TA.6 — W99 command palette** — new `static/src/js/palette/command_palette.js` + xml + `palette.scss`.
Overlay = fixed, centered, scrim; list = sections **Components** (index D-A4, jump = selectComponent +
scroll grid), **Views** (Cards/Grid/Tests/Settings/Compare when WP-C lands), **Actions** (New component,
Import…, Find & replace, Release preview, Shadow run, Explain formula, Problems), **Configs** (switch,
from `state.configs`). Fuzzy scorer: subsequence match with word-boundary bonus (~30 lines, no lib).
Keyboard: ↑↓ Enter Escape; typing filters live; `?` footer hint. Register `control+k` AND `meta+k`.
AC: ⌘K → "bhx" → Enter selects the BHXH component in the grid with focus + tint; ⌘K → "rel" opens release
preview; palette opens in < 50 ms (no RPC on open).

**TA.7 — W100 hover cards** — new `static/src/js/hover_card.js` (+xml/scss). Attach via event delegation
on the studio root for: token chips on editor cards, `depends_on`/`used_by` chips, grid formula-cell
component references (resolve token under cursor from the cell's token spans), palette rows (preview on
highlight). Card: name, col+code, category pill, formula as token chips, live sample value (formatted via
existing `formatValue`), validity/warning line. AC: hovering any reference chip on the VN demo shows the
card in ≤ 400 ms with the same value the grid value-row shows; card never intercepts clicks; scroll kills it.

**TA.8 — polish + tours** — pb_coach steps for find (⌘F), palette (⌘K), hover cards; shortcuts listed in
the palette footer. Chrome MCP validation run (below). Manifest bump; 4 feature commits (one per W).

### Skeleton S-A1 — the window + pinned-set core (the risky spot)

```js
// grid_studio.js — inside setup()
this.vcols = useState({ first: 0, last: Infinity, leftPad: 0, rightPad: 0, on: false });
this._colW = null; // lazily read from --g2-colw on first measure

_recomputeWindow() {
    const n = this.ordered.length;
    if (n <= 60) { if (this.vcols.on) Object.assign(this.vcols, {on:false, first:0, last:Infinity, leftPad:0, rightPad:0}); return; }
    const el = this.scrollerRef.el; if (!el) return;
    if (!this._colW) this._colW = parseFloat(getComputedStyle(el).getPropertyValue("--g2-colw")) || 160;
    const labelW = /* frozen label col width, measure once */ this._labelW ??= el.querySelector(".g2-rowlabel")?.offsetWidth || 0;
    const first = Math.max(0, Math.floor((el.scrollLeft) / this._colW) - 8);
    const last  = Math.min(n - 1, Math.ceil((el.scrollLeft + el.clientWidth - labelW) / this._colW) + 8);
    Object.assign(this.vcols, { on: true, first, last,
        leftPad: first * this._colW, rightPad: (n - 1 - last) * this._colW });
}
// PINNED SET — cells owning transient UI never unmount (D-A2).
get _pinnedIds() {
    const p = new Set();
    const add = id => id != null && p.add(id);
    add(this.ui.focus.colId); add(this.ui.editing?.colId); add(this.ui.dragId);
    if (this.ui.fill.active || this.ui.fill.pending) { add(this.ui.fill.srcId); this.ui.fill.targets.forEach(t => add(t.id)); }
    return p;
}
get visibleCols() { // template iterates THIS everywhere `ordered` was iterated
    if (!this.vcols.on) return this.ordered;
    const pin = this._pinnedIds;
    return this.ordered.filter((c, i) => (i >= this.vcols.first && i <= this.vcols.last) || pin.has(c.id));
}
// GOTCHA: pinned off-window columns break the contiguous spacer math — subtract
// each pinned column's width from the pad on its side, keyed by its `ordered`
// index. Compute pads in visibleCols' getter alongside the filter, not separately.
// GOTCHA: scroll listener must be passive + rAF-coalesced; never setState per event.
// GOTCHA: after `load()` replaces components, call _recomputeWindow() in onPatched —
// n may have changed and stale pads misplace the sticky header row.
```

### WP-A verification (Chrome MCP on pb_demo VN world)

1. Dormancy: VN demo config grid — DOM cell count and all Phase-1/2 grid interactions unchanged.
2. Build the persistent 250-component demo config (shell; add to demo-scheme library per C10).
3. Keyboard round-trip at scale (TA.2 AC), drag-fill across window edge, scenario + reorder (TA.3).
4. Find & replace: TA.4/TA.5 ACs including version-row count check via history panel.
5. ⌘K on both configs; ⌘F/⌘K/hover pb_coach tour steps fire.
6. Regression anchor: batch recompute of VN demo payruns — zero value drift (C10).

---

# WP-B — Import Integrity (`pb_hr_payroll_formula`, mixin only) — W37 → W40

## Locked decisions

- **D-B1 (W37)** Join-key health is computed **per selected secondary sheet against the main sheet's key
  set** at the same moment the preview lines are built (inside the existing
  `action_process_with_resolution` wrapper — one new call, no new wizard step). Metrics per sheet:
  `coverage` (% of main-sheet key values found in the sheet), `duplicates`, `blank_keys`,
  `type_mismatch` (numeric-as-text / `123.0` float artifacts), `fuzzy_only` (case/whitespace-only matches).
- **D-B2 (W37)** Confidence stays ONE score with the same 40/25/20/15 weights (C7): the 15% `key_ratio`
  term upgrades from binary "sheet has a key" to `avg(coverage)` over selected sheets (a sheet with no
  key = 0.0). Breakdown JSON gains a `key_health` sub-object. Rows that would silently drop become
  preview lines with the already-existing `issue_type='primary_key_miss'` (`:371-377`) — turning the
  `:344` "later tasks" comment into reality.
- **D-B3 (W37)** Fixable mismatches (case/whitespace/float-artifact) get a one-click fix action
  `normalize_keys` (extends the existing `fix_action` selection) that applies normalization to the
  in-wizard key matching only — source files are never mutated.
- **D-B4 (W40)** Diff re-import is a **preview layer over the existing `update_existing` commit path**
  (`multisheet_import_wizard.py:2721, 2765-2770`) — we do not build a second import pipeline. When the
  target config already has rules, the review step shows a config diff: **Added** (import code ∉ config),
  **Changed** (code match, resolved formula ≠ live `excel_formula`), **Unchanged**, **Missing from file**
  (config code ∉ import — reported, NEVER auto-deleted; per-line opt-in `archive` action only).
- **D-B5 (W40)** Before the commit that applies a re-import, record a milestone
  `Before re-import <filename>` (`hr.formula.config.milestone.record`, `formula_rule_version.py:74-78`).
  This makes every re-import instantly comparable (`compare_to_milestone`) and rollbackable (WP-C W86).
  Updated rules write with `formula_version_reason='import'`, note = filename (C4).

## Tasks

**TB.1 — W37 key-health scanner** — new mixin file `wizards/multisheet_join_health.py`
(`_inherit` the wizard; C6). Method `_scan_join_health()` → per-sheet dicts (D-B1 metrics + up to 20
sample missing keys); store `join_health_json`; called from the preview wrapper after
`_build_preview_lines`. Key sets come from the already-loaded sheet data (the wizard has parsed rows in
memory at this state — locate the parsed-rows structure next to `:124-167` primary-key resolution;
do not re-read the file). AC: a doctored 3-sheet VN workbook (10 missing keys, 3 dupes, 5 float-artifact
keys on sheet 2) reports exactly those counts per sheet.

**TB.2 — W37 preview + confidence wiring** — `primary_key_miss` preview lines for main-sheet rows whose
key misses a selected sheet (capped 200, C8); `key_ratio = avg(coverage)` in `_compute_confidence`
(D-B2); `key_health` in breakdown JSON; health table rendered in the review step
(`multisheet_wizard_view_inherit.xml` — Html field like `ai_review_html`).
AC: the doctored workbook's confidence drops vs the clean one specifically via the `keys` term (visible
in the breakdown gauge); clean VN Thaco template import score is unchanged to 3 decimals (regression, C10).

**TB.3 — W37 normalize fix** — `normalize_keys` fix action (D-B3): strip/casefold/`float→int` string
keys inside the wizard's matching pass; re-run `_scan_join_health` + `_compute_confidence` after applying.
AC: the 5 float-artifact keys match after one click; coverage and confidence rise accordingly; source
preview values untouched.

**TB.4 — W40 diff builder** — new mixin file `wizards/multisheet_reimport_diff.py`. After preview build,
if `config_id.rule_ids` non-empty: classify D-B4 buckets by code match (codes normalized per C5), store
`reimport_diff_json` + render an Html diff table (added=green, changed=amber with old→new formula text,
missing=grey with archive checkbox). Formula equality compares **resolved** import formula vs live
`excel_formula`, whitespace-insensitive. AC: re-importing the identical Thaco workbook → 0 added,
0 changed, all unchanged; re-importing with 2 edited formulas + 1 new column + 1 removed column reports
exactly 2/1/1.

**TB.5 — W40 guarded commit** — wrap `action_execute_import`: when a diff exists, (1) record the D-B5
milestone, (2) force `update_existing` semantics for Changed rows with reason='import' + filename note,
(3) apply `archive` only to explicitly ticked Missing rows (set `active=False`? — `hr.formula.rule` has
no `active` field: instead set `is_visible_in_grid=False` + note, and report; true deletion stays manual),
(4) after commit, chatter-log the summary on the config. AC: after the 2/1/1 re-import, version history
shows exactly 2 'import' rows with the filename note; `compare_to_milestone` against the auto-milestone
reproduces the diff table; the unticked missing rule is untouched.

**TB.6 — studio surfacing** — import drawer's confidence panel shows the key-health table and the diff
summary (data already in the wizard records the studio reads); pb_coach step. Manifest bumps both modules.

### Skeleton S-B1 — coverage scorer core (risky: key normalization must match the wizard's real matching)

```python
_FLOAT_ARTIFACT = re.compile(r'^\d+\.0$')

def _key_norm(self, v, fuzzy=False):
    """Mirror of the BASE matching semantics + optional fuzzy layer. Base match
    uses the raw cell values — verify against _resolve_primary_key_column's
    consumers before changing ANYTHING here; health must measure the real join,
    not an idealized one."""
    s = '' if v is None or v is False else str(v).strip()
    if _FLOAT_ARTIFACT.match(s):
        s = s[:-2]                      # '1023.0' -> '1023' (Excel float artifact)
    return s.casefold() if fuzzy else s

def _scan_join_health(self):
    main = self._main_sheet_line()      # the driving sheet (has the employee rows)
    main_keys = [self._key_norm(v) for v in self._sheet_key_values(main)]
    main_set = set(k for k in main_keys if k)
    out = []
    for sheet in self.available_sheet_ids.filtered('is_selected') - main:
        vals = [self._key_norm(v) for v in self._sheet_key_values(sheet)]
        nonblank = [v for v in vals if v]
        sset = set(nonblank)
        fuzzy_set = {self._key_norm(v, fuzzy=True) for v in nonblank}
        missing = [k for k in main_set if k not in sset]
        fuzzy_only = [k for k in missing if self._key_norm(k, fuzzy=True) in fuzzy_set]
        out.append({
            'sheet': sheet.sheet_name,
            'has_key': bool(sheet.primary_key_column_name),
            'coverage': (len(main_set) - len(missing)) / len(main_set) if main_set else 0.0,
            'duplicates': len(nonblank) - len(sset),
            'blank_keys': len(vals) - len(nonblank),
            'fuzzy_only': len(fuzzy_only),
            'sample_missing': missing[:20],
        })
    return out
# GOTCHA: sheets can be huge — never materialize per-row records; lists/sets only.
# GOTCHA: a sheet with no primary key contributes coverage 0.0 to key_ratio (D-B2),
# preserving today's binary penalty as the degenerate case.
```

### WP-B verification

1. Fixture workbooks (add to demo library, C10): clean Thaco template; doctored 3-sheet (TB.1 numbers);
   edited re-import pair (TB.4 numbers).
2. Full wizard walk via Chrome MCP for each: health table, confidence gauge + breakdown, fix actions,
   diff table, guarded commit, auto-milestone visible in the compare picker.
3. Regression: clean-template confidence unchanged; batch recompute anchor (C10).

---

# WP-C — Trust & Comparison — W82 → W86 → W97

> **✅ IMPLEMENTED 2026-07-13** (`ea29f138` W82 · `e7e9f052` W86 · `6c923ddf` W97). Deployed
> pb_hr_payroll_formula 19.0.1.33.0 · pb_formula_studio 19.0.1.48.0. Branch 19.1, **not pushed**.
> Implementation record + deviations:
> - **W82** — `hr.formula.config.run_sample_tests(changed_codes)` (new `models/formula_config_tests.py`);
>   wired into `save_formula`/`bulk_save_formulas`/`save_component`/`restore_version`/`promote_scenario`
>   + the WP-B re-import commit, each returning a `tests` object; studio test chip + failures popover +
>   danger-toast-on-new-failure. Verified live: controlled pass→fail→pass with exact expected/computed/
>   delta rows on Viet Retail. (D-C2's "large-config" guard runs only changed-code-mentioning samples.)
> - **W86** — `rollback_preview`/`rollback_simulate_prepare`/`rollback_apply` + Releases-History Rollback
>   button → change-list → simulate → type-to-confirm dialog. **Deviation (important):** the timestamp
>   milestone boundary is fatally second-granular (Odoo Datetime domain compares truncate sub-second), so
>   a milestone sealed in the same second as its edits can't be separated from them — this broke the
>   double-rollback round-trip. Fixed by adding `hr.formula.config.milestone.version_hwm` (max version id
>   at seal) and id-based boundary helpers (`_formula_at_ver`/`_constant_at_ver`/`_changes_between_ver`/
>   `_ms_hwm`/`_seal_milestone`); release_preview/approve/detail now use them too (which also makes
>   constant-only changes releasable → rollback-able, closing D-C5 end-to-end). Verified live: preview,
>   apply, double-rollback round-trip, not-latest + unreleased guards, constant rollback (SI cap reverted).
> - **W97** — transient `hr.formula.period.comparison` (cmp_create/prepare/batch/finalize/result/drop) +
>   `compare_*` studio RPCs + a new **Compare** view (5th toolbar button + palette). **Deviation:** reads
>   `formula_computed_values` **with a fallback to payslip line totals** (the demo history — and real
>   client data — store computed values as lines, not the JSON; only 28/26.5k slips carried the JSON), the
>   same fallback the F6/F8 drivers use. Verified live: engine sums match independent SQL exactly over 978
>   matched employees (9.7s), Compare UI driven end-to-end with zero console errors.
> - **UI validation scope:** the W97 Compare view was driven fully live (Chrome MCP). The W82 chip and W86
>   rollback dialog were validated by engine-correctness (shell) + a clean asset-bundle compile + a
>   zero-console-error mount of the shared bundle, but were not interactively driven (would require
>   mutating demo formulas / sealing a demo release).

> **Design refresh 2026-07-13 (after WP-A/WP-B/WP-E landed).** Still Opus-ready; three notes:
> 1. **`pb_formula_studio.py` line anchors below shifted ~+12** from the WP-A additions. Verified
>    current locations: `save_formula:741`, `bulk_save_formulas:705`, `restore_version:1000`
>    (python-rebuild + validity at **:1015-1022**), `_formula_at:1039`, `compare_to_milestone:1049`,
>    `_changes_between:1096`, `simulate_prepare:2080`, `promote_scenario:2265`. Methods are unchanged
>    by name — find them there, don't re-derive.
> 2. **`restore_version` restores only `excel_formula`, never `constant_value`** (verified `:1015-1022`)
>    — this is exactly the gap D-C5 closes; `_restore_rule_state` must add the constant path.
> 3. **The converter fix (ledger C12) strengthens W82/W97, not changes them.** Sample tests and period
>    comparison now read Excel-correct computed values through `_evaluate_rules_with_dependencies`. One
>    caveat for TC.1: a sample whose **expected** baseline was generated with the pre-fix converter
>    (e.g. a formula using `^`, `<>`, or `ROUND` on a .5 boundary) may now legitimately show a failure —
>    that is the fix surfacing a real correction, not a W82 bug. The VN demo has **zero** such drift
>    (proven), so its baselines still pass; note it in the failures UI wording, don't "fix" it by
>    reverting math. Also: **WP-B is now built**, so D-C2's "re-import commit calls `run_sample_tests`"
>    is a concrete edit to `multisheet_reimport_diff.py::action_execute_import` (add the `tests` call
>    after `super()` returns, once per commit).

## Locked decisions

- **D-C1 (W82)** Tests run on save is an **explicit post-save hook**, not an `@api.depends` widening —
  `_compute_results` intentionally depends only on membership (`formula_sample_data.py:164`); wiring it
  to formula text would synchronously re-evaluate every sample on every rule write in every code path
  (imports, packs, merges). Instead: new engine method
  `hr.formula.config.run_sample_tests(changed_codes=None)` → forces `_compute_results` +
  `_compute_validation` on `sample_data_ids` (invalidate + recompute), returns
  `{total, passed, failed, pending, failures:[{sample_id, sample, code, expected, computed, delta}]}` (≤ 20 failures).
- **D-C2 (W82)** Callers: studio `save_formula`, `bulk_save_formulas`, `restore_version`,
  `promote_scenario`, and WP-B's re-import commit — each calls `run_sample_tests` **once per logical
  operation** (after the batch, mirroring the C4 one-batch rule) and returns a `tests` object in its
  response. Guards: skip when the config has no samples; if `len(sample_data_ids) > 20`, run only the
  samples whose input/expected JSON mention a changed code (cheap containment check) and mark the rest
  `pending`. Tests **never block a save** — red is information, not a lock.
- **D-C3 (W82 UI)** Grid/status surfaces show a test chip (`✓ 4/4` green, `✗ 2/4` red, `— no tests` grey)
  next to the existing validity pill; clicking it opens the existing tests view filtered to failures.
  Red toast on save when tests newly fail.
- **D-C4 (W86)** Only the **latest release** of a config is rollback-eligible (linear history — no
  cherry-pick reverts). Rollback is blocked while unreleased changes exist (`release_preview.change_count
  > 0` → "Release or discard current changes first"). This keeps "rollback of release vN" ≡ "restore the
  config to milestone `from` of vN" with zero ambiguity.
- **D-C5 (W86)** Rollback compares via `_changes_between(config, release.from_milestone.date, None)`
  **extended to constants**: comparison reads `excel_formula` AND `constant_value` (from
  `snapshot_json`) — legislation packs edit constants (C4/VERSIONED_FIELDS), a formula-only rollback
  would silently keep a new SI cap. Apply loop reuses the `restore_version` restoration logic factored
  into a helper `_restore_rule_state(rule, excel_formula, constant_value)` (reason='restore',
  note='Rollback <release>', shared `formula_version_seen` set, single savepoint — all-or-nothing).
- **D-C6 (W86)** Simulate-first: the rollback dialog runs the delta through the existing simulation
  engine (`simulate_prepare` with `overrides={code: old_formula}` + value overrides for constants,
  `pb_formula_studio.py:2080`) and shows the org-wide distribution before the Apply button arms.
  After apply: milestone `Rollback of <release>` + a release row named the same (audit trail stays in
  one list), narrative auto-drafted.
- **D-C7 (W97)** Period comparison is a **read-only chunked aggregation** — new lean TransientModel
  `hr.formula.period.comparison` in the engine module cloning the simulation driver shape
  (`prepare → batch(~100 slip-pairs) → result`, C8); studio RPC wrappers `compare_prepare/batch/result/drop`
  mirroring `simulate_*`. No persistence beyond the transient.
- **D-C8 (W97)** Employee matching by `employee_id` across the two selected runs (runs filtered to slips
  with `calculation_method='formula'` and the studio's current config). Unmatched = joiners/leavers,
  counted separately. Per-component fold: `{code: {sum_a, sum_b, delta, n_changed, movers:[top ±5 slips]}}`;
  per-employee fold: net delta list (top ±25). **Cause candidates**: components changed for ≥ 90% of
  employees whose NET moved, cross-referenced with `_changes_between(config, run_a.date_end, run_b.date_end)`
  → "PIT formula changed in Release v4" attribution when the dates bracket a version row.

## Tasks

**TC.1 — W82 engine method** — `run_sample_tests` on `hr.formula.config` (new file
`models/formula_config_tests.py` or in `formula_config.py` if < 80 lines) per D-C1/D-C2 guards.
AC: shell test on VN demo config — edit a formula that breaks a sample's expectation, call the method,
get the failure row with correct expected/computed; runtime < 2 s for the demo config's samples.

**TC.2 — W82 caller wiring + UI** — extend the four studio RPC responses + WP-B commit; test chip +
failures toast + filtered tests view (D-C3). AC: grid-editing GROSS to a wrong formula turns the chip red
with the failing sample named in the toast, without blocking the save; drag-fill over 6 columns triggers
exactly ONE test run (log-verified); fixing the formula turns it green on save.

**TC.3 — W86 rollback preview RPC** — `rollback_preview(release_id)`: eligibility per D-C4 (+ block
reasons), change list per D-C5 (formula + constant rows, token-diff runs for formulas), and the
simulation work-list (D-C6). AC: on a demo config with two sealed releases, only the latest offers
rollback; preview lists exactly the release's changed components including a constant-only change.

**TC.4 — W86 apply RPC + UI** — `rollback_apply(release_id)` per D-C5 (savepoint, N version rows
reason='restore', milestone + audit release row); studio Releases surface gains the Rollback button →
dialog: change list → simulate (existing sim distribution component) → type-the-release-name confirm →
apply → refreshed history. AC: after rollback, every affected rule's formula/constant equals its
at-`from`-milestone value (`compare_to_milestone` returns 0 changes vs that milestone); history shows the
restore batch; the audit release row exists; a second rollback attempt is blocked (nothing unreleased,
but the rollback release is now latest and rolling IT back restores the original state — verify this
round-trips cleanly).

**TC.5 — W97 comparison engine** — `hr.formula.period.comparison` (fields: config/run_a/run_b/state/
`fold_json`; methods `cmp_create/cmp_prepare/cmp_batch/cmp_finalize/cmp_drop`) per D-C7/D-C8. Batch
parses `formula_computed_values` (`hr_payslip_formula.py:45-49`) for ~100 pairs per call, accumulates
into `fold_json`. AC: shell-driven comparison of two VN demo months over 4,512 employees completes in
< 60 s of chunked calls; component sums equal independent SQL/pandas spot-totals for 3 components;
joiners/leavers counts match the demo world's known churn.

**TC.6 — W97 studio surface** — new view `compare` (`static/src/js/compare/period_compare.js` + xml +
`compare.scss`; sidebar/palette entries): run pickers (runs listed via a small `compare_runs(config_id)`
RPC), progress bar during chunks (clone shadow-run UX), component delta table (sortable, delta-pct heat
tint), employee movers drawer, cause-candidates card with release attribution (D-C8), and a **Narrate**
button placeholder wired in WP-D. AC: Chrome MCP — full compare of two demo months from the UI; sorting
and drill-downs work; a month-pair spanning a known release shows that release in cause candidates.

### Skeleton S-C1 — rollback apply core (risky: atomicity + constants)

```python
@api.model
def rollback_apply(self, release_id):
    rel = self.env['hr.formula.release'].browse(int(release_id))
    config = rel.config_id
    guard = self._rollback_guard(rel)          # D-C4: latest release, no unreleased changes
    if not guard['ok']:
        return guard
    when = rel.from_milestone_id.milestone_date if rel.from_milestone_id else None
    changes = self._changes_between_full(config, when)   # D-C5: formulas + constants
    seen = set()
    ctx = dict(formula_version_reason='restore',
               formula_version_note=_('Rollback %s') % rel.name,
               formula_version_seen=seen)
    try:
        with self.env.cr.savepoint():          # all-or-nothing
            for ch in changes:
                rule = self.env['hr.formula.rule'].browse(ch['rule_id']).with_context(**ctx)
                self._restore_rule_state(rule, ch['old_formula'], ch.get('old_constant'))
    except Exception as e:
        return {'ok': False, 'msg': str(e)}
    self.env['hr.formula.config.milestone'].sudo().record(config, _('Rollback of %s') % rel.name)
    # audit trail: the rollback IS a release (D-C6)
    ...create release row with drafted narrative...
    tests = config.run_sample_tests()          # W82 synergy: rollback is a save too
    return {'ok': True, 'restored': len(seen), 'tests': tests}
# GOTCHA: _restore_rule_state must mirror restore_version's python_formula rebuild +
# validity check (pb_formula_studio.py:1015-1022) — a restored formula that no longer
# converts must FAIL the savepoint loudly, not land half-applied (C7). Note that
# restore_version writes ONLY excel_formula; the constant path is net-new here.
# GOTCHA: old_constant comes from snapshot_json of the version row bracketing `when`
# (_formula_at logic generalized) — do NOT add a second history (release = query, B3).
```

### WP-C verification

1. W82: shell + Chrome MCP per TC.1/TC.2 ACs on the persistent demo schemes (C10).
2. W86: two-release fixture on a demo config; TC.3/TC.4 ACs including the double-rollback round-trip;
   confirm rollback of a legislation-pack constant restores the old cap in a recomputed sample.
3. W97: TC.5 numeric spot-checks vs SQL; TC.6 UI walk; then the C10 batch-recompute anchor last —
   comparisons are read-only, drift here means a bug escaped earlier.

---

# WP-D — Payrun Anomaly Narration (`pb_formula_studio` + engine read-only) — W48

> **✅ IMPLEMENTED 2026-07-13** (`5a63508a`). pb_hr_payroll_formula 19.0.1.34.0 · pb_formula_studio
> 19.0.1.49.0. Branch 19.1, not pushed. `hr.formula.period.comparison.narrate(lang)` (deterministic EN+VI
> blocks in code, no .po pipeline) + `narrate_allowed_numbers()`; studio `narrate_comparison(cmp_id, lang)`
> wraps it with an optional `_llm_chat` polish gated by `_narr_numbers_ok` (pure, unit-tested — a poisoned
> wrong-total reply is rejected). Narrate card on the Compare surface (blocks, EN/VI toggle, source badge,
> copy). Verified live: EN+VI render with no AI key ("Built-in"), numbers match the fold, zero console
> errors. **Deviation:** VI comes from code-held templates (not the `_()` path) so it works with no
> translation catalogue — the D-D3 intent, more honest for a keyless demo.

Hard dependency: WP-C's `hr.formula.period.comparison` payload.

## Locked decisions

- **D-D1** Narration consumes the finished compare fold (`fold_json`) — no new aggregation. RPC
  `narrate_comparison(cmp_id, lang='en'|'vi')` on `pb.formula.studio`.
- **D-D2** Deterministic narrative FIRST, always produced: template sentences from (1) headline totals
  ("Total net −2.1% month-over-month"), (2) cause candidates with release attribution (D-C8:
  "Net fell for 14 employees; all share the changed SI cap — Release v4, sealed 03 Jun"),
  (3) joiners/leavers, (4) outlier movers. LLM (via `_llm_chat`, `json_mode=True`, facts-only payload —
  the D-D2 sentences plus the numeric fold, never raw slips) may **rewrite for fluency in the requested
  language**; any exception or empty return keeps the deterministic text (C1). Numbers in the LLM output
  are re-verified against the fold (regex-extract, compare, reject on mismatch — no invented figures).
- **D-D3** EN/VI both come from the deterministic layer too (template strings through the standard
  `_()` translation path with VI terms consistent with the payslip vocabulary), so narration works with
  no API key configured.
- **D-D4** The cron pulse (`payroll_ai_pulse.py`) is untouched — W48 is on-demand, per comparison, in
  the studio. (Feeding compare folds into pulse alerts is a Part-II/56-adjacent idea, out of scope.)

## Tasks

**TD.1 — deterministic narrator** — engine-side pure function (engine module, C1-clean:
`hr.formula.period.comparison.narrate(lang)`) building the D-D2 sentence blocks from `fold_json`.
AC: with no AI config at all, EN and VI narration render for a demo comparison, numbers match the fold,
release attribution sentence appears for the release-spanning pair.

**TD.2 — LLM polish + guard** — studio `narrate_comparison` wraps TD.1, optional `_llm_chat` rewrite +
number re-verification (D-D2). AC: with AI configured, narration is fluent and every number in it exists
in the fold; with a poisoned mock reply (wrong total), the deterministic text is served instead
(unit-test the guard).

**TD.3 — UI + tour** — Narrate card on the compare surface (skeleton button from TC.6): renders blocks,
EN/VI toggle, "AI-polished"/"Built-in" source label (clone the `action_ai_review` labeling pattern,
`multisheet_import_preview.py:250-258`); copy-to-clipboard. pb_coach step. Manifest bump, commit.

### WP-D verification

Chrome MCP: compare two demo months → Narrate in EN and VI, with and without an AI key; poisoned-reply
unit test; numbers cross-checked against the compare table on screen.

---

# Part II — Medium-priority design briefs (24)

Format: seam → locked direction → effort. Full task-level design happens in the cycle that schedules each.
Ordered by affinity to the WP surfaces they extend.

> **2026-07-14:** the first Medium batch — **W18, W4, W8, W104** — is promoted to a full Opus-ready
> package: see **WP-F** at the end of this doc. The four briefs below are kept for history; WP-F
> supersedes them where they differ (it was re-verified against the post-WP-A..E code).

**W18 Shortcuts overlay** *(Grid/UX, 1–2 d)* — `?` (and palette entry) opens a static overlay listing every
studio hotkey. Seam: hotkey handlers in `grid_studio.js:298-335` + `formula_studio.js:300`; render from the
same registry the W99 palette uses so it can never drift from reality. Build immediately after WP-A.

**W4 Multiple pinned sample rows** *(Grid, 3–4 d)* — 2–3 pinned value rows (junior/median/executive), each a
`compute_preview(cfgId, sample_id)` call (`pb_formula_studio.py:634`); extend `state.preview` to keyed store
`{sample_id: values}`; ROWS gains dynamic `value:<sample_id>` entries — touches the fixed-vocabulary
assumption (C3), design the row-model change carefully with W109 in place.

**W8 Collapse by category** *(Grid, 3 d)* — builds ON F111 grouping (shipped): fold a category's columns into
one summary column (sum of visible members from `preview.values`). Client-side fold state + a synthetic
column renderer; interacts with W109 windowing (fold changes `ordered` length — recompute window).

**W104 Snippet library** *(UX, 4 d)* — new engine model `hr.formula.snippet` (name, body with `${ref}`
placeholders, category, company-shared) + studio CRUD RPCs; insertion via cell autocomplete (`grid_studio.js:372`)
and the W99 palette; seed with proration/cap/bracket patterns from the VN demo formulas.

**W83 Test coverage view** *(Trust, 3–4 d)* — which components no sample exercises: for each
`hr.formula.sample.data`, coverage = codes in `expected_values_json` ∪ dependency closure of exercised
formulas (graph from `get_intelligence`); render as a lens in the problems rail (`get_problems`,
`pb_formula_studio.py:2303`) + a sortable coverage % column in the tests view. Pairs with W82's chip.

**W84 Boundary-value test generation** *(Trust, 3 d)* — deterministic, LLM-free core: for every
`hr.formula.rate.table` bracket edge (`formula_rate_table.py:48-150`) and every `MIN/MAX/IF` threshold
constant in formulas, generate sample rows at edge−1/edge/edge+1 into `hr.formula.sample.data` (marked
`generated`). Expected values seeded from current engine output (characterization tests) — flagged for
human confirmation before they count as passing.

**W49 AI test generation** *(PayAI, 3 d)* — LLM layer over W84: `_llm_chat` proposes realistic input
profiles + which expectations matter, engine computes the expected values (never the LLM); same
`generated`+confirm flow. Requires W84 first.

**W42 Rate-table extraction** *(Migration, 4–5 d)* — import-time detection of bracket-shaped constant
blocks / `IF`-chains → propose promotion to `hr.formula.rate.table` (+ rewrite the formula to `BRACKET()`
via `expand_brackets`' inverse). Seam: preview mixin + F11 typed-cell bracket editor (already designed in
PHASE2_3 F11 — extend, don't re-design). Wizard fix-action style acceptance.

**W41 Excel round-trip export** *(Migration, 4–5 d)* — config → living `.xlsx`: one row per sample
employee, one column per component, real Excel formulas rebuilt from `excel_formula` (letters map 1:1 by
design), rate tables as named ranges on a second sheet. Library decision inherited from F112's export
(cross-ref FEATURES_111_114 doc); engine-side action on `hr.formula.config`.

**W17 Smart paste from Excel** *(Grid, 4 d)* — paste TSV/formula column into the grid: parse clipboard in
`grid_studio.js`, map `A1`-style refs through the studio's existing letter machinery (`_expand_refs`
`pb_formula_studio.py:109`), stage as a drag-fill-style ghost preview (reuse `fill.targets` UX + one
`bulk_save_formulas` commit, reason='bulk').

**W40-adjacent W43 Multi-file import session** *(Migration, 1 wk)* — session model chaining the existing
wizards (formulas workbook + historical results + employee master) with one shared confidence view; heavy
lift is UX, all three imports exist (multisheet, shadow `shadow_import_wizard.py`, batch
`payroll_import_batch.py:20`). Design fully only when scheduled.

**W52 Duplicate-logic detection** *(PayAI, 3 d)* — token-normalized hash (rename refs to canonical slots)
over `python_formula` per config → "these 3 formulas are identical modulo references; extract a component";
problems-rail lens + optional LLM naming of the extracted component (W53 synergy). Pure engine + rail.

**W54 Simplification suggestions** *(PayAI, 3–4 d)* — detect nested-`IF` ladders convertible to brackets
(shares W42's detector), suggest `BRACKET()` rewrite with a token diff + equivalence check (evaluate both
against all samples + boundary rows; only offer when outputs are identical). Requires W84 to be honest.

**W62 Transforms on the wire** *(Mapping, 3–4 d)* — ×/÷/round/expression badges on mapping-canvas wires
with live preview against the batch-test employee. Seam: `mapping_canvas_data` (`pb_formula_studio.py:2562`)
+ the F10 canvas kit; transform stored on the mapping line, applied in the engine's input-building path.

**W65 Mapping templates** *(Mapping, 3 d)* — save/apply a mapping board as a named template across
configs/clients (bureau workflow). Seam: the mapping models behind the canvas + `bureau_clone`
(`pb_formula_studio.py:1272`) precedent for cross-config copying.

**W95 Budget vs actual** *(Simulation, 4 d)* — budget lines per config/period (lean model) vs W97's
per-component payrun fold; variance drill-down reuses the compare table component. Requires WP-C.

**W98 Offer calculator** *(Simulation, 3 d)* — synthetic-employee net/cost preview through the live config:
a one-off `_evaluate_rules_with_dependencies` call over hypothetical inputs (the sample-data path,
no records created); simple form UI + shareable summary. Good first post-WP-C filler.

**W50 Auto documentation** *(PayAI, 4 d)* — bilingual handbook generated from config: deterministic
skeleton (per-component `_explain` `pb_formula_studio.py:155`, rate tables, execution order) + `_llm_chat`
prose polish per section (C1 fallback = the skeleton itself); export as attachment (HTML→PDF via Odoo
report). Regenerate button + staleness stamp vs last milestone.

**W56 Copilot × coach tours** *(PayAI, 3 d)* — PayAI intent "how do I…" → launch the matching pb_coach
tour (engine: intent classifier already in `payroll_ai_engine.py:189`; map intents → tour ids; response
carries a `start_tour` action). Needs the tour registry exposed as data.

**W74 Slip-linked explainers** *(Payslip, 3 d)* — manager view: payslip line → its component's
explanation (deterministic `_explain` + `explain_formula_ai`) with THIS slip's numbers woven in from
`formula_computed_values`. Seam: payslip form/portal templates + `payslip_identifier_payload` grouping.

**W73 Payslip themes** *(Payslip, 3–4 d)* — brand tokens (logo, accent, typography) on the F9 payslip
studio scheme, within compliance bounds; render in both A4 and portal previews. Extend the F9 canvas —
cross-ref PHASE2_3 F9; do not fork its data model.

**W89 @mentions & notifications** *(Collab, 3 d)* — F15 comments exist (component `note_count`/
`review_open` in the studio payload): add partner parsing + `mail.thread` notification with a deep link
(config + component anchor via the palette's jump). Odoo mention widget reuse.

**W91 Guided handoff mode** *(Collab, 1 wk)* — consultant-authored narrated waypoints (ordered pins over
components/surfaces) stored per config; replays as a pb_coach-style walkthrough for the client team.
Design fully when scheduled; reuses B7 review-share auth for external viewers.

**W108 Tablet review mode** *(UX, 1 wk)* — read-only studios + full approval flow on iPad: audit
`studio_responsive.scss`, gate editing affordances behind `can_edit` + pointer-type, test release
sign-off and rollback dialogs at 1024×768 via Chrome MCP emulation. Honest phone scope: approvals only.

---

# Part III — Low-priority backlog (no design yet)

| W# | Feature | Pillar | Seam pointer |
|---|---|---|---|
| W15 | Conditional formatting on the live value row | Grid | heat-shade `preview.values` percentile in the value-row renderer |
| W53 | Naming & category suggestions | PayAI | creation-time `_llm_chat` + C5 code validation |
| W25 | Change heatmap | Intelligence | version-row counts + W82 failure counts per component |
| W87 | Presence | Collab | bus presence channel per config; defer with W90 (moonshot) |
| W102 | Formula timeline scrubber | UX | `get_rule_history` already returns the full sequence |
| W103 | Floating calculator | UX | tiny overlay evaluating expressions against `preview.values` |
| W106 | Dark mode | UX | token-swap layer over `studio.scss:1-5`; biz_theme coordination required |

---

# Report-back items (every package)

1. Diff summary per W-feature commit (files + line counts).
2. Any deviation from a locked decision, with reason (deviations without report = review finding).
3. New gotchas hit → **add to `FORMULA_ENGINE_CONVENTIONS.md`** in the same commit.
4. AC checklist with pass/fail per task, including the C10 batch-recompute anchor result.
5. Anything discovered that invalidates a Part-II brief.

# Opus kickoff lines

**WP-A:**
> Implement WP-A (Studio Command Layer: W109 virtualized grid, W14 find & replace, W99 command palette, W100 hover cards) exactly as specified in docs/PHASE5_FORMULA_ENGINE_DESIGN.md, honoring every rule in docs/FORMULA_ENGINE_CONVENTIONS.md. Work only in pb_formula_studio. Build in order TA.1→TA.8, one feature-scoped commit per W-feature, and report back per the Report-back items section.

**WP-B:**
> Implement WP-B (Import Integrity: W37 join-key health check, W40 diff re-import) exactly as specified in docs/PHASE5_FORMULA_ENGINE_DESIGN.md, honoring docs/FORMULA_ENGINE_CONVENTIONS.md — mixin-only, never grow the base wizard. Build TB.1→TB.6, one commit per W-feature, report back per the Report-back section.

**WP-C:**
> Implement WP-C (Trust & Comparison: W82 tests run on save, W86 one-action rollback, W97 period comparison) exactly as specified in docs/PHASE5_FORMULA_ENGINE_DESIGN.md, honoring docs/FORMULA_ENGINE_CONVENTIONS.md. Build TC.1→TC.6, one commit per W-feature, report back per the Report-back section.

**WP-D:**
> Implement WP-D (W48 payrun anomaly narration) exactly as specified in docs/PHASE5_FORMULA_ENGINE_DESIGN.md, honoring docs/FORMULA_ENGINE_CONVENTIONS.md — deterministic narrative first, LLM polish guarded. Build TD.1→TD.3, one commit, report back per the Report-back section.

**WP-F:**
> Implement WP-F (Grid & Command Polish: W18 shortcuts overlay, W4 pinned sample rows, W8 collapse by category, W104 snippet library) exactly as specified in docs/PHASE5_FORMULA_ENGINE_DESIGN.md §WP-F, honoring docs/FORMULA_ENGINE_CONVENTIONS.md (C1, C2, C3, C5, C7, C8, C10, C11 are load-bearing here). Build TF.1→TF.6 in order, one feature-scoped commit per W-feature, validate on the pb_demo VN world (throwaway-clone pattern for the perf/fold checks, delete the clone afterwards), and report back per the Report-back items section. Do not touch docs/FORMULA_ENGINE_TOUR.html.

---

# WP-E — Import Resolution Integrity (`pb_hr_payroll_formula` wizard) — converter-audit follow-up

**STATUS: ✅ IMPLEMENTED by Fable 2026-07-12** (commit on branch `19.1`; deployed to Payobook19v2,
smoke-tested on the live registry). This was the import-side kernel, so — like the converter fix — it
was coded directly rather than handed to Opus. Binding rules folded into
`FORMULA_ENGINE_CONVENTIONS.md` **C13**; regression gate
`pb_hr_payroll_formula/tools/import_resolution_battery.py` (18 cases, all green). See the
**Implementation record** at the end of this section for what shipped vs. the spec below.

*Added 2026-07-12 after the Excel→Python converter deep audit. The converter itself was fixed
directly by Fable (see `FORMULA_ENGINE_CONVENTIONS.md` C12 and the battery tool
`pb_hr_payroll_formula/tools/excel_semantics_battery.py`). WP-E is the IMPORT-side remediation: the
stage between openpyxl and the stored `excel_formula` still destroys or mis-rewrites formulas in the
scenarios below. Findings were produced by a full review and the top three verified line-by-line.*

**Ordering note:** WP-E overlaps WP-B's files (wizard + preview mixin). WP-E landed first, so W37/W40
now build on trustworthy resolution output.

## Locked decisions

- **D-E1** No resolver may return the literal `"0"` for an unresolved reference. Replace every such
  return (`multisheet_import_wizard.py:1297, :1327, :1355` and the same-sheet VLOOKUP fallback in
  `formula_rule.py::_resolve_vlookup`) with an explicit unresolved marker that (a) keeps the original
  ref text in the stored formula, (b) creates a red preview line (`issue_type='unresolved_xref'`),
  and (c) fails conversion loudly (C7/C12 pattern: ValueError → `has_evaluation_error`).
- **D-E2** Anchor the direct cross-sheet ref regex (`:1332`): sheet token must be
  `(?:'[^']+'|[\wÀ-ỿ][\wÀ-ỿ .\-]*)` with a left boundary `(?<![\w!])` — never
  `[^'!]+` unanchored (it swallows `IF(Sheet2` and shreds the formula). Must cover unquoted
  Vietnamese sheet names (`Lương!A1`) in BOTH the masking pass (`:1389`) and extraction passes
  (`:668, :737, :745, :753, :3596`).
- **D-E3** Generated codes MUST honor the C5 contract: no underscores, no substring collisions.
  Replace `f"{base}_{n}"` dedup (`:2986-2990`), `COL_{n}` (`:2977`), `FORMULA_COL` (`:2972`) with
  underscore-free, collision-checked generation (e.g. `BASICSALARY`, `BASICSALARYB`, checked against
  the FULL config code set for substring conflicts both directions).
- **D-E4** Blue-constant scan must exclude data rows: scan strictly ABOVE `data_start_row`
  (`:2176`), so an employee's first-row VALUE is never frozen into a workbook-wide constant.
- **D-E5** Constants that fail numeric parse (text/dates, `:1710-1732`, `:2755-2759`) must import as
  red preview lines, not silent `0.0`.
- **D-E6** VLOOKUP/SUMIF rewrites that DROP lookup-key semantics (key discarded at `:1269`,
  `cross_sheet_resolver.py:110-167`; bounded SUMIF ranges widened at `:1303-1329`) must at minimum
  emit a WARNING preview line ("resolved positionally — verify join semantics"); track W37 (join-key
  health) as the structural fix.
- **D-E7** Row-offset detection: when a formula references a row ≠ the detected data row (`B4` when
  data row is 5 — running totals), flag a warning preview line; do NOT silently collapse to same-row.
- **D-E8** All changes in the **preview mixin / new mixin classes** (C6). Base-wizard edits allowed
  ONLY for the regex constants and `return "0"` sites themselves.

## Tasks

- **TE.1** D-E1 unresolved markers + red preview lines (all resolver fallbacks). AC: importing a
  workbook with a ref to an unmapped sheet produces a red line naming the ref; stored formula still
  contains the original ref text; rule shows `has_evaluation_error`.
- **TE.2** D-E2 regex anchoring + Vietnamese sheet names. AC: `=IF(Sheet2!B2>0,1,0)` resolves (or
  red-lines) intact; `=Lương!A1+B3` fully resolves; no formula text is ever shredded.
- **TE.3** D-E3 code generation contract. AC: duplicate headers import as underscore-free,
  non-substring codes; `_check_converter_contract` passes on the resulting config.
- **TE.4** D-E4 + D-E5 constant integrity. AC: blue DATA cell no longer becomes a constant; text/date
  constant → red line, not 0.0.
- **TE.5** D-E6 + D-E7 warning lines. AC: keyed VLOOKUP to a non-PK sheet and a running-total formula
  each produce a visible warning in preview.
- **TE.6** Re-import the ORIGINAL VN customer workbook (the one behind the live 616-rule config) and
  the pb_demo generator output; AC: zero silent zeros, preview confidence unchanged or higher,
  `excel_semantics_battery.py` still green, C10 batch-recompute anchor unchanged.

## Implementation record (2026-07-12)

**Shipped.** All eight decisions implemented; TE.1–TE.5 fully, TE.6 as harness + live smoke (the
original customer workbook wasn't on hand — see caveat). File-level:

| Decision | What shipped | Location |
|---|---|---|
| D-E1 | All 4 resolver fallbacks return `self._UNRESOLVED_MARK` (`#REF!`), never `"0"` — visible in the stored formula, red-lined by the mixin, refused loudly by the converter | `multisheet_import_wizard.py` `_resolve_cross_sheet_formula` (VLOOKUP/SUMIF/direct) + `_resolve_same_sheet_formula` VLOOKUP |
| D-E2 | Direct regex re-anchored: `(?<![\w!.'])(?:'[^']+'\|[A-Za-z_À-￿][\w.À-￿]*)\s*!…`; resolves refs inside functions, covers unquoted Vietnamese sheet names, never shreds | `_resolve_cross_sheet_formula` direct_pattern |
| D-E3 | `_generate_code` → `_dedupe_code_c5`: underscore-free + unique (`FORMULACOL`/`COL2024`, letter-suffix dedup); non-substring is best-effort (see deviation note — substring verified harmless) | `_generate_code`, `_dedupe_code_c5` |
| D-E4 | Blue-constant scan bound changed `data_start_row + 2` → `data_start_row` (excludes data rows) | `_collect_constants_for_sheet` |
| D-E5 | Constants parse via `excel_semantics.coerce_number`; non-numeric → sticky warning on the completion notice (collected in `unparseable_constants`), not silent success | `action_execute_import` |
| D-E6 | Resolved VLOOKUP/SUMIF → `warning` (lookup key dropped, verify per-employee row) | `multisheet_import_preview.py` `_diagnose` |
| D-E7 | Same-column-two-rows reference → `warning` (running total may be flattened) | `_diagnose` |
| D-E8 | Diagnosis/warnings all in the mixin; base-wizard edits confined to the 4 `return "0"` sites, the one regex, and code-gen | — |

**Deviations from the spec above (all intentional):**
- D-E1 uses `#REF!` as the marker rather than *preserving the exact original ref text*. Preserving the
  original text of an unresolved **VLOOKUP/SUMIF** would let the later direct-ref pass re-grab the
  fragment and silently produce a malformed-but-clean-looking formula (the mixin would score it OK).
  `#REF!` is inert to every downstream pass, unambiguously flagged, and still names the failing
  *component*. Direct single refs would have been safe to preserve verbatim, but one uniform marker is
  simpler and safer than two code paths.
- D-E5 surfaces non-numeric constants as a **sticky completion-notice warning + loud log**, not as a
  preview line. Constants don't currently get preview lines (only formulas do); a full constant preview
  surface is more than the finding needs and is deferred.
- D-E2's line numbers in the spec drifted after the C12 edits; the extraction-pass regexes
  (`:668,:737…`) were already anchored/safe, so only the resolver's direct_pattern needed the fix.
- D-E3 relaxes the spec's *strict* non-substring requirement to **underscore-free + unique**, with
  non-substring as a best-effort cosmetic. Two reasons: (1) strict non-substring is mathematically
  impossible when a header maps to an existing code (`Amount` vs an existing `AMOUNT` — every
  underscore-free superstring contains it); (2) a direct converter test proved substring codes
  (`AMOUNT`/`AMOUNTX`, `SI`/`SIEMP`) resolve **correctly** — the converter tokenizes greedily, so the
  underscore is the only real breaker. The original C5 substring warning traced to the underscore in
  its example (`BON_PERF`), not substringing per se.

**TE.6 caveat:** validated by the 19-case `import_resolution_battery.py` (real resolver/code-gen/
diagnose) + a live-registry smoke test (`_resolve_cross_sheet_formula` and `_generate_code` on a
transient wizard). The original VN customer workbook was not available in this session; the
converter-side `excel_semantics_battery.py` remains green and the C10 batch-recompute anchor is
unaffected (no engine-eval change in WP-E). **Recommended before customer use:** one real re-import of
that workbook through the preview to confirm confidence and red/warning lines behave as intended.

---

# WP-F — Grid & Command Polish — W18 → W4 → W8 → W104

> **✅ IMPLEMENTED 2026-07-14** (Opus) — `642da268` W18 · `3b37ee64` W4 · `88b0198d` W8 ·
> `e13e2552` W104 engine · `c69c4320` W104 studio · `06ff8748` W104 palette-insert fix. Deployed
> pb_hr_payroll_formula 19.0.1.35.0 · pb_formula_studio 19.0.1.53.0 to Payobook19v2 (`-u` both;
> `formulas` pip dep is now present so the engine `-u` no longer rolls back). Branch 19.1, not pushed.
> Implementation + validation record:
> - **W18** — registry-driven overlay: `SHORTCUT_GRID` static table + `shortcutSections` getter
>   (Find row derived from `act.find`), a guarded `?` window listener, front-of-Escape-ladder, grid
>   `?`-seed exclusion, palette "Keyboard shortcuts" entry. Live: opens from grid+cards, Esc closes
>   first, typing-guard holds, all 15 bindings render.
> - **W4** — parent `pinnedSamples`/`previewExtra`, `extraPreviews` prop + display-only value rows,
>   pin control by the cycler, `_refreshPinned` on all 6 save paths. Live on an 85-col clone: 3-row
>   matrix correct per-sample (cross-checked), one-save refresh of all rows, cap (button hidden when no
>   spare) + unpin, config-switch clears. **Pin UX deviation (intentional):** pinning the active sample
>   ADVANCES the active row to the next free sample (so the invariant "active ∉ pinned" holds and the
>   pin gives immediate feedback); needs ≥3 samples for 2 pins. Unpin also exposed as preview-panel chips.
> - **W8** — `viewOrdered` transform + `baseCols`; all four consumers switched; summary column with
>   per-row Σ; focus relocation; parent `state.folds`. Live: fold Σ exact, window drift-free
>   (scrollWidth 14388→13884 = −3 units on 4→1 constants, = label+units×colW at every scroll), nav/fill
>   skip folded, W4×W8 compose (per-sample Σ in every row). **Note:** the VN demo's `category` field
>   holds Input/Formula/Constant, so fold groups by those (data-driven, `_catKey` = category∥group).
> - **W104** — engine model `hr.formula.snippet` + 6 seeds (idempotent, 6 after 2nd `-u`), studio RPCs
>   (manager-guarded), ${CODE} resolution in the grid, autocomplete rows + palette Snippets section +
>   manage overlay. Live: green insert (`${MSNV}+${MCLNGHL}`→`B1+G1`, valid), red insert
>   (`${AMOUNT}`→literal, invalid msg, C7), palette + autocomplete both insert, CRUD round-trips.
>   **Bug found+fixed in validation (`06ff8748`):** `_afterPatch`'s editor-seeding early-`return`
>   swallowed the palette-queued insert on the mount patch → now consumed inside that block (ledger C3).
> - **C10 anchor:** no eval-path file touched (git-verified) + `excel_semantics_battery` green + 25/25
>   demo slips recompute to their stored values (max 0.5 VND on one PIT = raw-vs-rounded-line, C15, not
>   drift). Console clean across the whole sweep. Throwaway clone (85-col) created→driven→deleted
>   (cascade-clean); the real demo config is byte-unchanged.

**Designed 2026-07-14 (Fable), after WP-A..E shipped.** First Medium batch, promoted from the Part-II
briefs and re-verified against the live code. Modules: `pb_formula_studio` for all four features;
`pb_hr_payroll_formula` ONLY for the W104 snippet model + seed data (C1 boundary — no other engine
edits, no eval-path changes). Deployed baselines at design time: studio `19.0.1.49.0`, engine
`19.0.1.34.0`. Effort ≈ 11–13 d.

Build order is dependency order: W18 is standalone warm-up; W4 and W8 both restructure how the grid
renders columns/rows, and W8's fold pipeline must be built ON TOP of W4's extra rows (they share the
value-row templates); W104 is last (only feature with a schema change + `-u pb_hr_payroll_formula`).

## Verified plumbing facts (do not re-derive)

*Grid (`pb_formula_studio/static/src/js/grid/grid_studio.js`, 908 lines):*
- `ROWS` fixed vocabulary + `EDITABLE_ROWS` — `grid_studio.js:7-8`. Grid-local UI state (id-keyed
  focus/selection/editing/fill/drag) — `:50-69` (C3).
- Display order getter `ordered` — `:101-104`. Keyboard nav walks `this.ordered` — `onKeydown :419-456`;
  the printable-char branch that seeds an editor is `:449-451`.
- **W109 window:** `vcols` state `:79-85`, `VCOL_THRESHOLD=60`/`OVERSCAN=8` `:110-111`,
  `_recomputeWindow` `:132-174` — NOTE it now walks **cumulative units** (base column = 1 unit +
  1 per scenario ghost of that column), not `floor(scrollLeft/colW)`. `_pinnedIds` `:177-190`,
  `displayColumns` `:723-749` (unit kinds `base`/`scenario`/`spacer`; a spacer bridges a run of
  hidden BASE columns with width `gap × colW`). Length-change recompute in `_afterPatch` `:867-875`.
- Value row template: ONE `<tr class="g2-prow g2-valrow">` rendered from `props.formatValue(c.col)` —
  `grid_studio.xml:144-160`. Band strip/contiguity: `_bandStarts` `grid_studio.js:256-267`.
- Drag-fill target resolution `_fillTargetsFor` `:601-606` (filters `this.ordered` by colNum span).
- Cell autocomplete: `_updateAutocomplete` `:496-517` (items `{id,col,code,name,value}`, max 8),
  `_insertAutocomplete` `:530-545`, `_refRow` `:523-529`; dropdown template
  `pb_formula_studio.CellAutocomplete` `grid_studio.xml:246-258` (fixed-position `.g2-ac`, C11).

*Studio root (`pb_formula_studio/static/src/js/formula_studio.js`):*
- Palette registry `paletteCommands` `:688-712` — sections Views/Actions/Components/Configs; every
  `run()` calls an existing method. `CommandPalette.SECTION_ORDER` is STATIC at
  `command_palette.js:15` — a new section must be added there or it ranks last.
- Hotkeys: `_setupCommandLayer` `:766-774` — `useHotkey("control+k"/"control+f", {global:true,
  bypassEditableProtection:true})` (macOS ⌘ folds into "control"), plus `useExternalListener(window,
  "mouseover"/"scroll"/"keydown")` for hover cards. The Escape close-ladder is `useHotkey("escape")`
  `:343-355` (palette → find → drawers).
- Shared search index `searchIndex` `:630-648` (rebuilt on `state.components` identity change).
- Preview: `state.preview = {sample_id, values}` (single sample); formatter chain
  `previewVal :906-909` → `fmtTyped :898-905` → `vnd :891-895`; `sampleName :840-843`;
  `state.samples = [{id,name}]`.
- Grid prop wiring (all callbacks): `studio.xml:1127-1144`. Save-path preview refresh sites that W4
  must extend: `formula_studio.js:558-666` (save/bulk/find-commit) and `:801-807` (restore/promote).

*Server (`pb_formula_studio/models/pb_formula_studio.py`):*
- `compute_preview(config_id, sample_id)` `:660-662` → `_compute` `:633-657` returns
  `{'sample_id': int, 'values': {col_letter: float}}`, computed via
  `sample._evaluate_rules_with_dependencies` (the real evaluator — C5). Already per-sample; W4 needs
  **zero server changes**.
- Components payload carries `category_id`, `category`, `group`, `sequence` — `:250-263`.

*Engine (`pb_hr_payroll_formula`):*
- Model registration pattern: `models/__init__.py` (one import per file); access rows pattern in
  `security/ir.model.access.csv` — user `1,1,1,0`, manager `1,1,1,1`, groups
  `pb_hr_payroll_formula.group_formula_user` / `group_formula_manager`.
- Data files load via the manifest `data:` list; seed data uses `noupdate="1"`.

## Locked decisions

- **D-F1 (W18 trigger)** — the overlay opens on a **window-level keydown listener** checking
  `ev.key === "?"` with guards (target is not input/textarea/contenteditable; palette/find/AI not
  open), NOT via a `useHotkey` token — hotkey-service token parsing for shifted punctuation is
  layout-dependent and not worth the risk. Also reachable from the palette ("Keyboard shortcuts",
  Views section) and it joins the FRONT of the Escape ladder (`:343`). The grid's printable-seed
  branch (`grid_studio.js:449-451`) must EXCLUDE `"?"` (not a legal formula-start token) so the
  overlay is reachable while the grid scroller is focused; an OPEN editor keeps `?` normally
  (editor keydown already `stopPropagation`s, `:686`).
- **D-F2 (W18 content is registry-driven)** — one static descriptor list module-level next to
  `paletteCommands`: sections + rows `{keys:[...], label}`. The Views/Actions rows are DERIVED from
  `paletteCommands` labels where a binding exists (⌘K, ⌘F, Esc); grid keys (arrows, Tab, Enter/F2,
  Esc, Ctrl+Z, type-to-edit, drag-fill Enter/Esc) are a static table in that same module — one file
  to update, so W99 and W18 cannot drift apart. Zero RPC; overlay reuses the `.g2-bulkpop` scrim
  pattern (C11); `<kbd>`-styled chips, Lucide icons only.
- **D-F3 (W4 keeps ROWS frozen — C3)** — extra samples do NOT extend the `ROWS` vocabulary. The
  active sample's value row stays exactly as-is (focusable, part of nav). Pinned samples render as
  ADDITIONAL display-only `<tr class="g2-prow g2-valrow g2-valrow-extra">` rows below it —
  non-focusable, no `data-row`, no keyboard participation (precedent: scenario cells). Row label =
  sample name + unpin ×.
- **D-F4 (W4 state & data flow)** — parent owns `state.pinnedSamples = [sid,...]` (max 2 extra; the
  active sample is never in it) and `state.previewExtra = {sid: {sample_id, values}}`; grid receives
  ONE new prop `extraPreviews: [{sample_id, name, values}]` and formats via a passed
  `formatValueFor(col, values)` (reuse `fmtTyped`). Pin/unpin UI lives in the Live-preview panel's
  sample row (pin icon beside the `tp-sel` cycler, `studio.xml:1155`). Every save path that today
  refreshes `state.preview` also refreshes all pinned samples via ONE `Promise.all` of
  `compute_preview` calls (C8: per-save, never per-keystroke). Pinned set is **client-session only**
  (D: no server persistence in v1; reload resets). Config switch clears pins (like `load()` clears
  tests).
- **D-F5 (W8 fold = display transform, single pipeline)** — introduce `viewOrdered`: the unit list
  `[{kind:'base', comp} | {kind:'summary', cat, label, members:[comp]}]` built from `ordered` by
  collapsing each CONTIGUOUS run of a folded category into one summary unit (contiguity matches the
  band strip, `_bandStarts`; a category split across the sheet folds into multiple summary units —
  correct by construction). **All four consumers switch from `ordered` to `viewOrdered`:**
  `_recomputeWindow` (summary unit = 1 colW unit; ghost math applies to base units only),
  `displayColumns` (windows viewOrdered indices; `_pinnedIds` applies to base comp ids; summary
  units are never pinned), keyboard nav (`cols` = base units only), and `_fillTargetsFor` (folded
  columns are NEVER silent fill targets). Fold state is a plain `{catKey: true}` map owned by the
  PARENT (`state.folds`), passed as a prop with `onToggleFold(catKey)` — the "Group by category"
  toolbar grows per-category fold chips. Folding a category containing the focused column moves
  focus to the nearest visible base column. Client-only state; clears on config switch.
- **D-F6 (W8 summary cell content)** — header: category name + member count + unfold affordance
  (click anywhere on the column unfolds). Value row(s): Σ of member values from that row's values
  map, formatted with `vnd()` (orientation aid, not accounting — deductions are summed as computed,
  not negated). Name/Category/Type/Formula/Status rows show an em-dash. Band tint follows
  `_bandColor`.
- **D-F7 (W104 model in the engine — C1)** — new file `pb_hr_payroll_formula/models/formula_snippet.py`,
  model `hr.formula.snippet`: `name` (required), `category` (Selection: proration / cap / bracket /
  rounding / other), `body` (Text, an Excel fragment with `${CODE}` placeholders), `description`,
  `sequence`, `active`, `company_id` (optional; empty = shared library). Access rows: user read-only
  (`1,0,0,0`), manager full (`1,1,1,1`) — snippet CRUD is manager-only. Seed
  `data/formula_snippet_data.xml` (`noupdate="1"`) with 4–6 patterns taken from the VN demo formulas
  (workday proration, cap-at-constant, `BRACKET()` PIT, round-to-thousands). Schema change ⇒ engine
  manifest bump + `-u pb_hr_payroll_formula` (the ONLY `-u` of the package).
- **D-F8 (W104 insertion semantics — C5/C7)** — placeholders resolve at INSERTION time, client-side:
  `${CODE}` → column-letter ref (`col + _refRow()`) when CODE exists in the current config's
  components; an unresolvable placeholder is inserted AS-IS so live validation flags the cell red
  (visible failure, C7 — never silently dropped or zeroed). Two entry points, both into an open cell
  editor: (a) the cell autocomplete gains snippet rows (distinct `snippet` style, listed after
  component matches) when the typed query matches a snippet name/category; (b) palette section
  **Snippets** (add to `SECTION_ORDER`) — if no editor is open, it starts an edit on the focused
  formula cell first, then inserts at caret. Snippet management (list/create/edit/delete) is a small
  scrim overlay reachable from the palette ("Manage snippets…", managers only via `can_edit`).
  Studio RPCs on `pb.formula.studio`: `list_snippets()`, `save_snippet(vals)`,
  `delete_snippet(snippet_id)` — write paths guarded by the same manager check as other studio
  writes. Loaded once per `load()` into `state.snippets`.
- **D-F9 (no tour edits)** — `docs/FORMULA_ENGINE_TOUR.html` stays untouched (user-deferred until all
  features land).

## Tasks

**TF.1 — W18 shortcuts overlay** *(studio only, ~1 d)*
Registry module + overlay component/template + `?` listener + palette entry + Escape-ladder front.
AC: opens from cards AND grid views; does NOT open while typing in any input (cell editor, formula
bar, find, palette, AI chat); every listed binding actually works as printed (spot-check all);
`?` excluded from grid edit-seeding; zero RPC on open; zero console errors.

**TF.2 — W4 pinned sample rows** *(studio only, ~3 d)*
Parent pin state + preview-panel pin UI + `extraPreviews` prop + extra value rows + save-path
refresh extension (ALL sites: save_formula, bulk update, drag-fill commit, find&replace commit,
restore_version, promote_scenario).
AC: pin 2 extra samples → 3 value rows with correct per-sample values (cross-check one component's
three values against the Tests view for those samples); editing GROSS updates all three rows after
ONE save; cap enforced at 2 extra with a polite notification; unpin removes the row; config switch
clears pins; W109 clone (>60 cols) scrolls smoothly with extra rows present (spacers span them).

**TF.3 — W8 collapse by category** *(studio only, ~3 d)*
`viewOrdered` pipeline (skeleton S-F1) + fold chips on the grid toolbar + summary column + the four
consumer switches + focus relocation.
AC: folding Earnings on the demo config hides exactly its columns and shows one summary column whose
Σ equals the sum of the hidden columns' displayed raw values; fold state survives a save/refresh
(state is client-side; components array replacement must not reset it); keyboard nav skips folded
columns; drag-fill never targets a folded column; focused-column fold relocates focus without a
console error; on a >60-column clone, fold/unfold keeps the window exact — total `scrollWidth`
equals (visible units × colW) + label width at every step (no spacer drift); pinned W4 rows render
correct summary Σ per sample.

**TF.4 — W104 engine model + seeds** *(engine, ~1 d)*
`formula_snippet.py` + `__init__` import + access CSV rows + seed XML + manifest `data:` entry +
version bump + server `-u pb_hr_payroll_formula`.
AC: upgrade clean in the deploy ritual; seeds present exactly once after a SECOND `-u`
(noupdate honored); C10 batch-recompute anchor still zero-drift (no eval-path change expected —
prove it).

**TF.5 — W104 studio surface** *(studio, ~2–3 d)*
RPCs + `state.snippets` + autocomplete snippet rows + palette Snippets section (+ `SECTION_ORDER`)
+ insertion with placeholder resolution + manage overlay.
AC: inserting the PIT bracket snippet into a formula cell on the demo config resolves `${...}`
placeholders to the right column letters and validates green; a snippet referencing a code the
config lacks inserts with the literal `${CODE}` and the cell goes red with a clear message (C7);
non-manager sees insertion but no manage entry; palette shows Snippets as its own ranked section;
manage overlay CRUD round-trips.

**TF.6 — package validation sweep** *(~1 d)*
Interactive Chrome-MCP drive of all four features on the pb_demo VN world; perf/fold checks on a
throwaway >60-component clone of a demo config (create → drive → DELETE, keeping demo pristine —
the WP-C pattern); zero console errors across the sweep; C10 anchor run once for the package.

### Skeleton S-F1 — the fold pipeline (the risky spot: one unit list, four consumers)

```js
// grid_studio.js — W8. `ordered` stays untouched; everything downstream reads viewOrdered.
_catKey(c) { return String(c.category_id || c.category || c.group || "?"); }
get viewOrdered() {
    const folds = this.props.folds || {};            // parent-owned {catKey: true}
    const out = [];
    let openCat = null;                              // contiguous folded run being absorbed
    for (const c of this.ordered) {
        const k = this._catKey(c);
        if (folds[k]) {
            if (openCat === k) { out[out.length - 1].members.push(c); continue; }
            openCat = k;
            out.push({ kind: "summary", cat: k, label: c.category, members: [c], key: "cat:" + k + ":" + c.id });
        } else { openCat = null; out.push({ kind: "base", comp: c, key: "b" + c.id }); }
    }
    return out;
}
// _recomputeWindow: iterate viewOrdered; unit width = 1 colW for summary units,
//   1 + scenarioGhosts(comp) for base units. first/last index into viewOrdered.
// displayColumns: window over viewOrdered; pin-check = (u.kind === 'base' && pin.has(u.comp.id));
//   summary units window like base ones; spacers bridge hidden runs exactly as today.
// keyboard nav + _fillTargetsFor: this.viewOrdered.filter(u => u.kind === 'base').map(u => u.comp)
// GOTCHA: ui.focus.colId can point at a column that just got folded — the parent's
//   onToggleFold relocates focus BEFORE the re-render, else `focused` resolves but its
//   cell no longer exists and _scrollFocusIntoView queries a missing node every patch.
// GOTCHA: W4 extra value rows iterate the SAME displayColumns — build TF.2 first and
//   render summary Σ from the row's own values map, so W4×W8 composition is free.
```

## WP-F verification (Chrome MCP on pb_demo VN world)

1. W18: `?` from grid and cards; blocked while editing; all bindings true; Esc closes first.
2. W4: 3-row value matrix correct vs Tests view; one-save refresh of all rows; cap + unpin + config
   switch behaviours.
3. W8: fold Σ correctness; window exactness on the >60-col clone (scrollWidth check); nav/fill skip
   folded; focus relocation.
4. W4×W8 composition: fold with 2 pinned samples → per-sample Σ correct in every extra row.
5. W104: seeded snippets insert + resolve on demo config; unresolvable placeholder goes visibly red;
   manager-only manage; second `-u` idempotent.
6. C10 batch-recompute anchor: zero drift.
7. Console clean across the whole drive; clone deleted afterwards.

Report back per the **Report-back items** section (deviations from D-F1..D-F9 must be flagged).
