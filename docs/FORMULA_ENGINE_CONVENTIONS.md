# Formula Engine — Conventions & Gotcha Ledger

The single shared ledger every Formula Engine handover references. Rules here are **binding** for any
implementation session (Opus or otherwise). When a new gotcha is hit during a build, add it here —
do not restate ledger content inside individual phase docs; link to the entry.

Sibling docs: `PHASE1_FORMULA_ENGINE_PLAN.md` (F1–F5) · `PHASE2_3_FORMULA_ENGINE_DESIGN.md` (F6–F15, B1–B9)
· `FEATURES_111_114_DESIGN.md` (F111–F114) · `PHASE4_MOONSHOTS_DESIGN.md` (M1–M7) · `PHASE5_FORMULA_ENGINE_DESIGN.md` (W-features).

---

## C1 — Module boundary (headless engine / studio UI)

Engine, wizard, and mapping **server** code lives in `pb_hr_payroll_formula` (must stay installable
headless, no studio dependency). All cockpit UI, OWL components, and studio RPCs live in
`pb_formula_studio` (model `pb.formula.studio`, an AbstractModel RPC facade). AI provider plumbing
lives in `pb_payroll_ai_insights`; the studio's `_llm_chat(messages, json_mode=False)`
(`pb_formula_studio.py:4179`) is the LLM entry point for studio features and **always** ships with a
deterministic fallback. Engine-side code may only reach the LLM guarded by
`'pb.formula.studio' in self.env` + try/except (pattern: `multisheet_import_preview.py:206-213`).

## C2 — Odoo 19 asset caching

Bump the `version` in `__manifest__.py` on **every** asset-list or asset-file change
(current: `pb_formula_studio` 19.0.1.60.0, `pb_hr_payroll_formula` 19.0.1.37.0). Develop with
`--dev=assets`. A new XML template file that isn't in the manifest's asset list fails only at first
render — add it in the same commit that creates it.

- **Sass `min()`/`max()` with MIXED units silently breaks the WHOLE bundle (WP-H, W98):** a rule like
  `width: min(640px, 96vw)` (px + vw) makes Dart Sass evaluate its OWN `min()` and die with
  `Internal Error: Incompatible units: 'vw' and 'px'` — this fails the ENTIRE `web.assets_backend`
  compile, so *none* of that module's new SCSS rules apply (the feature looks styled-but-broken with
  no obvious cause). `odoo-bin -u --stop-after-init` does NOT surface it (SCSS compiles lazily at
  page load); the error is only in `/var/log/odoo/odoo-server.log` (`assetsbundle: Internal Error`).
  Fix: use `width: 96vw; max-width: 640px;` (or `#{}`-interpolate to force CSS passthrough).
  Always Chrome-MCP a page + check the CSSOM for a new rule after any SCSS deploy.

- **Live-server validation double-cache:** after rsync + `DELETE FROM ir_attachment WHERE url LIKE
  '/web/assets/%'` (server bundle), the BROWSER may still serve a cached bundle on a plain reload. When
  driving Chrome via CDP, do a `Page.reload {ignoreCache:true}` (+ `Network.clearBrowserCache`) — a
  bare `Page.navigate` re-ran the OLD compiled template (W14 fix looked un-deployed until a hard reload).
