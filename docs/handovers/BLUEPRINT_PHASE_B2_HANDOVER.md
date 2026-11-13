# BLUEPRINT Phase B2 — Guided rules engine + the Components tab

Read `docs/handovers/BLUEPRINT_LEDGER.md` FULLY (rulings BP-R3, R4, R7, R8 are the heart of this
phase; gotchas BP1–BP8 plus whatever B1 appended), then `BLUEPRINT_PHASE_B1_REPORT.md` (what B1
actually built: file layout, RPC names, the preview classification path, the resume idiom), then
`BLUEPRINT_PLAN.md` §"Step 2 · Pay rules" and §"Server seam rulings". B1's code is the base —
extend it, do not fork it.

## 1. Goal (plain English)

On step 2 (**Pay rules → Components** tab) a person sees every pay component of the draft as a
plain sentence, can switch any of them off or back on, add a new one, and open any of them in an
editor that reads like English: *"For everyone, calculate the contract salary, prorated by paid
working days."* The Excel formula is generated from the sentence and shown underneath, updating
as they choose. People who prefer Excel switch to the **Excel** lane and type; the system then
keeps their formula and never overwrites it. The pay panel on the right recomputes after every
change. Nothing about this phase requires the person to know a column letter or a code.

## 2. Scope — in

- `_inherit hr.formula.rule` recipe provenance fields + `write()` guard (BP-R3).
- `pb_blueprint/models/recipe_compiler.py`: pure `compile_recipe` + `regenerate(config)` pass,
  helper-input provisioning, aggregate recipes, validation, dependency order.
- Recipe backfill for the Essentials starter (`vn_standard_2026`) at seed time and on load.
- RPCs: `bp_components`, `bp_component_get`, `bp_recipe_preview`, `bp_component_save`,
  `bp_component_exclude`, `bp_component_include`, `bp_component_restore_guided`, `bp_regenerate`.
- Client: the Components tab (list, groups, search, include/exclude, bulk, keyboard, health dots,
  removed tray, Add component) and the **sentence editor** (kit modal, Guided + Excel lanes,
  generated formula, proof strip, disclosure for tax/insurance/payout details).
- Pay rules step shell with three tabs: **Components** (this phase), **Tax & protection** and
  **Calendar & payment** as designed thin panels (B3 fills them).
- Tests (Python + hoot), deploy ×4 DBs, Chrome validation, commits, report, ledger gotchas.

## 3. Scope — binding non-goals

- No tax band editor / relief / caps UI (B3). The compiler MAY reference existing constants
  (DEDUCTSELF, DEDUCTDEP, CAPLO, CAPHI, SIRATE…) and the VNTAX rate table.
- No Vietnam · Complete template (B3) — but the recipe vocabulary below MUST cover all 38
  workbook components so B3 is pure content. Prove it with the vocabulary test (§7 test 14).
- No Mapping/Payslip round-trips (B4), no outputs table/tests (B5), no VI (B6).
- Do not change the Formula Studio grid, `save_formula`, or `pb_formula_studio.py`.

## 4. Design (the bar is ledger rule 6, verbatim: "extreme WOW, intuitive, out-of-this-world experience, best in class")

### 4.1 Pay rules step shell
Eyebrow "02 / WHAT GOES INTO PAY", H1 **"Every component. One clear rule."**, lead "Start with the
starter's earnings, deductions and benefits. Keep what you need, remove what you don't, and make
each rule your own." A segmented control (kit `pbim-seg`) with three tabs: **Components** ·
**Tax & protection** · **Calendar & payment**. Tab state persists in the blueprint
(`optional_status_json.rules_tab` is fine, or a new `ui_json`; your call, state it in the report).
The two later tabs render their real eyebrow/H1/lead from the plan plus a designed note card
"Arrives in the next release — the starter's tax values are already in place and you can see
them in the grid." (no dead end: link "Open the grid").

