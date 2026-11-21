# BLUEPRINT Phase B2 — report

Built, tested, deployed and Chrome-validated 2026-09-10. Scope delivered in
full; the deferred items in §11 are the ones the handover already assigned to a
later phase, plus one measurement that could not be taken and is named with its
reason.

**Live on all four databases**: `pb_blueprint 19.0.1.1.0`,
`pb_hr_payroll_formula 19.0.1.124.0` (`pb_formula_studio 19.0.1.183.0` and
`pb_import_kit 19.0.1.18.0` unchanged from B1 — no icon was added, so the kit
did not need to ship).

**Tests**: 56/56 Python on p9clone (`--test-tags /pb_blueprint,
/pb_hr_payroll_formula:TestBracketLint`), 0 failed 0 error · 27/27 hoot in the
browser (`@pb_blueprint`), of which 10 are new.

---

## 1. Acceptance cases

| # | Case | Result | Evidence |
|---|---|---|---|
| 1 | Components tab lists Essentials in five groups with correct counts; sample values shown | **PASS** | Earnings 4 · Deductions 4 · Benefits & employer costs 3 · Inputs & fixed values 19 · Totals 7 = **37**, chip "37 included". BASIC 10,000,000, SIDED 800,000, HIDED 150,000, UIDED 100,000 — every value from the real engine. `b2_01_components_1440.png` |
| 2 | Open a rule → sentence; change proration → formula updates; proof strip; Save → hero drops with the delta chip | **PASS** | Ran on **SIDED**, not BASIC — see the note below the table. "For everyone, calculate a percentage of another component at the rate held in Social Insurance Rate (EE) of SI/HI Base (capped), prorated by nothing." Proration → paid working days gave `=((SIBASE*SIRATE)*(PAIDDAYS/STDDAYS))`, proof 800,000. Saved; then paid days 13 of 26 → SI **800,000 → 400,000**, deductions 1,050,000 → 650,000, take-home **8.95m → 9.35m**. `b2_04_editor_sentence_1440.png` |
| 3 | Excel lane: type a formula → valid → Save → "Written as Excel" badge; hero changes; Guided shows the restore banner; Restore → back to generated | **PASS** | `=MIN(BASIC,CAPLO)*SIRATE*2` → proof 1,600,000 (10,000,000 × 8% × 2 ✓). Saved: hero **9.35m → 8.15m**, row badge "Written as Excel", reopening lands on the Excel lane, Guided greys the sentence and offers the banner. Restore → 400,000, hero back to 9.35m with a **+1.2m** chip |
| 4 | Invalid formula → rose message, Save disabled; close → previous formula intact | **PASS** | `=MIN(BASIC, CAPLO` → "A closing bracket is missing.", Save `disabled=true`, unsaved-changes guard on close, row unchanged at 400,000 |
| 5 | Add "Site allowance" fixed 2,000,000 taxable cash → under Earnings, totals include it | **PASS** | Code auto-derived `SITEALLOWANC`, formula `=ROUND(2000000,0)`, proof 2,000,000. Saved: cash earnings 10,000,000 → **12,000,000**, employer cost 12,150,000 → **14,150,000**, hero **+2m** chip, Earnings 4 → 5 |
| 6 | Remove it → confirmation (custom, not restorable) → gone; hero back | **PASS** | *"Remove Site allowance? It is not part of the starting point, so it cannot be restored later."* → hero **−2m** back to 9.35m, Earnings 5 → 4, **no** tray row (correct: it never came from the starter) |
| 7 | Untick BONUS → removed tray; GROSS regenerated; Restore → back with its rule | **PASS** | Tray "1 removed from this configuration · Bonus BONUS Restore"; GROSS became `=(BASIC+ALLOWIN+OTPAY)`. Restore → `=(BASIC+ALLOWIN+OTPAY+BONUS)` with a **new column letter**, chip back to "38 included" |
| 8 | A removal that must be refused, with the names | **PASS** (both kinds) | (a) SIBASE and every total/input has **no checkbox at all**, a lock icon and "Part of every configuration". (b) With OTPAY hand-written to use ALLOWIN, removing ALLOWIN is refused **inline on the row**, not in a toast: *"Used by OTPAY, which is written as Excel. Edit that calculation first."* — and ALLOWIN is still there. `b2_08_refusal_inline_1440.png` |
| 9 | Bulk: multi-select → Remove → tray shows them → Include all → back | **PASS** | Shift-click selected a range of 3 (`b2_09_bulk_1440.png`); ⌘-click toggled to 2; bulk bar "2 selected · Clear · Remove from this configuration"; removed → "36 included · 2 removed", tray listed both; **Restore all** brought both back to "38 included" and the tray disappeared |
| 10 | Keyboard: ↑↓ Space Enter Esc; ⌘/Ctrl+F focuses search; ⌘/Ctrl+Enter saves | **PASS** | ↑/↓ moved focus row to row, Enter opened the editor **and stayed on the step** (it did not, at first — defect 2 in §6), Escape closed it (defect 3), ⌘+F focused the search box. One registration serves ⌘ and Ctrl: the hotkey service maps both to "control" |
| 11 | Search "ins" → filters across groups; clear → all back | **PASS** | 15 hits spanning deductions, benefits, constants and totals (SIDED, HIDED, UIDED, SICOMP, HICOMP, UICOMP, SIRATE, HIRATE, UIRATE, SIEMPR, HIEMPR, UIEMPR, SIBASE, UIBASE, EEDED); group tabs hide and a count line replaces them; "zzzz" → *"Nothing matches “zzzz”."* with a Clear button; clearing restores every tab |
| 12 | Audience "local employees" → helper input appears; set it to 0 → the amount drops out of the hero | **PASS** | `=ROUND(IF(ISLOCAL=1,2000000,0),0)` and, in words, *"This adds one number the payroll will be given: Local employee (1 = yes)."* Saved → hero **9.35m → 11.35m**; the input appears under Inputs & fixed values at 1; setting it to 0 → hero **back to 9.35m**, cash earnings back to 10,000,000. `b2_12_editor_audience_1440.png` |
| 13 | Hourly rule at 200% → hours input provisioned; set 10 hours → the arithmetic checks out | **PASS** | `=ROUND((WEEKENDOVHRS*(BASIC/(STDDAYS*HOURSDAY))*200/100),0)`; needs line named *"Weekend overtime — hours this run"* and *"Hours in a working day"*. 10 hours → **961,538**, and 10,000,000 ÷ (26 × 8) × 2 × 10 = 961,538.46 ✓. Cash earnings 10,961,538 |
| 14 | Annual rule → 0 outside its month; set the month → pays | **PASS** | `=ROUND(IF(PAYMONTH=12,MIN(BASIC,BASIC*SERVDAYS/ANNUALDAYS),0),0)`, value **0** in month 1. Payroll month → 12: **10,000,000**, cash earnings 20,961,538, income tax appears at 240,576.9, take-home **20.07m** |
| 15 | The Essentials tests still pass after the backfill | **PASS** | On a freshly created draft on **payobook**: `run_tests` → **47 total, 47 passed, 0 failed, score 100**, `has_errors = False`. 37 of 37 components carry a rule; 14 are generated formulas |
| 16 | A configuration with no sample → proof strip guidance | **PASS** | Every sample deleted: `bp_components` still `ok` with empty values and `sample_id: false`; `bp_recipe_preview` returns `valid: true, value: null`, which the strip renders as *"Add a sample employee on the right to see a value"* |
| 17 | Concurrent edit → the person is told, and offered the newer version | **PASS** | A save carrying a stale revision returns `{ok: false, conflict: true, reason: "Someone else changed this configuration while you were editing. Reload to see their version."}` and creates nothing. The editor shows it as its own banner with **"Show me their version"** — it was rendered through the wrong panel at first (defect 9 in §6) |
| 18 | 390 px: rows stack, editor is a full-height sheet, no sideways scroll | **PASS** | Rail lies down as a horizontal stepper, group tabs scroll themselves, the health word hides, rows wrap to two lines, the pay panel becomes a bottom bar ("Estimated take-home pay 20.07m"), the editor fills the screen with the sentence wrapping and the disclosure in one column. `scrollWidth === clientWidth` throughout, with and without the editor open. `b2_18_phone_390.png`, `b2_18_phone_editor.png` |
| 19 | Thin Tax & Calendar tabs render with a working door | **PASS** | Tax: *"Tax and the protections that come with pay / The income-tax bands, the reliefs and the insurance caps this configuration uses. / Arrives in the next release — the starter's tax values are already in place and you can see them in the grid."* + **Open the grid**. Calendar likewise. `b2_19_thin_tabs_1440.png` |
| 20 | All four databases on 19.0.1.1.0; white-label scan passes | **PASS** | Versions and tree hashes in §8. A draft was created and walked on the **abm** tenant (rail foot "Saved to AB Mauri", 37 components, hero 8.95m) and discarded through the product's own path. Vocabulary sweep: **10,752 characters** of rendered text across every group tab, both editor lanes, the disclosure, both thin tabs and the Add-component modal — **0** hits for Odoo, schema, blueprint, config, rule set or recipe. **0** console errors. `b2_20_abm_1440.png` |

