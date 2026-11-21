# BLUEPRINT Phase B5 — Outputs & formulas, and Test

Read `docs/handovers/BLUEPRINT_LEDGER.md` FULLY (BP-R4, R10; gotchas through B4), the B1–B4
reports, and `BLUEPRINT_PLAN.md` §"Step 4 · Outputs", §"Step 5 · Test", §"Server seam rulings" 8.
B1–B4 code is the base.

## 1. Goal (plain English)

**Outputs** shows, before anything is tested or finished, exactly what the rules create: every
component, its Excel formula in readable code form, its value for the sample employee, and
whether it was generated from a sentence or written by hand — with an inspector that shows what
feeds a value and what it feeds. **Test** runs meaningful checks in one click (the starter's
scenarios plus boundary cases), shows a plain verdict per scenario, asks the person to confirm
the numbers they expect before a scenario counts as passed, and marks the evidence stale the
moment a formula or band changes afterwards. The pay panel becomes the scoreboard on this step.

## 2. Scope — in
- Outputs step: money-flow strip, outputs table with filters + search, row inspector
  (dependencies both ways, generated-vs-manual diff, Restore guided, Open in editor), export of a
  formula catalogue (JSON download through the existing Odoo download route, or a CSV — state
  which; not an .xlsx).
- Test step: scenario list (starter scenarios + boundary picks + "your samples"), one-click run,
  verdicts with reasons, confirm-expected gate (single + all), evidence hash + stale banner,
  scoreboard in the pay panel, "Try with a real person" using the existing real-employee preview.
- RPCs: `bp_outputs`, `bp_output_detail`, `bp_export_catalog`, `bp_tests`, `bp_run_checks`,
  `bp_confirm_expected`, `bp_boundary_picks`, `bp_add_boundaries`, `bp_evidence`.
- Tests, deploy ×4, Chrome validation, commits, gotchas, report.

## 3. Scope — binding non-goals
- No new evaluator: values come from `compute_preview`, tests from `run_tests`, coverage from
  `get_test_coverage`, traces from `replay_trace`. Never re-implement the engine's arithmetic.
- No .xlsx workbook export (plan: JSON/CSV catalogue only).
- No Finish-step changes beyond exposing `bp_evidence` for B6 to consume.

## 4. Design (bar: "extreme WOW, intuitive, out-of-this-world experience, best in class")

### 4.1 Outputs step
Eyebrow "04 / OUTPUTS & FORMULAS", H1 **"See what your rules create."**, lead "Review every
output before testing or finishing. The formulas below are the same ones used for the sample
calculation."

**Money-flow strip** (hero of this step): four nodes joined by arrows — "**79** inputs &
fixed values → **38** components → **114** formula rules → **Net pay & employer cost**" with the
sample's net and employer cost under the last node; numbers count up on arrival; hovering a node
highlights the matching filter chip. (Counts: inputs+constants; rules with a recipe group
earning/deduction/benefit; all formula rules; totals.)

**Filters** (chips, single-select + search box): Final outputs · Inputs & fixed values ·
Earnings · Deductions · Benefits & employer costs · Intermediate · Edited by hand · Needs a
decision · All. Default **Final outputs** (net, gross, PIT, deductions, employer cost, and every
`net_role == 'net'`/total-group rule).

**Table** (kit table, sticky header, virtualised above 150 rows): Component (name + code chip +
letter in muted mono) · Excel formula (code form, mono, truncated with a "show more" toggle per
row; inputs show "input", constants their value) · Sample value (right-aligned, formatted, "—" for
none) · Badge (Generated from your settings / Written as Excel / Needs a decision / Problem) ·
"Inspect" ghost button. Keyboard: ↑↓ move, Enter inspects, `/` focuses search.

**Inspector** (right-side sheet, 480px, or full-screen on phone): title + code + letter;
the formula in code form with each referenced code as a chip (click → jump to that row);
**Feeds from** list (direct dependencies with their sample values) and **Feeds into** list
(direct dependants) — from `formula_dependencies` and a reverse index; a "Show the whole chain"
toggle that expands transitively (bounded, breadth-first, max 60 nodes with "and N more");
for generated rules the sentence summary (B2 `summaryOf`) and "Edit the sentence" (opens the B2
editor); for manual rules the **generated vs yours** side-by-side (when `bp_generated_formula`
exists) with "Restore the guided version"; the step-by-step trace for the current sample from
`replay_trace` (the entry for this rule: inputs read → value), rendered as "read BASIC 30,000,000
· read PAIDDAYS 26 · … → 30,000,000".

