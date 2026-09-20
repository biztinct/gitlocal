# Integrations Program — Cycle 8: The Rule Composer — transformation rules a novice can write

> STATUS: FINAL. Conventions binding through **W157** (`docs/WORKFORCE_REDESIGN_CONVENTIONS.md`) + C18.x (`docs/FORMULA_ENGINE_CONVENTIONS.md`). Prior reports: `CYCLE5_REPORT.md` … `CYCLE7_REPORT.md`. Program state: `PROGRAM_STATE.md`.

Transformation rules are the values derived from a feed's records before mapping (OT-hour buckets, dependant counts, unit conversions). Today they are **Python programs in a read-only drawer**: the owner's screenshot shows `WORKEDHRS` as 15 lines of `str(r.get(...)).strip()` / `isdigit()` arithmetic labelled "Python Expression (Advanced)". On a SaaS where **clients configure their own connectors**, that is a dead end.

**Goal**: a payroll manager who has never seen code can create *"Overtime 150% hours = sum of Actual Pay Hour where OT Type is 150% and Approval Status is Approved"* — and **see it work on real data as they build it**. Opened as a **popup**, not a drawer (owner explicit). The owner-visible outcome: the WORKEDHRS drawer becomes a popup reading *"Take attendance records · add up Total Worked Hours (seconds) plus Paid Leave Hours (hours:minutes) · call it WORKEDHRS"* with live sample data proving it computes the number.

## Owner rulings (locked 2026-08-21 — do not re-litigate)
- **Payroll managers** create/edit guided and Excel rules; the raw-Python lane stays admin-only, edited via the backend form.
- **Three lanes**: guided (no-code, the star), **Excel formula** (owner-requested addition), python (**the `python_code` field STAYS** — "at least there is an option").
- **AI lane included**: "Describe it in words" → drafts the guided steps for review; never saves directly; degrades gracefully (deterministic fallback) when AI is unconfigured.
- **Migrate all 8 ABM rules** (6 OT sums + DEPCOUNT + WORKEDHRS) into guided form with proof of identical outputs before/after. Acceptance: the owner's whole live abm board opens as editable sentences.
- **Popup, not drawer** for rules; other ledger kinds keep the drawer.

## The design — "the rule is a sentence, and the data answers as you build"

A transformation rule is: *take some records → keep some → derive one number → name it*. The builder IS that sentence, four stacked step-cards, chips/pickers only — no free-text code anywhere in the guided lane:

```
1  TAKE     records from  [Overtime requests ▾]        (feed picker; or "rows inside [nested table ▾] of each record")
2  KEEP     [OT Type ▾] [is ▾] [150% ▾]   AND   [Approval Status ▾] [is ▾] [Approved ▾]     + add condition
3  DERIVE   [add up ▾] [Actual Pay Hour ▾]  — this field contains [a number ▾]      + plus another field
4  CALL IT  [OTHRS150]  "Overtime 150% — hours"     fallback if nothing matches: [0]
```

Beside it, the **living proof rail**: sample records flow through the steps in real time — "24 records → 5 match → **10.5**". Change a condition, watch rows get struck through. Per-step count chips; the result large at the bottom; a **synthetic banner** when previewing catalog illustrations; the rule's `last_error` surfaced when editing a failing rule.

---

## Verified plumbing (2026-08-21, line numbers current post-merge of d76f7f5a/ffab0b70 — do not re-derive)