**20 PASS · 0 FAIL.**

**Case 2 was run on SIDED rather than BASIC**, and the handover's wording could
not be met literally: in the Vietnam · Essentials starter `BASIC` is the
contract-salary **input**, not a formula, so it has no sentence of the form
"calculate the contract salary, prorated by…". The component that *is* that
sentence arrives with Vietnam · Complete in the next phase — it is
`SALARYPAID` in the vocabulary fixture (§4), and the compiler's very first unit
test asserts exactly that formula. What case 2 is really about — change a word,
watch the calculation change, watch the money change — is demonstrated on SIDED
with a number that moves and reconciles.

Screenshots are in `.bp_shots/` (gitignored, not committed), 1440×900 unless the
name says otherwise. The phone shots were taken with the viewport at its
narrowest reachable width through the automation bridge, **500 px** rather than
390; the breakpoint under test (899 px) is well inside that, and the layout was
also read at the 330 px window size, which the browser floors at the same 500.

---

## 2. The recipe schema, as implemented

```json
{
  "v": 1,
  "group": "earning | deduction | benefit | total | helper",
  "audience": "all | local | foreign | insured | union | enrolled | role",
  "amount": {
    "kind": "input | fixed | contract | percent_contract | percent_of | role |
             hourly | annual_ratio | linked | sum_group | bracket |
             insurance_base | taxable_base | net_total | employer_total | manual",
    "value": 0.0,
    "percent": 0.0,
    "rate_code": "SIRATE",
    "base": "SIBASE",
    "link": "PRIVHLTHDEP",
    "rate_pct": 150.0,
    "grades": [0.0, 0.0, 0.0],
    "payout_month": 1,
    "table": "VNTAX",
    "cap": "CAPLO",
    "relief_self": "DEDUCTSELF",
    "relief_dep": "DEDUCTDEP",
    "deps": "DEPS",
    "of": {
      "group": "earning",
      "cash": "cash | noncash | any",
      "insurance": "included | excluded | inherit | review | any",
      "tax": "taxable | … | any",
      "income_tax": "any | exclude | only",
      "pit_deductible": "no | yes | source | any",
      "exclude": ["CODE"]
    }
  },
  "proration": "none | working_days | calendar_days",
  "frequency": "monthly | annual | adhoc | scheme",
  "sign": 1,
  "round": "none | 0 | 2",
  "treatment": {
    "cash": "cash | noncash",
    "tax": "taxable | exempt | qualified | annual_cap | entitlement | inherit",
    "cap": 0.0,
    "insurance": "included | excluded | inherit | review",
    "tax_bearer": "employee | employer",
    "pit_deductible": "no | yes | source",
    "source_code": "BASIC",
    "employer_share_pct": 100.0,
    "is_income_tax": false
  }
}
```

