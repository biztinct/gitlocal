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
- **An `if`/statement inside an inline `t-on-*` arrow handler breaks the WHOLE OWL template compile
  (WP-I, W65):** `t-on-keydown="(ev) => { if (ev.key === 'Enter') this.save(); }"` makes the QWeb→JS
  compiler emit invalid JS (`Failed to compile template … Unexpected identifier 'vNNN'`), which fails
  the ENTIRE component template at first render — the cockpit goes blank with only a browser-console
  error. Expression/call arrows are fine (`(ev) => ev.stopPropagation()`, even multi-call
  `{ a(); b(); }`); it is the `if`/statement keyword the compiler mishandles. Like the SCSS mixed-unit
  trap above, `odoo-bin -u --stop-after-init` does NOT surface it (templates compile lazily in the
  browser) — always Chrome-MCP the cockpit after a template change. Fix: hoist to a named component
  method (`t-on-keydown="onFooKey"`).
- **`odoo-bin shell` deadlocks on `access_roles._update_role_groups_view` while the service is up
  (WP-I):** the shell rebuilds the registry, whose `_register_hook` rewrites the role-groups
  `ir_ui_view` arch; if the live service is concurrently up (or a stale detached `odoo-bin` still
  holds the row) it dies with `LockNotAvailable: … updating tuple in "ir_ui_view"`. Prefer validating
  against the RUNNING registry over JSON-RPC (`/web/dataset/call_kw`, public methods only) — no
  registry rebuild, no lock. If you must use the shell, stop the service AND confirm zero `odoo-bin`
  procs first (kill stale ones by PID — never `pkill -f odoo-bin`, it self-matches). Registry reload
  is ~150 s here because that view rebuild is slow (non-fatal warnings during boot).

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
`formula_boundary` had to move below `formula_sample_data`). **`_sql_constraints` is silently
IGNORED in Odoo 19** — `model_classes.py:162` only logs a warning ("no longer supported") and the
constraint NEVER reaches the database: every legacy list in the codebase produced tables with no
unique constraints at all (found in the WP-H review — `hr_formula_budget_line` accepted duplicate
codes; the sweep showed ZERO unique constraints across all `hr_formula_*` tables). The Odoo 19 form
is a class attribute: `_code_uniq = models.Constraint('unique(config_id, code)', 'message')`. All
13 engine constraints were converted 2026-07-14 (dup-checked live first — all clean). ~28 more
files elsewhere in the repo still carry dead `_sql_constraints`; convert on touch. **An unset Char
field reads as `False` from the ORM** — `raw is None or raw == ''` misses it and `float(False)` is
silently `0.0`; empty-checks on ORM Chars must be `if not raw` (bit the W62 preview fix TWICE
before landing). Full list in the memory ledger (odoo19-payroll-gotchas); check it before touching
core-model overrides.

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

## C16 — Progressive-chain detector (WP-J / W52·W54·W42)

The nested-`IF` progressive-tax detector is `formula_engine/if_chain.py` — **pure, no ORM**, the
single source shared by W54 (studio) and W42 (import mixin); never re-implement chain parsing in a
caller (D-J1). `detect(expr)` returns `None` for a non-chain, else a dict with `brackets`,
`deductions`, `span` (char offsets), `consistent`, `bad_band`, `reason`. Binding facts hit building it:

- **The VN demo PIT parses to 8 value-branches but 7 statutory brackets.** `=-MAX(0,IF(TXBASE<=0,0,
  IF(TXBASE<=5M,…)))` has a leading `<=0 → 0` non-negative guard plus 7 rate bands. The guard is NOT a
  bracket — `BRACKET()`'s own `MAX(0,…)` reproduces it — so the rate table has **7** brackets
  (0/5%…80M/35%), and the rewrite is `=-MAX(0,BRACKET(<code>,TXBASE))` with the guard folded away. The
  design's "8 brackets" prose (TJ.1/TJ.3 AC) counts branches; the table is 7 (matches the explicit
  statutory list at design:1892). (WP-J's other deviation: D-J7 said "no new models", but TJ.4 added the
  transient `hr.formula.import.rate.proposal` + 2 ACLs for the wizard proposal list — accepted in review.)
- **The guard fold is exact ONLY at threshold 0.** A leading `IF(D<=T,0,…)` with `T>0` must NOT fold
  into the first bracket's lower bound: the chain's first rate band taxes the FULL driver (`v*rate`)
  while `compile_brackets_excel` emits marginal `rate*(v−lower)` — divergent for every `v>T` (at T=1M,
  x=2M: chain 100k vs BRACKET 50k). W54's probes would catch it, but **W42 rewrites staged text with no
  evaluation gate**, so the detector itself returns `None` for non-zero guard thresholds (WP-J review
  M1; battery case 14).
- **Detection RPCs must be write-free — sample evaluation included.** `_evaluate_rules_with_dependencies`
  by default stamps `write_date` on EVERY rule of the config (`_compute_dependencies()` compute-field
  assignment + `evaluate()`'s `write_diagnostics=True`). Any read-only path (the W54 rail detection runs
  on every Problems-panel open) must call it with `readonly=True`, which skips the dependency refresh and
  evaluates via the `_run_formula(…, write_diagnostics=False)` overlay (WP-J review M2 — live-proven:
  one rail open bumped write_date on all 50 rules of a production config).
- **Equivalence is proven, never assumed.** W54 offers a rewrite only after `_run_formula` overlays
  match (|Δ|<0.005) on every sample PLUS edge probes at each bracket boundary −1/0/+1. Probes inject
  `{driver_code: x}` and work for ANY **single-token** driver — computed helper included (demo TXBASE
  is a helper formula, driver_kind `computed`) — because the chain references the driver only as a
  looked-up value. Only a COMPOUND driver expression (`MIN(A,B)`) is samples-only. For the demo that is
  8 edges × 3 = **24 probes** (7 lowers + one synthetic top edge). This reading of D-J3's "single input
  component" (= single reference, not literally an input column) is what makes the AC's 24 probes hold.
- **The equivalence draft must compile the SAME Excel the committed BRACKET emits.** Use the pure
  `formula_rate_table.compile_brackets_excel(brackets, value_expr)` (extracted from `compile_excel`),
  inlined into the span, so the proof matches the apply exactly — no table is persisted during
  detection.
- **`hr.formula.config.copy()` clones the unique `code`** → `ValidationError: Configuration code must
  be unique per company`. Always pass an override `code` in the copy defaults when cloning a config
  (validation harnesses: `copy(id, {'name':…, 'code':'ZZ…'})`).
