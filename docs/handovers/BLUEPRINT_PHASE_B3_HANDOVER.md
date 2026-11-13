# BLUEPRINT Phase B3 — Tax & protection, Calendar & payment, and the Vietnam · Complete starter

Read `docs/handovers/BLUEPRINT_LEDGER.md` FULLY (all rulings + gotchas through whatever B2
appended), then `BLUEPRINT_PHASE_B1_REPORT.md` and `BLUEPRINT_PHASE_B2_REPORT.md` (the recipe
schema as implemented, the helper-input codes, the 38-component vocabulary fixture, the BRACKET
lint fix), then `BLUEPRINT_PLAN.md` §"Step 2 · Pay rules" (Tax & protection, Calendar & payment)
and the owner decision on the two Vietnam starters. B1+B2 code is the base — extend it.

## 1. Goal (plain English)

Two more tabs on **Pay rules** become real, and the starter the owner asked for arrives.

- **Tax & protection**: one calm page that shows where the tax and insurance values come from
  (the 2026 rule pack), lets the person edit the income-tax bands and the reliefs and the
  insurance caps and rates, try an income and see the tax, and pull in the pack's values again
  if they drift. Every edit changes the take-home number on the right, live.
- **Calendar & payment**: the payroll calendar (input cut-off, payday rule, late-input policy)
  with a real "next payday" preview from the company's own work calendar, the payment currency and
  bank identifier type, and a door to the existing Pay & Deliver bank layouts.
- **Vietnam · Complete**: a second Vietnam starter with the full library of 38 workbook
  components, every one carrying a guided sentence, pre-selected on the Start step.

## 2. Scope — in
- Tax tab UI + RPCs (`bp_tax_data`, `bp_tax_save_bands`, `bp_tax_save_values`, `bp_tax_sync_pack`).
- Calendar tab UI + RPCs (`bp_calendar_data`, `bp_calendar_save`, `bp_calendar_preview`).
- Compiler extensions needed by the Complete library (§5.3): `pit_vn` routes, benefit employee
  share, plan totals excluded from employer-cost aggregate, employer-borne tax recorded as a
  review item.
- `pb_blueprint/data/config_template_vn_complete.xml` (`hr.formula.config.template`, code
  `vn_complete_2026`) with recipes inside `components_json`, rate table, 5 persona sample tests;
  Start step default → Complete when present (B1 already prefers `vn_complete_2026`).
- Tests, deploy ×4 DBs, Chrome validation, commits, gotchas, report.