Five additions to the handover's draft, each earned by something that would
otherwise be wrong:

- **`amount.kind: "manual"`** — a component whose Excel is fine as it is
  (`HOURRATE`, `OTPAY`) still has to declare **what it is**, or the totals do not
  know where to put it. Without this, `HOURRATE` — an hourly rate of ~180,000 —
  would have been classified as an earning and summed into gross pay.
- **`amount.rate_code`** — the Vietnam pack keeps 8% in a component called
  `SIRATE`. Referencing the constant rather than baking `8` into the formula is
  what makes "change the rate once, change every rule" true.
- **`round`** — `"none"` throughout the Essentials backfill, because the pack's
  certification expectations were computed without rounding and moving a number
  by half a dong for no reason nobody asked for is not an improvement. New
  components a person adds default to `"0"`.
- **`of.income_tax`** and **`treatment.is_income_tax`** — `EEDED` is "the
  insurance deductions", not "every deduction"; income tax is a deduction that
  this particular total excludes.
- **`amount.kind`** gained the four aggregates (`taxable_base`, `net_total`,
  `employer_total` beside `insurance_base`) so the pack's own totals are
  expressible rather than left as Excel.

**`validate_recipe(recipe, ctx)`** normalises and rejects: an unknown word names
itself and lists the alternatives, a referenced component that does not exist is
named, a self-reference is refused, and a conditional treatment without its
source component is refused. Every message is a sentence.

---

## 3. Helper inputs created for Essentials, and their starting values

The Essentials backfill on its own provisions **none** — every reference its
sentences make already exists in the pack. They appear as the sentences ask for
them. Measured on the walkthrough draft, in the order they were created:

| Code | What it says on screen | Starts at | Asked for by |
|---|---|---|---|
| `PAIDDAYS` | Paid working days | 26 | any rule prorated by working days |
| `ISLOCAL` | Local employee (1 = yes) | 1 | audience local / foreign |
| `HOURSDAY` | Hours in a working day | 8 | any hourly rule |
| `PAYMONTH` | Month being paid (1 to 12) | 1 | anything paid once a year |
| `SERVDAYS` | Days of service this year | 260 | an annual service ratio |
| `ANNUALDAYS` | Working days in a full year | 260 | an annual service ratio |
| `<CODE>HRS` | *"Weekend overtime — hours this run"* | 0 | that component's hourly rule |

The rest of the canonical set — `STDDAYS` (already in the pack), `MTHDAYS`,
`PAIDCALD`, `ISINSURED`, `ISUNION`, `ROLEGRADE` — and the remaining per-component
suffixes `<CODE>IN`, `<CODE>ENR`, `<CODE>QUAL`, `<CODE>YTD`, `<CODE>ENT` are
provisioned the same way by the sentences that need them; all 44 of them are
exercised by the vocabulary test.

Two deliberate renames from the handover's list: **`CALDAYS` → `MTHDAYS`** and
**`PAIDCALDAYS` → `PAIDCALD`**, because `CALDAYS` is a substring of
`PAIDCALDAYS` and the template registry refuses such a set at authoring time
(`formula_config_template.py:199-208`). Harmless on a configuration, fatal in
the starter the next phase has to write.

Every helper is `column_type='input'`, `column_role='payroll'`, hidden from the
payslip, named in words, and **written into every existing sample employee at
the moment it is created** — an input nobody has a value for is a silent zero in
somebody's pay.

---

## 4. The 38-component vocabulary fixture

`pb_blueprint/models/workbook_vocabulary.py` — the next phase can lift it
verbatim. Every one compiles to a letters-only formula on a live Essentials
configuration, asserted by `test_the_whole_workbook_vocabulary_compiles`.

| Workbook row | Code | The sentence |
|---|---|---|
| BASIC_SALARY | `SALARYPAID` | contract salary · prorated by working days · taxable · in the insurance base |
| UNIFORM | `UNIFORM` | approved amount · ad hoc · tax free up to a yearly limit (5,000,000) |
| SEVERANCE_STAT | `SEVERSTAT` | approved amount · ad hoc · tax free within an approved entitlement |
| OTHER_EXEMPT | `OTHEREXMP` | approved amount · ad hoc · tax free with evidence |
| AL_ENCASH_EXEMPT | `ALENCASH` | approved amount · ad hoc · tax free with evidence |
| TRANSPORT_ADD | `TRANSPADD` | approved amount · ad hoc · tax free with evidence |
| TRANSPORT | `TRANSPORT` | amount per grade (1.2m / 800k / 500k) · eligible roles · prorated by working days |
| PHONE_ALLOW | `PHONEALLOW` | fixed 500,000 · prorated by working days |
| PRIVATE_INS_ALLOW | `PRIVINSALW` | approved amount · foreign employees · **insurance still to be decided** |
| PREMIUM_INS_ALLOW | `PREMINSALW` | the same amount as `PRIVHLTHDEP` · enrolled employees · non-cash · by scheme |
| LOGISTICS_INC | `LOGISINC` | approved amount |
| AGS_INC | `AGROINC` | approved amount · by scheme |
| PRODUCT_LAUNCH_INC | `LAUNCHINC` | approved amount · ad hoc |
| VARIABLE_BONUS | `VARPAY` | 10% of the contract salary · by scheme |
| REFERRAL_INC | `REFERINC` | approved amount · ad hoc |
| OTHER_TAXABLE | `OTHERTAX` | approved amount · ad hoc |
| ADJ_ADD | `ADJADD` | approved amount · ad hoc · tax and insurance follow the original component |
| ADJ_DEDUCT | `ADJDEDUCT` | approved amount · **sign −1** · follows the original component |
| NONCASH_BENEFIT | `NONCASHBEN` | approved amount · non-cash · taxable |
| OT_WEEKDAY | `OTWD` | hours × hourly rate at **150%** · tax free with evidence |
| OT_WEEKEND | `OTWE` | hours × hourly rate at **200%** · tax free with evidence |
| OT_HOLIDAY | `OTHOL` | hours × hourly rate at **300%** · tax free with evidence |
| NIGHT_SHIFT | `NIGHTPREM` | hours × hourly rate at **30%** · tax free with evidence |
| THIRTEENTH_MONTH | `MONTH13` | annual service ratio · paid in month 1 |
| EE_SI | `SIDED` | percentage of `SIBASE` at the rate in `SIRATE` · counts against income tax |
| EE_HI | `HIDED` | percentage of `SIBASE` at the rate in `HIRATE` · counts against income tax |
| EE_UI | `UIDED` | percentage of `UIBASE` at the rate in `UIRATE` · local employees |
| UNION_DUES | `UNIONDUES` | 0.5% of `SIBASE` · union members |
| PIT | `PIT` | the amount the `VNTAX` bands give on `TAXABLE` · **is the income tax** |
| ADVANCE | `ADVANCE` | approved amount · ad hoc |
| PRIOR_DED | `PRIORDED` | approved amount · ad hoc · counts against income tax like the original |
| OTHER_DED | `OTHERDED` | approved amount · ad hoc |
| VN_SHUI_LOCAL | `SHUILOCAL` | 21.5% of `SIBASE` · local employees · employer |
| VN_SI_HI_FOREIGN | `SHUIFOREIGN` | 20.5% of `SIBASE` · foreign employees · employer |
| PRIVATE_HEALTH_EMP | `PRIVHLTHEE` | approved amount · enrolled · non-cash · taxable · employer |
| PRIVATE_HEALTH_DEP | `PRIVHLTHDEP` | approved amount · enrolled · non-cash · taxable · employer |
| UNION_MEMBER | `UNIONER` | 2% of `SIBASE` · employer |
| OTHER_BENEFITS | `OTHERBEN` | approved amount · non-cash · **insurance still to be decided** |