**Export** button (ghost, header right): "Download the formula catalogue" → JSON (`{configuration,
version, generated_at, components:[{code, name, letter, type, excel_codes, excel_letters, source,
recipe, sample_value}], rate_tables, samples}`) with `productionCompatible: false` omitted (that
was the prototype's flag; here the file is simply a catalogue — say so in a one-line note under
the button: "A readable catalogue of this configuration's rules. It is not a spreadsheet you can
run.").

### 4.2 Test step
Eyebrow "05 / BUILD CONFIDENCE BEFORE RELEASE", H1 **"Try the days that aren't ordinary."**,
lead "Use real-life examples to challenge the rules. A passing calculation is evidence, not a
substitute for policy approval."

**Run card** (top): "One click. **N** meaningful checks." + a plain list of what they are
("the starter's 5 scenarios · 6 boundary cases on insurance caps and paid days · your 2 samples")
+ primary **Run the checks** (→ `bp_run_checks`) + the evidence status chip: "Never run" ·
"Passed 12 of 12 · 2 min ago" (green) · "3 need attention" (rose) · "**Changed since the last
run** — run again" (amber, when `evidence_hash != tests_hash`).

**Scenario list**: one row per sample: name, kind chip (Starter · Boundary · Yours · Real
person), verdict pill (Passed / Needs attention / Pending your confirmation / Not run), a plain
reason ("PIT expected 265,000, got 257,500 (−7,500)"; for pending: "Confirm the numbers you
expect"), and actions: **Confirm these numbers** (pending only; opens a sheet listing the
expected vs computed per output with a one-line "These are the numbers I expect" button →
`bp_confirm_expected`), **Open** (sheet showing inputs and every output value), and for
"Yours" samples "Edit inputs" (reuses the B1 sample-inputs dialog). Header actions: "Confirm all
pending" (only when every pending sample's computed values are present), "Add boundary cases"
(→ modal listing the picks from `bp_boundary_picks` with checkboxes → `bp_add_boundaries`),
"Try with a real person" (opens the existing real-employee picker — reuse `preview_runs` /
`preview_from_payslip` through a small modal listing recent payslips of the company; anonymised
by default; "Keep as a sample" → `preview_keep_as_sample`). Guard the real-person actions with
the same permission the studio uses.

**Coverage line** under the list (from `get_test_coverage`): "**18 of 21** formula components are
checked by a confirmed scenario · 2 are exercised on the way · 1 is untested: NIGHTPREM" with
"untested" codes clickable → the Outputs inspector.

**Pay panel on this step** → scoreboard: big "12 / 12 passed", three small counters (passed ·
attention · pending), the evidence chip, and "Last run 2 min ago by <name>". Returning to any
other step restores the normal hero.

**Beyond the happy path** (bottom, muted card, from the prototype): five "integration recipes"
(multiple salary rates in a month · prior-year arrears · mid-cycle advances and loan recovery ·
net contracts and shadow payroll · concurrent rules and missing inputs), each a one-liner and
a chip "Later"; no buttons. Honest, not a dead-end: the text says these are separate recipes.

### 4.3 Evidence
`evidence_hash` (BP-R10) computed by `bp_evidence(config_id)`: sha256 over sorted
`(code, column_type, normalised excel_formula, round(constant_value, 6))` + sorted rate tables
`(code, [(lower, rate)])`. `bp_run_checks` stamps `tests_hash = evidence_hash`,
`tests_passed/failed/pending`, `tests_run_at`, `tests_run_by`. Stale = mismatch. The Components,
Tax and Test steps all show the amber "changed since the last run" chip when stale (a shared
small component). B6's Finish will require: not stale, failed 0, at least one confirmed scenario,
and the final outputs (NET, PIT, GROSS or their role equivalents) asserted per `get_test_coverage`.

### 4.4 Zero dead-ends
no samples → run card explains and offers "Add boundary cases" / "Add a sample" · run fails
(`run_tests` `ok False`) → rose card with the reason + retry · all pending → the run shows
"Pending your confirmation" everywhere with one clear next action · a scenario with a missing
expected output → reason names the code · huge configuration → virtualised table, inspector
chain bounded · real-person picker with no payslips → "No pay runs yet for this company" · export
on a blank canvas → catalogue with zero components, no error.

## 5. Server
- `bp_outputs(config_id, sample_id=None, filter='final', q='')` → `{ok, strip:{inputs, components, rules},
  totals:{net, employer_cost}, rows:[{id, code, name, letter, column_type, group, excel_codes, value,
  source, badge:'generated'|'manual'|'review'|'problem', badge_text}], counts:{per filter}, revision}`.
  Code-form formula: reuse B2's letters→codes translation (`excel_formula_display` if it renders
  codes; else the B2 helper). Values from one `compute_preview` call.
