# PHASE 5 — Formula Engine Design: the Not-Built Backlog, High-Priority First

> **⏸ PHASE 5 ON HOLD — 2026-07-22 (user decision).** All shipped packages (WP-A…WP-J, WP-L) are
> implemented, reviewed, and live (engine `19.0.1.48.0` / studio `19.0.1.68.0`). **WP-K
> (W50/W74/W89) is DESIGNED but NOT BUILT** — its kickoff line at the top of this doc is still
> valid; re-verify the §WP-K "Verified plumbing facts" file:line refs against the live code
> before reusing it after the hold. The wrap-up act (refresh `docs/FORMULA_ENGINE_TOUR.html`
> through WP-L + icebox Part II/III remainders) is deferred until pickup. Open flag: stray draft
> config `DEMO_CONSTRUCTION_END_V` (id 103, created 2026-07-14) on live awaits a user
> keep/delete decision. Branch `19.1`, never pushed.

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
> **2026-07-14 (later):** the second batch — **W83, W84, W49** — is promoted likewise: see **WP-G**
> (re-verified against the post-WP-F code, including the W82 hook it gates).
> **2026-07-14 (third):** **W95, W98** are promoted to **WP-H** (Simulation & Planning) — budget
> mode rides the W97 comparison transient; the offer calculator evaluates on an in-memory sample.
> **2026-07-14 (fourth):** **W62, W65** are promoted to **WP-I** (Mapping Intelligence). Cycle-wire
> transforms are a binding NON-goal there — live payruns bypass cycle-mapping records entirely.
> **2026-07-14 (fifth):** **W52, W54, W42** are promoted to **WP-J** (Formula Refactoring
> Intelligence) — one shared IF-chain detector; the demo PIT chain is the built-in acceptance case.

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

**WP-G:**
> Implement WP-G (Test Intelligence: W83 test coverage view, W84 boundary-value test generation, W49 AI test generation) exactly as specified in docs/PHASE5_FORMULA_ENGINE_DESIGN.md §WP-G, honoring docs/FORMULA_ENGINE_CONVENTIONS.md (C1, C2, C5, C7, C8, C9, C10 are load-bearing here — note the selection_add/ondelete rule in C9). Build TG.1→TG.6 in order, one feature-scoped commit per W-feature, validate on the pb_demo VN world, and report back per the Report-back items section. The non-negotiable invariant: a generated sample with an unconfirmed baseline counts as PENDING in run_sample_tests — it must never move the W82 chip's passed/failed counts. Do not touch docs/FORMULA_ENGINE_TOUR.html.

**WP-H:**
> Implement WP-H (Simulation & Planning: W95 budget vs actual, W98 offer calculator) exactly as specified in docs/PHASE5_FORMULA_ENGINE_DESIGN.md §WP-H, honoring docs/FORMULA_ENGINE_CONVENTIONS.md (C1, C2, C5, C7, C8, C10, C11 are load-bearing here). Build TH.1→TH.5 in order, one feature-scoped commit per W-feature, validate on the pb_demo VN world, and report back per the Report-back items section. Two binding rules above all: budget mode must NOT fork the comparison fold (extend the existing transient per skeleton S-H1, and prove period mode unchanged via the TH.1 regression AC), and the offer calculator reports net + per-group subtotals only — never a fabricated "employer cost". Do not touch docs/FORMULA_ENGINE_TOUR.html.

**WP-I:**
> Implement WP-I (Mapping Intelligence: W62 transforms on the wire, W65 mapping templates) exactly as specified in docs/PHASE5_FORMULA_ENGINE_DESIGN.md §WP-I, honoring docs/FORMULA_ENGINE_CONVENTIONS.md (C1, C2, C7, C8, C10, C11 are load-bearing here). Build TI.1→TI.5 in order, one feature-scoped commit per W-feature, validate on the pb_demo VN world (throwaway connector if no live one carries source fields — delete it after), and report back per the Report-back items section. Three binding rules above all: W62 touches the API adapter ONLY (cycle-wire transforms are a binding non-goal — live payruns bypass cycle-mapping records, see the WP-I facts); preview and sync application must share ONE transform function (skeleton S-I1); and the python transform moves to safe_eval with env REMOVED from the context after the env-usage sweep. Do not touch docs/FORMULA_ENGINE_TOUR.html.

**WP-J:**
> Implement WP-J (Formula Refactoring Intelligence: W52 duplicate-logic detection, W54 simplification suggestions, W42 import-time rate-table extraction) exactly as specified in docs/PHASE5_FORMULA_ENGINE_DESIGN.md §WP-J, honoring docs/FORMULA_ENGINE_CONVENTIONS.md (C1, C2, C4, C5, C6, C7, C10, C12 are load-bearing here). Build TJ.1→TJ.5 in order, one feature-scoped commit per W-feature, validate on the pb_demo VN world using THROWAWAY CLONES only — never mutate demo formulas — and report back per the Report-back items section. Three binding rules above all: one pure detector module shared by W54 and W42 (formula_engine/if_chain.py + its battery — no logic duplication); a rewrite may only be OFFERED after proven equivalence through the real evaluator on samples + edge probes (D-J3 — irregular chains are listed, never rewritten); and the rewrite is span-surgical so surrounding expression text survives verbatim (D-J4). Do not touch docs/FORMULA_ENGINE_TOUR.html.

**WP-K:**
> Implement WP-K (Explanation & Collaboration: W50 auto-documentation, W74 slip-linked explainers, W89 @mentions, plus the capture-phase-Escape debt pass) exactly as specified in docs/PHASE5_FORMULA_ENGINE_DESIGN.md §WP-K, honoring docs/FORMULA_ENGINE_CONVENTIONS.md (C1, C2, C3, C7, C10, C11, C14, C15, C16 are load-bearing here). Build TK.1→TK.5 in order, one feature-scoped commit per W-feature, validate on the pb_demo VN world (throwaway clones for the drift case; handbook attachments on demo configs may stay), and report back per the Report-back items section. Four binding rules above all: the handbook's every number/formula/name comes from the ORM — the LLM polishes section prose only and the deterministic skeleton IS the fallback (D-K1); the slip explainer is write-free end-to-end — every tier-2 reconstruction passes readonly=True and the C16 exact write_date probe must prove zero writes (D-K3); reconstruction honesty — cross-check reconstructed values against stored line totals and surface drift, never paper over it (D-K3); and mentions ride config.message_post with a runtime-resolved deep link — no custom notifier, no hardcoded /odoo prefix (D-K5). Do not touch docs/FORMULA_ENGINE_TOUR.html.

**WP-L:**
> Implement WP-L (Excel Bridge & Payslip Branding: W41 living-workbook export, W17 smart paste, W73 payslip themes) exactly as specified in docs/PHASE5_FORMULA_ENGINE_DESIGN.md §WP-L, honoring docs/FORMULA_ENGINE_CONVENTIONS.md (C1, C2, C3, C4, C5, C7, C10, C11 are load-bearing here). Build TL.1→TL.5 in order — W41 before W17 (smart paste's round-trip AC eats W41's own exported workbook) — one feature-scoped commit per W-feature, validate on the pb_demo VN world with throwaway configs/files only (deleted and count-verified), and report back per the Report-back items section. Four binding rules above all: exported formula cells are Excel-evaluable (BRACKET expands out via expand_brackets; the TL.2 round-trip through the multisheet wizard incl. the W42 re-promotion offer is the binding contract, D-L1/D-L2); one server ladder normalizes AND validates pasted formulas — the ghost shows exactly what commits (D-L5, the S-I1 lesson); smart-paste commit is all-or-nothing through one bulk_save_formulas(reason='bulk') call (D-L6, C4); and the themed print is a NEW report cloning the shadow-certificate wiring — om_hr_payroll's report_payslip and the portal binding stay byte-untouched (D-L8, and never the removed <report> shortcut tag). Do not touch docs/FORMULA_ENGINE_TOUR.html — the tour refresh is Fable's wrap-up act after this package's review.

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

