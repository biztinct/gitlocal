# BLUEPRINT Phase B5 — report

Built, tested, deployed and Chrome-validated 2026-09-10. Scope delivered in
full. The deferred items in §11 are the ones the handover already assigned to a
later phase, plus two measurements this bridge cannot take and one action I
declined to perform on live demo data.

**Live on all four databases**: `pb_blueprint 19.0.1.4.0`,
`pb_hr_payroll_formula 19.0.1.125.0` (one access row, §5). `pb_formula_studio
19.0.1.184.0`, `pb_import_kit 19.0.1.19.0` and `pb_hub 19.0.1.9.0` are unchanged
from B4 — **`pb_formula_studio` was not touched at all this phase**, and every
icon the two new steps use was already in the one registry, so the kit did not
have to ship.

**Tests**: **130 Python** on p9clone (`--test-tags /pb_blueprint`), 0 failed
0 error, of which **24 are new**. In the browser, **109 hoot tests under
`@pb_blueprint`, all green** (125/125 in the filtered run), of which **42 are
new**. B1's 23, B2's 56, B3's and B4's are all among them and all still green.

---

## 1. Acceptance cases

| # | Case | Result | Evidence |
|---|---|---|---|
| 1 | Outputs: strip counts match the table; Final outputs is the default; search "tax" filters | **PASS** | Strip **68 inputs & fixed values → 41 components → 43 calculations → 27,035,000 take-home / 36,950,000 employer cost**. Chips: Final outputs **10** · Inputs & fixed values 68 · Earnings 24 · Deductions 8 · Benefits & employer costs 9 · Behind the scenes 9 · Edited by hand 0 · Needs a decision 8 · All **111**, and the table painted exactly 10 rows on the default chip. `strip.inputs` equals the count of input+constant rows and `strip.rules` the count of formula rows, asserted live and by test. Search "tax" → ASSESSPAY, TAXABLE, PIT, GROSS, NET, ERCOST — each one matching in its name, its code or its calculation |
| 2 | Inspect PIT → chips for TAXABLE and the routes' inputs; feeds-into NET; trace shows the reads; "Show the whole chain" expands and stops at the bound with a count | **PASS** | Formula in codes: `=IF(ISRESIDENT=0,ROUND(ASSESSPAY*NONRESRATE,0),IF(CONTRACTMTH<3,IF(AND(ASSESSPAY>=SHORTTHRESH,TAXCOMMIT=0),ROUND(ASSESSPAY*SHORTRATE,0),0),ROUND(BRACKET(VNTAX,TAXABLE),0)))`. Chips: NONRESRATE · SHORTRATE · SHORTTHRESH · ASSESSPAY · TAXABLE · ISRESIDENT · CONTRACTMTH · TAXCOMMIT. **8 components feed this**, **1 component uses this → Take-home pay NET 27,035,000**. Trace: *"Flat rate for people who are not tax resident 0.2 · … · Income the tax bands apply to 5,650,000 · … → 315,000"*. The chain expanded to **60 nodes** and said **"and 17 more further away"** |
| 3 | Inspect a manual rule → generated vs yours side-by-side; Restore → row badge flips; hero updates | **PASS** | PHONEALLOW written as `=ROUND(750000,0)` through the Excel lane's own save path. Row: **Written as Excel**, chip "Edited by hand **1**". Inspector: *"What you wrote =ROUND(750000,0)"* beside *"What the sentence produces =ROUND((500000*(PAIDDAYS/STDDAYS)),0)"*. Restore asked first (*"The calculation you wrote for Phone allowance is replaced by the one the rule produces. Nothing else changes, and no payslip is affected."*) → source flipped to **From your settings**, the sheet's own figure moved 750,000 → 500,000, the chip went to "Edited by hand **0**" and cash earnings returned to 30,500,000 |
| 4 | Export → a JSON file downloads; open it: components + rate tables present | **PASS** | `B5_OUTPUTS_WALKTHROUGH-rules.json`, `application/json`, **105,762 bytes**, **111 components**, **1 rate table with 7 brackets**, 5 scenarios. The anchor click was intercepted to prove the idiom without saving a file: `href` `blob:https:/…`, `download` the filename above, toast *"Downloaded — 111 components in the file."* |
| 5 | Test: run → verdicts; starter scenarios Passed; pending boundary rows say so; confirm one → Passed; confirm all → all Passed; scoreboard shows the counts | **PASS** | Run → **5 checks passed**, all five starter scenarios *"Every expected number matched."* Six boundary rows added → **5 / 11 passed — the rest are waiting for you**, each *"Confirm the numbers you expect."* Confirm one → **6 / 11**. "Confirm all waiting" → **11 / 11 passed**, counters *11 passed · 0 need attention · 0 waiting for you* |
| 6 | Change a band on the Tax tab → amber "changed since the last run" on Test, Components and Tax; run again → clears | **PASS** | Band 2 rate 10 → 12, "Save the bands" → the chip on the **Tax** tab and on the **Components** tab both read **"Changed since the last check — run it again"** in amber, and pressing it walked to the Test step, whose own chip said the same. The scoreboard read **"11 / 11 passed — before the change"**. Running again cleared it |
| 7 | A change → run → Needs attention with a plain reason naming the code | **PASS** | The re-run after the band change: **5 checks need attention**, e.g. *"Personal income tax expected 315,000, got 328,000 (+13,000) · 1 other component disagrees too"* and *"Personal income tax expected 2,487,200, got 2,587,200 (+100,000)"*. The change was made through the Tax tab rather than by hand-breaking a formula in the grid; the hand-written path is exercised in case 3, and a deliberately wrong expectation is asserted by Python test 5 |
| 8 | Add boundary cases → rows appear (edge−1/0/+1 names), pending until confirmed | **PASS** | Modal: **Worth checking** — Insurance ceiling (Social and health) 46,800,000 · Insurance ceiling (Unemployment) 99,200,000 · No paid days 0 · A full month 26 · No dependants 0 · Three months on the contract 3 · Withholding threshold 5,000,000, all pre-ticked, plus *"Other edges found in your rules (11)"*. Two chosen → *"2 edges chosen — that adds 6 scenarios."* → **Edge BASIC=46799999 (−1) / =46800000 (0) / =46800001 (+1)** and the three PAIDDAYS rows, every one **Pending your confirmation** |
| 9 | Try with a real person on payobook; on abm the picker still works or explains | **PASS (with one part proven off-screen)** | On a configuration with real pay runs: **8 runs listed**, *"Payroll August 2026 · 902 people"*, a person picked, and the preview headed **"Employee · 08/01/2026 — the name is left off on purpose"** with **31 values** (Basic Salary 7,900,000, Commission 7,480,255 …). The empty path was seen on a brand-new draft: *"No pay run has used this configuration yet, so there is no real person to try. Everything else on this step still works."* **"Keep as a scenario" was NOT pressed on live demo data**; it was proven on p9clone through the same RPC — the kept row came back named "Employee Sample 1", `bp_origin = real`, `is_anonymized = True`, and the Test list showed it as kind **Real person** |
| 10 | Coverage line names untested codes and links to the inspector | **PASS** | With a plan-total benefit added (nothing sums it), the line read *"43 of 45 calculations are checked by a confirmed scenario · 1 is used on the way · 1 is untested **WELLPLAN**"*. Pressing WELLPLAN landed on the Outputs step with the filter widened to **All 113** and the inspector open on *Wellness plan total*, which explains itself: *"This calculation reads nothing from other components." · "Nothing else uses this value yet."* |
| 11 | Blank canvas → both steps render their empty guidance without errors | **PASS** | Outputs: strip **0 → 0 → 0 → — / —**, every chip 0, *"This configuration has no components yet. Add them on the Pay rules step, or import a workbook."* Test: *"One click. 1 meaningful check."*, coverage *"There are no calculations to check yet."*, scoreboard **—** with *"Add the boundary cases this configuration branches on, and the checks have something to run against."* No console errors |
| 12 | 390 px: table becomes stacked cards; inspector full-screen; scoreboard readable | **PASS** at the bridge's floor of **500 px** | The flow strip becomes a column with rotated arrows, the table header hides and each row stacks (name, calculation, then value/badge/Inspect on one line), the inspector fills the width, the rail lies down and the scoreboard becomes a bottom bar reading **"Checks passed —"** that opens to the full panel. `documentElement.scrollWidth === clientWidth === 500` throughout. A device-accurate 390-px capture is not something this bridge can take (B2 §11.4) |
| 13 | All four DBs on the new version; gates green | **PASS** | `pb_blueprint 19.0.1.4.0` and `pb_hr_payroll_formula 19.0.1.125.0` on p9clone, payobook, abm and payobook_template; tree hashes byte-identical repo↔server for both modules (§8). On **abm**: a Complete draft, strip **68 / 41 / 43 → 27,035,000 / 36,950,000** — the same certified numbers as payobook — run → **5 / 5 passed**, *"Last checked just now by LOOK P4 validator"*. **0 console errors** on either database |