- `bp_output_detail(config_id, rule_id, sample_id=None)` → `{ok, rule:{…}, feeds_from:[{code,name,value}],
  feeds_into:[…], chain:{from:[…], into:[…]} (bounded), summary, generated_formula_codes,
  manual_formula_codes, trace:{reads:[{code,value}], value}}` — trace from `replay_trace`
  (find this rule's entry; if the trace is expensive, cache per (config, sample, revision) in
  memory for the request only).
- `bp_export_catalog(config_id)` → the JSON string + suggested filename; the client triggers a
  download via the standard `download` helper (`@web/core/network/download`) — verify the idiom
  used elsewhere (grep `download(` in pb_* js) and copy it.
- `bp_tests(config_id)` → `{ok, samples:[{id, name, kind, verdict, reason, has_expected, confirmed,
  discrepancies:[{code, expected, computed, diff}]}], coverage:{asserted, exercised, untested:[codes], pct},
  evidence:{hash, tests_hash, stale, passed, failed, pending, run_at, run_by}, boundary_available:int}`.
  Kind: `starter` = seeded from the template (`source_type` the template seeder sets — check),
  `boundary` = `source_type == 'generated'`, `real` = has `source_payslip_id`, else `yours`.
  Reason text built from `hr.formula.test.result` rows (expected/computed/difference) in plain
  words; pending reason = "Confirm the numbers you expect".
- `bp_run_checks(config_id, revision)` → `run_tests` → recompute coverage → stamp evidence →
  return `bp_tests` payload.
- `bp_confirm_expected(config_id, sample_ids|'all', revision)` → `confirm_sample_expected` /
  `confirm_all_samples` → re-run → payload.