### 4.2 Components tab
Toolbar row: chip "**38 included** · 3 removed" (numbers live), search box "Find a component by
name or code" (filters as you type, ⌘/Ctrl+F focuses it), right-aligned **+ Add component**.
Group tabs under it (pill segmented): **Earnings** n · **Deductions** n · **Benefits & employer
costs** n · **Inputs & fixed values** n · **Totals** n. Group membership: `recipe.group` when a
recipe exists; otherwise derived: `column_type=='input'` → Inputs, `constant` → Fixed values (same
tab), `net_role in ('net',)` or code in NET/GROSS/TAXABLE/EEDED/ERCOST → Totals, `net_role
'earning'` → Earnings, `'deduction'` → Deductions, `'employer_cost'` → Benefits, else Earnings.

Rows (one per rule, 56px, white, hairline separators, hover tint `#FAFAFE`):
- include checkbox (kit style, purple) — for Inputs/Fixed values/Totals the checkbox is hidden
  and replaced by a lock icon with tooltip "Part of every configuration";
- **name** (600 weight) + code chip (mono, muted) + on the second line the **sentence summary**
  in muted text: guided rules → `summaryOf(recipe)` (e.g. "Contract salary · Prorated by working
  days · Taxable"); Excel-lane rules → "Written as Excel · =MIN(BASIC, CAPLO) × 8%" (display
  formula with codes, truncated with an ellipsis at 64 chars);
- **health dot** + word: green "OK", amber "Needs a decision" (review reasons below), rose
  "Problem" (invalid formula / evaluation error / missing dependency) — the word is the tooltip's
  first line, the reason its second;
- right: value for the current sample employee (from the last preview, muted mono, "—" for
  inputs without a value) and a **Configure** button (ghost, `sliders-horizontal` icon) that opens
  the editor; Enter on a focused row does the same.
Review reasons (amber) — computed server-side, returned per rule as `review: [{code, text}]`:
`insurance == 'review'` ("Choose the insurance treatment"), `tax == 'inherit'` or `insurance ==
'inherit'` without a valid `source_code` ("Choose the original component"), `amount.kind ==
'linked'` whose link is not included ("Restore or replace the linked benefit"), `frequency ==
'annual'` with no payout month.

Bulk + keyboard: click selects a row (purple left bar), shift-click selects a range, ⌘/Ctrl-click
toggles; a floating action bar appears at the bottom of the list: "3 selected · Remove from this
configuration · Include · Clear". ↑/↓ move focus, Space toggles include, Enter opens, Esc clears
selection. Screen-reader labels on every control.