Three constraints the codes satisfy, and the test asserts all three: ≤ 12
characters, capital letters and digits only, and **no code contains another** —
Essentials' 37 included. That last one is why the workbook's first row is
`SALARYPAID` and not `BASICPAY` (which contains `BASIC`), and why the variable
bonus is `VARPAY` and not `VARBONUS` (which contains `BONUS`).

The per-component helpers the compiler provisions **do** contain their parent's
code (`UNIFORMYTD`, `OTWDHRS`). That is safe: substrings are harmless to the
converter (MAPFIX settled it, `component_code.py:22-25`), and these are created
on the configuration, never in a template, so the registry's stricter rule never
sees them.

---

## 5. The Essentials backfill, and what it proves

Every generated total is arithmetically identical to the pack's own. Measured on
payobook, on a configuration created through the journey:

| Code | The pack shipped | The sentence produces |
|---|---|---|
| GROSS | `=A1+H1+W1+G1` | `=(A+G+H+W)` |
| SIBASE | `=MIN(A1,Q1)` | *unchanged* — identical after normalising |
| UIBASE | `=MIN(A1,R1)` | *unchanged* |
| SIDED | `=Y1*K1` | `=(Y*K)` |
| EEDED | `=AA1+AB1+AC1` | `=(AA+AB+AC)` |
| TAXABLE | `=MAX(0,X1-AD1-I1-J1*B1)` | `=MAX(0,(A+G+H+W)-(AA+AB+AC)-I-(B*J))` |
| PIT | `=BRACKET(VNTAX,AE1)` | *unchanged* |
| NET | `=X1-AD1-AF1` | `=(A+G+H+W)-(AA+AB+AC+AF)` |
| ERCOST | `=X1+AH1+AI1+AJ1` | `=(A+G+H+W)+(AH+AI+AJ)` |

`SIBASE`, `UIBASE` and `PIT` were **not rewritten**, because the sentence
produces exactly what was already there — regeneration writes only when the
normalised formula actually differs, so those three keep their history clean.

**47 of 47 certification tests pass, score 100, `has_errors = False`.** That is
the whole proof: the same numbers, from rules a person can read.

`sum_group` emits a parenthesised addition chain — `(A+G+H+W)` — rather than the
`SUM(A,G,H,W)` the handover suggested. Semantically identical, one less moving
part (`SUM` has to survive the converter's array-bracket rewrite in
`formula_rule.py:1288`), and it is the shape the pack's own totals are written
in, so a regenerated total reads like the one it replaced. With one member it
degenerates to the bare letter, which is why `MIN(A,Q)` comes out byte-identical
to the pack.

---

## 6. Nine defects the browser found that code review did not

1. **The whole page was blank.** Python's implicit string concatenation across
   lines is a *syntax error* in JavaScript, and it takes the entire backend
   bundle with it: "Uncaught SyntaxError: missing ) after argument list", white
   screen, no component-level failure to trace. Five occurrences. `node --check`
   on every `.js` file now precedes every deploy (**BP26**).
2. **Enter on a component row walked off the step.** The journey shell listens
   for Enter on the whole page and treats it as "continue", so opening a rule
   also advanced to Connect. A real bug in front of a user (**BP20**).
3. **Escape never reached the editor.** A hand-built `.pbim-modal` is not a
   framework Dialog: nothing claims focus, so the hotkey service has no surface
   to route to. It takes focus on mount and handles its own keys now.