- `bp_boundary_picks(config_id)` → candidate picks `{input_code, edge, label}` derived from the
  configuration: for each constant referenced by an `insurance_base` cap (CAPLO, CAPHI) → pick
  `BASIC` (or the base input) at the cap value, label "Insurance ceiling"; `PAIDDAYS` at 0 and at
  STDDAYS ("No paid days" / "Full month"); `DEPS` at 0; `CONTRACTMTH` at 3 ("Short-contract
  threshold") when present; `BASIC` at SHORTTHRESH when present. Each with `exists: bool`
  (already generated, via `boundary_key`).
- `bp_add_boundaries(config_id, picks, revision)` → `generate_boundary_samples` → payload.
- `bp_evidence(config_id)` → `{hash, tests_hash, stale, …}` (also used by B6).

## 6. Client
Files: `js/step_outputs.js`, `js/output_inspector.js`, `js/step_test.js`, `js/scoreboard.js`
(pay-panel variant), `js/evidence_chip.js` (shared), `js/outputs_text.js` (pure: badge text,
reason formatting, `filterRows`), XML + SCSS (`pbbp-out-*`, `pbbp-test-*`). Hoot tests for the
pure helpers (filter logic, reason formatting with negative diffs, count-up formatting reuse).

## 7. Tests (Python)
1. `bp_outputs` rows = every rule; final filter contains NET/PIT/GROSS/EEDED/ERCOST on Complete;
   code-form formulas contain no bare letters (regex) for generated rules.
2. `bp_output_detail` feeds_from/feeds_into correct for SIDED (from SIBASE, SIRATE; into EEDED);
   chain bounded at 60; trace entry present with reads.
3. Export catalogue: valid JSON, one entry per rule, rate tables present, no "Odoo".
4. Evidence: hash stable across reads; changes when a formula, constant or bracket changes;
   `bp_run_checks` stamps `tests_hash`; a later edit → `stale True`.
5. Verdicts: Complete's 5 starter scenarios pass; make one expected value wrong → "Needs
   attention" with the diff in the reason; unconfirmed generated sample → pending, never passed.
6. Boundary picks on Complete include CAPLO/CAPHI/PAIDDAYS/DEPS/CONTRACTMTH/SHORTTHRESH; adding
   creates edge−1/edge/edge+1 rows; re-adding reports skipped, creates nothing.
7. Coverage payload matches `get_test_coverage` for the same config.
8. Revision/company guards; white-label + vocabulary gate on new files.

## 8. Deploy + acceptance (bump `pb_blueprint` 19.0.1.4.0)
1. Outputs: strip counts match the table; Final outputs filter default; search "tax" filters.
2. Inspect PIT → chips for TAXABLE and the routes' inputs; feeds-into NET; trace shows the reads;
   "Show the whole chain" expands and stops at the bound with a count.
3. Inspect a manual rule (make one via the B2 Excel lane) → generated vs yours side-by-side;
   Restore → row badge flips; hero updates.
4. Export → a JSON file downloads; open it: components + rate tables present.
5. Test: run → verdicts; starter scenarios Passed; pending boundary rows say so; confirm one →
   Passed; confirm all → all Passed; scoreboard in the panel shows the counts.
6. Change a band on the Tax tab → amber "changed since the last run" on Test, Components and
   Tax; run again → clears.
7. Break a formula in the grid → run → Needs attention with a plain reason naming the code.
8. Add boundary cases → rows appear (edge−1/0/+1 names), pending until confirmed.
9. Try with a real person on payobook (company 5 has payslips) → values load anonymised; Keep as a
   sample → appears under Yours; on abm (fewer payslips) the picker still works or explains.
10. Coverage line names untested codes and links to the inspector.
11. Blank canvas → both steps render their empty guidance without errors.
12. 390 px: table becomes stacked cards; inspector full-screen; scoreboard readable.
13. All four DBs on the new version; gates green.

## 8b. Addendum after the B4 report (binding)
- **Baseline live on all four DBs**: `pb_blueprint 19.0.1.3.0`, `pb_formula_studio 19.0.1.184.0`,
  `pb_import_kit 19.0.1.19.0`, `pb_hub 19.0.1.9.0`, `pb_hr_payroll_formula 19.0.1.124.0`,
  `pb_pay_delivery 19.0.1.2.0`. Server files: `blueprint.py, blueprint_studio.py, blueprint_components.py,
  blueprint_tax.py, blueprint_calendar.py, blueprint_connect.py, payday.py, recipe_*.py,
  essentials_recipes.py, workbook_vocabulary.py, formula_*_ext.py`. Put B5's server code in
  `blueprint_outputs.py` and `blueprint_tests.py` (`_inherit = 'pb.blueprint.studio'`), reusing
  `_guard`, `_plain`, `_revision_guard`, `_display_formula`, `_codes_to_letters`, `_sample_values`.
  Client: `step_outputs.js`, `step_test.js` replace the last two uses of `step_thin.js` (delete
  `step_thin.js` once nothing uses it); text helpers follow the `connect_text.js` pattern —
  **every `_t()` inside a function, never at module scope** (BP28/BP37).
- **Tests**: 106 Python + 4 lint + 67 hoot are green; keep them so and state the new counts.
- **Evidence chip** is shared across Components, Tax and Test — build it once (`evidence_chip.js`)
  and mount it from `step_rules.js` and `step_test.js`; B6's Finish will mount it too.
- **URL/return doors**: `router.pushState` from `onWillStart` is overwritten at mount for any door
  carrying its payload in context (BP38) — reuse the fix B4 made in `blueprint.js`, do not add a
  second pushState.
- **Demo estate** on payobook: three demo configurations (see B4 report §12) — use
  "Vietnam · Complete (guided setup demo)" for the Outputs/Test walkthroughs where rich content
  helps; never delete or rename them; discard your own drafts through the product path.
- Gotchas BP37–BP40 are in the ledger; read before coding.

## 9. Report (`docs/handovers/BLUEPRINT_PHASE_B5_REPORT.md`)
Results 1–13; the evidence hash inputs exactly as implemented; the boundary pick rules; the
export shape; the download idiom used; `source_type` values found for starter samples; gotchas;
self-score; deferred items with reasons.