**Removed components tray** (collapsed section under the list, "3 removed from this
configuration"): rows with name + code + **Restore**. Only starter components can be restored
(they come back from the template JSON with their recipe); custom components are deleted for good
after a confirmation ("Remove 'Site allowance'? It is not part of the starter, so it cannot be
restored later.").

Removing a component someone else depends on: the server answers with the dependants; if all
dependants are generated rules the removal proceeds and they regenerate; if any dependant is
written as Excel the removal is **refused** with the reason "Used by OTPAY, which is written as
Excel. Edit that formula first." shown inline on the row (not a toast).

Empty states: blank canvas → illustration-free empty card "No components yet. Add your first one,
or change the starter on the Start step." with both actions. Search with no hits → "Nothing
matches 'xyz'". All removed → the tray expands automatically.

### 4.3 The sentence editor (kit `.pbim-modal`, 760px, scroll inside)
Head: component name (editable inline on click, pencil icon) · code chip · close. Lane segment:
**Guided** · **Excel**. Under it the provenance line: "Starter: Vietnam · Essentials · v2026.1"
or "Added by you".

**Guided lane** — the sentence, built from inline select "pills" (purple text on `#EDEAF8`,
chevron; native `<select>` under the hood for accessibility, styled), in one flowing paragraph:

> For **[everyone ▾]**, calculate **[the contract salary ▾]** **[amount detail]**, prorated by
> **[paid working days ▾]**.

Audience options: everyone · local employees · foreign employees · insured employees · union
members · enrolled employees · employees in eligible roles.
Amount kinds and their detail controls:
- an approved input → (none; amount comes from the input column `<CODE>` itself when the rule is
  an input, otherwise a linked input `<CODE>IN` is provisioned)
- a fixed amount → number field with currency
- the contract salary → (none)
- a percentage of the contract salary → percent field
- a percentage of **[base ▾]** → percent field + base picker (any included numeric component)
- a role-based amount → three number fields "Grade 1 / Grade 2 / Grade 3" (inputs
  `ROLEGRADE` provisioned)
- hours × hourly rate → percent field "at [150]% of the hourly rate" (input `<CODE>HRS`
  provisioned; hourly rate = contract salary ÷ (standard days × hours per day))
- an annual service ratio → payout month select (inputs `SERVDAYS`, `ANNUALDAYS`, `PAYMONTH`)
- a linked benefit premium → component picker (benefits)
Proration options: nothing · paid working days ÷ scheduled days · paid calendar days ÷ days in the
month. Frequency (shown after the sentence as a small line "Paid **[monthly ▾]**"): monthly ·
annual (in month [▾]) · when approved (ad hoc) · scheme-based.

Disclosure **"Tax, insurance & payout details"** (chevron, summary chips beside it e.g.
"taxable · in insurance base · cash"): cash / non-cash; tax treatment (taxable · exempt · exempt
with evidence · exempt up to an annual limit [amount] · exempt within an approved entitlement ·
follows the original component [picker]); in the insurance base (yes · no · follows the original ·
needs a decision); who bears the income tax (employee · employer); counts against income tax
(deductions only: no · yes · the approved amount); employer share (benefits only: percent).

Below the sentence, a card **"Excel generated from these choices"**: mono formula shown with
**codes** (not letters) — use the rule's `excel_formula_display` if it renders codes, otherwise
substitute letters→codes yourself — and, on the right, the **proof strip**: "For Linh · Example
employee: **30,000,000**" updated 300ms after any change via `bp_recipe_preview` (debounced; shows
a subtle skeleton while computing; on invalid: rose text with the validator's message).

**Excel lane** — a textarea with the formula in **code form** (the person types codes, e.g.
`=MIN(BASIC, CAPLO) * SIRATE`; the server translates codes ↔ letters both ways), live validation
pill (green "Valid" / rose message) via `validate_formula_live` after code→letter translation,
the same proof strip, and a helper row of the available codes as clickable chips (inserts at the
caret). Saving from this lane sets `bp_formula_source='manual'`. On a manual rule the Guided
lane shows the last recipe (if any) greyed with a banner: "This rule was edited by hand. **Restore
the guided version** — your Excel is kept in the history." (`bp_component_restore_guided`).

Footer: **Remove from this configuration** (ghost, rose text, left) · **Cancel** · **Save** (primary;
disabled while invalid; ⌘/Ctrl+Enter). Esc closes (ladder: open picker first, then modal —
`useHotkey`, never a raw keydown listener). Unsaved-changes guard on close.

**Add component** opens the same modal with name/code fields at the top (code auto from name —
reuse whatever `add_component` does to derive a readable underscore-free code; show it live,
editable, validated: letters+digits, 3–12 chars, unique), group select (Earnings / Deductions /
Benefits), and the sentence defaulting to "For everyone, calculate an approved input".

### 4.4 Zero dead-ends (demonstrate each in the report)
invalid formula on save → inline reason, Save disabled, previous formula untouched · circular
reference → "This formula would depend on itself through OTPAY" · removing a base that a
percentage-of rule uses → refusal naming the rule · the config has no sample → proof strip says
"Add a sample employee on the right to see a value" · rule with a formula the compiler cannot
express (manual) → Guided lane says so, Excel lane works · concurrent edit (revision) → reload
prompt · a starter component missing from the template JSON on restore → "This component is no
longer in the starter" · huge configs (200+ rows) → list virtualised or paginated by group,
still smooth.

## 5. Server design

### 5.1 Recipe fields (`models/formula_rule_ext.py`, `_inherit='hr.formula.rule'`)
`bp_recipe_json` Text; `bp_generated_formula` Char; `bp_generated_revision` Integer default 0;
`bp_formula_source` Selection `[('generated','Generated from the sentence'),('manual','Written as
Excel')]` default `manual`; `bp_template_key` Char (which starter the rule came from; set at seed).
`write()` override (mirror `formula_rule.py:1682-1690`): if `'excel_formula' in vals` and
`'bp_formula_source' not in vals` → for each record whose new formula ≠ `bp_generated_formula`
(normalised via `_normalize_excel_formula`) set `bp_formula_source='manual'`. Never touch
`bp_recipe_json` there. `copy()` carries the fields (they are ordinary stored fields — verify
`bureau_clone`'s `copy()` keeps them; add `copy=True` explicitly).

### 5.2 Recipe schema v1 (`models/recipe_schema.py` — constants + `validate_recipe(recipe, ctx)`)
```json
{"v":1, "group":"earning|deduction|benefit|total|helper",
 "audience":"all|local|foreign|insured|union|enrolled|role",
 "amount":{"kind":"input|fixed|contract|percent_contract|percent_of|role|hourly|annual_ratio|linked|sum_group|bracket|insurance_base",
           "value":0, "percent":0, "base":"CODE", "link":"CODE", "rate_pct":150,
           "grades":[0,0,0], "payout_month":1,
           "of":{"group":"earning","cash":"cash|noncash|any","insurance":"included|any"},
           "table":"VNTAX", "cap":"CAPLO"},
 "proration":"none|working_days|calendar_days",
 "frequency":"monthly|annual|adhoc|scheme",
 "sign":1,
 "treatment":{"cash":"cash|noncash","tax":"taxable|exempt|qualified|annual_cap|entitlement|inherit",
              "cap":0,"insurance":"included|excluded|inherit|review","tax_bearer":"employee|employer",
              "pit_deductible":"no|yes|source","source_code":"CODE","employer_share_pct":100}}
```
`validate_recipe` rejects unknown keys/values with plain messages, checks referenced codes exist
and are included, forbids self-reference, and returns the normalised recipe.

### 5.3 Compiler (`models/recipe_compiler.py`) — pure functions, no ORM
`compile_recipe(recipe, ctx) -> (excel_formula_with_letters, needs)` where
`ctx = {letters: {CODE: 'A'}, included: set(codes), rate_tables: set(codes), constants: {CODE: value}}`
and `needs` lists helper inputs the formula requires that do not exist yet (see 5.4).
Lowering rules (all references by letter; parentheses everywhere; only functions from
`FormulaValidator.SUPPORTED_FUNCTIONS` + `BRACKET`):
- audience: `all` → no wrapper; `local` → `IF(ISLOCAL=1, …, 0)`; `foreign` → `IF(ISLOCAL=0, …)`;
  `insured` → `ISINSURED=1`; `union` → `ISUNION=1`; `enrolled` → `<CODE>ENR=1`; `role` → `ROLEGRADE>0`.
- amount: `input` → the rule's own value if it is an input, else the helper input `<CODE>IN`;
  `fixed` → literal; `contract` → `BASIC`; `percent_contract` → `BASIC*p/100`; `percent_of` →
  `<base>*p/100`; `role` → `IF(ROLEGRADE=1,g1,IF(ROLEGRADE=2,g2,IF(ROLEGRADE=3,g3,0)))`;
  `hourly` → `<CODE>HRS*(BASIC/(STDDAYS*HOURSDAY))*rate/100`; `annual_ratio` →
  `IF(PAYMONTH=m, MIN(BASIC, BASIC*SERVDAYS/ANNUALDAYS), 0)`; `linked` → `<link>`;
  `sum_group` → `SUM(<letters of included components matching `of`>)` (or `0` when empty);
  `bracket` → `BRACKET(<table>, <base>)`; `insurance_base` → `MIN(SUM(<insurance-included
  earnings>), <cap>)`.
- proration: `working_days` → `*(PAIDDAYS/STDDAYS)`; `calendar_days` → `*(PAIDCALDAYS/CALDAYS)`.
- frequency `annual` → wrap `IF(PAYMONTH=m, …, 0)` (unless already an annual_ratio); others → none.
- sign −1 → `-( … )`. Rounding: wrap the whole amount in `ROUND(…, 0)` for money kinds.
- Taxable helper (only when `treatment.tax ∉ {taxable, exempt}`): a separate rule `<CODE>TX`
  (group helper, hidden from payslip, `report_visible=False`) with: `qualified` →
  `IF(<CODE>QUAL=1, 0, <CODE>)`; `annual_cap` → `MAX(0, <CODE>-MAX(0, cap-<CODE>YTD))`;
  `entitlement` → `MAX(0, <CODE>-<CODE>ENT)`; `inherit` → `<source>TX` if it exists else
  `<source>`; exempt → contributes nothing; taxable → the component itself.
- Aggregates (recipes on the total rules): GROSS = sum_group earnings cash; NONCASH = sum_group
  earnings noncash; TAXABLE = `MAX(0, SUM(taxable parts) - <PIT-deductible deductions> -
  DEDUCTSELF - DEPS*DEDUCTDEP)`; EEDED = sum_group deductions (excluding PIT and negatives
  handled by sign); NET = `GROSS - EEDED - PIT`; ERCOST = `GROSS + SUM(employer-cost benefits) +
  NONCASH`. These MUST reproduce the Essentials formulas' values exactly for its sample tests.
`regenerate(env, config, reason='refactor')`: order rules topologically by recipe references
(cycle → refuse with the path); for each rule with a recipe: compile; if `bp_formula_source ==
'generated'` and the normalised formula differs → write `excel_formula` + `bp_generated_formula`
+ bump `bp_generated_revision`; if `manual` → write only `bp_generated_formula`. All writes in
`with_context(formula_version_reason=reason, formula_version_seen=set())`. Then
`config.action_regenerate_formulas()` once, `action_validate_formulas()`, and return
`{changed:[codes], problems:[{code, message}]}`. Use `pb.formula.studio._check_formula` before
every write; a rule that fails validation keeps its previous formula and is reported.

### 5.4 Helper inputs (provisioned on demand, never duplicated)
Canonical codes, all `column_type='input'`, `column_role='payroll'`, sensible `default_value`,
`is_visible_in_grid=True`, hidden from payslip: `PAIDDAYS` (paid working days, default = the
config's STDDAYS constant/default or 26), `STDDAYS` (exists in Essentials; create only if
absent, default 26), `CALDAYS` 30, `PAIDCALDAYS` 30, `HOURSDAY` 8, `PAYMONTH` (current month),
`ISLOCAL` 1, `ISINSURED` 1, `ISUNION` 1, `ROLEGRADE` 0, `SERVDAYS` 260, `ANNUALDAYS` 260, and
per-component `<CODE>IN` 0, `<CODE>HRS` 0, `<CODE>ENR` 0, `<CODE>QUAL` 1, `<CODE>YTD` 0, `<CODE>ENT` 0.
Length rule: `<CODE>` + suffix ≤ 12 chars; when it would exceed, truncate the base to fit and
guarantee uniqueness (append a digit). Created through `add_component` semantics (or the same
letter allocation `seed_config` uses — read `formula_config_template.py:213-320` and reuse its
letter allocation, do not invent a second one). Every sample employee gets the new input with the
default value (update `input_values_json` of each `hr.formula.sample.data` — reuse
`save_sample_inputs` logic). Labels are plain: "Paid working days", "Standard working days",
"Hours per day", "Is a local employee (1 = yes)", "Uniform — approved amount this run" etc.

### 5.5 Essentials backfill (`models/essentials_recipes.py`)
A dict `ESSENTIALS_RECIPES` keyed by code for `vn_standard_2026`: inputs BASIC (contract
salary), DEPS, STDDAYS, OTHRS15/20/30, BONUS, ALLOWIN → `{kind:'input'}` recipes with group
earning/helper as appropriate; SIBASE `insurance_base` cap CAPLO; UIBASE cap CAPHI; SIDED/HIDED
`percent_of` SIBASE with the rate constant (express as `base*SIRATE` — extend `percent_of` with
`rate_code` so a constant, not a literal, is used; add that to the schema); UIDED on UIBASE;
SICOMP/HICOMP/UICOMP employer; EEDED sum_group deductions; GROSS sum_group cash earnings;
TAXABLE aggregate; PIT `bracket` VNTAX on TAXABLE; NET; ERCOST. HOURRATE and OTPAY stay manual
(no recipe — they are fine as Excel). Applied by `bp_start` after `seed_config` and by
`bp_components` on first load when every rule has an empty recipe and `template_key ==
'vn_standard_2026'` (backfill is idempotent). **Acceptance: after backfill + regenerate, every
Essentials sample test still passes** (`run_tests` → 0 failed) — this proves the compiler
reproduces the pack.

### 5.6 RPCs (`pb.blueprint.studio`)
- `bp_components(config_id)` → `{ok, groups:{earning:[…],deduction:[…],benefit:[…],inputs:[…],total:[…]},
  removed:[{code,name,group}], counts:{included, removed}, sample_values:{code: value}}`; each row
  `{id, code, name, column_type, letter, source:'generated'|'manual', summary, health:'ok'|'review'|'problem',
  health_text, review:[…], value, locked:bool, template_key}`.
- `bp_component_get(rule_id)` → `{ok, rule:{…}, recipe, display_formula, excel_codes, options:{audiences,
  kinds, bases:[{code,name}], links:[…], sources:[…], months}, provenance:{starter, version}}`.
- `bp_recipe_preview(config_id, rule_id|None, recipe|None, excel_codes|None, sample_id)` → compiles or
  translates codes→letters, validates, and evaluates **without persisting**: inside
  `self.env.cr.savepoint()` write the candidate formula (creating a temporary rule for a new
  component), call `pb.formula.studio.compute_preview`, capture the value, then raise a private
  `_Rollback` exception caught outside so nothing persists. Returns
  `{ok, valid, message, excel_letters, excel_codes, value, needs:[helper codes that would be created]}`.
- `bp_component_save(config_id, rule_id|None, payload)` where `payload = {name, code?, group, lane:
  'guided'|'excel', recipe?, excel_codes?, revision}` → validate → create via `add_component` when
  new → write recipe/formula/source → provision helpers → `regenerate` → `{ok, rule_id, changed,
  problems, revision}`.
- `bp_component_exclude(config_id, rule_ids, confirm=False)` → dependants check → delete →
  regenerate → `{ok, removed:[codes], regenerated:[codes]}` or `{ok:False, reason, blocked_by:[…]}`.
- `bp_component_include(config_id, code)` → reseed from template JSON (component + recipe from
  `ESSENTIALS_RECIPES` or, later, the template's own `recipe` key inside `components_json` — support
  both) → regenerate → `{ok, rule_id}`.
- `bp_component_restore_guided(rule_id)` → recompile, set source generated, write formula.
- `bp_regenerate(config_id)` → full pass (used by "Regenerate all" in the overflow menu).
All mutations bump the blueprint `revision`; all take `revision` and refuse on mismatch.

## 6. Client
Files: `js/step_rules.js` (tab shell), `js/components_tab.js`, `js/sentence_editor.js`,
`js/recipe_text.js` (pure: `summaryOf(recipe)`, sentence option labels, `codeFromName`),
`xml/components.xml`, `xml/sentence_editor.xml`, SCSS in `blueprint.scss` (`pbbp-cmp-*`, `pbbp-se-*`).
Every preview/save goes through the blueprint's `revision`; after any save call the B1 preview
refresh so the hero recomputes (count-up + delta).

## 7. Tests
Python (`tests/test_recipe_compiler.py` pure, `tests/test_components_rpc.py` with a seeded config):
1. compile: contract + working_days → `ROUND((A*(B/C)),0)` with the right letters.
2. compile: hourly 150% → references `<CODE>HRS`, BASIC, STDDAYS, HOURSDAY; `needs` lists missing helpers.
3. compile: audience local wraps in `IF(<ISLOCAL>=1, …, 0)`; helper provisioned once for two rules.
4. compile: annual_ratio month 1 → `IF(<PAYMONTH>=1, MIN(BASIC, BASIC*SERVDAYS/ANNUALDAYS), 0)`.
5. compile: sum_group cash earnings excludes noncash and excluded components; empty → `0`.
6. compile: bracket → `BRACKET(VNTAX, <TAXABLE letter>)`; unknown table → validation error.
7. compile: percent_of with rate_code uses the constant's letter, not a literal.
8. Essentials backfill + regenerate → `run_tests` 0 failed, every value identical to before (snapshot values, compare).
9. manual guard: write `excel_formula` via plain ORM → source flips to manual; regenerate leaves it, refreshes `bp_generated_formula`.
10. restore guided → formula equals generated; source generated.
11. exclude with generated dependants → dependants regenerated (GROSS no longer references it); with a manual dependant → refused, `blocked_by` names it.
12. include (restore) a starter component → recipe present, letters new, aggregates include it again.
13. preview never persists: `bp_recipe_preview` on a new component leaves `rule_count` unchanged and the value equals a subsequent save's preview.
14. vocabulary coverage: a fixture recipe for EACH of the 38 workbook components (codes per the plan's list, e.g. UNIFORM annual_cap, SEVERSTAT entitlement, TRANSPORT role + working_days, PREMINSALW linked, OTWD hourly 150, MONTH13 annual_ratio, ADJDEDUCT sign −1 inherit, UNIONDUES percent_of SIBASE 0.5% with cap, PIT bracket, SHUILOCAL employer percent) compiles and validates on a config seeded from Essentials.
15. revision conflict; cross-company refusal; white-label/vocabulary scan extended to the new files.
Hoot (`static/tests/recipe_text.test.js`): `summaryOf` for six recipes; `codeFromName("Site allowance") == "SITEALLOW"`-style rule (≤12, letters/digits); sentence option labels have no code words.

## 8. Deploy + verify
Ledger ritual: tests on p9clone (`-u pb_blueprint --test-enable --test-tags /pb_blueprint`), `pg_dump`
each DB, `-u pb_blueprint` on p9clone → payobook → abm → payobook_template, asset purge + version bump,
tree-hash + `latest_version` check, Chrome walkthrough on payobook (company Payobook Vietnam JSC)
and abm. Bump `pb_blueprint` to `19.0.1.1.0`.

## 9. Acceptance cases (Chrome, report PASS/FAIL with evidence)
1. Components tab lists Essentials in the five groups with correct counts; sample values shown.
2. Open BASIC → sentence reads "For everyone, calculate the contract salary…"; change proration to paid working days → generated formula updates; proof strip shows the reduced value; Save → hero take-home drops with the delta chip.
3. Excel lane on SIDED: type `=MIN(BASIC, CAPLO)*SIRATE*2` → valid → Save → row badge "Written as Excel"; hero changes; Guided lane shows the restore banner; Restore → back to generated.
4. Type an invalid formula → rose message, Save disabled; close → previous formula intact.
5. Add component "Site allowance" fixed 2,000,000 taxable cash → appears under Earnings, GROSS/NET include it (hero up by 2m minus tax effects), payslip visibility default on.
6. Remove Site allowance → confirmation (custom) → gone; hero back.
7. Untick BONUS → moved to the removed tray; GROSS regenerated; Restore → back with recipe.
8. Try to remove SIBASE → refused (used by manual/other rules) with the names inline.
9. Bulk: shift-select three earnings → Remove → tray shows 3 → Include all → back.
10. Keyboard: ↑↓ Space Enter Esc work; ⌘/Ctrl+F focuses search; ⌘/Ctrl+Enter saves the editor.
11. Search "ins" → filters across groups; clear → all back.
12. Audience "local employees" on ALLOWIN → helper input "Is a local employee" appears under Inputs with default 1; set it to 0 in the sample inputs dialog → allowance drops to 0 in the hero.
13. Hourly rule on a new component "Weekend overtime" 200% → `WEEKENDHRS` input provisioned; set 10 hours → value = BASIC/(STDDAYS×8)×2×10.
14. Annual rule "13th month" month 1 → value 0 now (PAYMONTH default ≠ 1) → set PAYMONTH 1 → value = BASIC.
15. Run the Essentials tests from the grid (Formula Studio → Test) → still all passing after backfill.
16. Config with no sample → proof strip guidance; add sample → works.
17. Concurrent edit: change the draft from a second tab → save in the first → reload prompt.
18. 390px: rows stack (checkbox, name, dot, Configure), editor is full-screen sheet, no horizontal scroll.
19. Thin Tax & Calendar tabs render with the "Open the grid" door.
20. All four DBs on 19.0.1.1.0; white-label scan passes; no "schema/blueprint/config" on screen.

## 9b. Addendum after the B1 report (binding)

- **B1's actual layout** (build on it): server `pb_blueprint/models/blueprint.py` (model),
  `blueprint_studio.py` (façade `pb.blueprint.studio` with `_config/_guard/_plain/_blueprint`
  helpers and `bp_templates, bp_start, bp_load, bp_save, bp_close, bp_preview, bp_sample_inputs,
  bp_save_sample_inputs, bp_add_sample, bp_restart, bp_finish, bp_discard, bp_studio_action,
  bp_steps`), `formula_studio_ext.py`, `formula_config_ext.py`; client `static/src/js/{blueprint,
  blueprint_steps, pay_preview, sample_inputs_dialog, step_start, step_thin, step_finish}.js`,
  `xml/{blueprint,pay_preview,steps}.xml`, `scss/blueprint.scss`; tests `tests/test_blueprint.py`,
  `tests/test_white_label.py`, `static/tests/blueprint_steps.test.js`. Reuse `_guard` for every new
  RPC; every failure returns `{'ok': False, 'reason': …}` via `_plain`.
- **Doors are opened BY TAG** (`doAction({type:"ir.actions.client", tag:"pb_blueprint", params})`),
  never by xmlid (BP14). Root class is `pbim pbbp` (BP11); read tokens as `var(--pbim-*, literal)` (BP12).
- **`net_role` is populated by `classify_net_roles()`** which `bp_start` already calls (BP16); the
  Components tab may rely on it for rules without a recipe, and should re-run it after regenerate.
- **BP-R12 (new ruling): fix the static formula lint so it knows `BRACKET`.** `hr.formula.rule.is_valid`
  flags `=BRACKET(VNTAX, AE)` as "Unsupported function" while the engine computes it correctly, so every
  Vietnam-pack configuration shows "2 errors" on its picker card and `has_errors=True`. Fix it in
  `pb_hr_payroll_formula` at the compute (expand `BRACKET` through `hr.formula.rate.table.expand_brackets`
  before calling `FormulaValidator.validate_formula`, exactly as `_check_formula` does; an unknown table
  remains an error with a plain message). Add a test; bump `pb_hr_payroll_formula`; deploy it with this
  phase; report the count of configurations per DB whose `has_errors` flipped True→False (expected: every
  VN-pack one) and confirm `bp_finish` still uses its conversion check. Do NOT widen `SUPPORTED_FUNCTIONS`
  with a fake `BRACKET` entry — expansion is the correct fix.
- Validator user `look.p4@payobook.com` (password in the B1 report §10) stays active through B6; use it.
- The two demo configurations B1 left on payobook stay (owner will decide at closeout); create your own
  walkthrough drafts with a "B2" prefix and discard them through the product's own path when done.

## 10. Report (`docs/handovers/BLUEPRINT_PHASE_B2_REPORT.md`)
Results 1–20 with evidence; the final recipe schema as implemented (paste the JSON); the helper
input codes created for Essentials after the walkthrough and their defaults; the 38-component
vocabulary fixture (so B3 can lift it verbatim); `excel_formula_display` behaviour found; any
compiler expression you could not make the validator accept and how you solved it; gotchas
appended as BP-numbers; self-score against the design bar; deferred items with reasons.