**13 PASS · 0 FAIL.**

Vocabulary sweep of both steps — all nine filter chips, the inspector with its
chain expanded, the run card, a scenario sheet, the boundary modal with its
second group opened, and the real-person modal, including `title` /
`placeholder` / `aria-label` / `alt`: **138,177 characters**, **0** hits for
Odoo, schema, blueprint, config or rule set. One hit for *recipes* — in "Beyond
the happy path", where the handover's own wording used it — was rewritten,
because "recipe" is this programme's internal name for the stored sentence and a
reader could reasonably think it meant something specific.

Both walkthrough drafts and the blank-canvas draft on payobook, and the
walkthrough draft on abm, were discarded through the product's own path. The
estate is back to B4's baseline: **payobook 22 configurations and the same three
demo setup rows**, abm unchanged. A temporary setup row created so the
real-person picker could be seen on a configuration with real pay runs was
deleted again in the same session.

---

## 2. The evidence hash, exactly as implemented

`pb.blueprint.studio._evidence_hash(config)` — sha256 over one JSON document,
`sort_keys=True`:

```python
{
  "components": sorted(
      (code.upper(),                                  # the component's code
       column_type,                                   # input | formula | constant
       hr.formula.rule._normalize_excel_formula(excel_formula) or '',
       round(float(constant_value or 0.0), 6))
      for every rule with a code),
  "tables": sorted(
      (table.code.upper(),
       sorted((round(float(lower), 6), round(float(rate), 6))
              for every bracket))
      for every rate table),
}
```

