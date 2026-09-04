# Phase-1 "Quick Wins" — Formula Engine Implementation Plan

Companion to the product vision book (Payobook Formula Engine — Product Vision artifact).
Scope: ~7 weeks, 1–2 devs. Everything below is grounded in the current codebase.

## Build order & effort

| # | Feature | Effort | Why this order |
|---|---------|--------|----------------|
| 1 | Formula Intelligence v1 (server graph API + panels) | 4–6 days | The dependency-graph RPC is the foundation for grid highlighting AND the import preview — build once, reuse twice |
| 2 | Grid Studio v1 | ~3 weeks | Biggest, highest-visibility; consumes #1's graph payload |
| 3 | Import Confidence | ~1.5 weeks | Independent of grid; reuses the resolver output already in memory |
| 4 | Mapping upgrades (a+b) | ~1 week | Small, self-contained |
| 5 | AI quick wins | 3–4 days | Thin layer over #1 and #3 outputs |
| — | Polish, pb_coach tour steps, demo verification | ~3 days | End of phase |

## Key technical decisions

- **D1 — New lean grid, not the legacy widget.** The disabled `pb_hr_payroll_formula/static/src/js/excel_grid_widget.js` stack (+5 siblings, ~2,750 lines, commented out of the manifest) is pre-cockpit, DOM-imperative, off-design-system. The studio already has a read-only grid view (`pb_formula_studio/static/src/xml/studio.xml`, `state.view === 'grid'`, `pbfs-gridview`) wired to `get_studio_data` / `compute_preview` / `selectComponent` — evolve that into the editable Grid Studio. Harvest column-letter math, formula-bar UX and autocomplete trigger logic from the legacy files as *reference only*.
- **D2 — Grid orientation: components as columns** (matches the imported Excel). Frozen first column = row labels; frozen header = `A..AA` + component code. Property rows: Name / Category / Type / Formula (editable) / Value (live, per selected sample) / Status badge. Multi-select = column selection for bulk edits.
- **D3 — Dependency graph computed server-side, traversed client-side.** `hr.formula.rule.formula_dependencies` already stores edges; ship the adjacency list once (in `get_studio_data` payload + standalone `get_intelligence` RPC); client BFS over ~100 nodes is instant — no round-trips for hover-highlighting.
- **D4 — Import preview never commits.** ⚠ CORRECTED after code verification: the wizard does NOT call `formula_engine/cross_sheet_resolver.py` (whose `resolve_formula` returns structured `unresolved_references` at lines 413–455). The wizard uses its OWN `_resolve_same_sheet_formula` (line 1361) and `_resolve_cross_sheet_formula` (line 1255), which silently substitute `"0"` and only `_logger.debug` the miss. Additionally, `action_process_with_resolution` line 1240 overwrites `component['excel_formula']` with the resolved text — **the original Excel formula is destroyed before preview records are created**. Therefore the mixin captures original→resolved pairs and unresolved events by *wrapping the two `_resolve_*` methods* (see skeleton S2), not by reading any result dict. All new code in a mixin file; do NOT grow the 3,814-line wizard.
- **D5 — All new RPCs on `pb.formula.studio`** (`pb_formula_studio/models/pb_formula_studio.py`), except wizard-scoped ones on the wizard mixin. AI reuses the studio's existing `_llm_propose` HTTP client refactored into a generic `_llm_chat(messages, json_mode=False)` — no hard dependency on `pb_payroll_ai_insights`; deterministic fallback when `pb_formula_studio.llm_api_key` is empty.

## Feature 1 — Formula Intelligence v1 (deterministic)

Server — `pb_formula_studio/models/pb_formula_studio.py`:
- `get_intelligence(config_id)` → `{nodes: [{id, code, col, name, category, appears_on_payslip, is_valid}], edges: [[from_col, to_col]], execution_order: [col...], unused: [col...], cycles: [{cols, human_explanation}]}`. Reuse the topological sort in `pb_hr_payroll_formula/formula_engine/evaluator.py`. "Unused" = components with zero downstream dependents and `appears_on_payslip == False`. Cycle explanation renders the path `A → C → F → A` with codes and offending sub-expressions.
- `get_impact_analysis(rule_id)` → upstream/downstream closure + payslip-visible descendants.

Client — `formula_studio.js` + `studio.xml`:
- "Insights" section in the editor card (below the flowchart): impact summary + expandable downstream list with click-to-jump.
- "Execution order" and "Unused components" panels under the Settings tab (extend `state.settingsTab`).
- Circular-ref explainer replaces the bare `has_circular_ref` flag everywhere it renders.
- `state.graph` stored once at load; `upstreamOf(col)` / `downstreamOf(col)` BFS helpers — these are the grid-highlight primitives for Feature 2.

SCSS — `studio.scss`: `.pbfs-insights`, `.pbfs-impact-chip`.

## Feature 2 — Grid Studio v1

New files (all `pb_formula_studio`, registered in `__manifest__.py` → `web.assets_backend`):
- `static/src/js/grid/grid_studio.js` — `GridStudio` OWL component mounted where the current `pbfs-gridview` div is. Owns cell focus `{col, row}`, keyboard nav (arrows/Tab/Enter/F2/Escape, Ctrl+click multi-select, Shift+arrows ranges), edit mode.
- `static/src/js/grid/formula_bar.js` — shows the focused component's `=excel_formula`, editable, syntax-colored with the editor's token classes; commits via existing `save_formula`, live-checks via `validate_formula_live` (260 ms debounce pattern).
- `static/src/js/grid/cell_autocomplete.js` — component code/column dropdown while typing (data: `state.components`; port trigger logic from legacy `formula_autocomplete.js`).
- `static/src/xml/grid_studio.xml` — frozen panes via CSS `position: sticky` (first col `left:0`, header `top:0`); no JS scroll-sync, do not port `dual_scrollbar.js`.
- `static/src/scss/grid.scss` — `.pbfs-grid2` namespace: `focused`, `in-selection`, `dep-upstream` (amber tint), `dep-downstream` (blue tint), `error`/`warning` corner badges; token palette reused.