- **Odoo `odoo-bin shell` breaks dict/list comprehensions** fed on stdin (`exec()` with split
  globals/locals → `NameError` on the comprehension's own loop var). Write plain `for` loops in shell
  scripts. Registry boot is ~60–90 s, so batch server-side checks and run them via `run_in_background`.

## C3 — OWL grid state invariants

- Grid-local UI state (focus/selection/editing) is keyed by **component id, never array index** —
  the parent replaces `state.components` wholesale after every save (`grid_studio.js:46-69`).
- Property rows are the fixed vocabulary `["name","category","type","formula","value","status"]`
  (`grid_studio.js:7`); only `formula` is cell-editable — other fields edit via the bulk popover.
- Display order = `sequence`; **column letters are frozen identities** that no longer track position
  (F111). Never renumber/reuse letters — a config-level high-water mark guarantees a freed letter is
  never reissued (`formula_rule.py:1129-1154`). Code renames are metadata-only; letter renames are forbidden.
- Cell editing uses a single overlay `<input>` (no contenteditable); Vietnamese IME commits on
  `compositionend`, never raw `keydown` (`ui.composing` guard).
- **Child studio components read inputs via `props.X`, never `state.X`.** A studio child (grid,
  find/replace, palette, hover) receives data through props; `this.state` is its OWN local `useState`.
  Referencing `state.canEdit` where `canEdit` is a prop silently reads `undefined` → the feature looks
  built but is dead (W14 find/replace shipped with `state.canEdit` and the replace UI never rendered
  until caught in live validation). Grep new child templates + getters for `state.<propName>`.
- **`_afterPatch` seeds the editor in an early-`return` block (W104 gotcha):** the grid
  seeds the overlay `<input>` value once, in a block that `return`s before the rest of
  `_afterPatch`. Any action that must run *after the editor mounts* (e.g. inserting a
  palette-queued snippet at the caret) has to be invoked INSIDE that block, not only at
  the tail of `_afterPatch` — otherwise it never fires on the mount patch (no further
  patch is scheduled) and the feature silently no-ops (found in W104 live validation).
- **Column virtualization (W109):** the grid windows COLUMNS only above 60 components (`.g2-virt`,
  `--g2-colw`); below that it renders everything (DOM identical to before). Any new grid feature that
  changes `ordered.length` (grouping/collapse/pinned rows) must let `_recomputeWindow` re-run and must
  keep the transient-UI owner in `_pinnedIds` so its cell never unmounts mid-interaction.
- **Overlays that don't take focus must close on Escape via a CAPTURE-phase window listener.** The
  grid navigator consumes Escape unconditionally (clear-selection + `stopPropagation`), so Odoo's
  bubble-phase `useHotkey("escape")` ladder never fires while the grid scroller has focus. The W18
  shortcuts overlay shipped un-closable on exactly the natural `?`-from-grid path (review Major).
  Either focus the overlay on mount, or intercept in capture phase gated on the overlay being open.

## C4 — F7 version capture funnel (all rule mutations)

Every write to a `VERSIONED_FIELDS` member (`formula_rule.py:14-20`) snapshots the **outgoing** state
via the `write()` override (`formula_rule.py:1157-1194`). Contract for any new feature that writes rules:

- Set `formula_version_reason` in context — one of
  `edit / bulk / import / fill / restore / lifecycle / rename / legislation / merge / sync`.
  Add a new enum value to `hr.formula.rule.version.reason` *and* `_VALID_VERSION_REASONS` if none fits.
- Batch operations (drag-fill, find-&-replace): N rules changed → exactly **N version rows, one
  reason** (not 1, not 2N). Use the shared `formula_version_seen` set in context to dedupe multiple
  writes to one rule inside a single logical operation.
- `skip_formula_version` opts a write out entirely — engine-internal recomputes only, never user edits.
- Version rows store the state **before** the edit; "formula live at time T" = earliest version row
  captured at-or-after T, else current (`pb_formula_studio.py:1027-1034` `_formula_at`).

## C5 — Formula code & converter contract

`hr.formula.rule` codes must be **underscore-free and non-substring of each other** or the
Excel→Python converter mangles references to 0. Validate any generated/renamed code through the
existing rename path (`rename_component`, `pb_formula_studio.py:2432`) which rewrites referencing
formulas atomically. Validate engine behaviour via `_evaluate_rules_with_dependencies`, **not**
`evaluate_all` directly.

## C6 — Import wizard: mixin only, capture in context

Never grow the 3,816-line `multisheet_import_wizard.py`. All import-preview behaviour is added in
mixin classes (`multisheet_import_preview.py` pattern: `_inherit` the wizard). Odoo 19 recordsets use
`__slots__` — instance attributes (`self._x = []`) raise; carry mutable capture state in **context**
(`_import_capture` pattern, `multisheet_import_preview.py:41-53`). The base wizard destroys original
formulas at resolution time (base lines 1238-1240) — the wrapper methods around
`_resolve_same_sheet_formula` / `_resolve_cross_sheet_formula` are the only place pre-resolution text
is visible. Broken refs must degrade **visibly** (red row / warning), never silently
(`no silent zeros` — W66 principle).

## C6b — Import join-key semantics (verified for W37)

The multi-sheet import join keys rows by `str(pk_value).strip()`, skipping falsy
values (`multisheet_import_wizard.py:2927-2961`). Any code measuring or altering the
join (health, diff, normalize) MUST mirror this exactly, or it measures a fake join.
Two verified facts:
- **The Excel connector coerces integral floats to int** (`1041.0` → `1041`) before
  values reach the wizard (`ExcelConnector.load_sheet_with_detection`), so the classic
  `123.0` float artifact is auto-normalized by the join itself — it never produces a
  key mismatch here. The fixable mismatch that actually SURVIVES is case/whitespace.
  Test join-key features with case-different keys (`EMP1` vs `emp1`), not int-vs-float.
- Parsed rows are NOT stored on the wizard — re-read via
  `connector.load_workbook_multisheet(b64decode(import_file))` then
  `load_sheet_with_detection(sheet_name)['data_rows']` (list of `{col: value}`).

## C7 — Silent failures are bugs

Any mapping/import/eval path that would produce `0` for an unresolvable reference must surface an
error row, warning pill, or loud log instead. Confidence scoring (40/25/20/15 weights,
`multisheet_import_preview.py:117-151`) must be *extended*, not forked, when new signals are added —
one score, one breakdown JSON.

## C8 — Performance guards

- Don't stack `compute_preview` + live validation on one keystroke: reuse the studio's debounce
  (260 ms) + monotonic supersede-token pattern (`grid_studio.js:80-81`).
- Batch server work in ~50-payslip chunks driven by the client, following the simulation pattern
  (`sim_prepare` work-list → `sim_batch` chunks → `sim_finalize`; `pb_formula_studio.py:2068-2098`).
- Cap import-preview rendering (~500 lines) with expanders; never a frozen tab.

## C9 — Odoo 19 breakages (recurring)

`safe_eval` nocopy · `res.users.group_ids` (not `groups_id`) · `res.groups.category_id` changes ·
`hr.employee.sex` · stateless recordsets (`__slots__`, see C6) · `ir_ui_view` lock via shell vs UI ·
`fields.Selection(selection_add=...)` **requires an `ondelete` policy that the base field can honor** —
`'set default'` asserts at registry load if the base field has no `default` (`ondelete policy of type
'set default' is invalid … does not define a default!`); use `'set null'` for a plain optional Selection
(WP-G used `ondelete={'generated': 'set default'}` safely because `hr.formula.sample.data.source_type`
defines `default='manual'`). **Import order for `_inherit`-only extension files matters** — Odoo 19 adds
model classes to the registry in *import order*, so a file that does `_inherit='hr.formula.sample.data'`
without a `_name` MUST be imported in `models/__init__.py` **after** the file that defines the base model,
or load aborts with `TypeError: Model 'hr.formula.sample.data' does not exist in registry` (WP-G:
`formula_boundary` had to move below `formula_sample_data`). Full list in the memory ledger
(odoo19-payroll-gotchas); check it before touching core-model overrides.

## C10 — Verification & delivery rituals

- Every feature is validated against the **pb_demo VN world** (4,512 employees, 30.5k formula-computed
  payslips, 2 configs, EN/VI) via Chrome MCP — reuse persistent demo schemes, never throwaway records.
- The regression anchor is a **batch recompute** of the VN demo payruns
  (`hr.payslip.run.action_recompute_formula_lines_batch`, `hr_payslip_run.py:10`) — zero value drift
  expected after any engine-side change.
- One **feature-scoped commit** after each feature is built + validated (explicit file staging,
  reviewer-focused message). Don't batch features into one commit; don't push unless asked.
- Payslip **Confirm is payroll-approval only** — GL auto-posting stays gated behind the
  `post_payslip_gl` context flag (off). `struct_id` is not required for formula payslips.

## C11 — Design system

Locked Payobook palette; no gradients, no emoji in UI; Lucide/SVG icons only. Studio tokens live in
`studio.scss:1-5` (`--i` indigo family, `--amber/--cyan` = upstream/downstream tint pair). New
overlays reuse the existing fixed-position primitives (`.g2-ac` autocomplete, `.g2-bulkpop` popover
scrim) rather than inventing new stacking contexts.

## C12 — Excel semantics: one source of truth, one regression gate

`formula_engine/excel_semantics.py` is the ONLY place Excel-vs-Python semantics live. Both evaluation
paths — `hr.formula.rule._run_formula` (payslips, sample tests, studio workbench) and
`FormulaEvaluator.evaluate_single` (studio fast paths, config Run Tests, sample-baseline generation) —
delegate every helper (`_if/_iferror/_round/_streq/…`) there. **Never implement an Excel function
inline in either path** — the pre-2026-07 duplicate helpers had already diverged (evaluator AVERAGE
excluded zeros; `self._if` didn't even resolve on the evaluator → silent 0s).

Converter contract (in `_convert_excel_to_python`):
- `IF` compiles to a **lazy Python ternary**, `IFERROR` to `self._iferror(lambda: …, fallback)` —
  Excel does not evaluate the untaken branch; eager helper calls exploded on `IF(B=0,0,A/B)`.
  Because of the lambda, eval passes the safe context as **globals** (lambdas resolve free names via
  globals at call time — locals-only eval NameErrors inside them).
- `ROUND/ROUNDUP/ROUNDDOWN` are Decimal-based half-away-from-zero / away / toward zero — Python's
  builtin `round()` is banker's rounding and drifts money on .5 boundaries. `CEILING/FLOOR` take a
  significance argument. All via excel_semantics.
- `<>` → `!=`, `^` → `**` (known edge: `-2^2`, right-assoc chains), `TRUE/FALSE` → `True/False`,
  `NOT(` stays a **call** (`self._not`) for precedence.
- Text equality routes through `self._streq` (case-insensitive, trimmed) on `raw_values`; `ISBLANK`
  reads `raw_values` (coerced `values` maps blank→0, making ISBLANK unsatisfiable).
- The "redundant parens" normalizer has a `(?<![A-Za-z0-9_])` lookbehind — without it `ISBLANK(G1)`
  → `ISBLANKG1` → `values.get('ISBLANKG',0)` → silent 0 for EVERY one-arg fn over a cell ref.
- **Unsupported constructs fail LOUDLY at conversion** (ValueError → `# Error:` python_formula +
  `has_evaluation_error`), never silently: `&` concatenation is currently in this class.
- Every eval is preceded by `excel_semantics.assert_safe_expression()` — formulas are user input;
  the deny-list blocks `__`/ORM/interpreter tokens outside string literals.

`python_formula` is a STORED compute — after changing the converter, regenerate it server-side (the
payslip path converts fresh per evaluation, but `evaluate_all` consumers read the cache).

**Regression gate:** `python3 pb_hr_payroll_formula/tools/excel_semantics_battery.py` (runs the real
converter/evaluator with odoo shimmed; 70 primary + 8 evaluator cases with hand-computed Excel
expectations, exit 0 = green). Run it after ANY change to formula_rule.py conversion/helpers,
evaluator.py, or excel_semantics.py, and add a case for every new Excel function or operator.

## C13 — Import resolution: degrade visibly, generate C5-safe codes (WP-E)

The stage between openpyxl and the stored `excel_formula` (`multisheet_import_wizard.py`
resolution + code generation) must never lose a formula silently. Binding rules:

- **Unresolved references become `#REF!`, never `0`.** The four resolver fallbacks
  (`_resolve_cross_sheet_formula` VLOOKUP/SUMIF/direct + `_resolve_same_sheet_formula` VLOOKUP) return
  `self._UNRESOLVED_MARK` (`#REF!`). The marker's trailing `!` makes the preview mixin's
  `SHEET_REF_RE` red-line it, and the converter refuses it loudly (`has_evaluation_error`). Returning
  `"0"` — the pre-WP-E behaviour — produced a silently-wrong component (C7 violation).
- **The direct cross-sheet regex is anchored.** Sheet token = `(?:'[^']+'|[A-Za-z_À-￿]
  [\w.À-￿]*)` with a `(?<![\w!.'])` left boundary. The old `'?([^'!]+)'?` greedily ate a
  preceding `=IF(` so `=IF(Sheet2!B2>0,1,0)` was shredded to `0>0,1,0)`. The token now covers unquoted
  **Vietnamese** sheet names (`Lương!A1`) and refuses to cross operators.
- **Generated codes are underscore-free and unique** (`_generate_code` → `_dedupe_code_c5`). The
  underscore is the actual converter-breaker; **substring collisions do NOT break the converter** —
  its code substitution is greedy/maximal-munch, so `AMOUNT`/`AMOUNTX`/`SI`/`SIEMP` all resolve
  correctly (empirically verified). Non-substring is therefore a *cosmetic preference*, taken only when
  a short letter suffix achieves it (impossible when the base equals an existing code — every
  superstring contains it). De-dup suffixes are **letters** (`AMOUNT` → `AMOUNTA`), never `_1`
  (underscore + substring). `FORMULACOL`/`COL2024`, never `FORMULA_COL`/`COL_2024`.
- **Blue-constant scan excludes data rows** (`_collect_constants_for_sheet`: `scan_up_to_row =
  data_start_row`, not `+2`) — otherwise employee #1's value freezes into a workbook-wide constant.
- **Non-numeric constants surface loudly.** Constant values parse via `excel_semantics.coerce_number`
  (handles `8%`, thousands); genuinely non-numeric (text/date) values still import as `0.0` but are
  collected and shown in a **sticky warning** on the completion notice (not a silent success).
- **Positional lookups and cross-row refs warn.** `_diagnose` flags a resolved VLOOKUP/SUMIF
  (`warning`: lookup key was dropped — verify per-employee row) and a same-column-two-rows reference
  (`warning`: running total may be flattened). Structural fix for lookup keys is W37.

All import-preview behaviour stays in the **mixin** (`multisheet_import_preview.py`, C6); base-wizard
edits are confined to the regex/`return "0"` sites and code-gen. **Regression gate:**
`python3 pb_hr_payroll_formula/tools/import_resolution_battery.py` (19 cases over the real resolver /
code-gen / diagnose, self-contained odoo shim, exit 0 = green).

## C14 — Milestone boundaries are version-id, not timestamp (WP-C / W86)

"What changed since milestone M" must be answered by a **version-id high-water mark**, never a
`create_date >= milestone_date` timestamp comparison. Odoo's `fields.Datetime.now()` is
**second-precision** while `hr.formula.rule.version.create_date` carries microseconds, and — worse —
**Odoo truncates sub-second precision when a datetime is used as a domain value**. So a milestone
sealed in the same wall-clock second as the edits it caps cannot be separated from them by timestamp.
This is invisible for B3 releases (sealed in a separate request from their edits, seconds apart) but
**fatal for one-action rollback** (W86), which edits AND seals in one transaction — a
rollback-of-a-rollback read its own sealing writes as "unreleased changes" and refused.

Binding rules:
- `hr.formula.config.milestone` carries `version_hwm` (max version id at seal time). `_seal_milestone`
  sets it; `_ms_hwm(ms)` resolves it (legacy milestones with `version_hwm = -1` fall back to the
  timestamp boundary — safe there, per above).
- All "changed since / between milestones" logic uses the id-based helpers `_formula_at_ver` /
  `_constant_at_ver` / `_changes_between_ver` (id `>` from_hwm, `<=` to_hwm), which compare **both**
  `excel_formula` and `constant_value` (so a legislation-pack constant change is releasable and
  therefore rollback-able — D-C5).
- Rollback restores each changed rule's formula+constant in **one savepoint** (all-or-nothing; a
  restored formula that no longer converts raises and aborts — C7), records a milestone + audit release
  row, and re-runs sample tests (W82 — a rollback is a save).

## C15 — Payrun value reads fall back to line totals (WP-C / W97, F6, F8)

Any feature that reads a payslip's computed component values (period comparison, shadow run,
simulation) must read `formula_computed_values` (JSON) **with a fallback to the paid line totals**
(`{pl.code: pl.total for pl in slip.line_ids if pl.code}`). The JSON snapshot is populated only on the
studio compute path; **historical and bulk-imported slips store their result as `hr.payslip.line`
rows, not the JSON** (in the VN demo, only 28 of 26.5k formula slips carry the JSON). Reading only the
JSON silently yields empty folds. Helper: `_slip_computed(slip)`.