Three decisions inside that, each of which changes when the amber chip appears:

- **The formula is normalised the way the ENGINE normalises it.** `=Y1*K1` and
  `=Y*K` are the same rules and must not read as a change; that is exactly what
  `_normalize_excel_formula` says (BP24).
- **A name is not in the key.** Renaming "Phone allowance" to "Telephone
  allowance" moves no money, and a key that cries stale for it is a key people
  learn to ignore. Asserted by test 11, which renames a component and requires
  the hash to be unchanged, then moves a constant, a formula and a bracket and
  requires it to change each time.
- **Sequence, payslip position, visibility and the recipe JSON are not in the
  key either.** Only the four facts above and the brackets can change a number.

`bp_run_checks` stamps `tests_hash = evidence_hash` plus `tests_passed`,
`tests_failed`, `tests_pending`, `tests_run_at` and `tests_run_by` on
`pb.formula.blueprint`. **Stale is `tests_hash != evidence_hash`**, and it is
computed on read, never stored. `bp_evidence(config_id)` is the whole answer in
one call and is what B6's Finish gate should read.

One correction the browser forced (BP43): the counters a SCREEN shows come from
the live list, not from the stamp. Adding six boundary cases changes no formula,
so nothing is stale — but a chip reading "5 checks passed" over a list of six
rows waiting for confirmation is a screen disagreeing with itself. `bp_tests`
overrides the stamped counters with the live tally before the payload leaves the
server; the stamp keeps the historical record.

---

## 3. The boundary pick rules

Two sources, in this order, and an edge is only ever offered when a **single
input** can land on it.

**Recommended (pre-ticked), the six this product knows the meaning of:**