Behaviors on existing RPCs: cell edit → `validate_formula_live` + `save_formula` → `compute_preview(config_id, sample_id)` refreshes the Value row. Click a formula cell → Feature 1's client BFS highlights. Badges from `is_valid` / `has_circular_ref` already in `get_studio_data`. Sample selector reuses `get_test_data`.

New server methods on `pb.formula.studio`:
- `bulk_update_components(rule_ids, vals)` — whitelisted keys (`category_id`, `number_format`, `appears_on_payslip`, `is_visible_in_grid`), single `write`, returns refreshed payload.
- `translate_formula(rule_id, target_column_letters)` — drag-fill: server-side relative column translation reusing `_col_num` / `_expand_refs` helpers so `$`-absolute and `AA`-style refs are handled by tested code. Returns `[{col, proposed_formula, valid}]`; client shows ghost-fill confirm, commits via `save_formula` loop (or new `bulk_save_formulas`).

Scope guard: drag-fill = fill-right with relative translation + preview/confirm only (no series detection). Undo = single-level (last committed formula kept client-side).

## Feature 3 — Import Confidence

New file `pb_hr_payroll_formula/wizards/multisheet_import_preview.py` (`_inherit = 'hr.formula.multisheet.import.wizard'`):
- Fields: `resolution_preview_json` (Text), `confidence_score` (Float), `confidence_breakdown_json` (Text).
- New transient model `hr.formula.import.preview.line`: `wizard_id`, `sheet_name`, `component_code`, `component_name`, `original_excel_formula`, `resolved_formula`, `status` (`ok/warning/broken`), `issue_type` (`unresolved_xref/unknown_column/becomes_zero/circular/primary_key_miss`), `issue_detail`, `fix_action` (`map_component/convert_to_input/acknowledge_zero/skip`), `fix_target_rule_code`. Add access rules in `security/ir.model.access.csv`.
- Override `action_process_with_resolution`: initialize a capture list on `self`, call `super()`, then build preview lines by pairing captured original→resolved events with the freshly created `component_preview_ids` (match on resolved formula + sequence order; see skeleton S2). Capture happens inside thin overrides of `_resolve_same_sheet_formula` / `_resolve_cross_sheet_formula` — the ONLY way to get originals, since line 1240 of the base method overwrites `excel_formula` with the resolved text.
- `_compute_confidence()`: weighted — 40% resolved-formula ratio, 25% no would-be-zero refs, 20% column-match ratio, 15% primary-key match ratio; store breakdown.
- `action_apply_preview_fixes()`: applies per-line `fix_action` mutations to the in-memory component JSON before `action_execute_import`.

Views — `multisheet_wizard_views.xml`: extend the `review_components` step (keep the 7-step flow) with a "Resolution Preview" notebook page: preview-line tree (side-by-side formula columns, status decorations), confidence gauge, filtered "Broken references" list with inline fix-action. Polish via existing `pb_formula_studio/views/multisheet_wizard_view_inherit.xml` + `import_wizard.scss`.

## Feature 4 — Mapping upgrades

**(a) Mid→End auto-suggest** — extend `wizards/payroll_cycle_component_mapping_wizard.py` + views:
- New wizard line model `hr.payroll.cycle.mapping.suggestion`: `wizard_id`, `mid_component_id`, `end_component_id`, `confidence` (Float), `match_reason`, `state` (`proposed/accepted/rejected`).
- `action_suggest_mappings()`: exact code match (1.0) → normalized code (strip `MID_`/`END_`, case/underscores) → `difflib.SequenceMatcher` on name ≥ 0.75. Skip pairs already mapped.
- `action_accept_all()` / per-line accept → create `hr.payroll.cycle.component.mapping` records. Wizard-land only this phase.

**(b) API field mapping browser + batch test** — `models/integration_field_mapping.py`:
- `get_available_source_fields(connector_id)` (@api.model): flatten the connector's most recent `hr.api.data.store` payloads into dot-path keys with sample values + inferred types; `ir.model.fields` traversal as secondary source keyed on `connector_type`.
- `test_mappings_batch(mapping_ids, employee_id)`: run each mapping's extraction + transformation against the employee's stored payload → `[{mapping_id, raw, transformed, error}]`. Silent nested-path failures become explicit errors.
- New OWL field widget `source_field_autocomplete` (`static/src/js/source_field_autocomplete.js` + xml), registered in the `fields` registry, dropdown fed by `get_available_source_fields`, styled after `.pbfs-combobox`. Add ONLY these two files to the `pb_hr_payroll_formula` manifest assets (leave legacy grid files commented).
- "Test against employee" button on the mapping list/form (`views/integration_views.xml`) → results dialog.

## Feature 5 — AI quick wins