### Rule model / engine / ledger
- **Model** `hr.api.transformation.rule` — `pb_hr_payroll_formula/models/api_transformation_rule.py:50`: `rule_type` ∈ count/sum/avg/min/max/date_diff/date_check/python (:23-32), `output_key` :75 (key into `computed_data`), `aggregate_field` :103, `filter_expression` :108, date fields :122-135, `python_code` :143, `default_value` :162. Nothing added by Cycles 3–6; no company_id, no error/state fields.
- **Engine** `_execute_for_records` :188 — groups store rows by `employee_external_id`, widens to all the employee's rows on the connector (:214-227), writes `computed[output_key]` into `computed_data` of salary→employee→main rows (:248-256). **THE GAP this cycle closes: every failure is a log WARNING + silent `default_value` (:234-246)** — no error field, invisible breakage.
- **Filter namespace** (:274-288): exactly `rec` (plain dict = `extracted_data`), `env`, `datetime`, `date`; per-record `except Exception: pass` drops rows. **Python namespace** (:415-427): `records`, `employee_data`, `all_records`, `period_start/end`, `employee`, `relativedelta`, `result` pre-seeded to default. Two namespaces one letter apart (`rec` vs mapping transforms' `record`, W145) — the footgun the builder designs out by never generating code.
- Branch quirks: `date_diff`/`date_check` read **`source_records[0]` only**; `date_check` returns 1/0; aggregates coerce `float(val)` skipping None/errors; `_parse_date` tries 7 formats (:464-483).
- **Templates** :486 (Cycle 3): 8 zoho rows, all `is_legacy_abm`, in `data/transformation_rule_templates.xml` — 6 OT sums (filter `rec.get('OT_Type') == '150%' and rec.get('ApprovalStatus') == 'Approved'`, aggregate `Actual_Pay_Hour`) + DEPCOUNT python (nested `tabularSections['Dependent and Dependent Health Insurance']`, count rows with `Dependent_PIT_Number`) + WORKEDHRS python (seconds + `H:MM` → hours). `_COPIED` tuple :558-564 — **extend it with every new field you mirror**; create-only sync hook `integration_connector.py:765-805`, matched on output_key.
- **ACLs** `pb_hr_payroll_formula/security/ir.model.access.csv:49-51`: user=read; **manager & admin already full CRUD** — "managers edit" is UI+RPC gating work, not ACL work. No ir.rule record rules on the model.
- **Ledger/drawer** `pb_integrations/models/pb_integrations.py`: `_ledger_rule` :551, `_detail_rule` :590 (read-only; known bug: `date_check_operator`/`date_check_value` never rendered — fix in passing). `get_ledger_detail` :281 already returns `id` + `res_model`; JS discards them (`openRow`, `integrations.js:377-399` — preserve its optimistic paint, in-flight-close guard, errors-never-swallowed).
- **"New rule" slot**: `.itg-tabs` trailing edge after `.itg-tabsub` (`pb_integrations/static/src/xml/integrations.xml:130`), `t-if="state.kind === 'rule'"`; precedent = the cockpit's right-aligned ghost button.
- **`pb.integrations` doctrine**: no-sudo, caller's-rights. Keep it.

### Preview & data
- **The preview law** — `preview_transform` (`pb_hr_payroll_formula/models/integration_field_mapping.py:354-421`): refuses python; **preview MUST BE the same engine function as execution** (its own comment says why); `_jsonable` everything on the wire; ValidationError → human message unlogged; unexpected → sanitized + logged (W40). Client wrappers `api_transform_preview`/`api_transform_save` (`pb_formula_studio/models/pb_formula_studio.py:4285-4330`) are the structural template for `rule_preview`/`rule_save` — **but the studio's `_can_edit` :625-634 fails OPEN; do NOT copy it for writes. `rule_save` is fail-closed.**
- **Sample data**: the payobook demo store has 27 rows across 5 data_types (dependents/leaves fan out one row per entry — `count` counts rows; zoho dependants instead live in `tabularSections` of the employee record: **both shapes needed in TAKE**). Never-synced case: synthesize from `hr.integration.endpoint.field.sample_value` (`integration_endpoint_field.py:75`) — its docstring is load-bearing: samples are **ILLUSTRATIONS, never presentable as received data** → the proof rail labels synthetic mode explicitly.
- **Excel engine**: `pb_hr_payroll_formula/formula_engine/excel_semantics.py` — lazy `excel_if`, Decimal `excel_round/up/down/ceiling/floor`, `excel_streq`, `excel_iferror`, `coerce_number/value`, list aggregates, **`assert_safe_expression` (:299)**, `UnsafeFormulaError`. Battery gate: `tools/excel_semantics_battery.py`. Use this — do not write a second evaluator.
- **AI seam**: `_llm_chat/_llm_propose/_validate_llm` (`pb_formula_studio.py:6683-6784`) — OpenAI-compatible, json_mode, `LLMUnavailable` → deterministic fallback; config params `pb_formula_studio.llm_base_url/api_key/model` (:20-25); probe `ai_status()` :6799; validation discipline = "every referenced name must exist in the real catalog, else reject the whole proposal". **pb_integrations does NOT depend on pb_formula_studio** → reimplement a ~30-line gateway in `pb_hr_payroll_formula` reading the SAME config params (one key powers both). Do not refactor the studio.

### UI precedents
- **Modal shell**: no shared pbim modal exists (the scrim+card recipe is hand-rolled ~25×). Shell = studio first-setup wizard `.pbfs-wz-scrim`/`.pbfs-wz` (`studio.xml:3394`, `studio.scss:519-520`); chrome = shared `.pplw-*` wizard shell (`pb_import_kit/static/src/scss/wizard_shell.scss`); step/footer logic = `IntegrationOnboarding` (`integration_onboarding.js:45-227`). **Invent: `--pbim-scrim` token + one z-index constant (census: 40→1400) in `pb_import_kit` as a `.pbim-modal` primitive** — other modules can adopt later.
- **Escape**: `useHotkey("escape", {global:true})` — plain keydown never fires (service intercepts at capture); ladder precedent `formula_studio.js:456-478`. Outside-click: scrim `t-on-click` + card `.stop`.
- **WfDrawer** (`pb_wf_kit/js/wf_drawer.js`): wrong host for a builder — add a sibling modal component; the drawer stays for other ledger kinds.
- **Live preview mechanism**: `_tfPreview` (`pb_formula_studio/static/src/js/mapping/mapping_canvas.js:839-860`) — 260ms debounce + `++token` supersede + RPC-as-prop. Presentation: studio Test workbench (`studio.xml:600-641`) and `.mc-tf-prev`'s `sample → result` line.
- **Condition rows**: closest precedent = pb_explorer's "Where" + dashed "+ Add filter" cascade (`pb_explorer/static/src/xml/explorer.xml:210-250`); chip visuals `.pbim-fchip`/`.mc-chip`.
- **Icons**: `IC`/`ic()` registry (`pb_import_kit/static/src/js/import_icons.js`) already has sigma/filter/plus/beaker/calculator/play/pencil/trash/check/alert/loader/search — add only what's missing, to the registry (W2). Lucide only, never emoji.
- Design laws: W1 pbim tokens (no invented hexes), W3 no gradients; powder pbim palette for pb_integrations surfaces.

---

## WP-1 — Model + engine: guided rules as first-class citizens (`pb_hr_payroll_formula`)

New fields on `hr.api.transformation.rule` (+ mirrored on the template model, `_COPIED` extended):
- `builder_mode` Selection **guided / excel / python** (default python for existing rows pre-migration; new composer rules guided/excel).
- `excel_formula` Char — the Excel lane's per-record value expression. **Bracket refs**: `[totalWorkedHours]/3600 + HOURS([paidLeaveHours])` — resolved against the record dict (exact key first, then case/space-insensitive), evaluated via `excel_semantics` under `assert_safe_expression`. Composes with the guided steps: filter stays chip-built; the formula computes the per-record value; the rule's aggregate applies across records. Add a `HOURS()` helper ("H:MM" text → hours) to the rule-path function table if not already expressible.
- `record_source` Selection `records`/`nested` + `nested_table_path` Char (DEPCOUNT's tabular section).
- `filter_conditions` Json — `{join: 'all'|'any', rows: [{field, op, value}]}`; ops: is / is not / contains / is present / is blank / > / ≥ / < / ≤. Comparison semantics match the legacy leniency: coerce numerics where both sides look numeric, else string compare; a row that errors just doesn't match (never crashes the rule).
- `value_steps` Json — `[{field, contains: number|seconds|hmm|minutes|days}]`; steps within a record ADD (WORKEDHRS = a seconds field + an H:MM field), then count/sum/avg/min/max applies across records. `count` ignores value_steps and counts matching records/rows.
- `plain_summary` computed+stored Char — the generated sentence ("Adds up Actual Pay Hour where OT Type is 150% and Approval Status is Approved") → the ledger's KIND/description display. Python rules: "Advanced rule (Python), maintained by your administrator". **Product voice — never the word "Odoo".**
- **`last_error` Char + `last_error_at` Datetime** — the except-arm at :241-246 writes them (sanitized, W40) and **clears them on success**. Ledger badge turns error-toned when set.

Engine: `_execute_single` gains the guided path — conditions evaluated **natively on plain dicts (zero safe_eval on the guided path)**; nested source iterates the tabular rows; value extraction applies unit conversions (seconds→h, "H:MM"→h, minutes→h, days pass-through); malformed values skipped with the same leniency as the legacy python (WORKEDHRS's isdigit guards). The excel lane evaluates `excel_formula` per record/row inside the same loop. date_diff/date_check stay field-driven (already declarative) and render as sentences in the composer.

Add a **traced twin** returning per-step data (records-in, matched ids, per-record values, per-step counts, result) **built from THE SAME primitives** — preview == execution (the `preview_transform` law). Do not fork the logic; the trace decorates it.

AI gateway: `models/llm_gateway.py` (or helpers on the rule model) — `_llm_chat`-equivalent reading `pb_formula_studio.llm_base_url/api_key/model`, json_mode, `LLMUnavailable` → deterministic keyword mapper ("sum/count/average … where X is Y" grammar over the catalog labels). Strict output validation: every referenced field must exist in the connector's catalog, ops/contains from the closed vocabulary, else reject the whole proposal.

## WP-2 — RPCs on `pb.integrations` (no-sudo, caller's-rights)

- `rule_composer_data(connector_id, rule_id?)` → field catalog per data_type via the existing provenance ladder (live store → endpoint.field catalog with sample_value → labelled fallback), feeds + nested-table paths, recipes (vendor `hr.api.transformation.rule.template` rows + generic starters), the rule's spec if editing, sample records (recent store rows, else **synthetic from catalog samples with `synthetic: true`**), `can_edit`, `ai` status.
- `rule_preview(connector_id, spec)` → the traced engine run. Refuses `builder_mode='python'` (same wording family as `preview_transform`). Sanitized errors (W40). `_jsonable` on the wire.
- `rule_save(connector_id, spec, rule_id?)` → **fail-closed** gate on `group_formula_manager`/admin; field whitelist that can never write `python_code` or `builder_mode='python'` (guided + excel only); validates output_key (unique per connector; uppercase, underscore-free, non-substring per the formula-converter contract — reuse the existing code validator if one exists); every referenced field against the catalog; **excel lane: parse before write** (bracket refs resolve, `assert_safe_expression` passes, function names in the supported set).
- `rule_archive(rule_id)` / unarchive — same gate.
- `rule_propose(connector_id, text)` → the AI lane via the WP-1 gateway; returns a DRAFT spec + `source: 'ai'|'deterministic'` — **never saves**.

## WP-3 — The Rule Composer component (`pb_integrations/static/src/js|xml|scss/rule_composer.*`)

- **`.pbim-modal` primitive in `pb_import_kit`** (`--pbim-scrim` token + z-index constant) + composer chrome from `.pplw-*`; ~1040px card; Escape via global useHotkey; outside-click per house recipe; busy-guard on save.
- **Front door**: recipe gallery (vendor templates prefilled + generic starters: "Sum hours by type" · "Count matching records" · "Count rows in a nested table" · "Seconds → hours" · "Days between dates" · "Start blank") + the **"Describe it" box** (always shown; degrades honestly to the deterministic mapper — say so in the UI when that's what happened).
- **The composer**: left = the four step-cards (TAKE feed/nested picker · KEEP condition rows with all/any toggle, searchable field picker grouped by feed showing sample values, dashed "+ add condition" · DERIVE op + value steps with "this field contains [a number|seconds|hours:minutes text|minutes|days]" + "plus another field", and **"Switch to a formula"** ⇄ back without data loss (the Excel lane: mono input, bracket-ref autocomplete from the catalog, function hint-bar) · CALL IT output_key auto-suggested from the name, label, fallback value). Right = **the proof rail** (samples, live strike-through, per-step count chips, big result, synthetic banner, `last_error` surfaced when editing a failing rule). 260ms/token debounce.
- **Python rules open read-only**: the plain summary + code collapsed; no edit affordances for non-admins; admins get a "maintained in the backend form" note (neutral product voice).
- **Ledger wiring**: `openRow` for `kind==='rule'` opens the composer (others keep the drawer); "New rule" primary in the tab strip, `can_edit`-gated; rule rows' Kind column shows `plain_summary`; error-toned badge when `last_error`. Fix the `date_check` drawer-render bug in passing.
- **AI draft** lands IN the composer as a filled sentence, proof rail live, a "drafted for review — check each step" ribbon; explicit Save.

## WP-4 — Migration + parity proof

- Migration (pb_hr_payroll_formula `migrations/`): rewrite the 8 vendor template rows AND instantiated rules on any DB (matched output_key + is_legacy_abm) to guided specs — 6 OT sums (conditions + aggregate), DEPCOUNT (nested count), WORKEDHRS (two value steps) — flipping `builder_mode='guided'`, **keeping the old python/filter text in place as inert provenance**. Template XML companions updated so fresh installs are guided-native (mind noupdate semantics — W13.1/W121).
- **Parity tests ship BEFORE the migration flips anything**: fixtures replicating the legacy payload shapes (OT records incl. rejected + out-of-band rows; an employee record with the tabular dependants section incl. PIT-less rows; attendance with seconds + "H:MM" incl. malformed values) — assert legacy-path result == guided-path result for every one of the 8. abm's live rules verified post-deploy by recompute comparison (read-only compute; **do not edit abm's seeded mappings**).

---

## Binding non-goals
No changes to `pb_formula_studio` (its AI + canvas stay as-is), `pb_import_advanced`, or the connector backend form (the admin escape hatch remains). No python codegen from guided specs, ever. No client path to python editing (W12) — server-enforced, not just hidden. **Do not press `Fetch fields` / any live-sync action on abm's owner connector (id 1)** — it calls the real Zoho account. No re-seeding or editing of abm's mappings. Don't touch the `pbms-canvas` collision or ⌘K fold (open owner items). Never stage `.claude/settings.json`, `thaco/`, `ABM/`; never push.

**White-label law**: the word "Odoo" must never appear in any user-visible string (labels, tooltips, placeholders, errors, banners, summaries). Product voice = **Payobook** or neutral. Technical identifiers (`from odoo import`, xmlids, module names) untouched. Cycle 7's static gate will fail your build if you slip — that is by design.

## Numbered tests
1. **Guided engine**: every operator (is / is not / contains / is present / is blank / > / ≥ / < / ≤) on typical + edge values; all/any join; nested source; each `contains` conversion (number, seconds, H:MM, minutes, days); malformed values skipped with legacy leniency (assert non-zero results, not just no-crash — the efbb64b5 lesson).
2. **Parity suite**: all 8 ABM rules — legacy path == guided path on the fixture payloads (rejected rows excluded, PIT-less dependants excluded, malformed H:MM skipped) — green BEFORE the migration commit.
3. **Excel lane**: bracket-ref resolution (fields with spaces/dots; unknown ref → parse error); each supported function through the rule path; `assert_safe_expression` rejects `__import__`, attribute access, dunder; parse error → proof-rail message AND save refusal; WORKEDHRS excel form parity vs both the python original and the guided form.
4. **Gates fail closed**: non-manager `rule_save` → refused; `builder_mode='python'` or `python_code` via RPC → refused; field-not-in-catalog → refused; bad output_key (lowercase, underscore, substring-collision) → refused; archive/unarchive gated.
5. **last_error**: a failing rule writes `last_error`/`last_error_at` and returns default; the next success clears both; ledger badge reflects it.
6. **Preview == execution**: the traced twin's result equals `_execute_for_records`'s for identical specs/records; `rule_preview` refuses python; sanitized error on a poisoned spec; `synthetic: true` when and only when no store rows exist.
7. **AI lane**: valid text → draft spec whose every field is in the catalog; a proposal referencing a fabricated field is rejected wholesale; no API key → deterministic fallback with `source:'deterministic'`; `rule_propose` never writes.
8. **UI behaviour**: row-click on a rule opens the composer, other kinds keep the drawer; "New rule" only for managers; Escape + outside-click close (dirty-state confirm); guided⇄formula switch loses nothing; python rule renders read-only; plain_summary in the ledger.
9. **Regression**: scoped suites across pb_hr_payroll_formula + pb_integrations + pb_import_kit green (modulo the known clock-dependent failures named in Cycle 6's report); the no-"Odoo" gate green; JS gate `node --input-type=module --check` on every touched file (W127).
10. **Live validation** (Chrome MCP, W129 temp single-company user, W130 own Chrome, /bizapp prefix), ~1450–1900px: **payobook demo** — build "count dependants" and "sum OT where…" from scratch as a novice would, screenshot every step, count the clicks; **abm** — all 8 rules open as sentences, the WORKEDHRS composer re-shot against the owner's original screenshot, synthetic banner visible on the never-synced seeded connector, "Describe it" drafts via deterministic fallback. Zero console errors, zero non-warmup ≥400 responses.

## Deploy + verify
Standard ritual to Payobook19v2: fresh staging dir, rsync the touched modules **plus the W118 reverse-dep closure** (version-diff to find it), **W136 stall-proof detached units** (unit restarts the service itself; sentinel + EXIT code) — `-u` the closure on **payobook** and **abm** (and `payobook_template` so future tenants inherit). W128 pre-deploy foreign-file check (another session may be active — rsync only files your diff owns; if a foreign uncommitted file overlaps a module you must ship, STOP and report). Asset-cache purge; a real Chrome page-load to compile SCSS; migration runs via the module upgrade. Post-deploy: the abm recompute comparison (test 2's live half).

## Self-review (before writing the report)
(1) preview and execution share one code path — diff your own functions to prove it; (2) `rule_save`'s whitelist genuinely cannot reach `python_code` (try it in a test, don't reason it); (3) no new user-visible string says "Odoo"; (4) `_COPIED` includes every new field; (5) no technical identifier renamed; (6) the migration is idempotent (safe to `-u` twice).

## Commits (per feature, explicit staging, W9 tests-with-feature)
1. `feat(pb_hr_payroll_formula): a rule is a sentence — guided model + native engine + last_error`
2. `feat(pb_hr_payroll_formula): the Excel lane — bracket refs over excel_semantics`
3. `feat(pb_hr_payroll_formula): the AI gateway drafts guided rules`
4. `feat(pb_import_kit): the modal primitive the drawer never was`
5. `feat(pb_integrations): composer RPCs — fail-closed, catalog-validated`
6. `feat(pb_integrations): the Rule Composer — four steps and a proof rail`
7. `feat(pb_hr_payroll_formula): the 8 ABM rules become sentences — with parity proof`
8. `docs: Cycle 8 ledger + report`

Write `CYCLE8_REPORT.md` **incrementally, committing at milestones** (a stall must not lose the record). Subagent commits end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

## Report back
Per-WP status; the parity table (8 rules × legacy/guided/excel where applicable); proof the gates fail closed (the actual refusal messages); the novice click-count for each live-built rule; before/after screenshots (drawer → composer; WORKEDHRS especially); synthetic-banner shot; AI draft shot (which source); deploy EXIT codes for payobook/abm/template; abm recompute comparison; deviations from this handover with reasons; new W-rules (W158+) appended to the conventions ledger.