| Pick | Where the edge comes from | Words on screen |
|---|---|---|
| Insurance ceiling, once per cap | every `insurance_base` recipe's `amount.cap` constant, moved on the contract-salary input | "Insurance ceiling — Social and health insurance ceiling" · 46,800,000 |
| No paid days | `PAIDDAYS` at 0 | "Somebody who was paid for nothing this run — the case that turns a proration into a division by zero." |
| A full month | `PAIDDAYS` at the value of `STDDAYS` in the base scenario | "Every working day paid, so proration has to leave the amount exactly as it was." |
| No dependants | `DEPS` at 0 | "Relief with nobody to claim for — the lower edge of income tax relief." |
| Short-contract threshold | `CONTRACTMTH` at 3 | "The length at which a short contract stops being one." |
| Withholding threshold | the contract-salary input at the value of `SHORTTHRESH` | "The payment at which withholding on a short contract starts." |

The contract-salary input is `recipe_compiler.build_ctx(config).contract_code`
with `BASIC` as the fallback, so a configuration that names it something else is
still served.

**Then up to twelve more** from the engine's own `hr.formula.config.boundary_candidates()`,
`reachable` only — an edge whose operand is a calculated column is not offered
at all, because no single input value would land on it and a checkbox for it
would be a promise we cannot keep. Their labels are rewritten in plain words: a
rate-table edge becomes "Tax band edge at 5,000,000"; an edge on a 0/1 switch
becomes "Dependants enrolled in private health cover — yes and no"; anything
else becomes "<Component> at <value>". On Vietnam · Complete that is 11 more,
with the remainder counted rather than hidden.

**`exists`** is true when all three of `CODE=edge−1`, `CODE=edge` and
`CODE=edge+1` are already among the configuration's generated scenarios, using
the engine's own `boundary_key` format (`_kv` is imported from
`formula_boundary.py` rather than re-implemented, so a re-offer cannot drift
from what the generator will actually create).

**The server decides.** `bp_add_boundaries` accepts only keys that are on the
list it just computed; `test_an_edge_nobody_offered_is_refused` sends
`BASIC@999999999` and asserts nothing is created.

---

## 4. The catalogue: shape, and the download idiom

`bp_export_catalog(config_id, sample_id=None)` returns
`{ok, filename, mimetype, content, components, rate_tables}` where `content` is
JSON **text**:

```json
{
  "configuration": "B5 outputs walkthrough", "code": "B5_OUTPUTS_WALKTHROUGH",
  "company": "Payobook Vietnam JSC", "country": "VN", "currency": "VND",
  "generated_at": "2026-09-10 10:14:02", "starting_point": "Vietnam · Complete",
  "components": [{
    "code": "SIDED", "name": "Social insurance deducted", "letter": "BR",
    "type": "formula", "group": "deduction",
    "excel_codes": "=ROUND(IF(ISINSURED=1,(SIBASE*SIRATE),0),0)",
    "excel_letters": "=ROUND(IF(H=1,(BP*AD),0),0)",
    "constant_value": null, "source": "generated",
    "recipe": { … the stored sentence … },
    "sample_value": 2400000.0, "on_payslip": true
  }],
  "rate_tables": [{"code": "VNTAX", "name": "…",
                   "brackets": [{"from": 0.0, "rate": 5.0}, …]}],
  "samples": [{"name": "Full month · local", "kind": "starter",
               "inputs": {…}, "expected": {…}, "expected_confirmed": true}],
  "note": "A readable catalogue of this configuration's rules. It is not a spreadsheet you can run."
}
```

**Both forms of every formula** are in it — the codes a person reads and the
letters the engine stores — because the file is for reading AND for anybody who
has to reproduce what the engine did. `productionCompatible` from the prototype
is deliberately absent; the note under the button says what the file is instead.

**The download idiom is `pb_records`'s** (`records_desk.js:732`): a `Blob` from
the returned text, `URL.createObjectURL`, an anchor with `download` set,
`click()`, `revokeObjectURL`. `@web/core/network/download` is used **nowhere** in
any `pb_*` module — I grepped before choosing — and the blob idiom needs no
route, no attachment and no server-side file, so exporting leaves no trace on the
configuration.

---

## 5. `source_type` on a starter's scenarios, and why a stamp was added

**Answer to the handover's question: `source_type` is `'manual'`.**
`hr.formula.config.template._seed_sample_tests` (`formula_config_template.py:321`)
creates the certification scenarios without setting `source_type` at all, so
they take the field's default. Their only distinguishing marks are a
`description` beginning "Certification test (template …)" — a translated string —
and the fact that they arrive with `expected_values_json` filled in.