4. **The sentence rendered as a stack of full-width boxes shouting in capitals.**
   The class was named `pbbp-pill`, which B1 already owns for the pay panel's
   status badge — `inline-flex`, uppercase. Renamed `pbbp-word` (**BP18**). The
   backend theme's blanket `select { display: block; width: 100% }` needed the
   element named in the selector to out-specify it without `!important`
   (**BP19**).
5. **The backfill silently did nothing.** `regenerate` wrote `excel_formula`
   without declaring `bp_formula_source`, so the rule's own write guard — which
   compares against `bp_generated_formula`, still empty on the first pass —
   marked regeneration's own output as somebody's hand-written Excel and then
   refused to touch it ever again. Symptom on screen: every total kept its pack
   formula and removing a component was refused with "used by ERCOST, GROSS,
   NET, TAXABLE, which is written as Excel" (**BP21**).
6. **A refused removal left the checkbox looking unticked.** The DOM toggled
   before the server said no.
7. **The row's value went stale when the sample changed.** The take-home figure
   moved while the row that caused the change still read 0 — measured at exactly
   the moment the weekend-overtime hours were set (**BP23**).
8. **An input was told it had been "edited by hand".** A component the payroll is
   simply given has no formula, so it is technically "manual"; the editor offered
   to restore a guided version that never existed, beside an Excel lane with
   nothing to write.
9. **A concurrent-edit refusal was shown through the "could not be opened"
   panel** — the wrong failure, in the wrong words, with no way forward.

Plus two of language rather than behaviour: the needs line said
"This adds PAIDDAYS" (it now says *"Paid working days"*), and the engine's own
checker said "Missing 1 closing parenthesis(es)" under a formula a payroll
manager had just typed (now *"A closing bracket is missing."*, with anything
unrecognised passed through rather than swallowed).

---

## 7. BP-R12 — the BRACKET lint

Fixed at the compute, by expansion, never by adding a fake `BRACKET` to
`SUPPORTED_FUNCTIONS`:

- `hr.formula.config.action_validate_formulas` runs
  `hr.formula.rate.table.expand_brackets` before the validator, exactly as
  `pb.formula.studio._check_formula` already did (F11);
- a new `hr.formula.config._missing_rate_tables()` keeps an **unknown table an
  error, by name** — `expand_brackets` replaces one with a harmless `0`, so
  without this a typo in a table name would become an invisible zero in
  somebody's pay;
- `hr.formula.rule.validate_formula` (the older, unused per-rule checker) got the
  same expansion so the bug cannot return through it;
- migration `19.0.1.124.0/post-bracket_lint.py` re-checks exactly the rules whose
  formula mentions BRACKET — `is_valid` is stored, so the fix alone changes
  nothing on existing data;
- four tests in `pb_hr_payroll_formula/tests/test_bracket_lint.py`, including
  *"a genuinely broken formula is still broken"*.

**`has_errors` flips True → False, per database:**

| Database | BRACKET rules found | Flipped to valid | Configurations that stopped reporting errors |
|---|---|---|---|
| payobook | 2 | 1 | **1** |
| abm | 0 | 0 | 0 |
| payobook_template | 0 | 0 | 0 |
| p9clone | 0 | 0 | 0 |

The number is small and it is the truthful one. Only two rules on the whole
cluster use `BRACKET` today — the two Vietnam-pack demo configurations B1 left on
payobook — and only one of them had ever been validated, so only one carried the
stale `is_valid = False`. The rest of the estate's configurations are demo
schemes that do not use band tables. **After the fix, `has_errors` is False on
every configuration on all four databases** (§8), and a *newly created* Vietnam
draft comes up clean — which is the case that mattered, and which B1 could not
finish because of it.

`bp_finish` still uses its own conversion check (`python_formula` non-empty)
rather than `has_errors`, unchanged: that is the test the engine actually
answers, and it is the same one `seed_config` uses to refuse a bad starter.

---

## 8. Deploy

Ledger ritual: clean `/tmp/bp_stage`, scoped per-module `rsync --delete`,
`pg_dump` per database before the upgrade, detached `systemd-run` per database,
asset purge plus a `web.assets.version` bump, never `pkill`.

Dumps taken before the upgrade: `/tmp/bp2_dumps/payobook.dump` (56 M),
`abm.dump` (18 M), `payobook_template.dump` (11 M), and
`/tmp/p9clone_preB2.dump` (55 M).

| Database | Upgrade | Modules loaded | ERROR / CRITICAL |
|---|---|---|---|
| payobook | 46.7 s | 230 | **0** |
| abm | 33.5 s | 226 | **0** |
| payobook_template | 35.8 s | 226 | **0** |