Server — `pb_formula_studio/models/pb_formula_studio.py`:
- Refactor `_llm_propose`'s HTTP client into `_llm_chat(messages, json_mode=False)`.
- `explain_formula_ai(rule_id, lang='en')` — prompt = excel formula + resolved dependency names (from `_tokenize`/`_explain`) + category + sample computed values; `lang='vi'` supported. Deterministic fallback: existing `_explain()` output when no API key.
- `ai_review_import(wizard_id)` — thin wrapper; heavy lifting on the wizard mixin (reads preview lines + confidence breakdown); asks for top suspicious items with reasons. Deterministic fallback: rule-based flags (literal `0` from unresolved ref, formulas referencing nothing, magnitude outliers vs sheet samples).

Client: "Explain" button next to "Ask PayAI" on the editor card → modal with EN/VI toggle. Import confirm step: "AI review" button + results panel (server-rendered HTML field is fine).

## Risks / gotchas

- **Odoo 19 asset caching**: bump the `pb_formula_studio` manifest version on every asset-list change; develop with `--dev=assets`; new XML template files must be in the assets list or OWL fails only at first render.
- **OWL reactivity**: the studio replaces `state.components` wholesale on refresh — key grid focus/selection by component `id`, never array index; keep grid UI state in a separate `useState` from shared data state.
- **Keyboard grid**: roving-focus container + single `<input>` overlay on F2 (no contenteditable). Vietnamese IME: commit on `compositionend`, not raw `keydown`.
- **Performance**: don't stack `compute_preview` + live validation — reuse the studio's debounce/cancel-token pattern. Import preview: cap side-by-side rendering at ~500 lines with an expander. `test_mappings_batch` runs against ONE employee in phase 1.
- **Wizard regression risk**: the mixin only *adds* (new fields, `super()` wrappers). Any touch of the resolver call path requires a test import of `Thaco payroll template.xlsx` before/after.
- **Module boundary**: engine/wizard/mapping server code stays in `pb_hr_payroll_formula` (headless-installable); all cockpit UI + studio RPCs in `pb_formula_studio`.

## Verification (pb_demo VN world + Chrome MCP)

1. **Intelligence**: impact-panel counts vs a hand-traced chain (BASIC → gross → PIT) on the VN active config; create a deliberate cycle in a draft config → the explainer names the exact path.
2. **Grid**: keyboard-walk A→AA; edit a formula via cell and via formula bar; Value row matches Cards/Test numbers; multi-select 5 columns → bulk-set category; drag-fill a pattern → confirm translated refs; console clean of OWL key warnings.
3. **Import Confidence**: import the Thaco template (VN + EN variants) into a fresh config; every resolver-reported unresolved ref appears in the broken-reference list; apply a `map_component` fix → score rises; abandoning at preview commits nothing.
4. **Mappings**: auto-suggest between demo mid/end configs → exact-code pairs at 1.0, accept-all creates records; batch-test with a deliberately broken nested path → explicit error, not 0.
5. **AI**: no API key → deterministic explain text (EN + VI); with an Ollama endpoint via `pb_formula_studio.llm_*` → LLM output renders, timeout degrades gracefully. Finish with a 30.5k-payslip batch recompute to prove no engine regression.

## Critical files

- `pb_formula_studio/models/pb_formula_studio.py`
- `pb_formula_studio/static/src/js/formula_studio.js`
- `pb_formula_studio/static/src/xml/studio.xml`
- `pb_hr_payroll_formula/wizards/multisheet_import_wizard.py` (read-only reference; extend via mixin)
- `pb_hr_payroll_formula/models/integration_field_mapping.py`
- `pb_hr_payroll_formula/wizards/payroll_cycle_component_mapping_wizard.py`

---

# Part II — Task checklists with acceptance criteria

Execute tasks in order within a feature. A task is done only when every acceptance criterion (AC) passes. "Studio" = the Formula Studio client action on the pb_demo VN world's active end-cycle config (~40 components) unless stated otherwise.

## Feature 1 — Formula Intelligence v1

**T1.1 — `get_intelligence(config_id)` RPC.** In `pb_formula_studio/models/pb_formula_studio.py`, following the existing `@api.model` pattern (see `get_studio_data` line ~171). Build nodes from `config.rule_ids`; edges by splitting each rule's `formula_dependencies` (verify the stored format first — it is a Char; check whether it stores codes or column letters and normalize to column letters); execution order via the same topological sort the evaluator uses; cycles via DFS back-edge detection with full path recovery.
- AC1: For the VN end-cycle config, `execution_order` length == number of formula-type rules, and every edge's source appears before its target in the order.
- AC2: `unused` contains exactly the components with zero downstream dependents AND `appears_on_payslip == False` AND type != input-consumed (hand-verify 2 examples).
- AC3: Create a 3-component draft config with A→B→C→A; `cycles` returns one entry whose `human_explanation` names all three codes in path order.