> **✅ REVIEWED 2026-07-14** (Fable auto-review: one bulk subagent — whole-diff read vs spec + independent
> ssh/psql/live-Chrome verification — plus personal reads of the flagged files). Verdict was fix-first
> with 1 Major + 8 Minor; deployment, seeds, ACLs, D-F3..D-F8 core mechanics all verified faithful.
> **Fixed by Fable (same day, deployed as studio 19.0.1.54.0):**
> - *Major:* Esc did not close the shortcuts overlay while the grid scroller had focus — the grid
>   navigator consumes Escape (clear-selection + stopPropagation), so the bubble-phase `useHotkey`
>   ladder never fired on exactly the natural `?`-from-grid path. Fixed with a capture-phase window
>   listener that closes the overlay before the grid can eat the event (ledger C3 note). The
>   implementer's "Esc closes first" live claim was false for this path — reviewer caught it live.
> - *Minors:* `?` guard now also checks `snipManageOpen`; read-only palette snippet insert shows the
>   locked notice instead of a silent no-op (C7); folding a category now purges hidden columns from
>   `ui.selection`/`anchorId` (bulk bar can't act on invisible columns); `openInFormulaView` unpins a
>   sample it makes active (W4 invariant); `save_snippet` rejects a non-numeric sequence loudly
>   instead of `except: pass`; unused `_` import dropped from `formula_snippet.py`; the missed C2
>   bump from `06ff8748` is absorbed by this fix's bump.
> **Deferred (recorded, not fixed):** snippet RPCs have no multi-company scoping — `list_snippets`
> filters shared+own-company but `save_snippet`/`delete_snippet` accept any id and nothing ever sets
> `company_id` (field is dead in v1). Acceptable single-company; revisit before any multi-company
> deployment. Also noted: `_scrollFocusIntoView` runs on every patch (pre-existing W109 trait, not a
> WP-F regression) — programmatic scrolling snaps back to the focused cell on virtualized configs.

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

---

# WP-G — Test Intelligence — W83 → W84 → W49

> **✅ IMPLEMENTED 2026-07-14** (Opus) — `8f4bc5ee` W83 · `6f71ebc1` W84 · `083f3765` W49 ·
> `28d1be64` import-order fix · `fe341bfd` verdict banner · `dd2c988d` ledger C9. Deployed engine
> 19.0.1.36.0 (schema migrated) + studio to Payobook19v2. The D-G3 invariant was proven live on
> demo config 44: generate trio → chip unchanged (3 land pending) → confirm → chip moves →
> re-generate dedupes (0 created / 3 skipped) → cleanup restores the exact original chip.
> Disclosed deviations: `has_tests` now means "has CONFIRMED testable samples" (accepted in review —
> no behavior change possible for existing configs); the rate-table candidate source was not
> live-driven by the implementer (demo has no BRACKET tables); the C10 full-batch anchor was
> skipped by reasoning (no eval-path file touched).

> **✅ REVIEWED 2026-07-14** (Fable auto-review: bulk subagent — full-diff read vs spec + live
> JSON-RPC/psql verification — plus personal reads of the flagged files). **Verdict: SHIP**, 5 Minors.
> The review CLOSED all three implementer gaps: (1) the rate-table branch was driven live on a
> throwaway config+BRACKET table (all 3 bracket lowers listed reachable, generated trio's
> characterization math hand-checked against progressive brackets, dedupe + chip gating re-proven,
> everything deleted with psql-verified cleanup); (2) C10 closed at mini-scale — diff shows zero
> eval-path hunks, semantics battery green, and a 130-line recompute snapshot on 5 live slips came
> back byte-identical; (3) migration psql-clean (all 33 pre-existing samples confirmed=t, 0
> generated leftovers). Prompt-injection surface on W49 verified closed (t-esc only, truncated
> text fields, numeric-only create path).
> **Fixed by Fable (same day):** `create_ai_samples` now rejects a WHOLE row on any invalid entry
> and reports `rejected` (was: silently created from surviving keys); `generate_boundary_samples`
> counts client-invalid picks as `dropped` (was: vanished); coverage "asserted" now requires a
> CONFIRMED baseline (review observation #5 — coverage no longer rises while the chip says pending).
> **Recorded, not fixed:** the Generate dropdown has no Escape/outside-click close (pre-existing
> pattern, amplified by the new 340px panels — fold into the next UI pass); the studio version-stamp
> lag was synced by this fix's `-u`. Pre-existing data note: legacy slips 1–5 carry a text value in
> their inputs and fail recompute (unrelated to WP-G).

**Designed 2026-07-14 (Fable), after WP-F shipped.** Second Medium batch: make the W82 test chip
*trustworthy at scale* — show what the samples DON'T cover (W83), then manufacture the missing
boundary tests deterministically (W84), then let the LLM propose realistic profiles on top (W49).
Modules: engine (`pb_hr_payroll_formula`) for coverage math, boundary extraction/generation and one
small schema change; studio (`pb_formula_studio`) for RPC wrappers + Tests-view UI + problems-rail
lens. Effort ≈ 7–9 d. Build order is a strict ladder: W84 depends on W83's coverage definitions in
the UI; W49 depends on W84's confirm flow.

## Verified plumbing facts (do not re-derive)

*Sample model (`pb_hr_payroll_formula/models/formula_sample_data.py`):*
- `hr.formula.sample.data`: `source_type` Selection `manual/employee/payslip/import` (`:57-62`,
  default `manual`); `input_values_json` / `expected_values_json` / stored-computed
  `computed_values_json` (`:91-118`); `_compute_results` depends ONLY on
  `input_values_json, config_id.rule_ids` (`:164` — membership, not formula text; that is WHY W82
  is an explicit hook); `_compute_validation` (`:183-242`): tolerance 0.01 %, `warning` ≤1 %,
  `failed` >1 %, `pending` when either JSON is empty. Evaluation path
  `_evaluate_rules_with_dependencies` (`:569-629`) — the C5-sanctioned path.
- `hr.formula.sample.input.line` and `hr.formula.test.result` also live in this file.

*W82 hook (`pb_hr_payroll_formula/models/formula_config_tests.py`):*
- `run_sample_tests(changed_codes)` `:43-115`; a sample is *testable* iff any expected value is
  non-null (`:95`); non-testable/skipped → `pending`; `_LARGE_SAMPLE_SET = 20`,
  `_MAX_FAILURES = 20`, `_DISC_PCT = 0.01`; failures collected by `_collect_sample_failures`
  `:117-146`. **W84 must gate here** (see D-G3).

*Rate tables (`pb_hr_payroll_formula/models/formula_rate_table.py`):*
- `hr.formula.rate.table` (+ `hr.formula.rate.bracket` lines with `lower` + `rate`);
  `compile_excel` `:83-111` (progressive bands, `IF(v>=lower_i, …)`); `expand_brackets` `:116+`
  (balanced-paren aware, `BRACKET(code, value_expr)`); config field `rate_table_ids`.

*Studio Tests view:*
- Server payload: `get_test_data` `pb_formula_studio.py:4240-4253` →
  `{samples:[_sample_row], input_components, currency}`; `_sample_row` `:4229-4237` already ships
  `source_type`; detail `get_sample_detail` `:4256-4267` (rows from `get_comparison_data`).
  Sample CRUD RPCs `:4269+`: `save_sample_inputs`, `add_manual_sample`, `generate_random_samples`
  (delegates to `hr.formula.sample.data.wizard._generate_random`), `snapshot_expected`,
  `clear_expected`, `delete_sample`, `rename_sample`, import/export.
- Client: `openTest/loadTestData/selectSample/...` `formula_studio.js:2833-2960`; the **Generate
  dropdown already exists** (`state.testGenOpen`, `toggleTestGen`, entries `addManualSample` /
  `generateRandom` / `generateFromWizard`) — W84/W49 entries slot in there, no new toolbar real
  estate.

*Coverage inputs:*
- Dependency graph: `get_intelligence` `pb_formula_studio.py:352` /
  `_normalized_dep_cols` `:320-349` (edges resolved letter-first-then-code, config-scoped).
- Problems rail: `get_problems` `:2768+`, shape
  `{key, kind, severity, title, detail, rule_id, col, code, note_id}` via the `_add` helper —
  a new lens = a new `kind` emitted there; the rail renderer is generic.
- W82 chip client state: `_applyTests` / `state.tests` in `formula_studio.js` (WP-C).

## Locked decisions

- **D-G1 (coverage is deterministic and three-valued)** — per formula-type component:
  **asserted** = ≥1 active sample has a non-null expected value for its code (the SAME testable
  rule as W82, `formula_config_tests.py:95` — one definition, never two); **exercised** = not
  asserted, but on the upstream dependency closure of an asserted component (its value feeds an
  assertion — computed via the `get_intelligence` edges); **untested** = neither. Coverage % shown
  = asserted / formula-components. Inputs/constants are excluded from the % but listed as
  "never referenced by any asserted formula" when applicable. Pure metadata — computing coverage
  NEVER evaluates a formula.
- **D-G2 (W83 surfaces)** — one new engine-free studio RPC `get_test_coverage(config_id)` returning
  `{pct, asserted:[...], exercised:[...], untested:[{rule_id, col, code, name}], orphan_inputs}`.
  Two renderings: (a) a coverage strip at the top of the Tests view (pct + count chips + expandable
  untested list; clicking a row jumps to the component in the grid — reuse `findJump`); (b) a
  problems-rail lens: `kind='untested'`, `severity='hint'`, one row per untested formula component
  (hint tier — absence of a test is a smell, not an error).
- **D-G3 (generated samples cannot inflate the chip)** — schema: `source_type` gains
  `('generated', 'Generated')` via `selection_add` **with `ondelete='set default'`** (safe here:
  the base field defines `default='manual'` — C9), plus new Boolean `expected_confirmed`
  (default **True** so every existing sample keeps its current standing; generated rows are created
  with **False**). `run_sample_tests` gains ONE rule: a testable sample with
  `expected_confirmed=False` counts as `pending`, never `passed`/`failed` — characterization
  expectations are hypotheses until a human confirms them. `_sample_row` / `get_sample_detail`
  expose `expected_confirmed`; the Tests view shows a "needs confirmation" pill, a per-sample
  **Confirm baseline** button and a confirm-all; confirm RPC `confirm_sample_expected(sample_id)`
  (manager-gated like other studio writes) flips the flag and re-runs the chip.
- **D-G4 (W84 extraction is deterministic, honest about reach)** — boundary candidates come from
  two sources, both engine-side (`models/formula_boundary.py`, new file, methods on
  `hr.formula.config`):
  1. **Rate tables**: every bracket `lower` of every `rate_table_ids` table. The generation
     dimension is the `BRACKET(code, expr)` call's `expr` ONLY when it resolves to a single
     input-type component ref/code; otherwise the candidate is still LISTED but marked
     `reachable=False` ("operand is computed — set inputs to hit this edge manually"). C7: shown,
     never silently dropped.
  2. **Comparison thresholds**: regex over each formula's `excel_formula` for
     `<ref> op <number>` / `<number> op <ref>` (op ∈ `> >= < <= =`), where `<ref>` resolves
     (letter-first-then-code, same as `_normalized_dep_cols`) to an **input** component →
     candidate `(input_code, threshold)`; refs resolving to formula/constant components →
     `reachable=False` listing.
  For each reachable pick, generate up to 3 samples at edge−1 / edge / edge+1 (deduped against
  existing ACTIVE generated samples via a `boundary_key` Char stamped `CODE=VALUE`; skip existing,
  report skips). Base inputs are cloned from a picker-chosen existing sample (default: first),
  overriding only the boundary dimension. Expected values are seeded from current engine output
  through `_evaluate_rules_with_dependencies` (characterization; C5 path) and the sample is created
  `source_type='generated'`, `expected_confirmed=False`, name `Edge CODE=VALUE (−1|0|+1)`,
  description recording the source (table/bracket or formula/threshold). Cap one generation run at
  60 created samples with a loud "N candidates not generated" remainder (C7/C8).
- **D-G5 (W49 = LLM proposes inputs, engine computes truth)** — studio RPC
  `ai_propose_samples(config_id)` calls `_llm_chat(json_mode=True)` with the input schema
  (codes, names, defaults, min/max observed across existing samples) asking for ≤8 realistic
  profiles `{name, inputs, rationale}`. Hard validation before ANY create: unknown input codes →
  row rejected; non-numeric → rejected; |value| > 1e12 → rejected; rejects reported in the
  response. Accepted rows become samples exactly like W84's (generated + unconfirmed + engine-
  computed expected; rationale → `description`). The LLM NEVER supplies an expected value — the
  number-invention class of bug is excluded by construction, no output guard needed. No API key /
  LLM error → `{ok: False, reason}` and the UI shows it plainly next to the still-working W84
  entry (C1 fallback).
- **D-G6 (schema/deploy)** — the only schema change is D-G3's field + selection_add ⇒ ONE engine
  `-u pb_hr_payroll_formula`; both manifests bump (C2).
- **D-G7** — `docs/FORMULA_ENGINE_TOUR.html` stays untouched.

## Tasks

**TG.1 — W83 coverage engine + RPC** *(~1 d)*
`get_test_coverage` in the studio facade (graph from `get_intelligence`, asserted set from sample
JSONs — reuse `_load`-style tolerant parsing) + the `untested` problems-rail lens in
`get_problems`.
AC: on a demo config, hand-verify 2 components in each bucket; coverage never evaluates formulas
(no `_compute_results` calls in the path); rail shows hint rows with working jump; empty-sample
config → pct 0, no crash.

**TG.2 — W83 Tests-view strip** *(~1 d)*
Coverage strip + expandable untested list + grid jump; loads with `loadTestData` (one extra RPC,
not per-sample).
AC: strip matches TG.1 numbers; jump lands + flashes the column (existing `findJump` behaviour);
zero console errors.

**TG.3 — W84 engine** *(~2 d)*
Schema (D-G3) + `boundary_candidates()` + `generate_boundary_samples(picks, base_sample_id)`
(D-G4) + the `run_sample_tests` unconfirmed→pending rule + `confirm_sample_expected` +
`_sample_row`/detail exposure.
AC: on the demo config with the PIT BRACKET table, candidates include every bracket lower with
correct reachable flags; generating one trio creates 3 `generated` samples whose expected==computed
(all-pass once confirmed); W82 chip counts UNCHANGED before confirmation, move after; re-running
generation dedupes (0 new, N skipped reported); C10 anchor zero-drift.

**TG.4 — W84 Tests-view UI** *(~1.5 d)*
"Boundary tests…" panel in the existing Generate dropdown: candidate list (reachable pick-boxes,
unreachable greyed with the reason), base-sample picker, generate button with created/skipped/
capped summary; "needs confirmation" pill + Confirm/Confirm-all wired.
AC: full flow drivable in the browser; unreachable candidates visibly listed; confirm-all flips
the chip in one round-trip.

**TG.5 — W49 AI proposals** *(~1.5 d)*
`ai_propose_samples` + validation + "AI suggest profiles…" entry in the same dropdown (proposal
list with rationale, accept-selected).
AC: with no API key the entry reports unavailability cleanly and W84 still works; with a key,
proposals with an unknown code or absurd magnitude are rejected and REPORTED; accepted rows arrive
unconfirmed and chip-neutral.

**TG.6 — package validation sweep** *(~1 d)*
Chrome-MCP drive of W83 strip → W84 generate/confirm → W49 propose on the pb_demo VN world
(throwaway clone for anything that mutates formulas; generated samples on the REAL demo config are
fine — they're the feature — but delete the ones created purely for drive-testing); C10 anchor;
zero console errors.

### Skeleton S-G1 — threshold extraction (the risky spot: resolve like the engine, stay honest)

```python
# formula_boundary.py — comparison-threshold candidates (D-G4.2)
_CMP_RE = re.compile(
    r'(?<![\w.])([A-Za-z][A-Za-z0-9]*)\s*(>=|<=|<>|>|<|=)\s*(-?\d+(?:\.\d+)?)'
    r'|(-?\d+(?:\.\d+)?)\s*(>=|<=|<>|>|<|=)\s*([A-Za-z][A-Za-z0-9]*)(?![\w.])')

def _threshold_candidates(self, rules):
    by_col = {r.column_letter: r for r in rules if r.column_letter}
    by_code = {r.code: r for r in rules if r.code}
    out = []
    for r in rules.filtered(lambda x: x.column_type == 'formula'):
        # IMPORTANT: scan the ORIGINAL excel_formula, not python_formula, and
        # strip cell-row digits first (A2 -> A) so 'A2>26' resolves ref=A, not A2.
        f = re.sub(r'(?<![\w])([A-Za-z]{1,3})\d+(?![\w])', r'\1', r.excel_formula or '')
        for m in _CMP_RE.finditer(f):
            ref, num = (m.group(1), m.group(3)) if m.group(1) else (m.group(6), m.group(4))
            dep = by_col.get(ref) or by_code.get(ref)      # letter first, then code —
            if not dep:                                    # same order as _normalized_dep_cols
                continue
            out.append({
                'source': 'threshold', 'rule_id': r.id, 'formula_code': r.code,
                'input_code': dep.code, 'edge': float(num),
                'reachable': dep.column_type == 'input',   # computed operand -> listed, not generated
            })
    return out
# GOTCHA: BRACKET(...) calls are still literal in excel_formula (expansion happens at
#   conversion) — handle them in the rate-table source, and SKIP thresholds found inside
#   a BRACKET call's argument span to avoid double-counting the same edges.
# GOTCHA: the cell-row strip regex must not eat function names (SUM2 is not a thing, but
#   guard with the 1-3 letter cap anyway); run candidates against the demo config and
#   eyeball before wiring generation.
```

## WP-G verification (Chrome MCP on pb_demo VN world)

1. W83: strip pct + buckets hand-checked (2 components per bucket); rail hints jump correctly.
2. W84: PIT bracket lowers all listed; reachable/unreachable split correct; edge trio generates,
   dedupes on re-run, expected==computed; chip pending-gating before confirm, counts move after.
3. W49: no-key fallback clean; with key — rejected rows reported, accepted rows chip-neutral.
4. `run_sample_tests` regression: existing (confirmed) samples' pass/fail counts identical to
   pre-WP-G on the demo configs.
5. C10 batch-recompute anchor: zero drift. 6. Console clean; drive-test artifacts deleted.

Report back per the **Report-back items** section (deviations from D-G1..D-G7 must be flagged).

---

# WP-H — Simulation & Planning — W95 → W98

> **✅ IMPLEMENTED 2026-07-14** (Opus) — `e37f5379` W95 engine · `ae6ac4e3` W95 UI · `226c389b` W98
> engine · `97f05c16` W98 UI · `0f7a8a58` ledger (C2 Sass mixed-unit gotcha). Deployed engine
> 19.0.1.37.0 / studio 19.0.1.60.0. Disclosed deviations: D-H4 non-numeric inputs pass through as
> TEXT (real configs carry text input columns; unknown codes + |v|>1e12 still rejected) and D-H6
> read-only evaluation via a narrowly-scoped sudo() instead of an eval-path flag (D-H7 forbade the
> flag). All ACs reported pass incl. the S-H1 period-path regression (263→313 matched=978).

> **✅ REVIEWED 2026-07-14** (Fable auto-review: bulk subagent — full-diff read + live security
> probes + budget round-trip — plus personal reads of offer_calc and the eval kernel).
> **Verdict: SHIP.** Both deviations PROVEN SAFE: client values are inert dict data end-to-end
> (`__import__('os').system('id')` as an input value computes a normal payroll — the compiled
> python comes solely from the rule's own formula, `__builtins__={}` +
> `assert_safe_expression` guard the eval), and the sudo is bounded — the config/rules read happens
> as the REAL user first, so the multi-company record rule blocks cross-company probes before any
> sudo work (live-probed: AccessError).
> **One Major — root cause SYSTEMIC, fixed same day:** the `(budget_id, code)` unique constraint
> never materialized on the live DB. The reviewer diagnosed a partial schema apply; chasing it
> revealed the real cause — **Odoo 19 silently ignores the legacy `_sql_constraints` list**
> (`model_classes.py:162` warning only), so NO `hr_formula_*` table had ANY unique constraint,
> ever. All 13 engine constraints were converted to the `models.Constraint` class-attribute API
> (dup-checked live first — zero violations, the app-level guards had held), deployed via engine
> `-u`, and pg_constraint-verified. Ledger C9 updated; ~28 non-engine files still carry the dead
> attribute (convert on touch). The app path was safe regardless (budget_save rebuilds lines from
> a code-keyed dict).
> **Minors fixed same day:** cross-company `offer_calc`/`budget_get` now return a graceful
> `{ok:False}` instead of a raw AccessError 500; numeric-string overflow (`"1e400"` → inf) is now
> rejected as out-of-range instead of slipping down the text-passthrough branch;
> `offer_sample_inputs` now gates through the parent config's record rule (samples carry no
> company rule of their own).

**Designed 2026-07-14 (Fable), after WP-G shipped.** Third Medium batch: put the compare surface to
planning work. **W95 budget vs actual** — author a per-component budget for a config and fold a real
payrun against it in the existing Compare table. **W98 offer calculator** — type a hypothetical
employee's inputs and see the full component breakdown (net + employer cost) through the LIVE config,
zero records created. Modules: engine (`pb_hr_payroll_formula`) for the budget model + comparison
extension; studio for RPCs/UI. Effort ≈ 6–7 d. W95 first (it extends the transient W98 doesn't touch);
W98 is independent and can land second without rebasing.

## Verified plumbing facts (do not re-derive)

*Comparison transient (`pb_hr_payroll_formula/models/formula_period_comparison.py`):*
- `hr.formula.period.comparison` is a **TransientModel** `:62-79`: `config_id`, `run_a_id`,
  `run_b_id` (both `ondelete='cascade'`, **not required**), `state draft/computing/done`,
  `headline_code`, `fold_json`, counters (`employees_a/b`, `matched`, `joiners`, `leavers`).
- Helpers: `_pick_headline_code` `:81` (NET-name heuristics, `_NET_CODES` `:33`); `_slip_computed`
  `:100` (JSON-or-line-totals, C15); `_run_slip_map` `:115`.
- Flow: `cmp_create` `:131` → `cmp_prepare` `:147` (builds map_a/map_b, work list) → `cmp_batch`
  `:168` (folds `components: {code: [sum_a, sum_b, n_changed, max_abs]}`, movers, net_moved) →
  `cmp_finalize` `:223` → `cmp_result` `:230` (rows, causes, movers ≤25) → `cmp_drop` `:292`.
  `_EPS = 0.005` `:24`. W48 `narrate()` `:297` sits on the same model.
- Studio wrappers: `compare_runs / compare_prepare / compare_batch / compare_result / compare_drop`
  in `pb_formula_studio.py`; client state `cmpRuns/cmpA/cmpB/cmpId/cmpBusy/cmpProgress/cmpResult…`
  (`formula_studio.js:2748+`), view branch `state.view === 'compare'` in `studio.xml`, styles in
  `compare.scss` (`.pbcmp*`).

*Evaluation for synthetic inputs (W98):*
- `hr.formula.sample.data._evaluate_rules_with_dependencies(input_values)`
  (`formula_sample_data.py:569-629`) needs only `self.config_id` — it reads `config_id.rule_ids`,
  topo-sorts, calls `rule.evaluate(results)` per rule, two fixup passes. It is an `ensure_one`
  recordset method, so W98 evaluates on an **in-memory record**: `Sample.new({'config_id': cid})`
  — zero rows created, same evaluator as previews/tests (C5).
- CAUTION: `rule.evaluate` → `_run_formula(..., write_diagnostics=True)`
  (`formula_rule.py:1500-1519`) — evaluation may write eval-diagnostic fields on the RULE (same
  side-effect every preview/sample compute already has; it is NOT a data mutation of configs).
  `rules._compute_dependencies()` is called at the top of the eval — also identical to previews.
- Input schema for the form: `get_test_data` payload `input_components` (`pb_formula_studio.py:4245-4247`
  — code/col/name/default per input-type rule).
- Component metadata for the breakdown: the studio components payload (name, category, `group`,
  `appears_on_payslip`, `number_format`) — `get_studio_data` `:242-270`.

*Misc:* palette registry `paletteCommands` (`formula_studio.js:905+`); Tools ▾ overflow `pickTool`;
engine access-CSV row pattern; transient models still need access rows (see the
`access_formula_period_comparison_*` rows added in WP-C).

## Locked decisions

- **D-H1 (W95 = a budget SIDE on the existing transient, not a parallel engine)** — new persistent
  engine models `hr.formula.budget` (`config_id` required cascade, `name` required, `period_label`
  Char, `note` Char, `active`) and `hr.formula.budget.line` (`budget_id` cascade, `code` Char
  required, `amount` Float; SQL-unique `(budget_id, code)`). The comparison transient gains
  `budget_id` (Many2one, optional) and `mode` (Selection `period/budget`, default `period`).
  In budget mode: side A = budget line amounts (no slips, no chunking for A), side B = the picked
  run's fold (same `cmp_prepare`/`cmp_batch` machinery over map_b only; map_a empty).
  `cmp_result` in budget mode emits the same row shape (`a` = budget, `b` = actual, delta, delta%)
  plus `coverage`: components in the run with NO budget line and budget lines matching NO component
  are BOTH listed explicitly (C7 — never silently dropped from the variance). Employee-level blocks
  (movers/joiners/leavers/causes/narrate) are period-mode only — budget mode returns them empty and
  the UI hides those cards.
- **D-H2 (W95 authoring UX)** — budgets are edited in a studio overlay (scrim pattern, C11):
  rows = the config's current formula components (code, name, amount input), plus **Seed from
  run…** (one click fills amounts from a picked run's actual per-component sums — reuses
  `_run_slip_map`/`_slip_computed` server-side) and **Seed from compare** when a period compare is
  on screen. Budget CRUD RPCs are manager-gated (`_can_edit`) server-side like every studio write;
  reads are open. `boundary`-style honesty: a budget line whose code no longer exists in the config
  renders struck-through with a "component gone" tag, not hidden.
- **D-H3 (W95 UI placement)** — the Compare view gains a mode toggle (`vs Period · vs Budget`).
  Budget mode swaps the second run-picker for a budget picker (+ "New budget…" opens the editor).
  The variance table reuses `.pbcmp-table` (columns Budget / Actual / Δ / Δ%; heat shading as
  today); stats strip shows total budget / total actual / variance / coverage counts. Palette entry
  "Compare vs budget".
- **D-H4 (W98 = in-memory evaluation, one RPC)** — studio RPC `offer_calc(config_id, inputs)`:
  validates inputs (known input codes only, numeric, reject |v| > 1e12 — same rules as W49's
  validator), evaluates via `Sample.new({'config_id': cid})._evaluate_rules_with_dependencies`,
  returns ordered component rows (col, code, name, group, value, `appears_on_payslip`,
  `number_format`) + headline net (same `_NET_CODES` heuristic as the comparison) + employer-cost
  subtotal = Σ of a `group == 'Deductions'`-excluded gross-side… **NO.** Employer cost is NOT
  derivable generically — v1 reports **net + per-group subtotals** (Inputs excluded; one subtotal
  per category band) and labels them exactly that. No invented "employer cost" number (C7 honesty:
  if the config has no employer-contribution components, we do not fabricate one).
- **D-H5 (W98 UI)** — a Tools-menu + palette entry "Offer calculator": overlay with the input form
  (prefilled from input defaults; a "start from sample…" picker copies an existing sample's
  inputs), live recompute on a 320 ms debounce (C8 — one RPC per pause, supersede-token like the
  grid validator), breakdown grouped by category band with the payslip-visible components
  highlighted, headline net card. **Shareable summary = clipboard text** (formatted lines: config,
  date, inputs, visible components, net) — no server-side share links in v1 (B7 share infra is for
  review flows; do not couple).
- **D-H6 (W98 is read-only for everyone)** — offer calc never writes; it is available to read-only
  users too (it is a calculator, not an edit). The RPC must therefore not trip `_can_edit` guards,
  and the evaluation side-effect noted above must be acceptable: rule diagnostic writes happen via
  the SAME code path previews already use for read-only users. Verify once in TG… TH.3 that a
  read-only session can run it without a permission error (if rule diagnostic writes fail on the
  read-only group, pass `write_diagnostics=False` through — `_run_formula` already supports it).
- **D-H7 (schema/deploy)** — two new engine models + 2 transient fields ⇒ one engine
  `-u pb_hr_payroll_formula`; access rows for budget models (user read, manager write — same split
  as snippets); both manifests bump (C2). No eval-path file changes.
- **D-H8** — `docs/FORMULA_ENGINE_TOUR.html` stays untouched.

## Tasks

**TH.1 — W95 engine** *(~2 d)*
Budget models + access rows + transient `mode`/`budget_id` + budget-mode prepare/batch/result +
seed-from-run helper + `-u`.
AC: budget-mode fold on a demo run: per-component actual sums EQUAL the same run's period-compare
sums (cross-check vs an existing period compare of run×itself or SQL); un-budgeted component and
orphan budget line both appear in `coverage`; movers/causes empty in budget mode; period mode
byte-identical for existing calls (regression: one period compare re-run matches pre-WP-H output).

**TH.2 — W95 studio UI** *(~2 d)*
Mode toggle + budget picker + budget editor overlay (seed-from-run) + variance table/stats + palette
entry + budget CRUD RPCs (manager-gated writes).
AC: author a budget seeded from May, compare June vs it — variance table renders with heat + correct
Δ%; editing a budget line and re-running updates; read-only user can view budgets/variance but gets
the locked notice on edit; zero console errors.

**TH.3 — W98 engine + RPC** *(~1 d)*
`offer_calc` with input validation + in-memory `Sample.new` evaluation + ordered breakdown + net
heuristic + per-group subtotals.
AC: for an existing sample's exact inputs, `offer_calc` returns values identical to that sample's
`computed_values_json` (the strongest correctness proof available); unknown/absurd inputs rejected
loudly; read-only session runs it without error (D-H6 — flip `write_diagnostics` if needed).

**TH.4 — W98 UI** *(~1.5 d)*
Overlay form + debounced live recompute + grouped breakdown + net card + copy-summary + Tools/palette
entries.
AC: typing updates within one debounce tick; values match the Tests view for copied inputs; clipboard
summary contains config name, inputs and visible components; works for read-only users; zero console
errors.

**TH.5 — package validation sweep** *(~0.5–1 d)*
Chrome-MCP drive of both features on the pb_demo VN world; budgets created for drive-testing deleted
afterwards (or kept ONLY if named `Demo Budget …` intentionally — say which in the report); C10
anchor n/a-by-construction is NOT claimable here — budget mode reads slips, so run the small-scale
recompute parity check (one run's per-component sums before/after) and the period-compare regression
of TH.1; console clean.

### Skeleton S-H1 — budget mode inside the existing flow (the risky spot: don't fork the fold)

```python
# formula_period_comparison.py — additions, not a parallel path
mode = fields.Selection([('period', 'Period vs period'), ('budget', 'Budget vs actual')],
                        default='period')
budget_id = fields.Many2one('hr.formula.budget', ondelete='cascade')

def cmp_prepare(self, cmp_id):
    cmp = self.browse(int(cmp_id))
    ...
    if cmp.mode == 'budget':
        # side A is synthetic: fold_json starts with the budget sums; only B chunks.
        lines = {l.code: l.amount for l in cmp.budget_id.line_ids}
        fold = {'components': {c: [amt, 0.0, 0, 0.0] for c, amt in lines.items()},
                'budget_codes': list(lines)}
        cmp.fold_json = json.dumps(fold)
        map_b = cmp._run_slip_map(cmp.run_b_id)
        work = [{'b': sid} for sid in map_b.values()]   # no matching — every B slip folds
        ...
    # period path UNCHANGED — do not touch the existing branch (TH.1 regression AC).
# cmp_batch: in budget mode fold ONLY sums into [., sum_b, ., .] per code — reuse the same
#   accumulator dict; skip movers/net_moved entirely.
# cmp_result: budget mode emits rows for the UNION of budget codes and folded codes;
#   coverage = {'unbudgeted': [...], 'orphan_lines': [...]} — both always present (C7).
# GOTCHA: budget lines key by CODE, folded sums key by code via _slip_computed — a slip
#   line with an empty code is already skipped there; do not "helpfully" match by name.
```

## WP-H verification (Chrome MCP on pb_demo VN world)

1. W95: budget seeded from May == May's own actuals (variance ≈ 0 row-by-row); June vs May-budget
   variance matches the May→June period compare's per-component deltas (same numbers, different
   framing — cross-check 3 components by hand).
2. W95 coverage honesty: delete one budget line → component appears under "unbudgeted"; add a bogus
   line `ZZZX` → appears under "orphan lines" struck through.
3. W95 regression: a period compare re-run on runs 263→313 produces the SAME stats as recorded in
   the WP-C validation (978 matched, NET sums).
4. W98: inputs copied from an existing sample reproduce its computed values exactly; read-only user
   drive; clipboard summary correct; debounce = no request storm (network tab ≤ 1 call per pause).
5. Drive artifacts (budgets, any samples) deleted; console clean throughout.

Report back per the **Report-back items** section (deviations from D-H1..D-H8 must be flagged).

---

# WP-I — Mapping Intelligence — W62 → W65

> **✅ IMPLEMENTED 2026-07-14** (Opus) — `ea35e4f5` W62 · `7ff93854` W65 · `620bf7fd` ledger (C2:
> OWL if-in-t-on-arrow breaks the whole template compile; odoo-shell ir_ui_view deadlock → use
> JSON-RPC for server-side validation). All three binding rules honored (API-adapter only, one
> ladder, safe_eval with env removed — env sweep found 0 using rows). 196 live mapping rows
> zero-drift; C10 anchor parity; throwaway fixtures cleaned.

> **✅ REVIEWED 2026-07-14** (Fable auto-review: bulk subagent — code trace + live probes — plus
> personal reads of both flagged files). **Verdict was FIX-FIRST**, two Majors, both fixed same
> day (engine 19.0.1.41.0):
> - *Major 1 (live-proven):* `preview_transform` diverged from sync on EMPTY/unparseable samples —
>   it laddered+clamped the default value while sync early-returns it raw (preview 5.0 vs sync 0.0
>   on an add+5 draft; all 196 live rows carry empty samples, so every live preview took the
>   divergent branch). Fixed: preview now mirrors sync's early-return exactly and says
>   "no sample stored — sync would emit the default" (S-I1 upheld for real). The first fix pass
>   did NOT close it — an unset ORM Char reads `False`, which `raw is None or raw == ''` misses
>   (float(False)==0.0 slid into the ladder); the landed guard is `if not raw` (ledger C9).
> - *Major 2 (undisclosed):* a LEFTOVER duplicate op ladder with raw `exec` + silent
>   divide-by-zero→0.0 survived in `integrations/base_connector.py` (dead code — zero callers —
>   but one future caller from reintroducing the pre-D-I4 hazard). Fixed by delegating
>   `_apply_transformation` to `mapping.transform_value` (the one ladder) and making
>   `_apply_validation` a passthrough.
> - *Minors fixed:* `record` in the safe_eval context is now dict-guarded (an ORM recordset there
>   would have exposed `record.env` — safe_eval only blocks underscore attrs); stale field help no
>   longer advertises `env`; ir.rules added for the template models (RPC-level company checks left
>   the direct-ORM path open to managers of other companies — the review's live probe confirmed
>   the RPC layer held, the rules close the flank).
> - *Everything else verified clean:* save whitelist structurally excludes `transformation_code`
>   (live injection probe → DB code still NULL), op-by-op old-vs-new ladder table shows zero drift
>   for the 196 live rows (176 direct / 19 multiply / 1 empty-python), W65 company checks real +
>   live-probed, vendor seed table exactly 52 rows, all four apply-result keys always present.
> **Recorded, not fixed:** transform popover + template panel don't close on Escape (same class as
> the WP-G Generate dropdown — one capture-phase pass over the newer overlays is due); engine
> version stamp lag (39→git 40) was disclosed and is synced by this fix's `-u` (41).

**Designed 2026-07-14 (Fable), after WP-H shipped.** Fourth Medium batch: finish the F10 mapping
canvas. **W62 transforms on the wire** — surface, edit and live-preview the per-mapping transforms
that ALREADY run at sync time, as badges on the API-adapter wires. **W65 mapping templates** — save a
mapped board as a named, reusable template and apply it across configs/connectors (bureau workflow).
Modules: engine for the transform hardening + template models; studio for badges/popover/template UI.
Effort ≈ 6 d.

## Verified plumbing facts (do not re-derive)

*Transforms already exist and already run (`pb_hr_payroll_formula/models/integration_field_mapping.py`):*
- `hr.integration.field.mapping` carries `transformation_type` (Selection: direct / multiply /
  divide / add / subtract / round / abs / default_if_empty / **python**), `transformation_value`,
  `transformation_decimals`, `transformation_code` — `:91-127`; plus `source_sample_value` (`:61`),
  `is_required` / `default_value` / `min_value` / `max_value` (`:131-153`).
- The apply site is `:228-275`: numeric coercion (required → ValidationError, else default), the
  op ladder, divide-by-zero guard, and — the hazard — **`python` runs raw
  `eval(transformation_code, {"__builtins__": {}}, {'value', 'record', 'env'})`** (`:264-275`) with
  the full `env` in scope; errors fall back to `default_value` with only a server log.
- W62 for this adapter is therefore SURFACING + HARDENING, not building: zero schema change.

*The two canvas adapters (`pb_formula_studio/models/pb_formula_studio.py`):*
- Cycle adapter: `mapping_canvas_data` `:3185-3221` (left/right/wires payload; wires
  `{id, kind: mapping|suggestion, ref, leftId, rightId, state, confidence?, reason?}`),
  `mapping_create` `:3257` (uniqueness by dropping existing wires on either side, `:3270-3273`),
  `mapping_delete` `:3279`, suggestion accept/reject `:3238/:3248` — all writes `_can_edit`-gated.
- API adapter: `api_mapping_data` `:3316-3390` (left = connector source fields via
  `get_available_source_fields`, incl. `sample`; right = input-type rules; accepted wires from
  persisted `hr.integration.field.mapping` rows; suggestions computed LIVE by name-match, never
  persisted; `supports_suggest: False`), `api_mapping_create` `:3391`, `api_mapping_delete` `:3409`.
- Canvas JS is adapter-generic (`mapping_canvas.js:6` — "just a different adapter"); the wire-badge
  action block is `:108+`. 140 lines total; styles `mapping.scss`.

*Cycle mappings and WHERE they are actually applied — the W62 scoping fact:*
- Model `hr.payroll.cycle.component.mapping` (`payroll_cycle_component_mapping.py:7-58`): pair of
  configs + pair of components, three SQL uniques (pair / one-per-mid / one-per-end), NO transform
  fields.
- The generic application machinery lives ONLY in the import path
  (`payroll_import_batch.py:1204-1210` search helpers, applied `:1314` / `:1427`).
- **Live payrun paths BYPASS the mapping records**: the demo payrun wizard reads the mid advance
  straight off mid-run slip lines by hard-coded code (`pb_demo/models/demo_payrun.py:78-137`, used
  `:246/:347`), and the history generator passes it directly (`demo_history.py:160-161`). A
  transform stored on a cycle mapping would run on imports but be IGNORED by live runs.

*W65 raw material:*
- `hr.integration.mapping.template` (`integration_mapping_template.py:22-44`) is the VENDOR-seeded
  canonical table (keyed `connector_type`, `source_path` → `target_code`, own transform columns,
  `verify` flag) applied by the onboarding wizard's `action_apply_template` (`:154`). It is seed
  data, not a user-save surface — do not overload it.
- Cross-config copying precedent: `bureau_clone` in the studio facade (B4). Snippet-library
  precedent for user-authored shared records: `formula_snippet.py` + manager-gated CRUD — including
  its REVIEW FINDING: writes were not company-scoped (deferred gap). W65 must not repeat it.

## Locked decisions

- **D-I1 (W62 scope = API adapter ONLY; cycle transforms are a BINDING NON-GOAL)** — because live
  runs bypass cycle-mapping records (facts above), a transform on a cycle wire would silently apply
  to import batches and NOT to live payruns — an architecture-level C7 violation. Cycle wires render
  unchanged. If cycle transforms are ever wanted, the prerequisite package is "unify the carryover
  read path through the mapping records", which is NOT this WP. State this in the canvas UI copy
  only if a user asks — no dead affordances.
- **D-I2 (badges surface the EXISTING fields)** — every accepted API wire shows a compact transform
  badge: `=` direct, `×n` multiply, `÷n` divide, `+n` / `−n`, `≈d` round, `|x|` abs, `?n`
  default_if_empty, and `ƒ` for python. Clicking opens a popover editor (scrim pattern, C11) for
  type/value/decimals with a LIVE preview line: `sample → transformed`. **The `python` type is
  read-only on the canvas** (badge + "edit in backend form" note, manager-only there) — the canvas
  must not grow the code-authoring surface.
- **D-I3 (one transform code path)** — refactor the `:238-275` op ladder into a pure helper
  `_apply_transform_ops(vals, value, record)` used by BOTH the persisted sync application and a new
  draft-preview RPC `api_transform_preview(mapping_id, draft_vals)` (evaluates the draft against
  `source_sample_value` WITHOUT writing). Persist via `api_transform_save(mapping_id, vals)`
  (manager-gated, whitelisted fields: type/value/decimals only — never `transformation_code`).
  Preview and application can never diverge because they are the same function.
- **D-I4 (safe_eval hardening, in scope)** — replace the raw `eval` with
  `odoo.tools.safe_eval.safe_eval(expr, {'value': …, 'record': …})` — **`env` is REMOVED from the
  eval context**. Before landing: grep the seed XML (`data/mapping_templates.xml`) and psql the live
  `hr_integration_field_mapping.transformation_code` rows for `env` usage; none expected — if any
  exists, migrate that row explicitly and say so in the report. Error behaviour: keep the
  default_value fallback + log, and ALSO mark the mapping row (`has_transform_error`-style rendering
  via the existing payload — a red tint on the badge) so the failure is visible on the canvas (C7),
  not only in a server log.
- **D-I5 (W65 = new lean user-template models; vendor seeds untouched)** — engine models
  `hr.formula.mapping.template` (`name` required, `adapter` Selection `api/cycle`, `connector_type`
  optional (api), `company_id` **required-by-default behaviour: writes are company-scoped from day
  one** — do not repeat the W104 snippet gap; empty company = shared, but save/delete RPCs must
  check the record's company against `self.env.company` for non-shared rows) and
  `hr.formula.mapping.template.line` (`source_key` — API source path or mid-component CODE;
  `target_code` — input/end-component CODE; `transformation_type/value/decimals` copied for api
  lines). Templates store CODES, never ids — they must apply across configs.
- **D-I6 (W65 apply semantics — loud, never destructive)** — `mapping_template_apply(template_id,
  config_id, connector_id?)` matches lines by code/path against the target board and returns
  `{applied, skipped_existing, unmatched_sources, unmatched_targets}`; it NEVER overwrites an
  existing wire (skip + report) and never deletes anything. `mapping_template_save(config_id,
  adapter, name)` snapshots the CURRENT accepted wires (+ transforms for api). Both manager-gated;
  list is open. UI: "Save board as template…" / "Apply template…" buttons on the canvas toolbar for
  both adapters (cycle templates carry pairs only, no transforms — D-I1).
- **D-I7 (schema/deploy)** — new template models ⇒ one engine `-u`; access rows user-read/
  manager-write; both manifests bump (C2). The refactor of the transform ladder touches
  `integration_field_mapping.py` — this is sync-path engine code, NOT payslip-eval code; the C10
  anchor still applies as the standard ritual plus one transform-regression check (see TI.5).
- **D-I8** — `docs/FORMULA_ENGINE_TOUR.html` stays untouched.

## Tasks

**TI.1 — W62 engine: transform helper + preview/save RPCs + safe_eval hardening** *(~1.5 d)*
Refactor ladder → pure helper; `api_transform_preview` / `api_transform_save`; safe_eval swap with
the env-usage sweep; extend `api_mapping_data` wires with `{transform: {type, value, decimals,
label, error}}`.
AC: preview(draft) == what the sync path would produce for the same vals (unit-check by calling
both on 5 op types incl. divide-by-zero → loud error not crash); python rows: preview refuses
(read-only), safe_eval runs a benign expr, `env` absent from context (attempt `env` in a test expr
→ NameError caught → default+badge error); no `transformation_code` writable via RPC.

**TI.2 — W62 canvas UI: badges + popover** *(~1.5 d)*
Badge rendering on accepted API wires; popover editor with live preview (260 ms debounce +
supersede token, C8); error tint; read-only python badge; read-only users see badges, no editor
(locked notice — W104 lesson).
AC: full drive on a connector board: set ×12 on one wire → badge updates, preview shows
`sample → sample×12`, sync-side value verified changed accordingly (or via preview==apply parity
from TI.1 if no live sync is safe to run); cycle canvas shows NO transform affordances; zero
console errors.

**TI.3 — W65 engine: template models + save/apply RPCs** *(~1.5 d)*
Models + access rows + `mapping_template_save/list/apply/delete` with D-I5/D-I6 semantics + `-u`.
AC: save a board with 6 wires (2 transformed) → template has 6 code-level lines; apply to a config
whose inputs match 4 → `{applied: 4, unmatched: 2 listed}`, existing wires untouched
(`skipped_existing` correct); company-scoping: non-shared template from another company is
invisible AND un-deletable (server-side check, not just UI).

**TI.4 — W65 canvas UI** *(~1 d)*
Toolbar Save-as-template / Apply-template pickers on both adapters; apply-result summary (applied /
skipped / unmatched, all shown); manager-gating.
AC: round-trip save→apply on a second config drivable in the browser; unmatched lines rendered, not
hidden; zero console errors.

**TI.5 — package validation sweep** *(~0.5 d)*
Chrome-MCP drive on the pb_demo VN world. If no live connector with source fields exists, create a
throwaway connector (+ sample fields) for the drive and DELETE it after (reviewer-verified cleanup
pattern). Transform-regression check: for every PRE-EXISTING live mapping row (psql list), compute
apply-before vs apply-after on its sample value across the refactor — zero drift expected. C10
anchor small-scale recompute parity (unchanged ritual). Console clean; artifacts deleted.

### Skeleton S-I1 — the shared ladder (the risky spot: preview and sync must be ONE function)

```python
# integration_field_mapping.py — refactor, not fork
def _apply_transform_ops(self, vals, value, record=None):
    """Pure op ladder. `vals` = {'transformation_type','transformation_value',
    'transformation_decimals','transformation_code'} — from the RECORD for the
    sync path, from the DRAFT for previews. Same function, both callers."""
    t = vals.get('transformation_type') or 'direct'
    v = vals.get('transformation_value') or 0.0
    ...
    if t == 'python':
        expr = vals.get('transformation_code') or ''
        # D-I4: safe_eval, NO env. Draft previews never reach here (RPC refuses
        # python drafts); the sync path logs + falls back + flags the row.
        from odoo.tools.safe_eval import safe_eval
        return safe_eval(expr, {'value': value, 'record': record or {}})
    ...
# apply_transformation(self, value, record) → coercion/required/default logic stays,
#   then: return self._apply_transform_ops({f: self[f] for f in _T_FIELDS}, value, record)
# api_transform_preview → coercion of the SAMPLE + _apply_transform_ops(draft, ...)
# GOTCHA: keep the numeric-coercion + is_required + min/max clamp OUTSIDE the shared
#   ladder and run it in BOTH callers identically — previews that skip the clamp
#   would show a value the sync would never produce.
```

## WP-I verification (Chrome MCP on pb_demo VN world)

1. W62: badge vocabulary renders for every op type; popover edit ×12 → preview parity with the
   sync-path function; divide-by-zero draft → loud popover error; python wire read-only + badge.
2. safe_eval: env-usage sweep result reported (seed XML + live rows); a `value * 2` python row
   still transforms; an `env`-touching expr fails visibly (badge error tint), not silently.
3. Transform regression: all pre-existing live mapping rows produce identical apply results across
   the refactor (list count + zero-drift statement in the report).
4. W65: save→apply round-trip with correct applied/skipped/unmatched accounting; cross-company
   invisibility + server-side delete rejection; vendor seed table row-count unchanged.
5. Cycle canvas byte-identical (no badges, no transform UI). 6. Artifacts deleted; console clean.

Report back per the **Report-back items** section (deviations from D-I1..D-I8 must be flagged).

---

# WP-J — Formula Refactoring Intelligence — W52 → W54 → W42

> **✅ IMPLEMENTED 2026-07-19** (Opus) — `75e69ff9` TJ.1 detector · `b049aaf0` W52 lens ·
> `433ede23` W54 · `fc4ea654` W42 · `6babfe51`+`f64fcbdd` TJ.5/batteries/C16 (6 commits — the
> report said 7). Deviations accepted in review: 8-branch/7-bracket guard fold (T=0 only — see
> below) and D-J3 "single input component" read as single-token reference (computed driver TXBASE
> probed; ruled SOUND — `_run_formula` never recomputes dependencies, injected values are
> authoritative). Undisclosed second deviation: D-J7 "no new models" — TJ.4 added transient
> `hr.formula.import.rate.proposal` + 2 ACLs (accepted).
>
> **✅ REVIEWED 2026-07-19** (Fable auto-review: bulk subagent — full-diff read vs D-J1..D-J8 + live
> psql/JSON-RPC verification incl. an E2E throwaway-clone suggestion cycle, 24/24 probes Δ≈7e-9,
> clone deleted+verified; all four batteries independently re-run green; demo PIT formulas confirmed
> unmutated, zero leftover clones/tables). Verdict FIX-FIRST → 2 Majors fixed by Fable:
> **M1** guard fold was accepted for ANY threshold but is only exact at T=0 (chain taxes full driver,
> BRACKET taxes marginal — empirically 100k vs 50k at x=2M) and W42 rewrites with no equivalence
> gate → detector now returns None for non-zero guard thresholds (battery case 14). **M2** the
> "read-only" detection RPC stamped write_date on ALL rules of the config on every Problems-panel
> open (`_evaluate_rules_with_dependencies` → `_compute_dependencies()` + `write_diagnostics=True`)
> → new `readonly=True` mode (skips dependency refresh, evaluates via non-writing `_run_formula`
> overlay), wired into `_equivalence_check`. Minors fixed: Apply button now `canEdit`-gated;
> no-evidence failures no longer claim "max Δ 0.0000"; `_slot_formula` tokenizer `[A-Z][A-Z0-9]*`
> (interior-digit codes like T2X no longer mis-split); C16 corrected. Deferred: D-J6 suppression is
> token-set-wide (a literal both inside and outside the span suppresses everywhere in that rule);
> failing sample rows silently skipped in equivalence (clone ACs pass on probes alone);
> `_can_edit` fails open on exception (pre-existing pattern).

**Designed 2026-07-14 (Fable), after WP-I shipped.** Fifth Medium batch: deterministic refactoring
intelligence over formulas. **W52 duplicate-logic detection** — "these N formulas are identical
modulo references" as a problems-rail lens. **W54 simplification suggestions** — detect progressive
IF-chains, prove equivalence, offer a one-click `BRACKET()` rewrite. **W42 rate-table extraction** —
the same detector at import-preview time, promoting incoming IF-chains to rate tables before they
ever land. One shared detector module powers W54 and W42. Engine for detector/rewrite; studio for
lenses/actions; import mixin for W42. Effort ≈ 9–10 d.

## Verified plumbing facts (do not re-derive)

*The target shape exists in production data:* the VN demo PIT is the canonical progressive chain —
`=-MAX(0,IF(TXBASE<=0,0,IF(TXBASE<=5000000,TXBASE*0.05,IF(TXBASE<=10000000,TXBASE*0.1-250000,…))))`
(`pb_demo/models/demo_catalog.py:51-54`; 7-deep, single driver `TXBASE`, `X*rate − quickdeduction`
bands). The rate-table docstring itself names this the replacement target ("one BRACKET call
replaces the hand-written 7-deep IF chain", `formula_rate_table.py` module docstring).

*Rate tables (F11, shipped):* `hr.formula.rate.table` + brackets (`lower`, `rate`),
`compile_excel(value_expr)` `formula_rate_table.py:83-111` (progressive bands with cumulative
bases, `MAX(0, …)` guard), `expand_brackets(formula, config)` `:116+` (balanced-paren aware),
`code` constraint letters/digits only `:72-78` — table codes obey C5.

*Analysis / rendering plumbing (studio):*
- Problems rail `get_problems` + `_add` helper (kind/severity/title/detail/rule_id/col/code);
  the magic-number lint (`pb_formula_studio.py:2897-3006`, kind `magic`) already flags the
  duplicated threshold constants these chains carry — W54's lens supersedes those hints when a
  chain is detected (one cause, one card).
- Token plumbing: `_tokenize_text` `:924` (broader tokenizer used by `diff_versions` `:987`) —
  reuse for the W54 before/after diff rendering; `_tokenize` `:155` builds the live chips.
- Draft evaluation WITHOUT persistence: `rule._run_formula(values, draft_text)`
  (`formula_rule.py:1519-1525`, factored for F8 exactly so drafts can be evaluated as overlays).
- W82 hook `run_sample_tests` (`formula_config_tests.py:43`) — a refactor is a save.
- W84 `boundary_candidates` / generated-sample machinery (`formula_boundary.py`) — edge probes.

*Versioning (C4):* `VERSIONED_FIELDS` + write-override capture (`formula_rule.py:14-20`,
`:1157-1194` region); version reason enum lives on `hr.formula.rule.version` — adding a value
means editing the Selection in the owning module AND `_VALID_VERSION_REASONS` (C4).

*Import side (C6):* all preview behaviour in the mixin `multisheet_import_preview.py`
(`_import_capture` context pattern; fix-action precedent = the W37/W40 preview actions). The
resolved formula text for each staged component is available at preview time (WP-E made
unresolved refs loud, C13).

## Locked decisions

- **D-J1 (one pure detector module)** — new engine file `formula_engine/if_chain.py`:
  `parse_progressive_chain(expr) -> {driver, brackets: [{lower, rate}], span: (start, end),
  wrapper_ok: bool} | None`, plus `verify_consistency(brackets, deductions, eps=0.5)`. It
  recognizes the canonical shape only: nested `IF(D<=c_i, D*r_i [- d_i], …)` chains over ONE
  driver expression, thresholds strictly increasing. **The quick-deductions must equal the
  cumulative-base values implied by (lowers, rates)** — the same math `compile_excel` emits — or
  the chain is reported `irregular` (LISTED with the reason, never offered a rewrite; C7). Pure
  python, no ORM — unit-testable standalone (add cases to a small
  `tools/if_chain_battery.py`, same pattern as the existing batteries, exit 0 = green).
- **D-J2 (W52 hash = canonical ref slotting)** — normalize `excel_formula`: strip `=`, uppercase,
  collapse whitespace, then replace every component reference (cell-letter form AND code form,
  resolved letter-first-then-code like the engine) with positional slots `§1, §2…` in order of
  first occurrence. SHA1 the result; group by (config, hash); groups of ≥2 formula components →
  rail lens `kind='dupe'`, `severity='hint'`, one row per GROUP (title "N components share this
  logic", detail lists cols/codes, jump to the first). **v1 is detection only** — no
  auto-extraction (extracting a shared component changes downstream reference semantics; that is
  a human decision). No LLM (W53 naming stays a Low).
- **D-J3 (W54 offer gate = proven equivalence, never vibes)** — for each detected+consistent
  chain, build the rewrite (D-J4) and accept it as a SUGGESTION only if original and rewrite
  evaluate identically (|Δ| < 0.005) on: every sample's input row (confirmed or not — this is
  equivalence, not assertion), PLUS synthetic probes at every bracket edge −1/0/+1 injected on the
  driver when the driver resolves to a single input component (driver = computed → samples only,
  and the suggestion says so). Evaluation via `_run_formula(values, draft)` overlays — nothing
  persisted during detection. Suggestions render in the problems rail (`kind='simplify'`,
  severity `hint`) with a before/after token diff; accepting calls `simplify_apply(rule_id)`
  which atomically: creates the `hr.formula.rate.table` (+brackets), rewrites the formula, and
  re-runs W82 tests. The write carries **new version reason `refactor`** (add to the enum +
  `_VALID_VERSION_REASONS`, C4).
- **D-J4 (rewrite is span-surgical)** — replace ONLY the detected IF-chain span with
  `BRACKET(CODE, driver)`; every character outside the span survives verbatim (the PIT's
  `=-MAX(0,…)` wrapper must remain). Table code = C5-safe generation (letters-only, deduped
  against existing table AND component codes — reuse the WP-E `_dedupe_code_c5` approach); name
  derived from the component name. If the config already HAS a rate table whose brackets equal
  the detected ones (± eps), reuse it instead of creating a twin (C7 honesty: the suggestion
  says which).
- **D-J5 (W42 = the same detector in the import preview, mixin-only)** — after resolution, run
  `parse_progressive_chain` over each staged formula; consistent chains render as promotion
  proposals in the preview (component, driver, N brackets, first/last edge) with accept/decline;
  ACCEPT creates the table and rewrites the STAGED text before commit (the committed rule is
  born clean); DECLINE imports unchanged. Never silent, never automatic. All code in
  `multisheet_import_preview.py` (C6) calling the shared module — zero logic duplication with
  W54.
- **D-J6 (rail lens dedup)** — when a `simplify` suggestion exists for a rule, suppress the
  `magic` hints whose literals sit inside the detected span (one cause, one card); W52 `dupe`
  groups and `simplify` can coexist (different findings).
- **D-J7 (schema/deploy)** — no new models; the version-reason enum edit + detector module ⇒
  engine `-u` (ritual); manifests bump (C2). `simplify_apply` is manager-gated like every studio
  write; detection RPCs are read-only.
- **D-J8** — `docs/FORMULA_ENGINE_TOUR.html` stays untouched.

## Tasks

**TJ.1 — detector module + battery** *(~2 d)*
`formula_engine/if_chain.py` + `tools/if_chain_battery.py` (≥12 cases: the exact demo PIT chain
(expect 8 bands, driver TXBASE, consistent), a 2-band minimal, inconsistent deductions →
irregular, non-monotonic thresholds → None, driver-mismatch mid-chain → None, `>=`-direction
variant if supported or explicitly None, wrapper preservation spans, nested func in driver
`IF(MIN(A,B)<=…)`).
AC: battery green; demo PIT parses to exactly the VN statutory brackets
(0/5%, 5M/10%, 10M/15%, 18M/20%, 32M/25%, 52M/30%, 80M/35% — lowers/rates recovered from the
chain, deductions verified consistent).

**TJ.2 — W52 dupe lens** *(~1.5 d)*
Slotting/normalizer + hash + rail lens + jump.
AC: two cloned formulas with different refs on a throwaway config group together; near-miss (one
constant differs) does NOT; rail row lists all members; zero evaluation calls in the path.

**TJ.3 — W54 suggestions + apply** *(~3 d)*
Detection RPC over the config, equivalence gate (samples + edge probes), rail cards with token
diff, `simplify_apply` (table create-or-reuse + span rewrite + reason `refactor` + W82 rerun),
suppression rule D-J6.
AC: on a CLONE of a demo config, the PIT component gets a suggestion whose equivalence report
shows all samples + 24 edge probes (8 edges × 3) MATCH; apply → formula becomes
`=-MAX(0,BRACKET(<code>,TXBASE))`-shaped, wrapper intact, table has 8 brackets, chip stays green,
version row reason `refactor`; a deliberately-corrupted deduction (edit one constant first) →
`irregular`, NO suggestion, magic hints remain; second run offers table REUSE not a twin.

**TJ.4 — W42 import promotion** *(~2 d)*
Mixin detection + proposal rows + accept-rewrites-staged-text + decline path.
AC: importing a workbook whose sheet carries the PIT chain (export one from the clone via F112 or
author a minimal fixture) shows the proposal; accept → committed rule is BRACKET-form + table
exists; decline → verbatim import; preview stays responsive (detector runs once per staged
formula, no evaluation).

**TJ.5 — package validation sweep** *(~1 d)*
All drives on throwaway clones (never mutate demo formulas — C10); battery + semantics battery
green; C10 small-scale recompute parity; clones + tables deleted, verified; console clean.

### Skeleton S-J1 — the consistency gate (the risky spot: no false equivalence)

```python
# formula_engine/if_chain.py — pure, no ORM
def verify_consistency(brackets, deductions, eps=0.5):
    """brackets = [(lower_i, rate_i)] ascending; deductions[i] = the literal
    quick-deduction in band i (0 for the first). A chain is a TRUE progressive
    table iff d_i == lower_i*r_i − Σ_{k<i} r_k*(lower_{k+1}−lower_k) … i.e. the
    exact cumulative base compile_excel() would emit. Compare within eps —
    statutory tables are integers, so 0.5 absorbs authoring rounding only."""
    base = 0.0
    for i in range(1, len(brackets)):
        lo_prev, r_prev = brackets[i - 1]
        lo_i, r_i = brackets[i]
        base += r_prev * (lo_i - lo_prev)
        expected_d = lo_i * r_i - base          # tax(x) = x*r_i − d_i form
        if abs(expected_d - deductions[i]) > eps:
            return False, i                     # irregular at band i — LIST, never rewrite
    return True, -1
# GOTCHA: the demo chain is ASCENDING <= with the ELSE carrying the top band —
#   parse from the innermost ELSE out, and reject any chain whose branches don't
#   all share the same driver TEXT (normalized) — near-miss drivers (TXBASE vs
#   TXBASE2) are silently-different tables.
# GOTCHA: equivalence probes must go through the SAME evaluator as production
#   (_run_formula overlay) — never re-implement eval in the detector (C12).
```

## WP-J verification (Chrome MCP on pb_demo VN world — clones only)

1. Battery green incl. the verbatim demo PIT case. 2. W52 group on the clone; near-miss excluded.
3. W54 full cycle on the clone (suggest → diff → apply → wrapper intact → chip green → reason
   `refactor`); corrupted-deduction chain → irregular, no offer; table reuse on re-run.
4. W42 import round-trip (accept + decline paths). 5. Magic-hint suppression only inside detected
   spans. 6. C10 parity + batteries; clones/tables deleted, verified; console clean.

Report back per the **Report-back items** section (deviations from D-J1..D-J8 must be flagged).


---

# WP-K — Explanation & Collaboration — W50 → W74 → W89

> **⏸ DESIGNED, NOT BUILT — on hold 2026-07-22 (user decision).** No Opus session was ever run
> for this package. The kickoff line above remains the entry point; before using it, spot-check
> the plumbing facts below (designed against engine `19.0.1.4x` / studio `19.0.1.6x` — later
> work may have moved lines). The W74 coverage numbers (28 slips with computed JSON /
> 13,353 with inputs) were measured 2026-07-19 and should be re-counted at pickup.

**Designed 2026-07-19 (Fable), after WP-J shipped.** Sixth Medium batch: make configs and payslips
*explain themselves*, and let teams talk about them. **W50 auto-documentation** — a bilingual
handbook generated from a config (deterministic skeleton + optional AI prose polish), exported as
PDF, with a staleness stamp. **W74 slip-linked explainers** — a manager opens a payslip and every
line explains itself with THIS slip's numbers woven in. **W89 @mentions** — the F15 note composer
learns @mentions that notify via the config's chatter with a deep link back to the component.
Plus one small debt task: the standing capture-phase-Escape pass. Engine owns report/fields;
studio owns RPCs/UI (C1). Effort ≈ 10–10.5 d.

## Verified plumbing facts (do not re-derive)

*Explanation machinery (studio):* deterministic per-component explainer `_explain(rule, by_col)`
(`pb_formula_studio.py:216`); language router `_explain_localized(rule, by_col, lang)` (`:6190` —
routes to `_explain_vi` for 'vi'); AI polish `explain_formula_ai(rule_id, lang)` (`:6149`) shows
the C1 pattern exactly: compute the deterministic floor FIRST, then try `_llm_chat(messages,
json_mode=False)` (`:6023`, raises `LLMUnavailable` pre-network when unconfigured), fall back to
the floor with `source:'deterministic'`. Component display names resolve
`salary_rule_id.name or name` (`:291`) — `salary_rule_id.name` is a translated field, so EN/VI
labels come free per reader lang.

*Execution order:* `FormulaEvaluator()._topological_sort(rules)` (`formula_engine/evaluator.py:322`,
Kahn's over `formula_dependencies`, graceful on cycles) — the same order production uses
(`hr_payslip_formula.py:140`).

*W50 rendering seams:* rate brackets = `hr.formula.rate.bracket` (`formula_rate_table.py:187-198`;
`lower`, `rate` fraction, `_order='lower, id'`). Staleness anchor: milestones carry `version_hwm`
(Integer, `formula_rule_version.py:61-87`) — **C14: boundaries are version-id, not timestamp**.
PDF precedent: `ir.actions.report` `qweb-pdf` at `pb_hr_payroll_formula/report/shadow_certificate.xml:4-14`
(template `shadow_certificate`, `t-call="web.external_layout"`) — the F6 certificate rendered
HTTP 200 live, so the wkhtmltopdf stack works. Attachment precedent: `shadow_run.py:69`
(`certificate_attachment_id` M2o to ir.attachment).

*W74 payslip seams:* `hr.payslip.formula_computed_values` (Text JSON, `hr_payslip_formula.py:45-49`,
readonly) stores the engine output **keyed by BOTH code and column letter** (F6 lesson);
`formula_input_values` (`:40-43`); `report_visible_string_payload` builder at `:197`. Real formulas
reference components by COLUMN LETTER, never code (F13 verified insight) — weaving substitutes
`<letter>2` cell refs. The live payslip form = `om_hr_payroll.view_hr_payslip_form` + the pb
notebook extension `view_hr_payslip_form_json_tabs`
(`pb_hr_payroll_formula/views/hr_payslip_formula_views.xml:3-51`) — extend THAT inherit chain.
Slip→config link = `formula_config_id`; line→rule = match `hr.payslip.line.code` to
`hr.formula.rule.code` within the slip's config (lines were created FROM the rules).

*W89 seams:* notes model `hr.formula.rule.note` (`formula_rule_note.py`: rule_id cascade,
config_id related+stored, body, author_id, is_review, resolved…), **no mail.thread**;
`hr.formula.config` DOES inherit `['mail.thread','mail.activity.mixin']` (`formula_config.py:19`)
— the notification channel exists, unused. post_note create site `pb_formula_studio.py:4656`.
Deep-link plumbing: the cockpit action parses `action.params || action.context` for `config_id` /
`open_wizard` / `open_settings` on mount (`formula_studio.js:475-484`); `selectComponent(id)`
(`:1248`) selects + scrolls; `gotoProblem` (`:3901`) is the jump precedent. Security groups for
mentionables: `pb_hr_payroll_formula.group_formula_user/manager/admin`
(`security/formula_security.xml:21-50`). **Backend URL prefix is `/bizapp`** (biz_deroute
white-label; `/odoo` 301s) — build deep links from `web.base.url` + the `/bizapp` router, never
hardcode `/odoo`.

## Locked decisions

- **D-K1 (the handbook IS the skeleton; AI polishes prose only)** — W50 generates a deterministic
  document: config header (name, country, currency, component/table counts, latest milestone),
  per-GROUP sections listing every component (letter, code, localized name, type, number_format,
  formula text, `_explain_localized` sentence), a parameters table (constants with values), rate
  tables (brackets rendered `from / rate%`), and the execution order (topo sort). `_llm_chat` MAY
  rewrite each section's intro prose (2-3 sentences) — **it never produces a number, formula, or
  component name**; on `LLMUnavailable` the skeleton text ships as-is (C1). Every number in the
  document comes from the ORM. Bilingual: `lang in ('en','vi')` renders via `_explain_localized` +
  `salary_rule_id.with_context(lang=…).name`.
- **D-K2 (storage + staleness, C14-correct)** — one QWeb `qweb-pdf` report in
  `pb_hr_payroll_formula/report/` (clone the shadow-certificate wiring). Generation stores an
  `ir.attachment` on the config plus two new config fields: `handbook_attachment_id` (M2o) and
  `handbook_version_hwm` (Integer = max `hr.formula.rule.version` id for the config at generation).
  **Stale iff a newer version row exists** (`version_id > hwm`) — version-id comparison, never
  timestamps (C14). Studio RPC `handbook_status` returns {exists, stale, generated_date, url};
  `generate_handbook(config_id, lang)` is manager-gated (write path: attachment + stamp). UI: a
  "Handbook" entry (settings/lifecycle rail) with a stale badge + Regenerate + Download.
- **D-K3 (W74 value source = three honest tiers; ALWAYS write-free)** — live coverage facts
  (verified 2026-07-19 by psql): only **28/26,607** formula slips store `formula_computed_values`;
  **13,353/26,579** demo slips store `formula_input_values` (code-keyed, e.g.
  `{"BASIC": 8900000.0, "OTWD": 0, …}`). So a stored-JSON-only explainer would degrade on
  essentially every slip. Tiers: **(1)** `formula_computed_values` present → weave from it
  directly (it carries code AND letter keys — F6). **(2)** else if `formula_input_values` present
  → RECONSTRUCT all intermediates via the write-free path shipped this cycle:
  `Sample.new({'config_id'})._evaluate_rules_with_dependencies(inputs, readonly=True)` (C16 —
  zero writes, zero persistence; results are CODE-keyed, map code→letter via by_col yourself),
  then CROSS-CHECK reconstructed values against the slip's stored line totals: if every line
  matches within its `default_tolerance(number_format)` (comparison.py), weave with a
  "reconstructed from stored inputs" note; if ANY line drifts, the formulas have changed since
  the slip was computed → show the drift banner ("config formulas changed since this slip — N
  lines differ") and weave only the lines that match, degrade the rest (C7: drift is surfaced,
  never papered over). **(3)** neither JSON → line values + raw formula text, labeled
  "no stored computation — imported/legacy slip". Constants always come from the config. The RPC
  is read-only end-to-end; prove with the exact write_date probe (C16 ritual).
- **D-K4 (W74 surface = wizard on the payslip form; portal is a non-goal)** — a transient
  `hr.payslip.explain.wizard` (engine module) opened from a header button on the payslip form
  (extend the existing pb inherit view), rendering a server-built HTML field: one row per payslip
  line (localized name, formatted value, woven explanation), EN/VI toggle re-opens with the other
  lang. Manager/officer-only (payroll user group on the button). Per-line AI polish is ON DEMAND
  only (a small "AI explain" per row would need JS in a wizard — SKIP; v1 is deterministic-only,
  the studio's existing explain_formula_ai already covers ad-hoc AI asks). Employee portal
  rendering is a BINDING NON-GOAL (separate privacy/exposure decision).
- **D-K5 (W89 = mentions ride the config chatter; no new models)** — the note composer gains
  @mention autocomplete: typing `@` opens a popover listing mentionable users (new read-only RPC
  `list_mentionables(config_id)` = users in `group_formula_user`+, company-scoped); selection
  inserts `@Name` in the body and collects the user id client-side. `post_note` gains
  `mention_user_ids=[]`: server validates each id IS mentionable (silently-dropped ids are
  returned in a `skipped` list — C7 loud), then `config.message_post(partner_ids=…)` with a body =
  note excerpt + component name + a **deep link** `web.base.url + /bizapp/action-…?config_id=X&
  select_rule_id=Y` (or the `/odoo`-router equivalent resolved at runtime — never hardcode the
  prefix). Odoo's standard message_post notification (inbox + email per user prefs) does the
  delivery — build NO custom notifier. The note body stores plain text (`@Name` inline); no HTML.
- **D-K6 (deep-link param)** — the cockpit mount handler learns `select_rule_id` alongside the
  existing `config_id` param (`formula_studio.js:475-484`): after `load()`, call
  `selectComponent(select_rule_id)` (cards view). One param, one call — reuse `gotoProblem`'s
  select+scroll behavior. This is the generic anchor W91 will reuse later.
- **D-K7 (Escape debt paid)** — the deferred capture-phase-Escape items (WP-G Generate dropdown,
  WP-I transform popover + template panel) get the C3 capture-phase window-listener treatment in
  this package, and the NEW mention popover is born with it. One pattern, four surfaces.
- **D-K8 (schema/deploy)** — new: 2 config fields + 1 transient wizard + 1 QWeb report + report
  action (engine `-u` required); `post_note`/RPC changes are studio-only. Manifests bump (C2).
  `docs/FORMULA_ENGINE_TOUR.html` stays untouched.

## Tasks

**TK.1 — W50 handbook generator + report** *(~2.5 d)*
Engine: report XML + QWeb template (clone shadow-certificate wiring; `web.external_layout`),
config fields `handbook_attachment_id`/`handbook_version_hwm`. Studio: `generate_handbook
(config_id, lang)` (builds section data: groups via `_group_for`, explains via
`_explain_localized`, params table, rate tables, topo order; optional `_llm_chat` intro polish
with C1 fallback; renders PDF via the report, stores attachment, stamps hwm), `handbook_status`.
AC: generate on a demo config → PDF downloads (HTTP 200), contains every component of the config
grouped, the PIT rate table brackets, and the execution order; VI variant renders VI names/
sentences; with no AI key the doc still generates (source deterministic); after editing one
formula, `handbook_status.stale` flips true (version-id, not date — prove by generating, editing,
checking); regenerate clears stale. Zero writes to rules.

**TK.2 — W74 slip explainer wizard** *(~2.5 d)*
Engine: transient `hr.payslip.explain.wizard` (+access rows) with HTML field + lang toggle;
payslip form button (manager-gated) on the pb inherit view. Weave helper shared server-side (one
function: tokenize → substitute letter refs → format by number_format).
AC: open on a demo End-cycle slip WITH stored inputs (tier 2 — the dominant case, 13,353 slips) →
every line shows name, formatted value, and a woven sentence; reconstructed values cross-check
green vs line totals; spot-check GROSS and PIT by hand against the stored lines; DRIFT case: on a
throwaway CLONE, alter one formula, point a copied slip at it → drift banner + only matching lines
woven; tier-3 (a slip with neither JSON) → honest degrade message, no zeros invented; EN/VI toggle
swaps names+sentences; RPC path makes ZERO writes (write_date probe on slip + config rules
before/after — the C16 exact-probe ritual).

**TK.3 — W89 mentions + chatter notify + deep link** *(~2.5 d)*
Studio: `list_mentionables`, `post_note(…, mention_user_ids)` validation + `config.message_post`
with deep link; composer popover (@-trigger, keyboard up/down/enter, capture-phase Escape);
mount-param `select_rule_id` (D-K6).
AC: mention a formula-manager user in a note on a demo config → that user's inbox shows the
notification whose link opens the studio ON that config WITH the component selected (drive the
link in Chrome as that user); mentioning a non-formula user → returned in `skipped`, no
notification; note body renders `@Name` inline; Escape closes the popover from any focus state;
notification body contains NO formula internals beyond the note text + component name.

**TK.4 — capture-phase Escape pass (debt)** *(~0.5 d)*
Apply the C3 capture-phase pattern to: WP-G Generate dropdown, WP-I transform popover, WP-I
template panel. AC: each closes on Escape with grid-scroller focus (the exact WP-F failure mode),
verified live per surface.

**TK.5 — package validation sweep** *(~1 d)*
All checks live on pb_demo (throwaway where anything is created; handbook attachments on demo
configs may STAY — they're regenerable, but note them in the report); batteries green (no engine
eval changes expected — confirm if_chain + excel_semantics + import_resolution + w42 all still
exit 0); C10 small-scale recompute parity; console clean; fixture deletions verified by count.

### Skeleton S-K1 — the weave (the risky spot: substitution must be exact, not regex-loose)

```python
# studio (or a small shared helper in the engine — either side is fine, ONE copy)
CELL_RE = re.compile(r'(?<![A-Z0-9$])(\$?)([A-Z]{1,3})\$?(\d+)(?![A-Z0-9(])')
def _weave(self, rule, computed, by_col, lang):
    """'=A2+AB2*X2' -> 'Basic Salary (10,100,000) + Overtime (825,000) x Rate (5%)'.
    computed carries BOTH code and letter keys (F6) — read the LETTER key first
    (formulas reference letters, F13), fall back to the code key, then to an
    honest '?' (never 0 — C7). Skip substitution inside string literals (mask
    them first, same trick as _strip_for_lint). The (?![A-Z0-9(]) tail guard
    keeps function names (MAX() / IF() ) and longer letters intact."""
    ...
# GOTCHA: format by the REFERENCED rule's number_format (percentage -> x100 '%'),
#   not the explained rule's — a PIT explanation cites both currency and rates.
# GOTCHA: formula_input_values is CODE-keyed ({"BASIC": 8900000.0, …} — verified
#   live); _evaluate_rules_with_dependencies returns CODE-keyed results too. The
#   letter-key duplication only exists inside stored formula_computed_values
#   (tier 1). Build ONE {letter: value} view from by_col + the code-keyed dict
#   and weave from that — do not assume letter keys exist in tiers 2/3.
# GOTCHA: readonly=True is MANDATORY on every tier-2 reconstruction call — the
#   default path stamps write_date on all config rules (WP-J review M2).
```

## WP-K verification (Chrome MCP on pb_demo VN world)

1. Handbook: generate EN+VI on a demo config, PDF 200, content spot-checks (components/brackets/
   order), no-AI-key fallback, stale flip on version-id (edit → stale → regenerate → fresh).
2. Slip explainer: woven values hand-checked vs formula_computed_values on one End slip; legacy
   degrade; EN/VI; zero-write probe (exact write_date before/after).
3. Mentions: end-to-end inbox → deep link → component selected, as the mentioned user; skipped
   list for non-formula users; popover Escape (capture-phase) from grid focus.
4. Escape debt: all three older surfaces close from grid-scroller focus.
5. Batteries + C10 parity; fixtures deleted (verified by count); console clean.

Report back per the **Report-back items** section (deviations from D-K1..D-K8 must be flagged).


---

# WP-L — Excel Bridge & Payslip Branding — W41 → W17 → W73 (final Medium batch)

> **✅ IMPLEMENTED 2026-07-21** (Opus) — `5544c2a0` W41 (cell_refs.py + battery + export) ·
> `55b0cc4e` W17 smart paste · `5ef2f160` W73 themes · `72cd2bd8` C17 ledger. One flagged open
> item (the TL.2 wizard re-import, honestly disclosed as un-driven).
>
> **✅ REVIEWED 2026-07-21** (Fable auto-review: bulk subagent — full-diff read vs D-L1..D-L9 +
> live verification that CLOSED both flagged gaps: the TL.2 round-trip was driven twice through
> the real wizard UI (two-header layout ruled harmless: names-row wins, code row ignored; W42
> re-promotion fires on the re-imported PIT chain) and W17's paste UI proven drivable end-to-end
> (C17's "needs trusted event" claim was WRONG — a synthetic ClipboardEvent with a real
> DataTransfer drives the OWL handler). Verdict FIX-FIRST → 3 Majors fixed by Fable
> (`c5d61cea` + seeding amendment): **M1** the themed print derived "Net pay" from visible
> section subtotals — 42.2M printed vs the real 12.1M on slip 138268; now reads the slip's NET
> line (code → category NET → card hidden), live probe = 12,107,031 exact. **M2** the importer
> dropped uniform value columns to input/0.0 (28/53 letters diverged on recompute) — new
> `uniform_value` detection threads column→preview→creation and seeds default_value; the first
> fix attempt seeded from sample_value and was defeated by the code-header row read as data
> (caught ONLY by re-driving the exact round-trip); final state proven live: DAYSTD 26 / EESI
> 0.08 / CAPLO 46.8M / MULTWD 1.5 seeded, BASIC stays 0, **53/53 recompute parity, 0 diffs**.
> **M3** `if_chain.detect` couldn't recognize the marginal-band form `compile_brackets_excel`
> itself emits, so BRACKET-expanded exports could never re-earn a rate-table offer — new
> `parse_marginal_chain` (battery 15-18), deployed-module probe returns form=marginal. Minors
> fixed: `_expand_refs` masks string literals; interior empty clipboard cells keep position;
> sample names/notes → Info sheet (phantom SAMPLE/note components gone, proven); stage_paste RPC
> failure → error toast; toast reports r.saved; theme accent/font loud-reject (live-probed).
> Engine `19.0.1.48.0` · studio `19.0.1.68.0`. Deferred: header-per-group styling (D-L1
> cosmetic); imported formulas are row-3 canonical (pre-existing importer trait, engine
> row-agnostic); pre-existing stray draft config `DEMO_CONSTRUCTION_END_V` (id 103, pre-WP-L)
> flagged for a user cleanup decision.

**Designed 2026-07-20 (Fable), after WP-K was designed.** Seventh and FINAL planned Medium batch —
the wrap-up package. **W41 Excel round-trip export** — a config becomes a *living* `.xlsx`: one
row per sample employee, real Excel formulas that evaluate in Excel, rate tables on a reference
sheet; re-importable through the multisheet wizard. **W17 smart paste** — paste a run of formulas
from Excel straight into the grid as a validated ghost preview, committed as ONE bulk save.
**W73 payslip themes** — brand tokens (accent, typography, logo) on the F9 payslip scheme,
rendered in the live preview AND a new themed QWeb print. Build order is W41 → W17 → W73: the
export gives smart-paste its natural round-trip fixture; themes are independent. Engine owns the
themed report + theme fields; studio owns RPCs/UI (C1). Effort ≈ 12–13 d.

## Verified plumbing facts (do not re-derive)

*Export precedent (D112.6, reuse verbatim):* `export_test_template(config_id)`
(`pb_formula_studio.py:5503-5534`) — `openpyxl.Workbook()` → base64 in the RPC response
(`file_b64`/`filename`/`mimetype`); client `exportTestTemplate` (`formula_studio.js:3456-3467`)
does atob → Blob → `<a download>`. No controller, no ir.attachment. openpyxl is a declared
external dependency (`pb_hr_payroll_formula/__manifest__.py:52`) with a loud no-lib fallback
(`:5510`). The reverse path `import_test_samples` reads via
`openpyxl.load_workbook(io.BytesIO(raw), data_only=True)` (`:5537-5603`). No
`defined_names` usage exists yet anywhere in the repo.

*Formula/column model:* `hr.formula.rule.column_letter` (computed from sequence order,
`formula_rule.py:66-72`, `_compute_column_letter` `:395-451`), `excel_formula` (`:175-178`),
`constant_value` (`:242-247`), `default_value` (`:233-237`), `number_format`
(number/currency/percentage/integer, `:258-263`). Formulas are row-2 canonical (`=A2+AB2`) and
reference components by COLUMN LETTER only (F13 verified insight). Samples:
`hr.formula.sample.data.input_values_json` (code-keyed), `get_input_values()`
(`formula_sample_data.py:304-307`). Rate tables: `expand_brackets(formula, config)`
(`formula_rate_table.py:128-164`) compiles `BRACKET(code, v)` → a plain nested-IF Excel string —
i.e. the exact Excel-evaluable form.

*Drag-fill machinery (W17 clones this UX):* fill state
`ui.fill = {active, pending, srcId, hoverCol, targets: [{col, id, proposed_formula, valid}]}`
(`grid_studio.js:74-75`, init `:722`); ghost render `grid_studio.xml:157`
(`g2-ghost` + `invalid` class); commit `_commitFill()` (`:776-794`) →
`props.onBulkSaveFormulas(items, 'fill')`. Server `bulk_save_formulas(items, reason='fill',
note=False)` (`pb_formula_studio.py:780-819`) — items `[{rule_id, formula}]`, reasons limited to
`('fill','bulk')`, shared `formula_version_seen` set ⇒ exactly N version rows (C4).
Ref machinery: `_translate_formula_horizontal(formula, offset)` (`:724-741`, regex
`(\$?)([A-Za-z]+)(\$?\d+)`, $-column-absolute preserved); `_expand_refs(formula, by_col)`
(`:170-184`) returns the set of referenced columns with ranges expanded. Grid keyboard: all keys
route through `onKeydown` (`grid_studio.js:527-567`); there is NO paste handler today; selection
= array of col ids (`:64`).

*F9 payslip scheme (W73 extends, never forks — the brief's binding rule):* sections =
`hr.payslip.config` (`payslip_config.py:6-64`: `salary_structure_id`→config, `identifier`,
`label`, `label_vi`, `color_key` default 'slate', `collapse_when_empty`); per-rule
`payslip_identifier` (M2o section, `formula_rule.py:101-105`), `payslip_sequence` (`:330`),
`visibility_rule` always/when_nonzero/never (`:335-340`). Client preview `.ps-slip`
(`studio.xml:2015-2029`, section class `sc-{{color_key}}`), palette tokens in `payslip.scss:98+`
(`.sc-slate{--sc:#64748B}` etc.), handlers `psToggleLang`/`psVisible`/`psNet`
(`formula_studio.js:4380/4388/4403`). **The PRINTED payslip today is
`om_hr_payroll.report_payslip`** (`report_payslip_templates.xml:1-22`, `web.external_layout`,
company logo via `image_data_uri(o.company_id.logo)`) — it knows NOTHING of F9 sections/
visibility/label_vi, and no pb_* module overrides it. The employee portal page
(`payslip_portal_templates.xml:76-131`) embeds the HTML report via
`payslip.get_portal_url(report_type='html')` in an iframe — whatever report is bound flows to
the portal. PDF stack proven live (F6 shadow certificate, HTTP 200).

*Toolbar:* new studio tools register in the `commandLanes` getter (the ⌘K Command Center picks
tools up from there — standing convention).

## Locked decisions

- **D-L1 (W41 layout: letters ARE the columns; one row per sample)** — Sheet 1 "Payroll":
  xlsx column A = config column_letter A, 1:1, in sequence order (this is what makes the stored
  formulas real Excel). Row 1 = localized component name; row 2 = code (a second header row —
  human-readable AND machine-matchable; if the multisheet importer's header parsing requires a
  single header row, drop to name-only and flag the deviation — the TL.2 round-trip AC is the
  binding contract, not the header cosmetics); data rows follow, one per
  `hr.formula.sample.data`. The sample name lives in a trailing meta column AFTER the last
  component letter (a LEADING column would break the 1:1 letter mapping — never do that).
  Input cells = the sample's input value (else
  `default_value`); constant cells = `constant_value`; formula cells = the REAL formula with row
  digits shifted 2→N (S-L1). Number formats per `number_format` (currency → VND format),
  header row styled per group, `freeze_panes` on the first data cell. If a config has zero
  samples, export one row from `default_value`s (loud note in the sheet) — never an empty
  workbook (C7).
- **D-L2 (BRACKET compiles out; rate tables ship as a reference sheet)** — exported formula
  cells carry the `expand_brackets`-compiled nested-IF (Excel-evaluable — Excel has no BRACKET).
  Sheet 2 "Rate Tables" renders each table (code, name, bracket rows `from / rate`) and gets an
  openpyxl `defined_names` named range per table (cosmetic/reference — formulas do NOT use it).
  Round-trip synergy is a FEATURE: re-importing the expanded chain makes the W42 detector offer
  re-promotion to a rate table — the AC proves this loop.
- **D-L3 (W41 is a studio RPC on the D112.6 blob pattern)** — `export_living_workbook(config_id)`
  read-only, manager-not-required (read access suffices), returns file_b64/filename/mimetype;
  client handler clones `exportTestTemplate`; toolbar entry via `commandLanes`. No engine schema
  change for W41.
- **D-L4 (W17 clipboard = the `paste` DOM event, never the async clipboard API)** — a `t-on-paste`
  /addEventListener on the grid scroller reading `ev.clipboardData.getData('text/plain')`
  (no permission prompt, works under Cmd/Ctrl+V). TSV shapes accepted: single row → horizontal
  run starting at the focused column; single column → transposed to a horizontal run; a 2-D
  block → loud reject toast ("paste one row or one column of formulas") (C7). Only base formula
  columns are valid targets; a run crossing an input/constant/scenario column marks that ghost
  invalid.
- **D-L5 (W17: ONE server ladder normalizes + validates)** — new read-only RPC
  `stage_paste(config_id, entries=[{col, text}])` → per-entry `{col, normalized, valid, msg}`.
  Normalization (server-side, shared helper with W41's row-shift — same CELL_RE + string-literal
  mask): strip `=`? no — keep leading `=`; rewrite EVERY row digit to the canonical row 2
  (`B5*C5` → `B2*C2`, `$`-row-absolutes too — the grid has exactly one formula row), then
  validate via the existing validate path + `_expand_refs` against by_col (unknown letters →
  invalid with the letter named). The ghost shows the NORMALIZED text — what you see is what
  commits (the S-I1 one-ladder rule; preview divergence was a live-proven bug class in WP-I).
  Values that are plain numbers (no letters, no `=`) → invalid with "constants are edited in
  their own row" (v1 scope: formulas only).
- **D-L6 (W17 commit = one bulk, all-or-nothing)** — Enter commits ONLY when every ghost is
  valid (else the toast names the failing columns); commit calls
  `bulk_save_formulas(items, reason='bulk', note='smart paste')` — N version rows, one reason
  (C4), restorable per rule. Escape cancels the ghost state (fill-state Escape already routes
  through `onKeydown` — verify it fires with the ghosts up, C3).
- **D-L7 (W73 theme = lean fields on hr.formula.config; palette is LOCKED)** — engine fields:
  `theme_accent` (Selection over the EXISTING `sc-*` palette keys — slate/indigo/emerald/amber/
  rose/sky/violet; no free hex — compliance/brand bounds per the design system, C11),
  `theme_font` (Selection: 'system' | 'serif' | 'mono' — three safe stacks), `theme_logo`
  (Binary, fallback `company_id.logo`), `theme_show_logo` (Boolean, default True). No new model.
  The F9 canvas gains a "Theme" panel (swatch row + font picker + logo upload, canEdit-gated);
  the `.ps-slip` preview applies tokens via CSS vars (`--ps-accent`, font class) — preview and
  print read the SAME fields.
- **D-L8 (W73 print = a NEW themed QWeb report; the legacy report is untouched)** — a new
  `qweb-pdf` `ir.actions.report` in `pb_hr_payroll_formula/report/` ("Print Payslip (Themed)",
  binding_model hr.payslip — clone the shadow-certificate wiring incl. the Odoo-19 explicit
  `<record model="ir.actions.report">` form, NEVER the removed `<report>` shortcut tag). It
  renders the F9 scheme faithfully from slip LINE data (write-free by construction): sections by
  `payslip_identifier` ordered by sequence, lines by `payslip_sequence`, `visibility_rule`
  honored against line totals, `collapse_when_empty` honored, `label_vi` when lang='vi', theme
  tokens applied (accent on section headers/net card, font stack, logo per
  theme_logo/theme_show_logo). Unsectioned appears_on_payslip lines render in a default
  "Payslip" section (C7 — never silently dropped). `om_hr_payroll.report_payslip` and the portal
  binding stay UNTOUCHED (binding swap/portal adoption is a separate product decision — binding
  non-goal).
- **D-L9 (schema/deploy)** — engine `-u` (4 config fields + report XML); studio asset bump (C2).
  W41/W17 are studio-only. `docs/FORMULA_ENGINE_TOUR.html` stays untouched by Opus — the tour
  refresh happens AFTER this package's review, by Fable, as the wrap-up act.

## Tasks

**TL.1 — W41 living workbook export** *(~3 d)*
`export_living_workbook` (sheet build per D-L1/D-L2, row-shift helper per S-L1), client download
+ toolbar/commandLanes entry.
AC: export a demo config → workbook opens (openpyxl re-read in the battery-style check): letters
1:1, per-sample rows, formula cells are real formulas (spot-check GROSS on row 3 = `=A3+…`),
BRACKET-free (expanded), Rate Tables sheet + named ranges present, currency formats set; a
config with 0 samples exports the default row with the loud note.

**TL.2 — W41 round-trip proof** *(~1.5 d)*
Nothing new built — the AC drives the loop: export the demo-clone config → import the file
through the multisheet wizard into a THROWAWAY config → every component matches (letter, code,
type, formula text modulo the expand/letterize normalizations the importer already applies) and
sample values recompute identically through the engine (C10-style parity); the re-imported PIT
chain triggers the W42 promotion proposal (the D-L2 synergy, proving the whole loop). Throwaway
config deleted, verified by count.

**TL.3 — W17 smart paste** *(~4 d)*
`stage_paste` RPC (D-L5 ladder + tests in the paste path of the semantics battery if any pure
helper is extracted), grid paste listener + shape detection (D-L4), ghost staging on the fill
machinery, all-or-nothing commit (D-L6).
AC: copy 3 formula cells from a W41-exported workbook (row 5, e.g. `=A5+AB5` forms) → paste on
the grid → 3 ghosts show row-2-normalized text, all valid → Enter → 3 formulas saved, 3 version
rows reason='bulk' note='smart paste', values recompute; paste with an unknown letter → that
ghost red + commit blocked + toast names the column; paste a 2-D block → loud reject; paste
plain numbers → rejected with the constants message; Escape clears ghosts; C10 recompute parity
after the session.

**TL.4 — W73 themes (panel + preview + themed print)** *(~3 d)*
Engine fields + themed report (D-L7/D-L8); studio Theme panel + `.ps-slip` token application;
save RPC manager-gated.
AC: set accent=emerald, font=serif, upload a logo on a demo config → `.ps-slip` preview shows
all three; Print Themed on a demo End slip → PDF renders the F9 sections (order, visibility
when_nonzero hides zero lines, collapse_when_empty, VI labels under lang=vi) with the theme;
a config with NO theme set → neutral slate/system/company-logo defaults; om_hr_payroll's
default Print action output is byte-unchanged; unsectioned lines appear in the default section.

**TL.5 — package validation sweep** *(~1 d)*
Batteries green (if_chain/excel_semantics/import_resolution/w42 — no evaluator changes expected);
C10 small-scale recompute parity; throwaway configs/files deleted, verified; console clean;
report-back with deviations from D-L1..D-L9 flagged.

### Skeleton S-L1 — the row machinery (the risky spot: refs must survive both directions)

```python
# ONE helper pair next to _translate_formula_horizontal (pb_formula_studio.py) —
# W41 shifts OUT (2→N at export), W17 normalizes IN (any→2 at paste). Same
# regex, same mask, two thin wrappers. Never two regexes (S-I1 / D-J1 lesson).
_CELL = re.compile(r'(\$?)([A-Za-z]{1,3})(\$?)(\d+)')
def _shift_rows(self, formula, to_row):
    """'=A2+MAX(AB2,5000)*X2' -> row 7 -> '=A7+MAX(AB7,5000)*X7'.
    Mask string literals FIRST (same trick as _strip_for_lint) so 'IF(A2=\"X2\",'
    keeps its literal. Function names never match (no trailing digit-group
    without a preceding letter run is touched; MAX( has no row digit)."""
    ...
# GOTCHA (W41): the sheet's FIRST data row must equal the row the formulas cite.
#   With two header rows (name, code), data starts at row 3 — shift 2→3 for the
#   first sample, 2→4 for the second… off-by-one here silently corrupts EVERY
#   formula; the TL.1 AC's openpyxl re-read must assert the exact cell text.
# GOTCHA (W17): normalization rewrites row digits to 2 INCLUDING $-row-absolute
#   ($B$5 -> $B$2) — the grid has one formula row; keeping $5 would reference a
#   nonexistent sample row after commit.
# GOTCHA (W41 formats): openpyxl number_format strings, not Odoo's — currency ⇒
#   '#,##0' (VND has no decimals), percentage ⇒ '0.00%' BUT our percentage
#   values are FRACTIONS (0.05) so Excel's % format displays 5.00% correctly —
#   do NOT pre-multiply by 100.
```

## WP-L verification (Chrome MCP on pb_demo VN world — throwaways only)

1. W41: export → openpyxl re-read assertions (letters, rows, formulas, formats, named ranges);
   0-sample config path.
2. Round-trip: export → multisheet re-import → component/value parity + W42 re-promotion offer;
   throwaway deleted, count-verified.
3. W17: paste-from-export happy path (normalized ghosts → one bulk commit → version rows);
   unknown-letter block; block-paste reject; number reject; Escape; recompute parity.
4. W73: panel → preview tokens → themed PDF (sections/visibility/VI/theme); no-theme defaults;
   legacy print unchanged.
5. Batteries + C10 parity; fixtures deleted (verified by count); console clean.

Report back per the **Report-back items** section (deviations from D-L1..D-L9 must be flagged).