Seven further rounds followed as the browser found defects; the last one is the
state below. p9clone was upgraded five times by the test runs, every one exit 0.

Final state — manifest vs `ir_module_module.latest_version`, all four:

| Database | pb_blueprint | pb_hr_payroll_formula | configurations | with errors |
|---|---|---|---|---|
| p9clone | 19.0.1.1.0 | 19.0.1.124.0 | 18 | **0** |
| payobook | 19.0.1.1.0 | 19.0.1.124.0 | 21 | **0** |
| abm | 19.0.1.1.0 | 19.0.1.124.0 | 1 | **0** |
| payobook_template | 19.0.1.1.0 | 19.0.1.124.0 | 0 | **0** |

Tree hashes repo vs server, byte-identical:
`pb_blueprint 15c2101df081cb6a`, `pb_hr_payroll_formula 5e7545ecc5e4ccb0`.

**Errors and how they were resolved**: the only ERROR lines in any log were the
twelve test failures of the first two runs (all traced and fixed, §6 and §10) and
the blank-page syntax error of defect 1. Zero ERROR or CRITICAL from module
loading on any database, on any round.

---

## 9. Files touched outside `pb_blueprint`

`pb_formula_studio` was **not touched at all** this phase — no new seam was
needed. `pb_import_kit` was not touched either: every icon the screen uses
(`sliders`, `search`, `plus`, `trash`, `undo`, `lock`, `refresh`, `sparkles`,
`fileSpreadsheet`, `info`, `alert`, `x`, `chevron`, `chevronDown`, `shield`,
`calendar`, `table`) was already in the one registry, so the kit did not have to
ship with this phase.

| File | Where | Before → After |
|---|---|---|
| `pb_hr_payroll_formula/models/formula_config.py` | new method before `action_validate_formulas`, `:1207-1221` | *(nothing)* → `_missing_rate_tables(formula)`, 15 lines: the band tables a formula calls that this configuration does not have |
| `pb_hr_payroll_formula/models/formula_config.py` | inside `action_validate_formulas`, was `:1220-1225`, now `:1236-1254` | `validator.validate_formula(rule.excel_formula, column_map)` → expand `BRACKET` first through `hr.formula.rate.table.expand_brackets`, and refuse by name when the table does not exist. 19 lines, 12 of them the comment explaining why |
| `pb_hr_payroll_formula/models/formula_rule.py` | inside `validate_formula`, was `:1770`, now `:1770-1777` | `formula = self.excel_formula.upper()` → the same expansion, so the older per-rule checker cannot resurrect the bug. 8 lines |
| `pb_hr_payroll_formula/migrations/19.0.1.124.0/post-bracket_lint.py` | new file, 56 lines | re-checks only the rules whose formula mentions `BRACKET`; a rule that is genuinely broken stays broken |
| `pb_hr_payroll_formula/tests/test_bracket_lint.py` | new file, 74 lines | four tests: a band formula is valid, an unknown table is still an error and names itself, a genuinely broken formula is still broken, and the helper's own behaviour |
| `pb_hr_payroll_formula/tests/__init__.py` | appended, `:+4` | `from . import test_bracket_lint` |
| `pb_hr_payroll_formula/__manifest__.py` | `:4` | `19.0.1.123.0` → `19.0.1.124.0` |

---

## 10. `excel_formula_display`, and the code ↔ letter translation

`excel_formula_display` **does not render codes** — it is a stored compute that
calls `_normalize_excel_formula`, which strips row numbers and nothing else
(`formula_rule.py:466-505`). `=Y1*K1` becomes `=Y*K`, not `=SIBASE*SIRATE`.

So the substitution is done in `pb.blueprint.studio._display_formula`: replace
each column letter with its code, longest letter first, with a lookaround that
refuses to match inside a longer identifier. The reverse — `_codes_to_letters` —
is what the Excel lane saves through, and it deliberately **skips rate-table
codes**, or `BRACKET(VNTAX, TAXABLE)` would have its table name rewritten into a
column letter.

Both are exercised live (case 3) and by
`test_the_excel_lane_speaks_codes_both_ways`, which asserts the round trip in
both directions and that what reaches the database is letters (BP-R4).

**One expression the validator would not accept**, and how it was solved: none
in the end. The only thing the compiler avoids is `SUM(...)`, and not because the
validator refuses it — it is in `SUPPORTED_FUNCTIONS` — but because the
converter's array-bracket rewrite is one more moving part between a sentence and
a payslip than an addition chain needs (§5). The 38-component fixture compiles
and validates in full.