## 3. Scope — binding non-goals
- No Mapping/Payslip round-trips (B4); no outputs table/test runner (B5); no VI (B6).
- Do not implement employer-paid tax gross-up (the prototype's 32 helper columns): record it
  as a review item (§5.3.4). Do not implement guaranteed-net contracts.
- Do not change `pb_pack_vn` or `vn_standard_2026`. Do not change the legislation pack model.
- Do not invent bank fields; the bank section is preferences + a door.
- Do not add a `legislation_pack_id` to `hr.formula.config` (BP-R5: pin on the blueprint).

## 4. Design (bar: "extreme WOW, intuitive, out-of-this-world experience, best in class")

### 4.1 Tax & protection tab
Eyebrow "02 / SHARED RULES, CLEARLY CONNECTED", H1 **"Tax and protection, in context."**, lead
"Choose the rule pack once. See where it comes from, when it applies, and what it changes in
someone's pay."

**Rule pack card** (top, full width, `#EDEAF8` tint): pack name + version + "effective 1 Jan
2026" + authority line (from `hr.formula.legislation.pack.authority`), state chip
("Aligned with the pack" green / "3 values differ from the pack" amber / "No pack for this
country" grey), button **Use the pack's values** (amber state only; opens a kit modal listing
each differing value: label, current, pack value, delta; Confirm → `bp_tax_sync_pack`), link
"Where these values come from" (opens the pack's `authority`/`description` in a popover).
The pack is the newest **published** pack for the configuration's country whose
`effective_date` ≤ the blueprint's `effective_from` (fallback: newest published). Its id and
version are stored on the blueprint (`pack_id`, `pack_version`) the first time the tab loads.

**Income tax bands** card: table "Monthly assessable income from · to (derived) · rate", one
row per bracket of the configuration's progressive rate table (the table the PIT rule's
`BRACKET(<code>, …)` references; if several tables exist, a segmented picker above the table).
Editing: inline number inputs (from, rate %), the "to" column derived from the next row's "from"
(last row "No upper limit"), so overlaps are impossible by construction; **+ Add band** appends;
a row's trash removes it; rows re-sort by "from" on blur; the first row's "from" is locked at 0.
Validation inline: duplicate "from" → "Two bands start at the same amount"; rate outside 0–100 →
"A rate is a percentage between 0 and 100". **Save bands** (primary, disabled until changed and
valid) → `bp_tax_save_bands` → hero recomputes. Under the table: **"Try an income"** — a slider
(0 → 200,000,000 VND, step 500,000) + number field; beside it "Income tax **4,500,000 VND** ·
effective rate 11.3%"; computed client-side with the same marginal arithmetic as
`compile_brackets_excel` (pure helper `taxFor(brackets, income)`, hoot-tested against three
hand-computed values) and labelled "After relief and deductible contributions".

**Relief before tax** card: Personal relief (VND/month), Per registered dependant (VND/month) —
number inputs bound to the constant rules resolved via the template's `legislation_code` mapping
(`DEDUCTSELF`, `DEDUCTDEP`) → `bp_tax_save_values`.

**Insurance follows eligibility** card: SI/HI salary ceiling (CAPLO), UI salary ceiling
(CAPHI); employee rates SI/HI/UI and employer rates SI/HI/UI as percent inputs (SIRATE HIRATE
UIRATE SIEMPR HIEMPR UIEMPR); two segmented choices stored on the blueprint's `calendar_json`?
No — on a new `tax_json`: insurance basis (contractual eligible pay / actual eligible pay) and
rounding (nearest whole VND / round down) — both are **displayed and stored** and wired into the
compiler where the recipe schema already supports them (rounding: `ROUND` vs `ROUNDDOWN`;
basis: which components feed `insurance_base`) — state in the report exactly what each does.
Note under the card: "Foreign employees use a distinct eligibility plan. Unemployment insurance
is excluded for them." Link **Review insurance components** → jumps to the Components tab
filtered to the insurance rules.

**Other tax routes** (disclosure, closed by default): non-resident flat rate (NONRESRATE),
short-contract withholding rate (SHORTRATE) and threshold (SHORTTHRESH) — shown only when
those constants exist on the configuration (Complete has them; Essentials does not — then the
disclosure says "This configuration taxes every employee as a resident. The Complete starter
adds non-resident and short-contract routes.").

Every value input has a "pack: 15,500,000" ghost hint when it differs from the pack; a
one-click "↺ pack value" chip restores it. All saves are optimistic-revision guarded, write
through `formula_version_reason='legislation'` (values) / the rate-table save path (bands), and
end with the hero refresh. Read-only when the configuration is not `draft` (banner "This
configuration is active. Values are managed from the grid.").

### 4.2 Calendar & payment tab
Eyebrow "02 / FROM APPROVED PAY TO PAYDAY", H1 **"Close the loop on payday."**, lead
"Calculations, bank files and payslips have different jobs. Connect them without mixing payment
details into payroll formulas."
A five-node flow strip (Approved inputs → Calculation → HR + Finance review → Bank release →
Payslip), muted, with the current configuration's cycle label under "Calculation".

**A calendar people can rely on** card: Monthly input cut-off day (1–28, number), Planned
payday (segmented: second-last working day · last working day · a fixed day [1–31]), Late
variable inputs (segmented: next cycle with traceable carry-forward · separate off-cycle approval
· controlled reopen with HR + Finance). Under it a live line from `bp_calendar_preview`:
"**Friday 27 March 2026** is the next payday in the company calendar (weekends and 1 public
holiday skipped)." — computed server-side from `res.company.resource_calendar_id` attendance
weekdays and `resource.calendar.leaves` with `resource_id = NULL` (public holidays), for the
month after the blueprint's `effective_from` (or the current month if that is past). If the
company has no calendar: "Set the company's working calendar to get an exact date; weekends
only are skipped for now."

**Payment destination** card: Payment currency (read-only chip = configuration currency, with
"Paid in another currency? The bank layout converts at release; this configuration calculates in
VND"), Bank identifier type (segmented: domestic bank code · SWIFT/BIC), and a door **Open bank
file layouts** → `doAction({type:"ir.actions.client", tag:"pb_pay_delivery"}, {additionalContext:
{pb_back: {label:"New configuration", tag:"pb_blueprint", context:{config_id}}}})`, guarded by
`registry.category("actions").contains("pb_pay_delivery")` (hidden otherwise). Text: "Account
numbers stay text, leading zeros preserved. No file is sent from here."
All choices persist to the blueprint's `calendar_json` via `bp_calendar_save`; the Finish step
shows them (B6 polishes).

### 4.3 The Start step with two Vietnam starters
Cards: **Vietnam · Complete** ("All 24 earnings, 8 deductions and 6 benefits from the standard
workbook, each with a guided rule. Remove what you don't need." · "v2026.1 · effective 1 Jan
2026" · "6x components · 1 rate table") pre-selected; **Vietnam · Essentials** (existing card,
renamed on the card only via the template's `name` — do NOT rename the pb_pack_vn record; if the
registry name must stay "Vietnam Standard 2026", show it as is and add the subtitle "Essentials:
basic, overtime, insurance, tax, net"); then Import Excel workbook; Blank canvas. The note under
the grid names the selected starter.

### 4.4 Zero dead-ends
no pack for the country → grey chip + editing still works · pack items whose codes have no rule
(unmatched) → listed under "Not used by this configuration" in the sync modal, never written ·
rate table missing (blank canvas) → bands card says "No income-tax table yet. Add one from the
grid, or start from a Vietnam starter." · invalid band edits → inline, Save disabled · company
without a work calendar → weekends-only note · Pay & Deliver not installed → door hidden, text
stays · non-draft configuration → read-only banner.

## 5. Server design

### 5.1 Tax RPCs (`pb.blueprint.studio`)
- `bp_tax_data(config_id)` → `{ok, pack:{id,name,version,effective_date,authority,description,state}|None,
  status:'aligned'|'drift'|'na', drift:[{code,label,current,target,delta,rule_id,number_format}],
  unmatched:[{code,label,target}], tables:[{id,code,name,brackets:[{lower,rate}], used_by:[codes]}],
  values:{relief:{DEDUCTSELF:{rule_id,value,pack,label}, DEDUCTDEP:…}, insurance:{CAPLO,CAPHI,SIRATE,HIRATE,
  UIRATE,SIEMPR,HIEMPR,UIEMPR}, routes:{NONRESRATE,SHORTRATE,SHORTTHRESH}|None}, prefs:{basis,rounding},
  editable:bool, revision}`.
  Resolution of pack item → rule: first a rule whose `legislation_code` matches (check whether
  `hr.formula.rule` stores `legislation_code` from `seed_config`; if it does not, derive the map
  from the template's `components_json` for `blueprint.template_key`, and for imported/blank
  configs fall back to `_legis_constant` by code). State which in the report. Reuse
  `pb.formula.studio._legis_eval` where it fits; do not copy its logic if you can call it.
- `bp_tax_save_bands(config_id, table_id, brackets, revision)` → validates (ascending unique
  `lower`, first 0, rates 0–1), calls `pb.formula.studio.save_rate_table(config_id, {...})`
  (BP3: ids change), regenerates (B2 `regenerate`), returns `{ok, brackets, revision}`.
- `bp_tax_save_values(config_id, values:{code: number}, prefs:{basis, rounding}, revision)` →
  writes `constant_value` with `formula_version_reason='legislation'`, stores prefs in
  `tax_json`, regenerates if prefs changed anything the compiler reads → `{ok, revision}`.
- `bp_tax_sync_pack(config_id, revision)` → applies every drifted matched item (reuse
  `legislation_apply` if its guards allow a draft; otherwise the same writes + milestone) →
  `{ok, applied:[codes], revision}`.
### 5.2 Calendar RPCs
- `bp_calendar_data(config_id)` → `{ok, calendar:{cutoff_day, payday_rule, payday_day, late_inputs},
  payment:{currency, bank_id_type}, preview:{date, weekday, skipped_weekends, skipped_holidays, calendar_name}|None,
  doors:{pay_delivery:bool}}`.
- `bp_calendar_save(config_id, calendar, payment, revision)` → validates ranges → `calendar_json`.
- `bp_calendar_preview(config_id, month=None)` → the payday computation above (pure helper
  `payday_for(rule, day, year, month, workdays:set[int], holidays:set[date])` unit-tested).
Blueprint model: add `tax_json` Text (prefs) — `calendar_json` exists from B1.

### 5.3 Compiler extensions (extend B2's schema; keep B2's tests green)
1. `amount.kind = 'pit_vn'`: `{table, base, routes:{nonres_rate:'NONRESRATE', short_rate:'SHORTRATE',
   short_threshold:'SHORTTHRESH', resident_input:'ISRESIDENT', months_input:'CONTRACTMTH',
   commit_input:'TAXCOMMIT', gross_base:'TAXGROSS'}}` → `IF(ISRESIDENT=0, ROUND(TAXGROSS*NONRESRATE,0),
   IF(CONTRACTMTH<3, IF(AND(TAXGROSS>=SHORTTHRESH, TAXCOMMIT=0), ROUND(TAXGROSS*SHORTRATE,0), 0),
   ROUND(BRACKET(<table>, <base>),0)))` with letters. `TAXGROSS` = the sum of taxable parts before
   relief (a `sum_group` helper the Complete template defines).
2. Benefit with `employer_share_pct < 100`: the compiler provisions `<CODE>EE` (deduction, group
   deduction, name "<name> — employee share") = `ROUND(<premium>*(100-share)/100,0)` and the
   benefit's own value = employer share only.
3. `treatment.plan_total = true` on a benefit → its recipe is `sum_group` over other employer-cost
   components (with an audience wrapper) and it is **excluded** from the ERCOST aggregate
   (`net_role_detail` set True after classification, or the aggregate filter `of.exclude_plan_totals`).
4. `treatment.tax_bearer == 'employer'` → no arithmetic change; the rule carries a review item
   "Employer-paid tax on <name>: this version taxes the value to the employee; the employer-borne
   top-up is a later recipe." surfaced by `bp_components` (amber) and later by Finish.
5. `treatment.tax == 'annual_cap'` etc. already exist from B2; `sign: -1` exists. Verify with the
   38-component fixture from the B2 report — every one must compile on the Complete template.

### 5.4 The Vietnam · Complete template (`data/config_template_vn_complete.xml`)
`hr.formula.config.template`: `code vn_complete_2026`, `name "Vietnam · Complete"`, `country_code
VN`, `flag` as the VN pack uses, `version 2026.1`, `effective_date 2026-01-01`, `state draft`,
`sequence` lower than the pack's so it lists first, `description` (plain, no "Odoo"),
`legislation_refs_json` copied from the VN pack, `rate_tables_json` = the VN pack's VNTAX
(7 brackets — the pack is the truth; the owner's 5-band question is logged, see §8),
`components_json` = spine + library, each component carrying `"recipe": {…}` (B2 confirmed
`bp_component_include` reads a template component's `recipe` key) and `legislation_code` where
the pack owns the value. Letters: allocate sequentially like the pack does; inputs first, then
constants, then formulas in dependency order.
**Spine** (from Essentials, same codes/letters where possible): inputs BASIC, DEPS, STDDAYS,
PAIDDAYS (26), HOURSDAY (8), PAYMONTH, ISLOCAL (1), ISINSURED (1), ISUNION (1), ISRESIDENT (1),
CONTRACTMTH (12), TAXCOMMIT (0), ROLEGRADE (0), SERVDAYS (260), ANNUALDAYS (260); constants
DEDUCTSELF, DEDUCTDEP, SIRATE, HIRATE, UIRATE, SIEMPR, HIEMPR, UIEMPR, CAPLO, CAPHI, UNIONCAP
(253,000), UNIONRATE (0.005), UNIONEMPR (0.02), NONRESRATE (0.2), SHORTRATE (0.1), SHORTTHRESH
(5,000,000); helpers SIBASE, UIBASE, TAXGROSS, TAXABLE; totals GROSS, NONCASH, EEDED, PIT, NET,
ERCOST. Drop Essentials' OTHRS15/20/30, MULT15/20/30, HOURRATE, OTPAY, BONUS, ALLOWIN (the
library replaces them).
**Library — 24 earnings** (code · recipe essentials): BASIC is the contract salary input itself
(recipe input, working_days proration applied in a helper? No: BASIC stays the input; the paid
amount is `BASICPAY` = contract × PAIDDAYS/STDDAYS, earning, taxable, insurance included — and
GROSS/insurance base use BASICPAY, not BASIC); UNIFORM (input, adhoc, tax annual_cap 5,000,000
with `UNIFORMYTD`); SEVERSTAT (input, adhoc, entitlement `SEVERSTATENT`); OTHEREXEMPT (input,
adhoc, qualified `OTHEREXEMPTQUAL`); ALENCASH (input, adhoc, qualified); TRANSADD (input,
monthly, taxable); TRANSPORT (role grades 500k/800k/1.2m, working_days, taxable); PHONE (role
grades 200k/300k/500k, working_days, taxable); PRIVINSALW (input, audience foreign, taxable,
insurance `review`); PREMINSALW (linked PRIVHLTHDEP, noncash, taxable, tax_bearer employer);
LOGISTINC, AGSINC, LAUNCHINC, VARBONUS, REFERINC, OTHERTAX (inputs, taxable, frequencies per the
workbook); ADJADD (input, tax inherit, source_code empty → review); ADJDEDUCT (input, sign −1,
inherit); NONCASHBEN (input, noncash, taxable); OTWD (hourly 150), OTWE (hourly 200), OTHO (hourly
300), NIGHTPREM (hourly 30) — all `qualified` exempt with `<CODE>QUAL` default 1 (the workbook says
"PIT exempt for qualifying OT": the premium above the normal rate is exempt — implement as the
whole line exempt when qualified, and note it as a review item "Confirm which part of overtime
is tax-exempt"); MONTH13 (annual_ratio, month 1, taxable).
**8 deductions**: SIDED, HIDED (percent_of SIBASE × rate constant, audience insured), UIDED
(percent_of UIBASE, audience local+insured — express as audience `local` plus `insured` flag:
extend audience to accept a list, or use `IF(AND(ISLOCAL=1,ISINSURED=1)…)` via a new audience
value `local_insured`), UNIONDUES (percent_of SIBASE × UNIONRATE, cap UNIONCAP, audience union,
pit_deductible no), PIT (`pit_vn`), ADVANCE (input, pit_deductible no), PRIORDED (input,
pit_deductible source with `PRIORDEDAPP`), OTHERDED (input). SI/HI/UI employee contributions are
PIT-deductible (`pit_deductible: yes`) so TAXABLE subtracts them.
**6 benefits**: SHUILOCAL (plan_total over SICOMP+HICOMP+UICOMP, audience local), SIHIFOREIGN
(plan_total over SICOMP+HICOMP, audience foreign), PRIVHLTHEMP (premium input `PRIVHLTHEMPIN`,
audience enrolled `PRIVHLTHEMPENR`, employer share 100, noncash, taxable, tax_bearer employer),
PRIVHLTHDEP (same shape, linked from PREMINSALW), UNIONMEMB (percent_of SIBASE × UNIONEMPR,
audience union, employer cost), OTHERBEN (premium input, employer share 100, review "Configure a
named plan or remove this placeholder"). Employer statutory costs SICOMP/HICOMP (audience insured)
and UICOMP (local_insured) are part of the spine (benefit group).
**Sample tests** (5 personas, `pack_version 2026.1`, `tol 1.0`): "Full month · local" (BASIC
30,000,000, DEPS 1, PAIDDAYS 26), "Joined mid-month" (PAIDDAYS 13), "Foreign · non-resident"
(ISLOCAL 0, ISRESIDENT 0, DEPS 0, ISUNION 0), "Short contract" (CONTRACTMTH 2, BASIC 6,000,000,
ISINSURED 0, ISUNION 0), "Enrolled in private health" (PRIVHLTHDEPENR 1, PRIVHLTHDEPIN 2,000,000).
Expected values are produced by the engine at authoring time, then **three numbers per persona
hand-verified in the report** (e.g. Full month: SIDED = 8% × min(30m, 46.8m) = 2,400,000;
TAXABLE = 30m − 3,150,000 − 15.5m − 6.2m = 5,150,000; PIT = 5,150,000 × 5% = 257,500; NET =
30m − 3,150,000 − 257,500 = 26,592,500 — matches the Essentials pack's "Mid 30M, 1 dep"). The
certification harness the pack uses must pass for Complete on install (find how `pb_pack_vn`'s
`post_init_hook` runs it and run the same for `vn_complete_2026`; report the result).

## 6. Client
Files: `js/tax_tab.js`, `js/calendar_tab.js`, `js/tax_math.js` (pure: `taxFor`, `bandRows`,
`validateBands`), `xml/tax_tab.xml`, `xml/calendar_tab.xml`, SCSS `pbbp-tax-*`, `pbbp-cal-*`;
`step_rules.js` mounts them in place of the thin panels; `step_start.js` unchanged except the
subtitle for Essentials. Hoot: `static/tests/tax_math.test.js` (three hand-computed tax values,
derived "to" column, overlap impossibility, `payday` helper mirrored client-side only if you
duplicate it — prefer server-only).

## 7. Tests (Python)
1. `bp_tax_data` on an Essentials draft: pack resolved (`legis_pack_vn_2026`), status aligned, 7
   brackets, all 10 values matched via legislation_code mapping (SIRATE ↔ EESI etc.), routes None.
2. Band save: reorder + rate change → rate table rebuilt, PIT recomputed on the sample (assert the
   new PIT for a known income), revision bumped; invalid (duplicate lower / rate 1.5) refused.
3. Value save with reason legislation → `hr.formula.rule.version` row with that reason.
4. Drift + sync: change DEDUCTSELF → status drift, sync restores, `hr.formula.legislation.application`
   (or whatever `legislation_apply` logs) recorded.
5. Non-draft configuration → `editable False`, saves refused.
6. Calendar preview: weekend-only company → second-last working day correct for a month ending on
   a weekend; with a global leave on the target day → skipped; fixed day 31 in a 30-day month →
   last day.
7. Compiler: `pit_vn` routes (resident/non-resident/short with and without commitment);
   employee-share deduction provisioned; plan totals excluded from ERCOST.
8. Complete template: seeds with the expected component count (spine + 38 + provisioned helpers —
   state the exact number), every formula converts, all 5 sample tests pass through
   `run_tests`, hand-verified values equal the engine's.
9. Complete + include/exclude round trip (B2 RPCs) on OTWD and PRIVHLTHDEP; UNIONDUES cap applied.
10. White-label + vocabulary gate covers the new files and the template's user-visible names/descriptions.

## 8. Owner questions to log in the report (do not block on them)
- The workbook proposes a **5-band** 2026 schedule (Law 109/2025, effective 2026-07-01); the
  shipped pack carries **7 brackets**. B3 ships the pack's 7 and makes editing trivial; the owner
  decides which is right for July 2026 onward (a new pack version is the proper vehicle).
- Union dues 0.5% vs 1% (workbook conflict): 0.5% shipped, review item on UNIONDUES.
- Overtime exemption scope (whole line vs premium part): whole line when qualified, review item.

## 9. Deploy + acceptance
Ritual per ledger; bump `pb_blueprint` to `19.0.1.2.0` (plus `pb_hr_payroll_formula` if the
compiler needed an engine change — avoid). Chrome cases (report PASS/FAIL with evidence):
1. Start step shows Vietnam · Complete first and pre-selected; Essentials second; create a draft
   from Complete → footer "Vietnam · Complete · N components"; hero shows a sensible take-home
   (state the number) with the four lines.
2. Tax tab: pack card aligned; bands table 7 rows with derived "to"; try-income slider at
   40,000,000 → tax and effective rate shown; hand-check the number.
3. Edit band 2 rate 10 → 12, Save → hero PIT changes; reload → persisted; version row reason.
4. Add a band starting at 3,000,000 → sorts into place; duplicate start → inline error, Save off.
5. Personal relief 15.5m → 11m → status "1 value differs", ghost hint "pack: 15,500,000", ↺ chip
   restores; sync modal lists the difference and applies.
6. Insurance: CAPLO 46.8m → 20m → SIDED on the sample drops (hero deductions change).
7. Routes disclosure: Complete shows the three values; an Essentials draft shows the
   explanatory sentence instead.
8. Calendar: cut-off 25, second-last working day → preview names a real date, weekends and the
   public holiday counted; fixed day 31 → last day of the month; late-input policy persists.
9. Pay & Deliver door opens the cockpit with a back chip that returns to the journey at the
   Calendar tab.
10. Components tab (B2) on Complete: 38 library rows in their groups; open TRANSPORT → role
    sentence with three grades; open PIT → sentence reads as the tax route (read-only amount with
    "Edit bands on the Tax tab" link); open PREMINSALW → linked sentence + amber review item text.
11. Non-draft configuration (activate a test draft via the grid) → both tabs read-only banner.
12. Blank canvas → bands card guidance; values cards show only the constants that exist.
13. 390 px: tables scroll inside their cards; sliders usable; no sideways page scroll.
14. All four DBs on the new versions; Complete template present on each (`hr.formula.config.template`
    count +1); vocabulary gate green.

## 9b. Addendum after the B2 report (binding — supersedes conflicting lines above)

- **Use B2's code as it is.** Server: `pb_blueprint/models/blueprint_components.py` (RPCs
  `bp_components, bp_component_get, bp_component_get_new, bp_recipe_preview, bp_component_save,
  bp_component_exclude, bp_component_include, bp_component_restore_guided, bp_regenerate, bp_set_tab`
  + helpers `_template_recipes`, `_apply_recipes`, `_provision_helpers`, `_seed_samples_with`,
  `_display_formula`, `_codes_to_letters`), `recipe_schema.py` (`KINDS`, `validate_recipe`,
  `review_items`, `helper_code`, `HELPER_INPUTS`, `HELPER_SUFFIXES`), `recipe_compiler.py`
  (`compile_recipe`, `taxable_helper_formula`, `build_ctx`, `dependency_order`, `regenerate`,
  `derived_group`), `essentials_recipes.py`, `workbook_vocabulary.py` (`WORKBOOK_COMPONENTS`).
  Client: `components_tab.js`, `sentence_editor.js`, `recipe_text.js`, `step_rules.js`.
- **The schema as implemented** (B2 report §2) has 16 amount kinds: `input fixed contract
  percent_contract percent_of role hourly annual_ratio linked sum_group bracket insurance_base
  taxable_base net_total employer_total manual`; plus `amount.rate_code`, `round` (`none|0|2`),
  `of.income_tax`, `treatment.is_income_tax`, `of.exclude`. `sum_group` emits `(A+G+H)`, not
  `SUM(...)`. **Add `pit_vn` (§5.3.1) as a 17th kind**, and the benefit employee-share + plan-total
  behaviours (§5.3.2–3) as schema extensions with `validate_recipe` coverage; keep B2's 56 tests green.
- **Codes: lift `WORKBOOK_COMPONENTS` verbatim.** The fixture's codes supersede §5.4's list:
  `SALARYPAID` (not BASICPAY), `OTHEREXMP`, `TRANSPADD`, `PHONEALLOW`, `LOGISINC`, `AGROINC`,
  `VARPAY`, `OTHOL`, `SHUIFOREIGN`, `PRIVHLTHEE`, `UNIONER`, and helper names `MTHDAYS`/`PAIDCALD`
  (CALDAYS/PAIDCALDAYS were substrings). The template registry **refuses any code that contains
  another** (`formula_config_template.py:199-208`), so the Complete template's `components_json`
  must satisfy the no-substring rule over its whole set — which means it must **NOT ship the
  per-component helpers** (`OTWDHRS`, `UNIFORMYTD`, …): ship inputs, constants, the 38 components
  and the totals, and let `_provision_helpers` create the suffix helpers at seed time (B2's
  `_apply_recipes` path already does this for template recipes — verify and extend `bp_start`
  so a Complete draft is fully provisioned and sample-seeded before the first preview). Shared
  helper inputs (`PAIDDAYS`, `ISLOCAL`, `ISINSURED`, `ISUNION`, `ISRESIDENT`, `CONTRACTMTH`,
  `TAXCOMMIT`, `ROLEGRADE`, `HOURSDAY`, `PAYMONTH`, `SERVDAYS`, `ANNUALDAYS`) may ship in the
  template as plain inputs if they pass the no-substring check against every other code — test it.
- **`BASIC` becomes group `helper`** in Complete (the contract-salary input), `SALARYPAID` is the
  earning that GROSS and the insurance base read (B2 report §11.2).
- **Rounding**: Essentials recipes use `round: none` to keep the pack's expectations byte-equal;
  Complete's new components default to `round: "0"`. The Tax tab's "rounding" preference maps to
  this field on money components (nearest = `"0"`, down = a new `"down"` value emitting
  `ROUNDDOWN(…,0)` — add it to `ROUNDING` and the compiler).
- **Viewport**: the browser bridge floors the viewport at 500 px on this machine (B2 §11.4);
  exercise the 899 px breakpoint and say so, do not claim a 390 px capture you could not take.
- Gotchas BP18–BP28 are now in the ledger (class-name collisions with `.pbbp-pill`, Enter
  bubbling out of a step, `regenerate` must pass `bp_formula_source` explicitly, helper rules need
  a `helper` group, `_normalize_excel_formula` keeps the leading `=`, hoot cannot read `_t()` at
  module level). Read them before the tax editor.
- Deployed baseline: `pb_blueprint 19.0.1.1.0`, `pb_hr_payroll_formula 19.0.1.124.0` on all four DBs.

## 10. Report (`docs/handovers/BLUEPRINT_PHASE_B3_REPORT.md`)
Results 1–14; the legislation_code resolution path used; the Complete template's final component
list with letters and recipe kinds (table); the five personas' expected values with the
hand-verified numbers; certification-harness result; what "insurance basis" and "rounding" do in
the compiler; the payday algorithm and its inputs; owner questions (§8); files touched outside
pb_blueprint; deploy per DB; gotchas BP-numbers appended; self-score; deferred items with reasons.