The engine records two of the four kinds reliably (`source_type == 'generated'`
is a boundary case; `source_payslip_id` is a real person) and cannot know the
other two, because a starter's scenario and one somebody typed are both an
ordinary manual row. So `pb_blueprint` adds **`hr.formula.sample.data.bp_origin`**
and stamps it at the one moment anybody can tell:

- `starter` — every scenario present immediately after `template.seed_config()`
  inside `bp_start` / `bp_restart`;
- `yours` — `_ensure_sample` and `bp_add_sample`;
- `real` — `bp_real_keep`, which matters more than it sounds: the studio's
  `create_from_payslip(anonymize=True)` leaves `source_payslip_id` **empty**, so
  without the stamp a kept real person would read as somebody's own sample.

Anything created before the field existed still reads correctly: `generated` →
boundary, a payslip link → real, "arrived with expected values" → starter, else
yours.

---

## 6. Six defects the browser found that code review did not

1. **The Test step never appeared, and nothing said why.** `StepTest` handed its
   answer to the shell from `onWillStart` so the pay panel could become the
   scoreboard; the shell's state changed, which re-rendered the shell, which
   rebuilt the child, which asked again — an infinite render loop that Owl
   reports as silence. The rail kept its old highlight, the previous step stayed
   painted, `state.step` WAS `test`, and the console was empty. Diagnosed by
   patching the component's `setup` and counting: 30+ constructions in 2.5 s.
   Nothing reaches the parent before `onMounted` now (**BP41**).
2. **The checks could only ever be run once**, by anybody who is not a
   superuser — an access row missing `unlink` on a model the run's own first act
   is to clear. A real bug, older than this phase, and it affects the studio's
   own Test workbench too (**BP42**, §7).
3. **A scoreboard reading "5 / 5 passed" beside a chip saying "Not checked
   yet"**, and later "11 / 11 passed" in green over rules that had changed since,
   and later still a chip reporting the stamped counters while the list beside it
   had six new rows. One mistake in three costumes (**BP43**).
4. **The step-by-step trace said the calculation read nothing.** The engine's
   replay finds only spreadsheet-style references (`A1`), and every formula the
   guided setup writes is stored without row numbers, so the trace line read
   "→ 2,400,000" with nothing before the arrow (**BP44**).
5. **The Inspect button was clipped off the edge of the table.** Five columns
   whose minimums added up to 878 px in a 735 px container that hides its
   overflow (**BP45**).
6. **"Nothing in this configuration is a edited by hand yet."** A sentence built
   from a chip's label is a sentence in the wrong grammar for at least one chip
   (**BP46**) — and on a blank canvas it answered a question nobody had asked.