**T1.2 — `get_impact_analysis(rule_id)` RPC.** Upstream/downstream transitive closure + payslip-visible descendants + employee count (employees attached to the config's division/scheme; reuse whatever `get_studio_data` uses for config scope).
- AC: For a hand-traced component (BASIC in the VN config), downstream list matches a manual trace of `formula_dependencies`, and the payslip-visible subset matches rules with `appears_on_payslip`.

**T1.3 — Client graph state + BFS helpers.** In `formula_studio.js`: extend `load()` (line ~162) to also fetch/store `state.graph = {edges, order, unused, cycles}` (either piggyback on `get_studio_data` payload or a second `orm.call`). Add pure functions `upstreamOf(col)` / `downstreamOf(col)` doing BFS over `state.graph.edges`.
- AC: In the browser console, `upstreamOf` on the PIT column returns exactly its transitive inputs; both functions return in <5 ms for the 40-component config (log `performance.now()` once, then remove).

**T1.4 — Insights section on the editor card.** New collapsible block in `studio.xml` below the flowchart: impact sentence + expandable downstream list, each item click → `selectComponent(id)`.
- AC: Selecting any formula component renders the correct counts; clicking a downstream item navigates to it; components with zero downstream show "Nothing depends on this yet" (not an empty block).

**T1.5 — Execution-order + Unused panels.** Add `settingsTab === 'intelligence'` (state field exists, line ~110): ordered list with column letters + per-rule validity, and unused list with an "Archive" action calling existing `update_component`/`delete_component`.
- AC: Order list matches T1.1's `execution_order`; archiving an unused component refreshes the list and does not break `compute_preview`.

**T1.6 — Circular-ref explainer.** Wherever `has_circular_ref` renders in cards/grid, replace the bare flag with the cycle sentence from T1.1 + a "Show path" action that highlights the cycle members in the outline.
- AC: The deliberate-cycle config from T1.1-AC3 shows the sentence in the card; no cycle → no explainer UI at all.

## Feature 2 — Grid Studio v1

**T2.1 — Read-only GridStudio component.** New `static/src/js/grid/grid_studio.js` + `static/src/xml/grid_studio.xml` + `static/src/scss/grid.scss`, all added to the `pb_formula_studio` manifest assets (bump manifest version). Mount inside the existing `state.view === 'grid'` block of `studio.xml`, receiving the parent component (or `{components, preview, graph, canEdit}` slices) as props. Render header row (letter + code), property rows (Name/Category/Type/Formula/Value/Status), CSS-sticky header (`top:0`) and label column (`left:0`).
- AC1: Grid tab renders all components in `column_letter` order with values matching the Cards preview for the same sample; horizontal scroll keeps header + label column pinned.
- AC2: No OWL console warnings (missing `t-key` etc.); `t-key` on every `t-foreach` uses component `id`.

**T2.2 — Focus model + keyboard navigation.** Implement skeleton S1 (below). Roving focus: the scroller div is the single tabbable element; arrows/Tab/Enter move a `{colId, row}` focus cell; F2/typing opens the edit overlay; Escape cancels; Ctrl/Cmd+click toggles column selection; Shift+arrows extends a column range.
- AC1: With the mouse unplugged (keyboard only): reach the grid via Tab, walk from A to the last column and through all 6 rows, open an editor with F2, cancel with Escape — focus visibly tracked (`.focused` cell outline) the whole way.
- AC2: After a save triggers a data refresh (`state.components` replaced), focus and selection survive on the same component (id-keyed, per skeleton S1).
- AC3: Typing Vietnamese via IME in the edit overlay commits only on Enter after `compositionend` — no premature commits mid-composition (test with Telex "aa" → â).

**T2.3 — Cell + formula-bar editing.** `grid/formula_bar.js`: shows focused component's `=excel_formula`, editable; both cell overlay and bar debounce 260 ms → existing `validate_formula_live` (call signature at `formula_studio.js:327`), commit → existing `save_formula` (model line ~317) → re-call `compute_preview` and refresh Value row.
- AC1: Editing PIT's formula in the cell updates its Value cell to the same number the Test tab computes; invalid syntax shows the error inline and does NOT call `save_formula`.
- AC2: Editing via formula bar and via cell overlay produce identical round-trips; a validation request superseded by newer input never overwrites newer state (reuse the studio's timer/cancel pattern, `_liveTimer` line ~137).

**T2.4 — Dependency tinting.** On focusing a formula cell, apply `dep-upstream` (amber) / `dep-downstream` (cyan) classes to entire columns via T1.3's BFS helpers; legend row at grid footer.
- AC: Focusing PIT tints its upstream inputs amber and NETPAY-side dependents cyan (hand-verify against T1.2); focusing an input clears upstream tint; tint clears on blur.

**T2.5 — Validation badges.** Per-column status row from `is_valid` / `has_circular_ref` / warnings already in `get_studio_data`; error corner triangle on the formula cell.
- AC: A deliberately broken formula shows a red corner + message on hover/focus; fixing it clears the badge without a full reload.

**T2.6 — Cell autocomplete.** `grid/cell_autocomplete.js`: typing a letter sequence after `=`, an operator, or `(` in the edit overlay opens a dropdown of matching component codes (from `state.components`) showing code, name and current sample value; Enter/Tab inserts the column letter reference; arrow keys navigate the list without moving grid focus.
- AC: Typing `=BA` proposes BASIC; insertion produces the correct column-letter reference at the caret; Escape closes the dropdown but keeps the editor open.

**T2.7 — `bulk_update_components` RPC + bulk edit popover.** Server method with whitelist `{'category_id','number_format','appears_on_payslip','is_visible_in_grid'}` — reject other keys with `UserError`; single `write` on the recordset; return refreshed studio payload. Client: with ≥2 columns selected, a floating popover offers the whitelisted fields.
- AC1: Selecting 5 columns and setting category updates all 5 in one RPC (verify single call in network tab) and the grid re-renders with selection intact.
- AC2: Passing a non-whitelisted key (test via console) raises a clean error, no partial write.

**T2.8 — `translate_formula` RPC + drag-fill.** Server-side relative column translation reusing `_col_num` (line 81) / `_expand_refs` (line 91); returns `[{col, proposed_formula, valid}]`. Client: drag the fill handle right across columns → ghost-preview rendering of proposed formulas → Enter commits (loop of `save_formula` or new `bulk_save_formulas`), Escape discards.
- AC1: Filling `=D2+E2` from column F to G,H yields `=E2+F2`, `=F2+G2` (relative) while `=$D2+E2` keeps `$D2` fixed (absolute preserved).
- AC2: Nothing is written until Enter; Escape leaves all target formulas untouched (verify via re-read).

**T2.9 — Single-level undo.** Keep `{ruleId, previousFormula}` of the last commit in grid-local state; Ctrl+Z re-saves it.
- AC: Edit → Ctrl+Z restores the prior formula and Value row; a second Ctrl+Z does nothing (and does not error).

## Feature 3 — Import Confidence

**T3.1 — Mixin + models scaffold.** New `pb_hr_payroll_formula/wizards/multisheet_import_preview.py` with `_inherit = 'hr.formula.multisheet.import.wizard'` (new fields: `confidence_score`, `confidence_breakdown_json`) + new transient model `hr.formula.import.preview.line` (fields per Part I) + `security/ir.model.access.csv` rows + import in `wizards/__init__.py`.
- AC: Module upgrades cleanly; existing import flow unchanged when the new page is ignored (regression: full Thaco template import before/after produces identical `hr.formula.rule` sets).

**T3.2 — Resolution capture.** Implement skeleton S2: wrap `_resolve_same_sheet_formula` / `_resolve_cross_sheet_formula` to record (original, resolved, issues) events; override `action_process_with_resolution` to init capture, call `super()`, then build preview lines pairing events with `component_preview_ids`.
- AC1: After the resolution step on the Thaco template, every component with a formula has a preview line whose `original_excel_formula` is the pre-resolution text (spot-check 3 against the raw workbook) — proving capture happened before line 1240's overwrite.
- AC2: A test workbook with one VLOOKUP into a deselected sheet produces a `broken` line with `issue_type='becomes_zero'` naming the lost reference; the log-only behavior is preserved (super still called).

**T3.3 — Confidence score.** `_compute_confidence()` weighted 40/25/20/15 per Part I; breakdown stored as JSON.
- AC: All-clean import scores ≥ 0.95; the broken-VLOOKUP workbook scores measurably lower and the breakdown attributes the loss to the would-be-zero term.

**T3.4 — Resolution Preview UI.** Extend the `review_components` step in `multisheet_wizard_views.xml` with a notebook page: preview-line list (original vs resolved side by side, status decorations `decoration-danger` on broken), confidence gauge, "Broken references" filter, inline `fix_action` selection. Cap rendered lines ~500 with a "show all" toggle.
- AC: Wizard still completes with the page never opened; broken rows are visually distinct; abandoning the wizard at this step leaves zero `hr.formula.rule` records created.

**T3.5 — Fix actions.** `action_apply_preview_fixes()`: mutate the matching `component_preview_ids` records per line's `fix_action` (`map_component` → rewrite the `0` token to the target rule's column letter; `convert_to_input` → clear formula, set `column_type='input'`; `acknowledge_zero` → mark line ok; `skip` → uncheck `include_in_import`), then recompute confidence.
- AC: Applying `map_component` on the broken-VLOOKUP line updates the resolved formula, flips status to ok, raises the score; executing the import then creates the corrected rule.

## Feature 4 — Mapping upgrades

**T4.1 — Suggestion model + generator.** `hr.payroll.cycle.mapping.suggestion` + `action_suggest_mappings()` on the existing cycle-mapping wizard: exact code (1.0) → normalized code (strip `MID_`/`END_`/case/underscores, 0.9) → `difflib.SequenceMatcher` name ratio ≥ 0.75. Skip already-mapped pairs; one suggestion per mid component (best match wins).
- AC: On the demo mid/end configs, ADVPAY-style exact pairs appear at 1.0; already-mapped pairs are absent; no mid component appears twice.

**T4.2 — Accept flow.** Per-line accept + `action_accept_all(min_confidence=0.9)` → create `hr.payroll.cycle.component.mapping` records; rejected suggestions persist as `rejected` so re-running doesn't resurface them.
- AC: Accept-all creates exactly the ≥0.9 set; re-opening the wizard shows them as existing mappings, not suggestions.

**T4.3 — `get_available_source_fields(connector_id)`.** On `hr.integration.field.mapping`: flatten the connector's most recent stored payloads into dot-paths with sample values + inferred types; fall back to `ir.model.fields` traversal for Odoo-side connector types.
- AC: For the demo connector, returns a non-empty list where each entry has `{path, sample, type}`; nested dicts appear as `a.b.c` paths.

**T4.4 — `source_field_autocomplete` widget.** OWL char-field widget registered in the `fields` registry; dropdown fed by T4.3, substring match on path + sample; selecting fills the field. Register JS+XML in the `pb_hr_payroll_formula` manifest (only these files — legacy grid stays commented).
- AC: On the mapping form, typing `sal` proposes `base_salary` with its sample value; free-text entry still allowed (widget must not block unknown paths).

**T4.5 — `test_mappings_batch` + dialog.** Server method running extraction + transformation per mapping against one employee's stored payload → `[{mapping_id, raw, transformed, error}]`; "Test against employee" button opens the results dialog.
- AC: A deliberately broken nested path (`employee.department.INVALID`) returns an explicit error string for that row — not `0`, not `None`-as-success; healthy rows show raw → transformed values.

## Feature 5 — AI quick wins

**T5.1 — `_llm_chat(messages, json_mode=False)`.** Extract the HTTP client from `_llm_propose`; `_llm_propose` becomes a caller of it. Timeout + non-200 → raise a typed exception callers catch for fallback.
- AC: Existing "Edit with PayAI" behavior unchanged (manual smoke test); with no API key, `_llm_chat` raises immediately without a network call.

**T5.2 — `explain_formula_ai(rule_id, lang)`.** Prompt = excel formula + dependency names via `_tokenize`/`_explain` + category + sample values; `lang in ('en','vi')`. On any LLM failure return `{'text': _explain(...), 'source': 'deterministic'}`.
- AC1: No API key → deterministic text in both languages (VI via existing translation of `_explain` output or the template strings), `source='deterministic'`.
- AC2: With an Ollama endpoint configured in `pb_formula_studio.llm_*` → LLM text returns; killing Ollama mid-session degrades to deterministic without a traceback reaching the client.

**T5.3 — Explain UI.** "Explain" button beside "Ask PayAI" on the editor card → modal with EN/VI toggle; badge shows AI vs deterministic source.
- AC: Modal opens under 200 ms with the deterministic floor even while the LLM call is in flight (progressive: floor first, LLM replaces when it lands).

**T5.4 — `ai_review_import(wizard_id)`.** Wizard-mixin method reading preview lines + confidence breakdown; LLM prompt asks for top suspicious components with reasons; deterministic fallback = rule-based flags (literal `0` from capture events, formulas referencing nothing, magnitude outliers vs `sample_value`). "AI review" button + HTML results panel on the confirm step.
- AC: The broken-VLOOKUP fixture is flagged by the deterministic path with the zero-substitution reason; with LLM enabled, output renders as a ranked list, and LLM failure silently falls back.

**T5.5 — Tours + final verification.** pb_coach tour steps for Grid, Import preview, Mapping suggest; run the full Part I verification list; finish with the 30.5k-payslip batch recompute.
- AC: All Part I verification items pass; recompute totals match pre-phase baseline exactly.

---

# Part III — Code skeletons for the two risky spots

These are load-bearing skeletons: structure, state shape and event wiring are the decisions; bodies marked `…` are routine. Match surrounding code style (the studio uses 4-space indent, no semicolonless style).

## S1 — Grid focus/selection model (`pb_formula_studio/static/src/js/grid/grid_studio.js`)

```js
/** @odoo-module **/
import { Component, useState, useRef, onPatched } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

// Property rows are a fixed vocabulary — index math stays trivial.
const ROWS = ["name", "category", "type", "formula", "value", "status"];
const EDITABLE_ROWS = new Set(["formula"]); // category/type edit via bulk popover in v1

export class GridStudio extends Component {
    static template = "pb_formula_studio.GridStudio";
    // Parent passes the SHARED data (never copied) + callbacks. Grid never mutates parent state.
    static props = {
        components: Array,     // parent's state.components (id, col, code, name, group, type, excel_formula, is_valid, ...)
        preview: Object,       // parent's state.preview {sample_id, values: {COL: number}}
        graph: Object,         // parent's state.graph {edges: [[fromCol, toCol], ...]}
        canEdit: Boolean,
        onSaveFormula: Function,   // (ruleId, formula) => parent RPC save_formula + refresh
        onValidateLive: Function,  // (formula, excludeRuleId) => parent RPC, returns {valid, message}
        onSelect: Function,        // (ruleId) => parent.selectComponent
    };

    setup() {
        this.orm = useService("orm");
        // CRITICAL: grid-local UI state lives in its OWN useState, keyed by component *id*,
        // never array index — parent replaces state.components wholesale after every save.
        this.ui = useState({
            focus: { colId: null, row: "formula" },  // colId = hr.formula.rule id
            selection: [],                            // array of colIds (Ctrl/Shift multi-select)
            anchorId: null,                           // Shift-range anchor
            editing: null,   // { colId, row, buffer, valid, message } | null
            composing: false, // IME guard
            ghostFill: null, // { targets: [{col, proposed_formula, valid}] } | null
        });
        this.scrollerRef = useRef("scroller");
        this._liveTimer = null;      // same debounce pattern as formula_studio.js
        this._lastCommit = null;     // { ruleId, previousFormula } — single-level undo
        onPatched(() => this._scrollFocusIntoView());
    }

    // ---- derived (recomputed against CURRENT props each render — survives data refresh) ----
    get ordered() {
        return [...this.props.components].sort((a, b) => this._colNum(a.col) - this._colNum(b.col));
    }
    get focused() { return this.props.components.find(c => c.id === this.ui.focus.colId) || null; }
    _colNum(col) { let n = 0; for (const ch of String(col || "")) n = n * 26 + ch.charCodeAt(0) - 64; return n; }

    // Dependency tinting: BFS over props.graph.edges (column letters), memoized per focus change.
    depClass(comp) {
        if (!this.focused || comp.id === this.focused.id) return "";
        if (this._upstream?.has(comp.col)) return "dep-upstream";
        if (this._downstream?.has(comp.col)) return "dep-downstream";
        return "";
    }
    _recomputeTint() {
        const f = this.focused;
        this._upstream = f ? this._bfs(f.col, "up") : null;
        this._downstream = f ? this._bfs(f.col, "down") : null;
    }
    _bfs(startCol, dir) { /* … walk props.graph.edges; return Set of column letters … */ }

    // ---- focus & selection ----
    setFocus(colId, row) {
        if (this.ui.editing) return;                 // an open editor owns the keyboard
        this.ui.focus = { colId, row };
        this._recomputeTint();
        this.props.onSelect(colId);                  // keep cards/outline in sync
    }
    onCellClick(ev, comp, row) {
        if (ev.ctrlKey || ev.metaKey) return this._toggleSelect(comp.id);
        if (ev.shiftKey && this.ui.anchorId) return this._rangeSelect(comp.id);
        this.ui.selection = []; this.ui.anchorId = comp.id;
        this.setFocus(comp.id, row);
    }
    _toggleSelect(colId) { /* … add/remove colId in ui.selection … */ }
    _rangeSelect(colId) { /* … select ids between anchor and colId in `ordered` order … */ }

    // ---- keyboard: ONE handler on the scroller (roving focus; cells are inert divs) ----
    onKeydown(ev) {
        if (this.ui.editing) return this._onEditorKeydown(ev); // editor input has its own path
        const cols = this.ordered, ci = cols.findIndex(c => c.id === this.ui.focus.colId);
        const ri = ROWS.indexOf(this.ui.focus.row);
        const move = (dc, dr) => {
            const c = cols[Math.max(0, Math.min(cols.length - 1, ci + dc))];
            const r = ROWS[Math.max(0, Math.min(ROWS.length - 1, ri + dr))];
            if (c) this.setFocus(c.id, r);
        };
        switch (ev.key) {
            case "ArrowRight": move(+1, 0); break;
            case "ArrowLeft":  move(-1, 0); break;
            case "ArrowDown":  move(0, +1); break;
            case "ArrowUp":    move(0, -1); break;
            case "Tab":        move(ev.shiftKey ? -1 : +1, 0); break;
            case "Enter": case "F2": this._startEdit(); break;
            case "z": if (ev.ctrlKey || ev.metaKey) { this._undo(); break; } return;
            default:
                // printable char on an editable cell → open editor pre-seeded with the char
                if (ev.key.length === 1 && !ev.ctrlKey && !ev.metaKey
                    && EDITABLE_ROWS.has(this.ui.focus.row) && this.props.canEdit) {
                    this._startEdit(ev.key); break;
                }
                return; // unhandled: let it bubble
        }
        ev.preventDefault(); ev.stopPropagation();
    }

    // ---- editing (single <input> overlay swapped in; no contenteditable) ----
    _startEdit(seed) {
        const f = this.focused;
        if (!f || !EDITABLE_ROWS.has(this.ui.focus.row) || !this.props.canEdit) return;
        this.ui.editing = {
            colId: f.id, row: this.ui.focus.row,
            buffer: seed !== undefined ? seed : (f.excel_formula || ""),
            valid: null, message: "",
        };
    }
    onEditorInput(ev) {
        this.ui.editing.buffer = ev.target.value;
        if (this.ui.composing) return;               // IME: never validate mid-composition
        clearTimeout(this._liveTimer);
        const mine = this.ui.editing;
        this._liveTimer = setTimeout(async () => {
            const res = await this.props.onValidateLive(mine.buffer, mine.colId);
            // stale-guard: a newer editor session may have replaced `mine`
            if (this.ui.editing === mine) Object.assign(mine, { valid: res.valid, message: res.message || "" });
        }, 260);
    }
    // IME guards — bind t-on-compositionstart / t-on-compositionend on the overlay input
    onCompositionStart() { this.ui.composing = true; }
    onCompositionEnd(ev) { this.ui.composing = false; this.onEditorInput(ev); }
    _onEditorKeydown(ev) {
        if (ev.key === "Enter" && !this.ui.composing) { ev.preventDefault(); this._commit(); }
        else if (ev.key === "Escape") { ev.preventDefault(); this.ui.editing = null; } // discard
        ev.stopPropagation(); // NEVER let editor keys reach the grid navigator
    }
    async _commit() {
        const e = this.ui.editing, comp = this.props.components.find(c => c.id === e.colId);
        if (!comp || e.valid === false) return;      // red editor cannot commit
        this._lastCommit = { ruleId: comp.id, previousFormula: comp.excel_formula };
        this.ui.editing = null;
        await this.props.onSaveFormula(comp.id, e.buffer); // parent saves + refreshes + compute_preview
        // focus survives refresh automatically: ui.focus.colId is an id, and `focused`
        // re-resolves against the NEW props.components on next render.
    }
    async _undo() {
        if (!this._lastCommit) return;
        const { ruleId, previousFormula } = this._lastCommit;
        this._lastCommit = null;
        await this.props.onSaveFormula(ruleId, previousFormula);
    }
    _scrollFocusIntoView() { /* … querySelector [data-col-id][data-row] → scrollIntoView({block:'nearest', inline:'nearest'}) … */ }
}
```

Template contract (`grid_studio.xml`): the scroller div has `t-ref="scroller" tabindex="0" t-on-keydown="onKeydown"`; every cell is `t-att-data-col-id` / `t-att-data-row` with `t-key="comp.id"`; the edit overlay is a single absolutely-positioned `<input>` rendered only when `ui.editing`, with `t-on-input`, `t-on-keydown="_onEditorKeydown"`, `t-on-compositionstart`, `t-on-compositionend`, and autofocus via `t-ref` + `onPatched`.

Parent wiring in `formula_studio.js`: `onSaveFormula = async (id, f) => { await this.orm.call("pb.formula.studio", "save_formula", [id, f]); await this.load(this.state.config.id); this.state.preview = await this.orm.call("pb.formula.studio", "compute_preview", [this.state.config.id, this.state.preview.sample_id]); }` — mirroring the existing patterns at lines 317/730.

## S2 — Resolver capture mixin (`pb_hr_payroll_formula/wizards/multisheet_import_preview.py`)

```python
import json
import re
from odoo import api, fields, models, _

# Why wrapping is required (verified against the base file):
#  * action_process_with_resolution (line 1029) loops components calling
#    _resolve_same_sheet_formula (1361) then _resolve_cross_sheet_formula (1255),
#    whose inner match-handlers return "0" for unresolved refs with only _logger.debug.
#  * Line 1240 then sets component['excel_formula'] = resolved — the ORIGINAL formula
#    is gone before preview records are created. Only these wrappers ever see it.

SHEET_REF_RE = re.compile(r"(?:'[^']+'|\w+)\s*!")   # any remaining sheet-qualified ref


class MultisheetImportPreview(models.TransientModel):
    _inherit = 'hr.formula.multisheet.import.wizard'

    preview_line_ids = fields.One2many('hr.formula.import.preview.line', 'wizard_id')
    confidence_score = fields.Float(readonly=True)
    confidence_breakdown_json = fields.Text(readonly=True)

    # ---- capture plumbing -------------------------------------------------
    # Plain instance attribute, NOT a field: capture is scoped to one server call.
    # The base method runs the whole loop inside one action, so this is safe.

    def action_process_with_resolution(self):
        self._capture = []          # [{'original','after_same','resolved','sheet'}]
        res = super().action_process_with_resolution()
        # super() succeeded: component_preview_ids exist, state == 'review_components'
        self._build_preview_lines()
        return res

    def _resolve_same_sheet_formula(self, formula, sheet_name, column_mapping):
        resolved = super()._resolve_same_sheet_formula(formula, sheet_name, column_mapping)
        if getattr(self, '_capture', None) is not None and formula:
            # One event per component: the base loop calls same-sheet FIRST.
            self._capture.append({'original': formula, 'after_same': resolved,
                                  'resolved': None, 'sheet': sheet_name})
        return resolved

    def _resolve_cross_sheet_formula(self, formula, column_mapping):
        resolved = super()._resolve_cross_sheet_formula(formula, column_mapping)
        cap = getattr(self, '_capture', None)
        if cap is not None and cap and cap[-1]['resolved'] is None \
                and cap[-1]['after_same'] == formula:
            cap[-1]['resolved'] = resolved      # completes the most recent event
        return resolved

    # ---- pairing + diagnosis ----------------------------------------------
    def _build_preview_lines(self):
        self.preview_line_ids.unlink()
        Line = self.env['hr.formula.import.preview.line']
        # Events were appended in the exact order the base loop walked formula
        # components; component_preview_ids preserves that creation order.
        events = list(getattr(self, '_capture', []) or [])
        previews = self.component_preview_ids.filtered(lambda p: p.resolved_formula)
        vals_list = []
        for preview, event in zip(previews, events):
            # Belt & braces: sequence pairing must agree on the resolved text.
            resolved = event['resolved'] if event['resolved'] is not None else event['after_same']
            if resolved != preview.resolved_formula:
                event = next((e for e in events
                              if (e['resolved'] or e['after_same']) == preview.resolved_formula),
                             event)  # fall back to content match before giving up
                resolved = event['resolved'] if event['resolved'] is not None else event['after_same']
            status, issue_type, detail = self._diagnose(event['original'], resolved)
            vals_list.append({
                'wizard_id': self.id,
                'sheet_name': preview.source_sheet,
                'component_code': preview.generated_code,
                'component_name': preview.generated_name,
                'original_excel_formula': event['original'],
                'resolved_formula': resolved,
                'status': status, 'issue_type': issue_type, 'issue_detail': detail,
            })
        Line.create(vals_list)
        self._compute_confidence()

    def _diagnose(self, original, resolved):
        """Classify one original→resolved pair. Deterministic, no LLM."""
        # 1) A sheet-qualified ref survived resolution → converter will choke or zero it.
        if SHEET_REF_RE.search(resolved or ''):
            return 'broken', 'unresolved_xref', _("Sheet reference not resolved: %s") % resolved
        # 2) Zero substitution: base handlers replace unresolved lookups with "0".
        #    Heuristic: original had a sheet ref or lookup, and resolved gained a bare 0 token.
        had_xref = bool(SHEET_REF_RE.search(original or '')) or 'VLOOKUP' in (original or '').upper()
        zeros_before = len(re.findall(r'(?<![\w.])0(?![\w.])', original or ''))
        zeros_after = len(re.findall(r'(?<![\w.])0(?![\w.])', resolved or ''))
        if had_xref and zeros_after > zeros_before:
            return 'broken', 'becomes_zero', _(
                "A reference in %s could not be mapped and became 0") % original
        # 3) Column letters outside the assigned range → unknown_column …
        # 4) otherwise ok
        return 'ok', False, False

    def _compute_confidence(self):
        lines = self.preview_line_ids
        total = len(lines) or 1
        resolved_ratio = len(lines.filtered(lambda l: l.status == 'ok')) / total
        no_zero_ratio = 1 - len(lines.filtered(lambda l: l.issue_type == 'becomes_zero')) / total
        column_ratio = ...   # selected columns that mapped / selected columns
        key_ratio = ...      # sheets whose primary key matched / sheets
        score = 0.40 * resolved_ratio + 0.25 * no_zero_ratio + 0.20 * column_ratio + 0.15 * key_ratio
        self.write({'confidence_score': round(score, 3),
                    'confidence_breakdown_json': json.dumps({
                        'resolved': resolved_ratio, 'no_zeros': no_zero_ratio,
                        'columns': column_ratio, 'keys': key_ratio})})
```

Pairing rationale: sequence-zip is the primary mechanism because the base loop and `component_preview_ids` creation share one deterministic order; the content-match fallback covers any future reordering of the base method. If both disagree for a line, mark it `warning` with `issue_detail='pairing uncertain'` rather than guessing silently — visible degradation over silent misattribution, which is the whole point of the feature.