---

## 11. Deferred, with reasons

1. **The tax band editor, the reliefs and the caps** (Tax & protection tab) and
   **the calendar and payment preferences** — the next phase, as scoped. Both
   tabs are honest panels today: they say what arrives and offer the door that
   works (case 19).
2. **Vietnam · Complete** — the next phase, as scoped. This phase's obligation
   was that the vocabulary can *say* all 38 components, which §4 discharges and
   a test asserts. B3 lifts the fixture verbatim; the only work left there is
   content, plus giving `BASIC` a `helper` group so `SALARYPAID` is the earning.
3. **A hoot test that mounts the Components tab.** The ten new hoot tests cover
   the pure layer — the words, the summaries, the code derivation, the
   vocabulary gate. Mounting the component needs a mocked `pb.blueprint.studio`,
   which is a fixture worth building once for B4/B5 where there are three
   surfaces to cover rather than one; the behaviour is covered live in cases
   1–14 meanwhile.
4. **A 390-px viewport measured at exactly 390 px.** The automation bridge floors
   the page viewport at 500 px on this machine (verified by requesting 330 and
   getting 500). The breakpoint under test is 899 px, so the phone layout was
   genuinely exercised; a device-accurate 390-px capture is not something I could
   take.
5. **No Vietnamese `.po`** — B6, as scoped. Every visible string is inside a
   literal `_t(...)` or QWeb text, so extraction will find it. Note for B6: the
   two `helper_label` / `helper_suffix_label` functions exist precisely so the
   extractor sees real literals, because a module-level `_t()` runs at import
   time before any language is known.

---

## 12. Owner items

1. **The temporary validator user is still switched on**, unchanged from B1:
   `look.p4@payobook.com` on payobook and abm, password `BpB1validate!2026`.
   Say the word and it is archived — or better, the working administrator
   password and it can go for good.
2. **The two demo configurations B1 left on payobook are untouched**, as the
   handover instructed. Both walkthrough drafts this phase created — one on
   payobook, one on abm — were discarded through the product's own path
   ("The draft was discarded. Nothing was kept."), so the estate is back to 21
   configurations on payobook and 1 on abm.
3. **Nothing has been pushed.** Six commits this phase, on top of the seven from
   B1 and the ~104 the branch was already carrying.

---

## 13. Self-score against the bar

> "extreme WOW, intuitive, out-of-this-world experience, best in class."

- **Hero** — 9/10. The hero of this phase is not the number, it is the moment a
  person changes one word in an English sentence and watches somebody's pay
  move. "Prorated by *nothing* → *paid working days*", then 13 days instead of
  26, and social insurance halves from 800,000 to 400,000 while take-home rises
  8.95m → 9.35m — computed by the real engine, on a real starter, in under a
  second. It is genuinely convincing. A point off because the proof strip shows
  one number where a small before/after would land harder.
- **Zero dead-ends** — 9/10. Every state is designed and was walked: loading,
  nothing in a group, nothing matching a search, a formula the engine refuses, a
  removal that is refused (twice, two different ways, both naming who is
  affected), a component with no formula at all, no sample employee, a draft
  somebody else changed, a blank canvas, and 500 px. The refusal that reads best
  is the one *on the row* rather than in a toast — a message about a thing
  belongs next to the thing. Half a point off: "Restore all" restores one at a
  time, so a tray of twenty is twenty round trips.
- **Plain language** — 9/10. 10,752 characters swept, zero banned words, and two
  language defects found and fixed that no gate would have caught: a code in a
  sentence, and the engine's own "parenthesis(es)" reaching a payroll manager.
  The sentence itself is the product — "For everyone, calculate a percentage of
  another component at the rate held in Social Insurance Rate (EE) of SI/HI Base
  (capped)" is long, and shortening those option labels is the next gain.
- **Motion with purpose** — 8/10. The count-up and delta chip carry every save,
  the proof strip shows a shimmer while it computes rather than a spinner, the
  bulk bar rises into place. Nothing moves that is not reporting a change;
  `prefers-reduced-motion` is honoured. Unchanged from B1's toolkit rather than
  extended.
- **Keyboard and bulk** — 8/10. ↑/↓/Space/Enter/Escape, ⌘F, ⌘⏎, shift-ranges,
  ⌘-click, a floating action bar, and — the part that mattered — the two
  keyboard bugs that only appear when somebody actually presses the key. Two
  points off for the serial restore and for having no "select all in this group".

**With one more hour**: (a) make "Restore all" one server call instead of N;
(b) shorten the amount labels so the sentence fits one line at desk width;
(c) give the proof strip a before → after pair when a change moves the number.