Plus three of language rather than behaviour: the group badge in the inspector
read "Benefits & Employer Costs" (BP19, the kit's `capitalize` again); an input's
row said "Given to the payroll" twice, once in each of two columns; and the
pay-run picker said "1 people".

---

## 7. The one line changed outside `pb_blueprint`

`pb_formula_studio` was **not touched at all**. `pb_import_kit` and `pb_hub` were
not touched either — every icon the two steps use (`arrowRight`, `download`,
`eye`, `sigma`, `gitBranch`, `history`, `beaker`, `target`, `play`, `gauge`,
`route`, `checkCheck`, `circle`, `clock`, `alert`, `info`, `undo`, `sliders`,
`table`, `x`, `back`, `search`, `plus`, `user`, `chevronUp`, `chevronDown`) was
already in the one registry.

| File | Where | Before → After |
|---|---|---|
| `pb_hr_payroll_formula/security/ir.model.access.csv` | `access_test_result_manager`, `:9` | `…,group_formula_manager,1,1,1,**0**` → `…,1,1,1,**1**` |
| `pb_hr_payroll_formula/__manifest__.py` | `:4` | `19.0.1.124.0` → `19.0.1.125.0` |

`hr.formula.config.action_run_tests` opens with `self.test_result_ids.unlink()`.
With `perm_unlink = 0` the first run works — deleting an empty set is allowed —
and every run after it fails with the framework's own refusal, which names the
technical model and is not white-labelled. Measured on payobook as the validator
user; the second press of "Run the checks" produced exactly that message.

---

## 8. Deploy

Ledger ritual: clean `/tmp/bp_stage`, scoped per-module `rsync --delete`,
`pg_dump` per database before the upgrade, service stopped for the production
upgrades, detached `systemd-run` with a sentinel per round, asset purge plus a
`web.assets.version` bump, service restart, never `pkill`, never `--delete` into
the addons directory itself.

Dumps before the upgrade: `/tmp/bp5_dumps/payobook.dump` (53 M), `abm.dump`
(17 M), `payobook_template.dump` (11 M).

| Database | `-u pb_blueprint` | `-u pb_hr_payroll_formula,pb_blueprint` | ERROR / CRITICAL |
|---|---|---|---|
| p9clone | exit 0 | exit 0 | **0** |
| payobook | exit 0 | exit 0 | **0** |
| abm | exit 0 | exit 0 | **0** |
| payobook_template | exit 0 | exit 0 | **0** |

Seven further asset-only rounds followed as the browser found the defects in §6
(JS, QWeb and SCSS live in the bundle, so a purge and a restart is the whole
deploy for them). Two full test runs on p9clone, both 130/130.

Final state — manifest vs `ir_module_module.latest_version`, all four:

| Database | pb_blueprint | pb_hr_payroll_formula | pb_formula_studio | pb_import_kit | pb_hub |
|---|---|---|---|---|---|
| p9clone | 19.0.1.4.0 | 19.0.1.125.0 | 19.0.1.184.0 | 19.0.1.19.0 | 19.0.1.9.0 |
| payobook | 19.0.1.4.0 | 19.0.1.125.0 | 19.0.1.184.0 | 19.0.1.19.0 | 19.0.1.9.0 |
| abm | 19.0.1.4.0 | 19.0.1.125.0 | 19.0.1.184.0 | 19.0.1.19.0 | 19.0.1.9.0 |
| payobook_template | 19.0.1.4.0 | 19.0.1.125.0 | 19.0.1.184.0 | 19.0.1.19.0 | 19.0.1.9.0 |

Tree hashes repo vs server, byte-identical: `pb_blueprint 508b210bcbd41fa0`,
`pb_hr_payroll_formula 06f4620db5bf663d`.

**Errors and how they were resolved**: zero test failures on either Python run —
the 24 new tests were green first time — and zero ERROR or CRITICAL from module
loading on any database on any round. Everything that went wrong this phase went
wrong in the browser, and all six are in §6. One process note: a foreground test
run was killed by a watchdog at ten minutes; every install, upgrade and test run
after that was launched detached with `systemd-run` and a sentinel file, and
polled with short calls.

---

## 9. Tests

**Python — `pb_blueprint/tests/test_outputs.py`, 23 new, plus 1 in the
white-label gate.** Every one runs against a real draft created through
`bp_start` on the Vietnam · Complete starter; where the starter is absent the
test says so and skips rather than asserting something weaker under the same
name.

| # | What it holds |
|---|---|
| 1 | the table holds every rule; the default view is Final outputs and contains NET, PIT, GROSS, EEDED, ERCOST; the strip's counts equal the table's own |
| 2 | **a generated calculation may not contain a bare column letter** — every token that is neither a component code, a rate table nor an Excel function fails the test by name |
| 3 | every filter chip shows exactly the number of rows it counts, for all nine |
| 4 | search reaches the name, the code and the calculation, and finds nothing for nonsense |
| 5 | SIDED feeds from SIBASE and SIRATE and into EEDED, each with its value |
| 6 | the chain is bounded at 60 and reports what it left out |
| 7 | the trace names what the calculation read, through the fallback of BP44 |
| 8 | an input is not pretended to have a calculation, a dependency or a trace |
| 9 | the catalogue is valid JSON with one entry per rule, the brackets, the scenarios, both formula forms, and no "Odoo" |
| 10 | a blank configuration exports and renders without an error |
| 11 | the evidence key is stable, survives a **rename**, and moves for a constant, a formula and a bracket |
| 12 | a run stamps the key it ran against; a later band change makes it stale |
| 13 | the starter's five scenarios pass and are all reported as `starter` |
| 14 | a wrong expectation is named with both numbers and the code |
| 15 | **a number nobody agreed to is pending and never passed**, and confirming it turns it green |
| 16 | confirming a scenario with nothing expected snapshots first, so it can acquire expectations at all |
| 17 | the picks include both ceilings, PAIDDAYS, DEPS, CONTRACTMTH and the withholding threshold, each with a label and a reason |
| 18 | adding a pick creates exactly three unconfirmed rows; a second press creates none and reports them skipped; the pick then reports itself as already there |
| 19 | an edge nobody offered is refused and creates nothing |
| 20 | coverage agrees with `get_test_coverage` component for component |
| 21 | a stale revision changes nothing, for both writing paths |
| 22 | a configuration that does not exist is refused in words by all five read RPCs |
| 23 | nothing to check is said rather than crashed |
| 24 | (white-label) the four new payloads are swept, because this step renders the engine's own health message, the pack's component names and the boundary extractor's own words |

**Hoot — `pb_blueprint/static/tests/outputs_text.test.js`, 42 new, all green.**
Eleven suites over the pure layer: the nine chips (each with a label and a hint
of its own), badges and groups, the four flow nodes and which chips each one
lights, numbers and formulas (including a real minus sign and an em dash for
nothing), search and windowing (the spacers always add up to the whole list),
coverage in words, the evidence chip's precedence (stale beats a full pass, a
failure beats a pending confirmation), when it last ran, verdicts and the run
card, a real person's plurals, and the honest parts.