- **Battery-shim upkeep:** `tools/if_chain_battery.py` is pure (no shim). `tools/w42_promotion_check.py`
  exercises the preview-mixin promotion logic offline (call_kw can't reach private mixin methods). Any
  new `from ..formula_engine import X` in a shimmed file must be mirrored in the battery's fake package
  (`import_resolution_battery`), and the `excel_semantics_battery` odoo shim needs `models.Constraint`
  (class-attribute constraints since the C9 conversion).

## C17 — Excel bridge & payslip branding (WP-L / W41·W17·W73)

The row machinery and the live-validation lessons hit building the export/paste/theme trio:

- **One row helper, two directions.** `formula_engine/cell_refs.shift_rows(formula, to_row)` is the ONLY
  place cell-ref row digits move — W41 shifts stored row-2 formulas OUT to the sheet data row at export,
  W17 normalizes any pasted row back IN to the canonical row 2. Same `_CELL` regex, same string-literal
  mask (mask FIRST so `IF(A2="X2",…)` keeps its literal). Never a second regex (S-I1 / D-J1). Battery:
  `tools/cell_refs_battery.py` (pure, 20 cases incl. the OUT→IN round-trip invariant). The studio wraps it
  as `_shift_rows`.
- **W41 places by LETTER, not sequence.** The xlsx column position MUST equal `_col_num(column_letter)`
  (A→1, AB→28) so a stored `=A2+AB2` is a real Excel formula in the sheet; letters are frozen identities
  that no longer track sequence (F111). A reordered/gap-lettered config leaves blank xlsx columns — fine,
  the refs still land. A leading meta column would break the 1:1 map — the "Sample" name column trails the
  last letter. **openpyxl number formats are openpyxl's, not Odoo's:** currency/integer ⇒ `#,##0` (VND has
  no minor units), percentage ⇒ `0.00%` and our values are FRACTIONS (0.05) so do NOT pre-multiply.
  `wb.defined_names[name] = DefinedName(name, attr_text=ref)` on openpyxl ≥3.1 (`DefinedNameDict`).
- **QWeb widgets never on `<td>`.** `t-field` directly on a `<td>` raises `AssertionError: QWeb widgets do
  not work correctly on 'td' elements` (only surfaces at PDF render, not `-u`). Wrap: `<td><span t-field=…/></td>`.
- **The themed payslip is a NEW report; the legacy one is byte-untouched.** Clone the shadow-certificate
  wiring (explicit `<record model="ir.actions.report">`, binding_model hr.payslip, NEVER the removed
  `<report>` shortcut — see [[payobook-deploy]]). Render data comes from a WRITE-FREE model helper
  (`hr.payslip._themed_payslip_render`) reading line totals + the F9 scheme; `om_hr_payroll.report_payslip`
  and the portal binding stay put (binding swap is a separate product decision).
- **Live-validation gotchas (cost me real time — read before Chrome-MCP'ing an edit UI):**
  - **can_edit gates every edit affordance.** The default studio session user in pb_demo is `ash@ashsohani.com`
    (uid 20) — NOT a formula manager/system admin, so `_can_edit()` is False and the grid paste handler, the
    Theme panel button, Add/Delete, drag-fill, etc. are ALL hidden/short-circuited. Validate editor UIs as
    **`ash@biztinct.com` / `admin1234` (Mitchell Admin, uid 2, system)** — authenticate via a
    `/web/session/authenticate` fetch, then reload. (`get_session_info` tells you who you are.)
  - **OWL `t-on-paste` IS drivable headlessly — build the event correctly.** (The original WP-L claim
    that it needs a trusted event was WRONG; the reviewer drove the whole ghost flow in Chrome MCP.)
    `new ClipboardEvent('paste', {clipboardData: new DataTransfer(), bubbles: true})` with
    `ev.clipboardData.setData('text/plain', tsv)` dispatched on the grid scroller invokes the OWL handler
    end-to-end (ghosts, invalid states, Escape, Enter commit). What does NOT work is CDP
    `press_key("Meta+v")` (no clipboard pipeline on a non-editable `<div>`) or a ClipboardEvent without a
    real `DataTransfer`. Never mark a UI path "unvalidatable" without trying the synthetic-event route
    first — a false "can't drive" claim skips real validation for every future session.
  - Prod Odoo strips `__owl__` off DOM nodes — you can't read a component's props/state from the page;
    verify wiring by grepping the loaded `web.assets_web.min.js` (via `fetch`) and by calling the RPCs.
- **Review lessons (WP-L, 2026-07-21):**
  - **Never re-derive money the slip already states.** The themed print originally summed visible section
    subtotals for "Net pay" — double-counting GROSS/NET and adding employer contributions (printed 42.2M
    vs the real 12.1M on an employee-facing PDF). The slip's own NET line (code, then category `NET`) is
    the only trustworthy figure; with neither, HIDE the card — never print a derived number. Any rendered
    money must be traced to a stored line, and "the PDF renders" is NOT validation — check the figures.
  - **Round-trip fidelity includes VALUES, not just formulas.** The multisheet importer used to drop
    uniform value columns to `input`/default 0 — a re-imported config recomputed 28/53 letters wrong while
    every formula matched. Uniform columns now seed `default_value` (varying columns stay 0: seeding a
    first-row value would silently pay it to employees missing the input). When an AC says "recompute
    identically", verify on a config whose samples actually EXERCISE the constant-driven branches.
    Trap inside the trap: the W41 two-header layout puts the CODE row where the importer sees the first
    data row, so a constant column reads `['DAYSTD', 26, 26, …]` — `_column_uniform_value` tolerates
    exactly ONE leading non-numeric cell and the seed is the detected `uniform_value`, NEVER
    `sample_value` (which IS that code string). The first fix attempt seeded from sample_value and
    silently seeded nothing; only re-driving the exact wizard round-trip caught it (53/53 parity after).
  - **`if_chain.detect` recognizes BOTH canonical forms:** the hand-written progressive `v*rate − ded`
    ascending-`<=` chain AND the marginal `base + rate*(v−lower)` descending-`>=` form that
    `compile_brackets_excel` itself emits (`form: 'progressive'|'marginal'`). Without the second, a W41
    export (BRACKET expanded) could never re-earn its rate-table offer on re-import. The WP-J M1 zero-guard
    conservatism applies to the PROGRESSIVE fold only — a marginal chain with a non-zero first lower is
    exact by construction (battery cases 15-18).

## C18 — Sudima field-HR program (Phases A–E: driver GPS, OT grid, trips, bank OCR, young workers)

Binding for every `docs/handovers/SUDIMA_PHASE_*.md` implementation session. Sub-points are cited by
number from the handovers — keep the numbering stable.

1. **Engine/overlay split.** Reusable engines are `biz_*` modules with ZERO Payobook deps (no
   `pb_sidebar`, no `--pbim-*` scss imports, no Vietnam fields) — `biz_geo_tracking`, `biz_week_grid`,
   `biz_approval_chain`, `biz_doc_ocr`. All cockpit UI, sidebar items, theme tints, VN/payroll
   bindings live in the consuming `pb_*` overlay (same convention as [[biz-theme-base]] → pb_theme).
   Widgets in `biz_*` style themselves through their own CSS custom props (`--bwg-*`, `--bac-*`,
   `--bdo-*`) with defaults; overlays override.
2. **Formula-input override convention + code registry.** New payroll inputs do NOT ride the
   `WD_`/`HOURS_` worked-days branch (`hr_payslip_formula.py:305-306` strips only underscored
   prefixes — an underscore-free code never matches it). Instead: `_inherit` `hr.payslip` in a GLUE
   module (`pb_workforce_payroll_bridge`, `pb_trip_payroll_bridge`), override
   `_get_formula_input_values`, call super, inject ONLY codes present in the config's input rules.
   Codes must be underscore-free + pairwise non-substring (see [[formula-converter-contract]]).
   **Registry (check before adding any new code):** `OTHRS150 OTHRS200 OTHRS300 OTHRSNGT`
   (approved hr.overtime.request hours by type) · `TRIPDAYS PERDIEM` (approved pb.business.trip).
   Each bridge ships a post_init collision warning against existing `hr.formula.rule` codes.
3. **One OT source per formula config.** The legacy Zoho path (`om_hr_payroll/hr_payslip.py:483-491`)
   emits OT worked-day lines (`OT15/OT2/OT3/…`); the bridge feeds `OTHRS*` from approved OT requests.
   A config may consume ONE of these, never both — double-count is silent money.
4. **Trip presence is a virtual overlay, never materialized `hr.attendance`.** Trip days are injected
   at read time (timecard/grid/dashboard overrides via `pb.business.trip.get_trip_day_map`) and
   excluded from missing-punch logic by the same helper. Materialized rows would double-count payroll
   worked days (WORK100), pollute GPS/attendance analytics, and need cancellation cleanup.
5. **Realtime = polling, not bus.bus.** No Payobook module uses the bus; live surfaces poll
   (driver map 5 s, other cockpits 30 s) with `{silent:true}` orm context and `clearInterval` on
   unmount. Do not introduce websocket/bus dependencies for these features (deployment risk on
   client boxes).
6. **Provider-vision contract.** `BaseAIProvider.generate_vision(prompt, images, …)` +
   `supports_vision()` (default False); `images = [{'mime', 'data_b64'}]`; providers registered in
   `PROVIDER_REGISTRY` (`provider_factory.py`). All provider SDK imports are try/except-guarded —
   a missing pip package must degrade to `is_available() == False`, never an ImportError at registry
   load. `payroll.ai.config` is the ONLY AI config model (extended via selection_add + `purpose`);
   consumers resolve by purpose with fallback. Every AI consumer ships a deterministic no-AI path (C1).
7. **Demo tooling is quarantined.** Simulated data is always flagged at the row level
   (`biz.geo.ping.source='sim'`), excluded from real analytics/payroll by default, labeled SIMULATED
   in any UI that shows it, and activated only by admin-gated toggles on records shipped
   `active=False`. The simulator must exercise the REAL pipeline (same endpoints/models) — a demo
   that bypasses the product path validates nothing.

### Phase-A findings (driver GPS PWA — 2026-07-22, WP-Sudima-A). Numbering continues C18.

8. **Odoo 19 `res.groups` has NO `category_id` field** (replaced by `privilege_id` → `res.groups.privilege`).
   A `<field name="category_id">` on a `res.groups` record aborts the registry load with
   `ValueError: Invalid field 'category_id' in 'res.groups'`. Ship groups without it (a plain technical
   group is fine) or set `privilege_id`. This is the concrete form of C9's "res.groups.category_id changes".
9. **`ir.actions.client` has NO group field in Odoo 19** — neither `groups_id` nor `group_ids` exists on
   the client-action model (only `ir.act.window`/`ir.act.server` carry `group_ids`). You cannot gate a
   client action by group on the action record. Enforce access in the RPC facade instead (a `_require_*`
   guard on the AbstractModel's public methods that raises `AccessError`), and hide the launcher via the
   sidebar item's own `groups_id`. A driver hitting `/odoo/action-<tag>` then gets the themed access-error
   dialog on data load.
10. **A standalone page CANNOT load an Odoo asset bundle via `t-call-assets`.** Odoo wraps every compiled
    bundle in module-loader boilerplate that references the `odoo` global; a bare page that doesn't boot
    the webclient dies with `Uncaught ReferenceError: odoo is not defined`, and the whole bundle (Leaflet
    included) fails to execute. For a no-webclient PWA, serve the plain library + a plain-IIFE app as
    direct static tags: `<link href="/module/static/.../x.css?v=N">` + `<script src="/module/static/.../x.js?v=N">`.
    Odoo serves anything under `/{module}/static/` publicly; bump the `?v=` query on change (there is no
    bundle hash to bust). Never mark such a page "can't be built" — the static-tag route is the pattern.
11. **Company-scoped OWL cockpits see the web client's SELECTED companies, not all allowed.** An
    `orm.call` carries `allowed_company_ids` from the company switcher (`cids` cookie), so a cockpit that
    scopes to `self.env.companies` shows nothing for records in a company the user hasn't selected — even
    though a context-free `call_kw` (which defaults differently) returns them. Seed demo records into the
    demo's OPERATING company, not the install-time default (records created by data XML with no
    `company_id` land in "Your Company"/id 1, which the VN demo user never views). Resolve it with no
    hard-coded id via a `post_init_hook` that assigns the seed records to the company with the most
    employees (the real operating company; the pb_demo world runs in **Payobook Vietnam JSC**). Existing
    records on an already-installed module need a one-off RPC/data migration — a plain `-u` with
    `noupdate="1"` will not move them.
12. **`_attendance_action_change(geo_information)` maps dict keys straight onto `in_<key>`/`out_<key>`.**
    Passing `{'latitude':…, 'longitude':…, 'mode':'gps'}` writes `in_mode='gps'` on check-in and
    `out_mode='gps'` on check-out with no post-hoc write — the ⚠ in the Phase-A handover §2 resolves to
    "mode is a first-class key". The base field's `default='manual'` makes `selection_add=[('gps','GPS')]`
    with `ondelete={'gps':'set default'}` valid (C9: `'set default'` only asserts when the base has no default).
13. **Records shipped `active=False` are invisible to a plain `search`** (the ORM auto-injects
    `active=True`); pass `context={'active_test': False}` to find them. The product path is unaffected when
    it resolves the record by xmlid (`env.ref`) rather than searching — which is why `toggle_demo` finds the
    inactive seed route sims but a test harness `search([...])` must set `active_test=False`. Also: Odoo's
    `ir.attachment` image post-processing (Pillow) rejects a hand-crafted 1×1 PNG with
    `OSError: Truncated File Read` — generate a real ≥2×2 PNG for any attachment-create test.
14. **NEVER ship a `<field name="password">` on a `res.users` record in a manifest `data` file** (Phase-A
    review Major). Seed users that must resolve by xmlid (demo drivers for `toggle_demo`/route sims) ride
    `data`, so a literal password becomes a live internal-user credential on EVERY production install —
    documented in the repo, guessable, and grants a backend RPC session, not just the PWA. Ship such users
    with NO password field (login stays impossible until an admin sets one at demo time, and clears it
    after). If a record does not need xmlid resolution from product code, put it under the manifest `demo`
    key instead. Related data-quality rule from the same review: never default missing GPS to `0,0` —
    build the `geo_information` dict with only the keys you actually have (`{'mode': 'gps'}` alone is a
    valid punch); a null-island coordinate is worse than no coordinate.

### Phase-B findings (OT weekly-entry grid — 2026-07-22, WP-Sudima-B). Numbering continues C18.

15. **Odoo 19 `hr.attendance.worked_hours` SUBTRACTS the calendar lunch interval** (unless the resource
    `_is_flexible()`) — `_get_worked_hours_in_range` does `Intervals([(ci,co)]) - lunch_intervals`. So
    writing `check_out = check_in + hours` stores a `worked_hours` LESS than the entered figure whenever
    the span crosses the schedule's lunch window (enter 8 → `worked_hours` 7). Any grid that treats the
    entered number as the net figure must READ BACK the wall-clock span (`check_out − check_in`), NOT
    `worked_hours`, or the round-trip is lossy and looks like data loss. The Weekly Entry grid displays the
    span (`_att_hours`) and its "no lunch arithmetic" write rule (§3.2) is exactly this convention.
16. **A parent cockpit that mutates its OWN reactive state inside a child's adapter `fetch()` remounts the
    child in an infinite fetch loop.** Pattern: an adapter-driven OWL child fetches in `onWillStart`; the
    adapter closure sets the PARENT `useState` (ceilings/summary). Parent re-render → child RECREATED (not
    patched) → onWillStart → fetch → parent state → … a fetch storm that renders the action BLANK with NO
    console error (invisible to `-u`; only a pile of repeated notifications hints at it). Fixes, all three:
    (a) the parent pre-fetches in its own `onWillStart` and serves the child a cached bootstrap on the first
    `fetch`; (b) pass STABLE prop references — bind handlers once in setup, a stable `params` object — and an
    explicit `t-key` so OWL reuses the child; (c) guard any live-delta state write behind a change check so
    the empty mount-time `onDirty([])` emit doesn't setState. ALWAYS Chrome-MCP an adapter-driven cockpit.
17. **Concurrency/stale tokens must be MICROSECOND-precise.** A per-cell snapshot token from
    `fields.Datetime.to_string(write_date)` is SECOND precision (the C14 trap in another guise), so a
    fetch+edit inside the same wall-clock second slips past stale detection. Use `str(write_date)` (keeps
    microseconds) for the token compared on save (`_att_token`). AND the comparison must be
    unconditional: `if token and token != current` lets an EMPTY token (cell had no record at fetch) or an
    omitted key bypass the check entirely — a record created concurrently then gets silently mutated
    (Phase-B review F5). Compare `(token or '') != current` so "no record at fetch, record exists now" is
    stale too.
    **Companion rail (review F1/F2): every RPC facade must keep its reads and writes in ONE permission
    world.** The weekentry cockpit wrote via `sudo()` (gated by `_require_officer` + company scope) while
    reading WITHOUT sudo — but the officer record rule on `hr.overtime.request` is own-records-only, so a
    plain officer saw blank editable chips over other people's locked requests, zeroed ceilings, and
    `submit_week` couldn't find the drafts its own sudo path created. Same trap in the payroll bridge: a
    non-sudo `hr.overtime.request` search inside `_get_formula_input_values` silently computed **0 OT
    hours** for every other employee when a non-manager ran payroll (money path). If the facade gate is
    the auth model, sudo BOTH sides; never mix.
18. **Company-scoped OWL cockpits render EVERY selected company** (the read side of C18.11). The grid shows
    company-1 "Your Company" demo employees (Abigail Peterson &c., English names sorting first under
    `order='name'`) alongside VN whenever the browser's `cids` cookie has more than the VN company selected.
    Verification RPCs must use the SAME company scope the cockpit used, or saved records "vanish" (a save to
    a company-1 employee is invisible to an `allowed_company_ids=[5]` search). Seed/validate against the VN
    operating company, and the demo employees carry a single `Europe/Brussels` resource calendar (no VN tz
    anywhere), so synthesized punches land at Brussels-local 08:00 — a demo-data limitation, not a code bug.

### Phase-C findings (business trips + virtual attendance — 2026-07-22, WP-Sudima-C). Numbering continues C18.

19. **Trip presence is ONE virtual overlay helper, read sudo.** `pb.business.trip._get_trip_day_map`
    (`pb_business_trip/models/pb_business_trip.py`) is the single source every presence surface reads —
    the Timecards Gantt inherit, the Weekly-Entry grid inherit (row `flags.trip_days` + REG lock +
    server-side `'trip'` refusal in `_save_reg`), the Workforce dashboard KPI, and the payroll bridge.
    It searches `state='approved'` trips **sudo** (trip presence is system-derived and must be visible to
    whoever is looking — the C18.17 one-permission-world rail). Never materialize `hr.attendance` rows for
    trip days (C18.4): a day the traveller ALSO punched keeps its real bars + a `is_trip` tag; an empty
    trip day gets a full-width violet (`#7c3aed`) bar injected at read time.
20. **A "company-specific else global" resolver must do TWO searches, never `order='company_id desc'`.**
    Postgres sorts NULLs **FIRST** on `DESC`, so a single ordered `search([... '|' company=X, company=False],
    order='company_id desc', limit=1)` returns the GLOBAL (`company_id` NULL) fallback row AHEAD of the
    company-specific one — every company silently gets the fallback caps. `pb.ot.ceiling._for_company` had
    this latent bug (masked in the demo, which ships only a global ceiling, and by a Phase-B test whose
    global cap happened to equal the company cap); the F8 per-company ceiling test exposed it. Fix: search
    `company_id = X` first, then `company_id = False`. Applies to any per-diem-policy / ceiling / rate
    fallback resolver.
21. **Odoo 19 search-view group-by container must be `<group name="group_by">`** — NOT `<group expand="0"
    string="Group By">`. The `expand`/`string` combo fails RNG validation with a *generic*
    `ValidationError: Invalid view <name> definition` (no field/attribute named, '-no context-'), which
    aborts the whole module install. Match the existing working pattern (`overtime_request_views.xml`).
    Surfaces only at load, and even `--log-handler odoo.tools.convert:DEBUG` gives only the generic message
    — diff against a known-good search view rather than hunting the RNG detail.
22. **`hr.leave.type.requires_allocation` is a Boolean in Odoo 19** (default `True`), not a Selection —
    pass `False` to create a leave with no allocation; a truthy string like `'no'` is `True` and
    `hr.leave.create` raises `ValidationError: You do not have any allocation for this time off type`
    (via `_check_validity`, through the `hr_work_entry_holidays` / `hr_holidays_attendance` create stack).
23. **Deploy: a `-u` dies with `LockNotAvailable: … updating tuple … in ir_ui_view`** when a stale detached
    `odoo-bin` worker still holds the `access_roles._update_role_groups_view` row (the C2 role-groups view
    rebuild). `service odoo-server stop` + a 2 s sleep is NOT enough — leftover worker PIDs survive. Before
    any `-u`: stop the service, `pgrep -af odoo-bin`, and `sudo kill <PID>` each leftover BY PID (never
    `pkill -f odoo-bin` — it self-matches), confirm zero, THEN run. `--stop-after-init` test runs cause
    `EXIT=255` (registry init failure) on this lock, distinct from `EXIT=1` (a genuine test failure).
24. **A state machine is decorative unless `write()` enforces it — and client context is FORGEABLE.**
    (Phase-C review C1/C2.) Server-side `_approval_can` gates mean nothing while any ACL+rule-writable user
    can `call_kw write({'state': 'approved'})` and skip every tier (the payroll bridge pays on `state`
    alone). `biz.approval.chain.mixin` now blocks `state` in `create`/`write` unless the context carries a
    **module-level Python `object()` sentinel** set only by `_chain_state_write()` (used by
    `_advance_state`, `action_refuse_chain`, and consumer reset/cancel actions); su/admin exempt. NEVER gate
    a rail on a plain boolean context key — `call_kw` merges the CLIENT-supplied context, so
    `{'trip_bypass_lock': 1}` from a browser would have unlocked an authorized trip (that escape is now
    su-only). Corollaries: lock child LINES too, not just the header (rail-2 "dates/rate/lines"); a no-sudo
    audit log still needs `create()` to force `user_id`/`stamp` server-side or any user can forge a trail
    row in someone else's name; a sudo `@api.model` helper is a call_kw endpoint — underscore-prefix it
    (`_get_trip_day_map`) unless it is deliberately public and gated.
25. **`ir.attachment` orphans are creator-only readable — sudo cross-user copies.** An employee-uploaded
    receipt bound via a plain `Many2one('ir.attachment')` has no `res_model`, so an HR approver's
    `attachment.copy()` in the authorization hook raises AccessError mid-transition (works in tests, which
    create receipt and approve as the same superuser env). `pb_trip_expense_bridge` sudo's the copy and the
    line-link writes (the line is rail-2-locked by then).

### Phase-D findings (AI bank-account validation — 2026-07-22, WP-Sudima-D). Numbering continues C18.

26. **`res.users.employee_id` is COMPANY-DEPENDENT — a cockpit that defaults to it fails cross-company.**
    `self.env.user.employee_id` resolves through the user's *active* company (the `cids`/`allowed_company_ids`
    context), so a create that defaults `employee_id = self.env.user.employee_id.id` returns `False` — and
    raises "No employee is linked to your user." — whenever the browser is in a company where the user has no
    employee (Mitchell Admin's employee lives in "Your Company"/1; the web client opened company 2). Same
    root as C18.11. Pass `allowed_company_ids` explicitly, or resolve the employee with `active_test`/company
    context, before relying on `env.user.employee_id`.
27. **An own-only CREATE record rule blocks create-on-behalf; reviewer groups need their own create grant.**
    `pb.bank.change.request`'s employee rule is `perm_create` with `employee_id.user_id = user.id`, and the
    HR/finance reviewer rules ship `perm_create=False` (least privilege). Net effect: the request must be
    created by the EMPLOYEE themself — HR cannot upload on an employee's behalf, and even a payroll-manager
    (who holds the ACL create) is blocked by the row rule for another employee's record. This is the intended
    self-serve flow (handover §3.3), but any "HR uploads for the worker" variant needs an explicit
    create rule keyed to the reviewer groups.
28. **Deterministic bank-name matching must be token-SUBSET, not substring.** A real VN document reads
    "NGAN HANG TMCP NGOAI THUONG VIET NAM"; the registry alias "Ngan hang Ngoai thuong" is NOT a contiguous
    substring (the interposed "TMCP" breaks it), so a `folded_alias in folded_target` test returns no match.
    `pb.bank.registry.match` folds + splits into word tokens and matches when ALL alias tokens are present in
    the target set (most-letters-matched wins) — order-independent and robust to interposed legal-form words.
    Whitespace tokenization keeps "SAIGON" distinct from "SAI GON" so short aliases don't over-match.
29. **`payroll.ai.config` resolver name collision.** The handover asked for an `@api.model get_provider(purpose)`
    returning a *config*, but the module already has an instance `get_provider()` returning a *provider*. Adding
    the classmethod would shadow the existing insights call path. Named the resolver `get_config_for_purpose`
    instead (insights byte-untouched). Rule: never overload an existing provider-layer method name with a
    different return type; pick a distinct name and note the deviation.
30. **`pytesseract` (pip) ≠ the `tesseract` binary (apt).** `is_available()` must probe the binary
    (`get_tesseract_version()` in a try/except), not just the import — the pip package installs cleanly while
    `tesseract` is absent from PATH, and only the binary probe distinguishes "provider ready" from
    "keyless-but-unusable" on the settings card (C18.6 guarded-import doctrine, extended to the runtime).
    Provider PDF handling: Anthropic reads PDFs natively (`accepts_pdf()==True`); OpenAI / Ollama / Tesseract
    gate PDFs on `accepts_pdf()==False` and return a clear "upload an image" message rather than half-working.

### Phase-D review findings (2026-07-23, Fable review of WP-Sudima-D). Numbering continues C18.

31. **The approver approves what the FIELDS show — every system-derived verification field needs the C18.24
    sentinel, not just `state`.** `readonly=True` on an Odoo field does NOT block `call_kw write`; with an
    own-record `perm_write` rule, a requester could forge `name_match_score/band`, `v_format_ok`, the `cur_*`
    diff snapshot, `confidence_json`, clear `duplicate_ids`, self-tick `duplicate_ack` — and swap
    `x_account_number` between HR review and finance approval (TOCTOU), redirecting the master write to a
    fraudulent account. Rails (pb.bank.change.request): `_SYS_FIELDS` writable only via a module-level
    `object()` token (`_sys_write`); `_REVIEW_FIELDS` (x_*, attachment, employee) frozen to the owner once
    out of draft, immutable for all once decided; `duplicate_ack` = HR/finance testimony only; and the
    approve transition RE-RUNS `action_validate()` against the final values plus the hard gates, so a stale
    green gauge can never authorize the write. Corollary: the audit-skip context (`from_bank_request`) is
    also an `object()` sentinel — a client-forged truthy flag still logs the 'manual' history row.
32. **A generic service that sudo-reads attachments (or any record) and RETURNS their content must be
    underscore-private.** `biz.doc.ocr.extract` as a public `@api.model` method was an
    arbitrary-attachment-exfiltration endpoint over call_kw (pass any attachment id → get its OCR text back);
    renamed `_extract` (Python-only; consumers gate access on their own record first — same class as
    Phase C's `_get_trip_day_map`). And the JOB rows that persist extraction results are PII: they need an
    own-only (`create_uid`) record rule, or any employee `search_read`s every colleague's extracted bank
    account — proven live with a leftover test job. Test residue rule: an end-to-end test on the live DB must
    clean up EVERY row it created, including engine-side job/log rows, not just the domain records.

### Phase-E findings (young worker rules — 2026-07-23, WP-Sudima-E). Numbering continues C18.

33. **An advisory wrapper around `pb.payrun.wizard` must be MRO-OUTER of `pb_demo`.** `pb_demo` REPLACES
    `create_and_compute`/`compute_batch` for its division path and does NOT call `super()`, so a wrapper that
    only `super()`-appends to `exceptions` runs only if it sits before `pb_demo` in the MRO. It does: `pb_young_worker`
    (via the deep `pb_hr_workforce` chain) loads AFTER `pb_demo`, so its class is the more-derived override — a
    test asserts `type(env['pb.payrun.wizard']).mro()` places the young-worker class before the pb_demo class, and
    the demo path's warnings surface. **No `pb_demo` dependency was needed** (keeping the guard demo-agnostic); if a
    future refactor changes module depths and the MRO test fails, add `pb_demo` to `depends` to force the order.
34. **App-wide `@api.constrains` gates need a `_has_any_rule()` short-circuit + sudo birthday reads.** The under-18
    OT/daily/night gates constrain `hr.overtime.request`/`hr.attendance`/`hr.shift.planning`, which fire on EVERY
    write system-wide; guard the hot path with a cheap `search_count` so the general population pays ~one query,
    and resolve the band per (employee, local-day). `birthday` IS a real readable column on `hr.employee` in
    Odoo 19, but it's `hr.group_hr_user`-scoped — the engine reads it via `.sudo()` (never guess an age). Corollary
    surfaced in test: the base grid's `get_ot_ceilings` reads `e.company_id`, which triggers hr's `_check_private_fields`
    and raises AccessError for a plain attendance officer on a VN employee (many private `vietnam_*` fields) — grid
    users need `hr.group_hr_user`, not just the attendance-officer group.
35. **Seed country defaults via `post_init_hook` per-company, not static XML — the demo company is not
    base.main_company.** The live demo runs under 'Payobook Vietnam JSC' (a non-main company), so a data-XML rule
    on `base.main_company` would leave the demo employees ungated. The hook seeds an editable VN rule for every
    company lacking one (caps stay data — a module constant — and remain deactivatable per company). Test isolation:
    that seeded rule collides with a test's own rule, so `setUpClass` must deactivate pre-existing rules first (same
    class as the bank test's `payroll.ai.config` isolation).
36. **`check_period` bounds violations to ≤ `date_to`; the week gauge sums the full ISO week.** A future-dated
    over-cap day shows on the cockpit's week-hours gauge (`check_week_hours`, whole Mon–Sun) but NOT in the 30-day
    violation feed (`check_period`, clipped to `[from, to]`) — correct (a past-window feed must not count future
    days). When validating the feed live, seed a fully-PAST complete week, or the gauge lights up while the feed
    stays empty.

### Phase-E review findings (2026-07-23, Fable review of WP-Sudima-E). Numbering continues C18.

37. **Overlays sharing a payload dict must MERGE, never REPLACE.** Two independent `get_week_entries` overlays
    (trip badges, young-worker locks) both populate the per-row `flags` dict; the MRO-outer one ran last and did
    `row['flags'] = {...}`, wiping the trip overlay's keys for a minor on a business trip. Rule: any inherit that
    contributes to a shared payload key uses `row.setdefault('flags', {}).update(...)` — assume you are not alone
    in the chain. Same doctrine as override-and-super for formula inputs (C18 code registry).
38. **"Report, don't retro-enforce" means corrective REDUCTIONS must always pass.** The grid week-cap check gated
    every non-zero REG write, so an over-cap week seeded before the rule existed could not be walked down (10→8
    still failed the cap). Gate only a POSITIVE delta (`new > current`); a reduction commits even when the week
    stays over cap. Applies to any cap-style guard over historical data.
39. **Config seeded per-company at install needs a `res.company` create hook too** — otherwise a company created
    after install has no rule, no gates, and nothing hints at the gap (the rule lookup is deliberately
    company-only, no global fallback). Pair every per-company `post_init_hook` seed with a `res.company.create`
    override calling the same idempotent `_seed_*` helper, and make its has-one check `active_test=False` so a
    manager's deliberate deactivation survives a reinstall.
40. **Retention vacuums key on `write_date` (terminal date), not `create_date`** — a job created 31 days ago but
    decided yesterday must not be purged on day one. And on live: NEVER run `--test-tags` without a scoping `-u` —
    a bare test run imports the test packages of EVERY installed module, and legacy `om_hr_payroll`'s own tests
    import a misspelled `odoo.addons.om_om_hr_payroll`, crashing the whole DB init (EXIT=255,
    "Failed to initialize database"). The `-u`-scoped form only imports the updated modules' tests.

### F4 ops closure (2026-07-23, access_roles registry-reload storm — root causes). Numbering continues C18.

41. **Generated-view writers must compare NORMALIZED, and store-what-you-search.** The F4 storm was two bugs
    compounding in `access_roles`: (a) `_update_role_groups_view` compared `etree.tostring(...)` (which appends a
    trailing newline) against the stored arch (which loses it on read-back) — a guaranteed-true `!=` meant a 1-byte
    view rewrite on EVERY registry load, whose `['templates']` signal reloaded every other process, forever;
    (b) the filter/groupby registries searched rows by technical name but stored the display name — labelled
    filters were re-created on every sync (live reached 1.49M junk rows / 210 MB, and searching those tables was
    ~215s of every 217s load). Fixes: `.strip()` both sides + log a real-change diff; search by the stored value;
    gate all view-scan `_register_hook`s behind an ir_ui_view signature (`access.registry.sync`). Live result:
    registry load 217s → 1.9s steady (4.1s with full resync), no self-signaling, stable single process. Lesson for
    any module: a `_register_hook` that WRITES must be provably idempotent byte-for-byte, or it becomes a
    self-sustaining reload storm; and a create-or-update helper must search by exactly what it stores.

### Sudima F–J program rules (2026-07-24 design phase). Numbering continues C18.

42. **F–J cross-phase rails** (full detail in each `docs/handovers/SUDIMA_PHASE_[F-J]_*.md`): (a) **WOW-or-upgrade**
    — every touched surface is bespoke design-system UI, and any LEGACY screen a phase builds on (stock export
    wizard form, stock /my portal pages, native lists on menus) is redesigned as part of that phase; native views
    survive only off-menu as admin fallbacks (admin CONFIG forms exempt). (b) **Bank-file layouts are DATA**
    (`pb.bank.file.layout` column vocabulary) — a new bank is a data file; generation validates via `account_ok`
    and NEVER silently drops a row. (c) **PDF passwords are resolved in memory per employee and never logged or
    stored.** (d) **MSS never writes state** — the My-Team facade calls each model's own gated actions as the real
    user (C18.17/24). (e) **ESS never writes the employee master** — profile edits ride a sentinel-guarded change
    request (bank-request clone, C18.31). (f) **The audit console is read-only** — it surfaces existing logs
    (biz_audit_trail engine from Phase H), masked PII, capped-and-surfaced exports. Order F→G→H→I→J; I needs H;
    J needs H; F and G independent.

### Phase-F findings (Pay & Deliver — 2026-07-24, WP-Sudima-F). Numbering continues C18.

43. **`hr.payslip.run` has NO `company_id` field in this om_hr_payroll (Odoo 19).** A `create({'company_id': …})`
    or a `run.company_id` read raises `ValueError: Invalid field 'company_id' in 'hr.payslip.run'` (it aborts the
    whole test DB init → EXIT=255, distinct from an EXIT=1 assertion failure). Scope company via `self.env.company`,
    never off the run. The run DOES carry `date_start`/`date_end`/`state`/`name`/`slip_ids` (the pb_payruns board
    proves those). Verify a run field against the actual model before use — several sibling models (payslip,
    delivery batch) DO have `company_id`, so it's an easy false assumption.
44. **A test-fixture attribute named `run` (or any `unittest.TestCase` method name) shadows the runner and dies
    cryptically.** `cls.run = <recordset>` in `setUpClass` overrides `TestCase.run(self, result)`, so the loader
    calls the *recordset* → `TypeError: 'hr.payslip.run' object is not callable`, reported as `Failed to initialize
    database` (EXIT=255) with a traceback pointing at `return self.run(*args, **kwds)` — NOT at your test. Never name
    a fixture `run`/`id`/`subTest`/`skipTest`/`assert*`; use `payrun`, `rec`, etc. Cost real cycles here.
45. **wkhtmltopdf can't render report assets during a `--stop-after-init` test run** — there is no HTTP server for
    it to fetch the report CSS/layout from, so `_render_qweb_pdf` returns broken bytes and PyPDF2 chokes with
    `EOF marker not found` (the PDF has no `%%EOF`). This is NOT a code bug; the render works with the service up.
    Any headless test that needs real PDF bytes must **mock the render** (a valid PDF via `PdfWriter.add_blank_page`
    → `write`) and exercise the downstream logic (encrypt / attach / queue), then validate the real wkhtmltopdf
    render live (Chrome-MCP, service up). wkhtmltopdf on Payobook19v2 is 0.12.6 (unpatched-qt) and renders fine live.
46. **Live `pb_hr_payroll_formula` on Payobook19v2 is FAR behind the repo** — installed `19.0.1.0.0` vs repo
    `19.0.1.48.0`; the entire Formula-Engine WP-* body (incl. `hr.payslip._themed_payslip_render`, the connector
    `_sync_mapping_ids`, F9 theme fields) is NOT deployed there, even though the themed-report *XML template* is
    (a data-only artifact that loads without its Python). So `action_report_payslip_themed` is **currently broken on
    live** (`AttributeError: 'hr.payslip' object has no attribute '_themed_payslip_render'`). Any Phase-F–J feature
    that reuses a formula-engine surface must **degrade gracefully**: `pb_pay_delivery._report_ref()` prefers the
    themed report only when `hasattr(env['hr.payslip'], '_themed_payslip_render')`, else falls back to
    `om_hr_payroll.action_report_payslip` (the always-present legacy report). Deploying 48 versions of
    `pb_hr_payroll_formula` to production is a **separate, owner-signed-off decision** — do NOT slip it into a
    feature phase. `-u pb_hr_payroll_formula` is unblocked now (the `formulas` pip dep is installed, C-deploy),
    but the accumulated schema/data migrations make it a deliberate release, not a side effect.
    **RESOLVED 2026-07-24:** the engine was deployed to Payobook19v2 — `-u pb_hr_payroll_formula,
    pb_formula_studio,pb_sidebar,pb_pack_*` (1.0.0→1.48.0 / 1.65.0→1.68.0), the sole F111 migration
    (`19.0.1.19.0` freeze-letters, idempotent) ran, registry loaded in 26s, EXIT=0. Root cause of the
    live Formula-Engine crash was exactly this drift: `pb_formula_studio` (1.65.0) called
    `env['hr.formula.rule.note']` which the 1.0.0 engine did not register (an orphan `ir.model` row
    survived from a half-applied earlier upgrade, so it looked present but the class was absent →
    `KeyError` at `get_studio_data`). Post-deploy: model registered, `get_studio_data` clean, themed
    payslip report live (so `pb_pay_delivery` now auto-renders THEMED PDFs via its `hasattr` switch).
47. **Live has a REAL Gmail SMTP server** (`smtp.gmail.com:587`, "Payobook Outgoing Server") and ~179 mails sitting
    in `exception` state (dead — not dispatchable; the cron ignores them). A `send_payslips` with `force_send=False`
    only QUEUES, but the "Mail: Email Queue Manager" cron is ACTIVE and would then dispatch to real
    addresses — so demo/validation must NEVER trigger a live send against real employees. Validate the delivery
    lane's UI (recipient/skip/password cards) without dispatching; the send path is covered by server tests
    (mock-rendered PDF → mail.mail queue rows + skip + idempotence + encryption round-trip). Report SMTP posture
    on any server before any bulk-mail feature demo (handover safety-rail: no accidental demo emails).
48. **Clicking a live bulk-send is never a validation step** (Phase-F review, 2026-07-24). During Phase-F
    validation, "Send payslips" was clicked on a live 500-slip run; it was mail-safe only by luck (every demo
    employee lacked `work_email` → 500 `skipped_no_email`, 0 queued). Binding rule: exercise a live send lane
    ONLY on a run first VERIFIED email-free (`SELECT count(*) FROM hr_employee ... work_email IS NOT NULL` over
    its slips = 0), or with the mail queue cron paused for the demo window — and delete the residue batch
    afterwards (demo-pristine). The password fallback is hardened too: an underivable password (no account
    digits, no birthday, no employee code) now FAILS the slip with a surfaced reason — a static fallback
    password is never acceptable on an encrypted payslip.

### Phase-G findings (attendance workflow — 2026-07-24, WP-Sudima-G). Numbering continues C18.

49. **The exception feed CONSUMES `compliance_status`; it never re-derives the tolerance.** Phase G made the
    shift tolerance config-driven by OVERRIDING `hr.shift.planning._compute_compliance_status` (the base 15-min
    hardcode) to read `pb.attendance.rule._grace_for_company` — grace_in for late, grace_out for early, branch
    order byte-identical to the base so the default (15/15) is unchanged. The engine then reads the stored
    `compliance_status` ('absent'→missing_punch, 'late', 'early_leave') plus a punchless-day guard (a shift can
    read 'absent' while an UNLINKED punch exists — flag missing_punch ONLY when the day truly has no
    `hr.attendance`, never invent an absence). `missing_checkout` is computed from OPEN punches older than the
    config threshold (not a shift concept). Verified live: 4 seeded shifts computed absent/late(25m)/early(45m)
    correctly and the cockpit classified all four kinds. Config resolver is company-else-GLOBAL via TWO searches
    (C18.20) — a `company_id=False` seed row ships as data (visible to every company, so no per-company
    post_init seed needed, unlike C18.35's company-only case).
50. **The single guarded writer applies as SUDO; the sentinel is belt-and-braces.** `hr.attendance.correction`
    rides `biz.approval.chain.mixin`; on approve, ONE writer `_apply()` creates/adjusts/deletes the punch. The
    approval DECISION (state + `biz.approval.step.log`) runs as the real clicking user (truthful log,
    `_approval_can` auth — a plain line-manager passes via `employee_id.parent_id.user_id`, the trip precedent),
    but the hr.attendance MUTATION is `.sudo()` — a line-manager who may approve a report's correction has no
    direct attendance write right. The module-level `object()` sentinel context still travels with it (opens the
    device-delete guard for corrections), and su already opens that guard; the young-worker `@api.constrains`
    fires under sudo too, so a cap-breaching correction still raises inside `_apply` and is CAUGHT by
    `action_approve` (savepoint) → the request lands in `refused` with `apply_error` set, never a traceback
    (test 7 live-equivalent). A device punch (blank `pb_entry_source`) is deletable ONLY through this path.
51. **Completeness is enforced at SUBMIT, integrity at create.** A cockpit composer files a DRAFT first, then
    the user picks the target punch / types the times. So the `@api.constrains` must hold only ALWAYS-VALID
    integrity (target punch belongs to the employee+day; check_out ≥ check_in) — putting "create needs a
    check-in" or "adjust needs a target" in `@api.constrains` makes the very act of opening the composer raise.
    Move those completeness checks to a `_check_ready_to_submit()` called from `action_submit`. (Found live: the
    File-correction button silently no-op'd because create-without-times tripped the constraint.)
52. **A cockpit that FILES on behalf needs BOTH an ACL create grant AND a record-rule create grant for the
    approver tiers** — the sharper edge of C18.27. The own+reports base rule (perm_create) only lets the
    employee or their manager create; an officer/HR filing a correction for ANY employee from the exceptions
    queue is blocked by BOTH the model ACL (`perm_create=0`) and the approver record rule (`perm_create=False`).
    Grant `perm_create=1` on the officer/payroll ACL rows and `perm_create=True` on the approver `ir.rule`.
    Approver≠requester still holds — `_approval_can` refuses self-approval by the filer, admin excepted.
53. **A NEW asset FILE imported by a cockpit must be in the manifest `assets` list, or the whole component is
    dead** (the concrete C2 symptom, cost real live-debug time). The cockpit imports a sibling
    `pbaf_icons.js`; omitting it from `web.assets_backend` means the bundle DEFINES `@…/pb_attendance_flow` but
    NOT its dependency `@…/pbaf_icons`, so the loader reports "modules … have unmet dependencies", the action
    never registers, and `/action-<tag>` bounces to the home page with only a console error (invisible to
    `-u --stop-after-init`). Grep new cockpit imports against the manifest asset list. **And: a manifest
    asset-list change needs a full service RESTART, not `button_immediate_upgrade` / in-process `-u`** — the
    manifest is cached per-process, so an in-process upgrade re-runs data files but keeps the OLD asset list;
    only a fresh `odoo-bin` process re-reads it. (Always `service restart` after a manifest `assets` edit, then
    clear `/web/assets/%` and hard-reload.)
54. **`--stop-after-init` hangs on shutdown on Payobook19v2 (C18.23 in another guise) — never chain
    `service start` AFTER it in the same script.** The `-i/-u --test-enable --stop-after-init` run completes
    tests and prints "Initiating shutdown" but the process does not exit for many minutes (site stays DOWN if a
    trailing `service start` waits on it). Deploy pattern that works: run odoo-bin in the BACKGROUND, poll the
    log for completion, then `kill -9` the `odoo-bin.*stop-after-init` PID (never `pkill -f`) and `service
    start` — do not rely on the test process exiting on its own.

### Sudima K–M program rules (2026-07-24 design phase). Numbering continues C18.

55. **K–M cross-phase rails** (full detail in `docs/handovers/SUDIMA_PHASE_[K-M]_*.md`): (a) **K/M facades are
    read-and-act surfaces** — they never write a state field and never sudo a mutation; every change rides the
    target model's OWN gated action as the real clicking user (C18.17 made explicit for cockpit facades).
    (b) **Bonus Hours doctrine** (owner-directed, Phase K): OT beyond the `pb.ot.ceiling` period caps — daily /
    weekly / bi-weekly (ISO-odd-anchored week pairs) / monthly / annual, **tightest remaining allowance wins** —
    is SPLIT into `hr.overtime.request.bonus_hours`, never blocked for adults and never silently dropped;
    `bonus_hours` has exactly TWO writers (grid save + approve-time recompute) and is readonly everywhere else;
    minors keep the Phase-E hard block (bonus is NEVER a young-worker bypass); the allowance counter and the
    OTHRS* payroll inputs count only `approved_hours`, while the new **`BONHRS`** input carries the bonus stream —
    the formula-input code registry is now `OTHRS150/200/300/NGT, TRIPDAYS, PERDIEM, BONHRS`. The Bonus review
    surface is server-gated (payroll manager tier), filterable, and capped-and-surfaced on export.
    (c) **One limit source**: `hr.overtime.config.max_hours_per_day/month` are legacy per-type metadata — never
    enforced a second time beside `pb.ot.ceiling`.
    (d) **Design-time finding (Phase L's mandate)**: the payroll approval chain was gated by BUTTON VISIBILITY
    only — `pb.approval.approve_run` and the `action_payslip_run_level*_done` methods carry no group checks, and
    the cockpit's `submit_for_approval` called `level1_done` from draft (which writes `level2` unconditionally →
    the HR tier was skippable). Fix doctrine: model-side `_pb_require_tier` gates on every advance/cancel, chain
    entry only via `done_payslip_run`, and **state KEYS are frozen downstream contracts** (`done` is the approved
    signal for pay delivery/analytics — insert `level0`, rename nothing).
    (e) **M is read-only and CDN-free**: the analytics rebuild writes nothing, leaves the `payroll.analytics`
    JSON/state contract and its level2 auto-generation hook untouched, vendors every asset locally (no CDN,
    test-asserted), and existence-checks its G/K-fed tiles so phase ORDER can never crash a board.
    Order: K, L, M mutually independent; M soft-consumes K (bonus tile) and G (pulse row); H→I→J unchanged.

### Phase-H findings (Employee 360 — 2026-07-24, WP-Sudima-H). Numbering continues C18.

56. **hr.employee `department_id` / `job_title` are NON-STORED related fields backed by `hr.version`** in
    Odoo 19 (`related='version_id.department_id'` / `version_id.job_title`, `store=false` in
    `ir_model_fields`), so a field-change audit write-hook on hr.employee NEVER captures them — the write is
    redirected to the current version and the hr.employee override sees no old→new (proven live: after
    `emp.write({'department_id': x})` the employee reads the new value but zero hr.employee audit rows appear;
    parent_id / company_id / active ARE stored and audit fine). The write UPDATES the existing version in
    place (version_id unchanged, count stays 1 — NOT a new-version create), so the correct capture point is a
    `biz.audit.mixin` on **hr.version** watching `department_id, job_title`; the Employee 360 timeline maps
    those entries back onto the employee via `hr.version.employee_id`. Rule of thumb before auditing ANY
    hr.employee field: check `store` in ir_model_fields — a version/resource-related field must be audited on
    its backing model. (`wage` on hr.contract IS stored and audits directly — contracts ≠ versions here.)
57. **`biz.audit.mixin` on hr.employee/hr.version applies app-wide, so its rule lookup must be ormcached and
    the entry create must never block the write.** `biz.audit.rule._watched_fields(model)` is
    `@tools.ormcache('model_name')` (cleared via `self.env.registry.clear_cache()` on any rule create/write/
    unlink — the only reliable Odoo-19 invalidation); an unwatched model pays one cached dict lookup +
    empty-set intersection. Measured live: watched vs unwatched employee writes are indistinguishable
    (Δ ≈ 0, within RPC noise). The mixin wraps its logging in try/except and swallows failures (a broken
    audit must not break an HR write). Entries are append-only with FORCED actor/stamp — the mixin creates
    them via `.sudo()` (it fires for any user, who may lack create rights on the entry) and `create()` sets
    `user_id = env.uid` (sudo keeps the real uid) + pops any client stamp, so nothing client-supplied ever
    sets who or when; write()/unlink() raise for everyone but system and the retention GC (module-level
    `object()` sentinel). Same doctrine as the [[biz-approval-chain]] step log, hardened for a generic engine.
58. **A soft component registry keeps a cockpit extensible without a hard dep.** The Employee 360 drawer
    (pb_employee_vault) registers into `registry.category("pb_people_drawer")`; the People cockpit (pb_people)
    checks `.contains("employee_360")` and mounts it via a dynamic `t-component`, else falls back to the
    legacy full-page detail action — People stays fully installable WITHOUT the vault (same doctrine as the
    trip `registry.category("fields")` overlay widgets). PII rails on the vault: documents are own-read for
    employees / company-scoped for HR / manager-unlink (C18.32); `verified/verified_by/at` are HR testimony
    behind a `_VAULT_SYS_TOKEN` sentinel (C18.31 — even HR's direct `write({'verified':True})` raises; only
    the gated `action_verify()` sets it); the timeline RPC is HR-gated and wage VALUES are scrubbed from the
    payload server-side for non-payroll-managers (two-tier serialization, NOT CSS hiding). Attachment upload
    follows the C18.25 order (attachment first, bind res_model/res_id after the document exists).
59. **A demo-seed that writes a cross-company relation crashes a company-scoped cockpit read.** Seeding an
    employee's `department_id` from `hr.department.search([], limit=5)` grabbed a company-1 ("Your Company")
    department onto a company-5 (VN) employee; the 360 drawer's `orm.call` carries the web client's SELECTED
    company (`cids=5`), so reading that cross-company department raised AccessError and the drawer showed
    "Could not load" — while a context-free RPC succeeded (the C18.11 trap in a new guise). Demo/validation
    writes of a company-scoped relation MUST resolve the target within the record's OWN company
    (`search([('company_id','=',emp.company_id.id)])`), never a bare `search([])`.

### Phase-I findings (ESS/MSS — 2026-07-24, WP-Sudima-I). Numbering continues C18.

60. **`editable` is a RESERVED website render-context variable — never reuse it as a portal template
    key.** A `website=True` portal route rendering merges a website context that sets `editable` (the
    editor edit-mode boolean); a controller value passed as `values['editable'] = [...]` is SHADOWED to
    that bool, so `t-if="'x' in editable"` raises `TypeError: argument of type 'bool' is not iterable`
    → HTTP 500 on the page (only, invisible to `-u`; the portal HttpCase never hit it because tests
    exercised the models, not the rendered page). The qweb error's compiled line number does NOT match
    the source line — read the `Element:`/`Path:` fields in the QWeb traceback to find the real node.
    Fix: name the key anything else (`editable_fields`). Other reserved-ish portal context names to avoid:
    `request`, `page_name`, `pager`, `error`, `message`. Rule: prefix ESS payload keys distinctively
    (the profile page also renamed `requests`→`pcr_requests` defensively) and ALWAYS Chrome-MCP each
    portal route — a green model test is not a rendered-page test.
61. **`t-key` is OWL-only — it is INVALID in server-rendered (frontend/report) QWeb.** A `t-key` on a
    server `t-foreach` logs `Unknown directives or unused attributes: {'t-key'}` and is ignored; keep it
    out of portal/report templates (it belongs only in `web.assets_*` OWL `.xml`). Frontend portal icons
    are inline `<svg>` Lucide paths (a small `ess_icon` t-call ladder), never Font Awesome `<i class="fa">`
    or emoji (C11 extends to the portal).
62. **An employee-owned attachment BIND needs sudo when the owner has read-only on the target record.**
    The ESS document self-upload creates the attachment as the user, creates the `pb.employee.document`
    (own-create rule), then binds `attachment.res_model/res_id` to the doc — but Odoo re-checks attachment
    access against the NEW linked record, and the employee's own-doc rule is READ-only (no write), so a
    self-user `att.write({'res_model':…})` raises `AccessError` ("not allowed to access this document") →
    HTTP 403 on the upload POST (looks exactly like a CSRF failure in the werkzeug log — it is NOT; grep
    for the "not allowed to access" warning to tell them apart). The bind is a system op on a record they
    already own → `att.sudo().write(...)`. The C18.25 order (attachment first, bind after the doc exists)
    is preserved. The model test created the doc but never exercised the bind — a live upload is required
    to catch this.
63. **MSS is a read-and-act facade over EXISTING model actions, not a new approval engine (C18.55a made
    concrete).** `pb.team.act(model, res_id, action, note)` is a hard whitelist `{model: {action: method}}`
    → the target model's own gated method, called AS THE REAL USER, no sudo. A non-whitelisted model/action
    RAISES (`res.users`, `frobnicate`); a record outside the caller's team RAISES (team-scope defense in
    depth); a MODEL business refusal (tier lacked, decided-record no-op) is CAUGHT and returned
    `{ok:False,error}` so the cockpit toasts the model's own words and keeps the row. Two access facts hit
    wiring it: (a) **OT approval needs `hr_attendance.group_hr_attendance_manager`** — unlike trips /
    attendance-corrections (which admit the specific `employee_id.parent_id.user_id` via `_approval_can`
    with NO group), `hr.overtime.request` has ONLY an own-records officer rule + an all-records manager
    rule, so a plain line manager cannot approve a report's OT; the facade scopes the queue to the team,
    the model grants the write. (b) The young-worker OT gate is a CREATE/write `@api.constrains`, and
    `action_approve` writes only `state`+`approved_hours` (NOT in the constrains trigger set), so a minor
    OT can NEVER become a submitted-then-refused-on-approve queue item — the E-gate blocks it at
    submission (a STRONGER guarantee than a queue refusal). The MSS refusal-surfacing path is therefore
    validated via the trip-tier / decided-record route, not a young-worker queue item (handover §6.11
    prose predates this finding).
64. **A `pb.demo.generator` extension MUST inherit `models.TransientModel`** — it is a wizard-style
    transient; a `models.Model` `_inherit` aborts registry load with "transforms the transient model … into
    a non-transient model." The ESS/MSS demo enablement (`demo_ess.py`) re-links three PASSWORDLESS logins
    (C18.14) to the CURRENT demo employees on every `action_generate_all` (employees are recreated each
    run, so linkage is rebuilt), re-parents the demo minor under the demo manager for the MSS story, and
    seeds a couple of submitted OT for adult reports so the queue is non-empty. `clean_demo_employees` now
    also unlinks OT / profile-change-requests / documents for is_demo employees BEFORE `emps.unlink()` (a
    required `employee_id` on `hr.overtime.request` would otherwise block the unlink). `res.users.employee_id`
    reads `None` in a bare `odoo-bin shell` (company-dependent, C18.26) even when `employee.user_id` is set
    — verify the link on `hr.employee.user_id`, not `res.users.employee_id`.