**Whole suite**: 130/130 Python on p9clone, **109/109 hoot** under
`@pb_blueprint` (125/125 in the filtered run, tab title ✔).

One process note that cost twenty minutes and is worth repeating from BP37: a
hoot tab that has been navigated repeatedly reports a red that a **fresh tab**
does not. The green above is from a tab opened once and left alone.

---

## 10. Gotchas added to `BLUEPRINT_LEDGER.md`

**BP41** a child that sets parent state from `onWillStart` is an infinite render
loop with no error and no symptom beyond a step that never appears · **BP42** an
ACL that permits create and write but not unlink is a bug whenever the code's
first act is to clear what it wrote last time · **BP43** a screen may not be
confident about something it has not checked, in three costumes · **BP44** the
studio's replay finds only spreadsheet-style references, and a guided formula has
none · **BP45** five columns whose minimums exceed the container is a button
nobody can press · **BP46** a sentence built from a label is a sentence in the
wrong grammar.

---

## 11. Deferred, with reasons

1. **No .xlsx workbook export** — a binding non-goal. The catalogue is JSON and
   the button says so in the line beneath it.
2. **No new evaluator, anywhere.** Values come from `compute_preview`, the checks
   from `run_tests`, coverage from `get_test_coverage`, the trace from
   `replay_trace`, and expected-versus-computed from the sample model's own
   `get_comparison_data`. The only arithmetic in this phase's server code is
   `computed − expected` for the sentence that reports a difference.
3. **The Finish step is untouched** beyond exposing `bp_evidence` for B6 to
   consume, as scoped.
4. **"Keep as a scenario" was not pressed on live demo data.** It writes a sample
   onto a configuration that has produced 4,469 real payslips, and the acceptance
   case does not require me to leave one there. It is proven on p9clone through
   the same RPC, with the kept row inspected (`bp_origin = real`, anonymised) and
   then removed.
5. **The real-person picker's populated state was not seen on abm.** abm's own
   configurations have no pay runs, so the picker there can only show its
   explanation. The populated path is proven on payobook against a 902-person run
   and the empty path is proven in the browser.
6. **A hoot test that mounts either new step.** The 42 new ones cover the pure
   layer — every sentence the two steps say. Mounting needs a mocked
   `pb.blueprint.studio`, the fixture B2, B3 and B4 each deferred; the behaviour
   is covered live in cases 1–13 meanwhile. It is now four surfaces waiting for
   one fixture, and B6 is the last chance to build it inside this programme.
7. **A device-accurate 390-px capture.** The bridge floors the page viewport at
   500 px on this machine (B2 §11.4). The breakpoints under test are 1199 px and
   899 px, so the phone layout was genuinely exercised; I have not claimed a
   390-px shot.
8. **No Vietnamese `.po`** — B6, as scoped. Every visible string is inside a
   literal `_t(...)` or QWeb text, and `outputs_text.js` puts every one of them
   inside a function so the extractor sees a real literal and no label is built
   before a language is known.

---

## 12. Owner items

1. **The temporary validator user is still switched on**, unchanged from B1–B4:
   `look.p4@payobook.com` on payobook and abm, password `BpB1validate!2026`. Say
   the word and it is archived — or better, tell me the working administrator
   password and it can go for good.
2. **The three demo setup rows B1 and B3 left on payobook are untouched**, and
   everything this phase created was discarded through the product's own path.
   payobook is back to 22 configurations; abm is unchanged.
3. **One access row changed in the payroll engine** (§7). It is the smallest
   possible fix and it makes the studio's own Test workbench work again as well,
   but it is a security file, so it is named here rather than buried.
4. **B3's owner questions (its §13) are still open** and were not acted on.
5. **Nothing has been pushed.** Eight commits this phase, on top of the 25 from
   B1–B4 and the ~104 the branch was already carrying.

---

## 13. Self-score against the bar

> "extreme WOW, intuitive, out-of-this-world experience, best in class."

- **Hero** — 9/10. The money-flow strip is the picture this journey has been
  missing since B1: four nodes and three arrows that say, in one line and in
  real numbers, that 68 things you are given become 41 components through 43
  calculations and come out as somebody's take-home pay and what they cost. It
  counts up on arrival, hovering a node lights the chips that show exactly those
  rows, and pressing one takes you there — the picture and the table are the same
  thing at two zoom levels, which is the part I am most pleased with. The
  scoreboard is the other half: the panel stops answering "what is this doing to
  somebody's pay" and starts answering "how much of this is proven", and goes
  back when you leave. A point off because the strip does not yet animate the
  flow itself, only the counts.
- **Zero dead-ends** — 9/10. Every state was designed and walked: nothing in a
  filter, nothing matching a search, a configuration with no components at all,
  no scenarios, no expected numbers, a scenario nobody has agreed to, an edge
  already covered, an edge nothing can reach, no pay run to try a real person
  from, a person who may look but not run, a stale revision, a chain too long to
  draw, a formula too long to show, and 500 px. The one I like best is the
  coverage line: it names the component nobody is checking AND is the door to it,
  so the sentence that reports the problem is also the way to look at it. Half a
  point off because "Beyond the happy path" is honest but inert, and half because
  a scenario cannot be renamed or deleted from this step — you have to go to the
  grid.
- **Plain language** — 9/10. 138,177 characters swept, zero banned words, and
  the sentence I would defend hardest is the confirmation note: *"Confirming says
  these are the right answers for this person. Until you do, the scenario counts
  as waiting rather than as passed — a number the engine produced is not yet a
  number anybody agreed to."* That is the whole idea of the step in two lines. A
  point off for three wordings the browser had to teach me, all of them cases of
  a screen being confident about something it had not checked.
- **Motion with purpose** — 8/10. The counts run up over 520 ms, the inspector
  slides in over 200 ms, nothing else moves, and `prefers-reduced-motion` turns
  both off. Everything that moves is reporting a change. Two points off because
  the verdict pills do not animate when a run flips them, which is the one moment
  on the step where a change is worth pointing at.
- **Keyboard and bulk** — 8/10. Arrow keys walk the table, Enter inspects,
  ⌘/Ctrl+F finds, Escape closes the sheet and the modals and never reaches the
  journey behind them (BP20), and the bulk gestures that matter are there:
  "Confirm all waiting", "Add boundary cases" with everything worth checking
  pre-ticked, and one button that runs the lot. Two points off: there is no way
  to select several scenarios and confirm just those, and no keyboard route
  between the filter chips.

**With one more hour**: (a) animate the verdict pills when a run changes them,
so the one moment that deserves motion gets it; (b) let a scenario be renamed
from the row, since "Edge BASIC=46799999 (−1)" is the engine's name and not a
person's; (c) put the coverage percentage in the rail's Test hint, so the step
reports itself from two steps away.
